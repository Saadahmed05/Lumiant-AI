"""Command line for the prototype. `catalog`, `describe` and `sql` make no AI call; `ask` needs an Anthropic login."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from lumiant.nomap.agent import AnthropicModel, NoMapAgent
from lumiant.nomap.catalog import Catalog, render_table
from lumiant.nomap.discovery import discover, profile_table
from lumiant.nomap.safe_sql import AccessPolicy, UnsafeSqlError, prepare
from lumiant.nomap.source import Source, SourceError

HIDDEN_TABLES = frozenset({"_dataset_info"})


def load_access(path: str | None) -> AccessPolicy:
    if path is None:
        return AccessPolicy()
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return AccessPolicy(
        row_scope={k: (v["column"], frozenset(v["values"])) for k, v in raw.get("row_scope", {}).items()},
        hidden_columns={k: set(v) for k, v in raw.get("hidden_columns", {}).items()},
        denied_tables=set(raw.get("denied_tables", [])),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lumiant-nomap")
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--db", help="Path to a DuckDB database")
    # A URL can hold a password, so it may also come from LUMIANT_NOMAP_URL instead of the command line.
    target.add_argument("--url", default=os.environ.get("LUMIANT_NOMAP_URL"), help="SQLAlchemy URL of any database")
    parser.add_argument("--access", help="JSON file with one user's limits")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("catalog")
    sub.add_parser("find", aliases=["find_tables"]).add_argument("words")
    sub.add_parser("describe", aliases=["describe_table"]).add_argument("table")
    sub.add_parser("sql").add_argument("query")
    sub.add_parser("ask").add_argument("question")
    args = parser.parse_args(argv)
    if not args.db and not args.url:
        parser.error("give --db, --url, or set LUMIANT_NOMAP_URL")

    source = Source.duckdb(Path(args.db)) if args.db else Source(args.url)
    access = load_access(args.access)
    catalog: Catalog = discover(source, exclude=HIDDEN_TABLES).without(
        access.hidden_columns, access.denied_tables, frozenset(access.row_scope)
    )
    if args.command == "catalog":
        print(catalog.render())
    elif args.command in ("find", "find_tables"):
        print("\n".join(f"{t.qualified}: " + ", ".join(c.name for c in t.columns) for t in catalog.search(args.words)))
    elif args.command in ("describe", "describe_table"):
        table = catalog.lookup(args.table)
        if table is not None and not table.profiled:
            table = profile_table(source, catalog, table, access)
        print(render_table(table) if table else f"Unknown table: {args.table}")
    elif args.command == "sql":
        try:
            result = source.execute(prepare(args.query, catalog, access, max_rows=source.max_rows))
        except (UnsafeSqlError, SourceError) as exc:
            print(f"Query refused or failed: {exc}")
            return 1
        rows = [[str(v) if v is not None else None for v in r] for r in result.rows[:50]]
        print(
            json.dumps(
                {
                    "columns": result.columns,
                    "rows": rows,
                    "row_count": len(result.rows),
                    "more_rows_exist": result.truncated,
                }
            )
        )
    else:
        outcome = NoMapAgent(source, catalog, AnthropicModel(), access).ask(args.question)
        print(json.dumps(outcome.__dict__, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
