"""No-mapping SQL that must behave the same on every engine: stored name case, '%' in text, query timeouts."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest
import sqlglot

from lumiant.nomap.catalog import Catalog, Column, Table
from lumiant.nomap.discovery import discover
from lumiant.nomap.safe_sql import prepare
from lumiant.nomap.source import Source, SourceError


def sap_catalog(dialect: str) -> Catalog:
    stock = Table(
        None, "ZV_STOCK", 2, (Column("MATNR", "VARCHAR"), Column("WERKS", "VARCHAR"), Column("LABST", "DECIMAL"))
    )
    item = Table(None, "ZV_MATERIAL", 2, (Column("MATNR", "VARCHAR"), Column("MAKTX", "VARCHAR")))
    return Catalog(dialect, (stock, item))


@pytest.mark.parametrize("dialect", ["postgres", "oracle", "snowflake", "tsql", "mysql", "duckdb"])
def test_names_keep_their_stored_case_on_every_engine(dialect: str) -> None:
    sql = prepare(
        "SELECT s.labst, zv_stock.werks FROM zv_stock s JOIN zv_material USING (matnr) WHERE s.matnr = 'X'",
        sap_catalog(dialect),
    )
    tree = sqlglot.parse_one(sql, read=dialect)
    names = {c.name for c in tree.find_all(sqlglot.exp.Column)}
    assert {"LABST", "WERKS", "MATNR"} <= names
    assert all(c.this.quoted for c in tree.find_all(sqlglot.exp.Column))


def test_output_aliases_are_not_renamed() -> None:
    sql = prepare("SELECT SUM(labst) AS total FROM zv_stock ORDER BY total DESC", sap_catalog("postgres"))
    assert "ORDER BY total DESC" in sql


@pytest.fixture
def sqlite_source(tmp_path: Path) -> Source:
    path = tmp_path / "erp.sqlite"
    con = sqlite3.connect(path)
    con.execute('create table "ZV_MATERIAL" ("MATNR" text, "MAKTX" text)')
    con.executemany(
        'insert into "ZV_MATERIAL" values (?, ?)', [("1", "Pump impeller 175 mm"), ("2", "100% cotton rag")]
    )
    con.commit()
    con.close()
    return Source(f"sqlite:///{path.as_posix()}", timeout_s=1)


def test_percent_in_text_is_not_read_as_a_parameter(sqlite_source: Source) -> None:
    catalog = discover(sqlite_source)
    sql = prepare("SELECT COUNT(*) FROM zv_material WHERE maktx LIKE '%impeller%175%' OR maktx LIKE '100%%'", catalog)
    assert sqlite_source.execute(sql).rows[0][0] == 2


def test_runaway_query_is_stopped(sqlite_source: Source) -> None:
    started = time.perf_counter()
    with pytest.raises(SourceError):
        sqlite_source.execute("WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM n) SELECT COUNT(*) FROM n")
    assert time.perf_counter() - started < 10
