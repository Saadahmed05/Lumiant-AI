"""Live cross-engine check: load the demo databases into PostgreSQL and compare the no-mapping path with DuckDB.

Usage: python eval/nomap/live_postgres.py <postgresql admin URL, e.g. postgresql://postgres:pw@127.0.0.1:5432/postgres>
Creates and replaces the databases db_a, db_b and db_c on that server, so point it at a disposable server only.
Needs the API's postgres extra (psycopg).
"""

# ruff: noqa: E501, S608

from __future__ import annotations

import sys
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb
import psycopg
import sqlglot

sys.path.insert(0, str(Path(__file__).parent))
from cases import DATABASES

from lumiant.nomap.discovery import discover
from lumiant.nomap.safe_sql import AccessPolicy, prepare
from lumiant.nomap.source import Source

DATA = Path(__file__).parents[2] / "data" / "synthetic"
HIDDEN = frozenset({"_dataset_info"})
TYPES = {
    "VARCHAR": "TEXT",
    "BOOLEAN": "BOOLEAN",
    "INTEGER": "INTEGER",
    "BIGINT": "BIGINT",
    "DATE": "DATE",
    "TIMESTAMP": "TIMESTAMP",
    "DOUBLE": "DOUBLE PRECISION",
}


def pg_type(t: str) -> str:
    t = t.upper()
    return t.replace("DECIMAL", "NUMERIC") if t.startswith("DECIMAL") else TYPES.get(t, "TEXT")


def load(admin: str, tenant: str, dbname: str) -> str:
    """Copy one demo database into PostgreSQL, keeping schema and the stored case of every name."""
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{dbname}"')
        conn.execute(f'CREATE DATABASE "{dbname}"')
    url = admin.rsplit("/", 1)[0] + f"/{dbname}"
    src = duckdb.connect(str(DATA / f"{tenant}.duckdb"), read_only=True)
    tables = src.execute(
        "select table_schema, table_name from information_schema.tables where table_name <> '_dataset_info'"
    ).fetchall()
    with psycopg.connect(url, autocommit=True) as pg:
        for schema, name in tables:
            cols = src.execute(
                "select column_name, data_type from information_schema.columns where table_schema=? and table_name=? order by ordinal_position",
                [schema, name],
            ).fetchall()
            target = f'"{name}"' if schema == "main" else f'"{schema}"."{name}"'
            if schema != "main":
                pg.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
            pg.execute(f"CREATE TABLE {target} (" + ", ".join(f'"{c}" {pg_type(t)}' for c, t in cols) + ")")
            with pg.cursor() as cur, cur.copy(f"COPY {target} FROM STDIN") as copy:
                for row in src.execute(f'select * from "{schema}"."{name}"').fetchall():
                    copy.write_row(row)
    src.close()
    return url.replace("postgresql://", "postgresql+psycopg://", 1)


def same(a: list[tuple[Any, ...]], b: list[tuple[Any, ...]]) -> bool:
    def norm(rows: list[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
        return sorted(
            tuple(round(float(v), 2) if isinstance(v, (int, float, Decimal)) else str(v) for v in r) for r in rows
        )

    return norm(a) == norm(b)


def main(admin: str) -> int:
    problems = 0
    for name, (tenant, cases) in DATABASES.items():
        started = time.perf_counter()
        pg = Source(load(admin, tenant, name))
        dk = Source.duckdb(DATA / f"{tenant}.duckdb")
        cat_pg, cat_dk = discover(pg, exclude=HIDDEN), discover(dk, exclude=HIDDEN)
        print(f"{name}: loaded and discovered in {time.perf_counter() - started:.1f}s")
        for t in cat_dk.tables:
            p = cat_pg.find(t.name, t.schema)
            if p is None or p.rows != t.rows or set(p.checks) != set(t.checks):
                problems += 1
                print(f"  catalog differs for {t.qualified}")
        if {(j.from_table, j.from_column, j.to_table, j.to_column) for j in cat_pg.joins} != {
            (j.from_table, j.from_column, j.to_table, j.to_column) for j in cat_dk.joins
        }:
            problems += 1
            print("  joins differ")
        matched = 0
        for case in [c for c in cases if c.truth]:
            try:
                got = pg.execute(
                    prepare(sqlglot.transpile(case.truth, read="duckdb", write="postgres")[0], cat_pg)
                ).rows
                ok = same(got, dk.execute(prepare(case.truth, cat_dk)).rows)
            except Exception as exc:
                ok = False
                print(f"  {case.id} failed: {exc}")
            matched += ok
            problems += not ok
        print(f"  answer-key queries matching DuckDB: {matched} of {len([c for c in cases if c.truth])}")
        if name == "db_a":
            viewer = AccessPolicy(
                row_scope={"zv_stock": ("WERKS", frozenset({"3100"}))}, hidden_columns={"zv_stock": {"VERPR"}}
            )
            sites = {r[0] for r in pg.execute(prepare("SELECT DISTINCT WERKS FROM ZV_STOCK", cat_pg, viewer)).rows}
            problems += sites != {"3100"}
            print(f"  scoped user sees warehouses {sites}")
        pg.dispose()
        dk.dispose()
    print("PROBLEMS", problems)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
