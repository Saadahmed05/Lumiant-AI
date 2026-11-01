"""Check model-written SQL and rewrite it so that one user's limits hold whatever the model wrote.

Limits are not prompt text. Each restricted table is replaced by a subquery that selects only the columns the
user may see and only the rows in their scope, so a hidden column cannot be named and SELECT * cannot reach it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import sqlglot
from sqlglot import exp

from lumiant.nomap.catalog import Catalog, Table

SYSTEM_SCHEMAS = {"information_schema", "pg_catalog", "sys", "system", "temp"}
FORBIDDEN_NODES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Merge,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.Command,
    exp.Into,
    exp.Lock,
    exp.TableFromRows,
    exp.Lateral,
)
DANGEROUS_FUNCTION = re.compile(
    r"READ_|FILE|LOAD|SLEEP|ENV|EXEC|SHELL|OPENROWSET|DBLINK|SETTING|GENERATOR|SYSTEM", re.I
)
# sqlglot models functions it does not know as Anonymous. Those must be named here to run.
SAFE_UNKNOWN_FUNCTIONS = frozenset(
    [
        "strftime",
        "strptime",
        "date_part",
        "datepart",
        "date_diff",
        "datediff",
        "dateadd",
        "date_add",
        "date_sub",
        "date_trunc",
        "trunc",
        "today",
        "now",
        "getdate",
        "sysdate",
        "nvl",
        "nvl2",
        "isnull",
        "iif",
        "decode",
        "to_char",
        "to_date",
        "to_number",
        "len",
        "format",
        "string_agg",
        "listagg",
        "median",
        "quantile_cont",
        "percentile_cont",
        "contains",
        "regexp_matches",
        "regexp_replace",
        "try_cast",
        "epoch",
        "age",
    ]
)


class UnsafeSqlError(Exception):
    """The query was refused. The message is safe to show to the model."""


@dataclass(frozen=True)
class AccessPolicy:
    """What one user may see. Keys are lower-case qualified table names."""

    row_scope: dict[str, tuple[str, frozenset[str]]] = field(default_factory=dict)
    hidden_columns: dict[str, set[str]] = field(default_factory=dict)
    denied_tables: set[str] = field(default_factory=set)

    @property
    def restricted(self) -> bool:
        return bool(self.row_scope or self.hidden_columns or self.denied_tables)


def _check_shape(root: Any) -> set[str]:
    if not isinstance(root, exp.Query):
        raise UnsafeSqlError(f"Only read queries are allowed, not {type(root).__name__}.")
    with_ = root.args.get("with_") or root.args.get("with")
    if with_ is not None and with_.args.get("recursive"):
        raise UnsafeSqlError("Recursive queries are not allowed.")
    for node in root.walk():
        if isinstance(node, FORBIDDEN_NODES):
            raise UnsafeSqlError(f"{type(node).__name__} is not allowed.")
        if isinstance(node, exp.Anonymous):
            name = str(node.this).lower()
            if name not in SAFE_UNKNOWN_FUNCTIONS:
                raise UnsafeSqlError(f"Function {name} is not allowed.")
        elif isinstance(node, exp.Func) and DANGEROUS_FUNCTION.search(node.sql_name()):
            raise UnsafeSqlError(f"Function {node.sql_name()} is not allowed.")
    return {cte.alias_or_name.lower() for cte in root.find_all(exp.CTE)}


def _resolve(node: exp.Table, catalog: Catalog) -> Table:
    if not isinstance(node.this, exp.Identifier):
        raise UnsafeSqlError("Table functions are not allowed.")
    schema = node.db or None
    if (schema or "").lower() in SYSTEM_SCHEMAS or node.name.lower().startswith(("duckdb_", "pg_", "sqlite_")):
        raise UnsafeSqlError("System tables are not allowed.")
    table = catalog.find(node.name, schema)
    if table is None:
        raise UnsafeSqlError(f"Unknown or ambiguous table {node.sql()}. Use a table from the catalog, with its schema.")
    return table


def _physical(table: Table) -> exp.Table:
    return exp.table_(
        exp.to_identifier(table.name, quoted=True),
        db=exp.to_identifier(table.schema, quoted=True) if table.schema else None,
    )


def _scoped(table: Table, access: AccessPolicy, alias: str) -> exp.Expression:
    key = table.qualified.lower()
    hidden = {c.lower() for c in access.hidden_columns.get(key, set())}
    visible = [c.name for c in table.columns if c.name.lower() not in hidden]
    query = exp.select(*[exp.column(c, quoted=True) for c in visible]).from_(_physical(table))
    if key in access.row_scope:
        column, values = access.row_scope[key]
        query = query.where(
            exp.In(this=exp.column(column, quoted=True), expressions=[exp.Literal.string(v) for v in sorted(values)])
        )
    return query.subquery(alias=exp.to_identifier(alias, quoted=True))


def prepare(sql: str, catalog: Catalog, access: AccessPolicy | None = None, *, max_rows: int = 1000) -> str:
    """Return SQL ready to run in the catalog's dialect, or raise UnsafeSqlError."""
    access = access or AccessPolicy()
    try:
        statements = [s for s in sqlglot.parse(sql, read=catalog.dialect) if s is not None]
    except sqlglot.errors.SqlglotError as exc:
        raise UnsafeSqlError("The query could not be parsed.") from exc
    if len(statements) != 1:
        raise UnsafeSqlError("Send exactly one statement.")
    root: Any = statements[0]
    cte_names = _check_shape(root)

    known = {t.name.lower() for t in catalog.tables}
    if cte_names & known:
        # A CTE named after a real table would escape the rewrite below for every later reference to that name.
        raise UnsafeSqlError("A CTE may not reuse the name of a real table.")
    for node in list(root.find_all(exp.Table)):
        if not node.db and node.name.lower() in cte_names:
            continue
        table = _resolve(node, catalog)
        key = table.qualified.lower()
        if key in access.denied_tables:
            raise UnsafeSqlError(f"Table {table.qualified} is not available to this user.")
        if key in access.row_scope or key in access.hidden_columns:
            node.replace(_scoped(table, access, node.alias or table.name))
        else:
            node.set("this", exp.to_identifier(table.name, quoted=True))
            node.set("db", exp.to_identifier(table.schema, quoted=True) if table.schema else None)
    for column in root.find_all(exp.Column):
        if column.args.get("db"):
            column.set("db", None)
    if root.args.get("limit") is None and root.args.get("fetch") is None and isinstance(root, exp.Query):
        root = root.limit(max_rows + 1, copy=False)
    prepared = root.sql(dialect=catalog.dialect)
    sqlglot.parse_one(prepared, read=catalog.dialect)
    return str(prepared)
