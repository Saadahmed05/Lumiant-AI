"""Study a database from its own metadata and contents: no mapping file is read.

Only low-cardinality columns (codes and statuses) keep sample values, so free text such as descriptions never
reaches the model through the catalog.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

import sqlalchemy as sa

from lumiant.nomap.source import Source

SYSTEM_SCHEMAS = {"information_schema", "pg_catalog", "sys", "system", "temp"}
MAX_SAMPLED_DISTINCT = 30
MAX_SAMPLES = 12
MAX_JOIN_VALUES = 20_000
MIN_JOIN_COVERAGE = 0.9
SAMPLE_CHARS = 40


@dataclass(frozen=True)
class Column:
    name: str
    type: str
    rows_filled: int
    distinct: int
    low: str | None = None
    high: str | None = None
    samples: tuple[str, ...] = ()
    comment: str | None = None

    @property
    def is_text(self) -> bool:
        return any(t in self.type.upper() for t in ("CHAR", "TEXT", "STRING"))


@dataclass(frozen=True)
class Table:
    schema: str | None
    name: str
    rows: int
    columns: tuple[Column, ...]
    comment: str | None = None

    @property
    def qualified(self) -> str:
        return f"{self.schema}.{self.name}" if self.schema else self.name

    def column(self, name: str) -> Column | None:
        return next((c for c in self.columns if c.name.lower() == name.lower()), None)


@dataclass(frozen=True)
class Join:
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    coverage: float


@dataclass(frozen=True)
class Catalog:
    dialect: str
    tables: tuple[Table, ...]
    joins: tuple[Join, ...] = field(default=())

    def find(self, name: str, schema: str | None = None) -> Table | None:
        """Resolve a table case-insensitively. A bare name that exists in two schemas resolves to nothing."""
        hits = [t for t in self.tables if t.name.lower() == name.lower()]
        if schema is not None:
            hits = [t for t in hits if (t.schema or "").lower() == schema.lower()]
        return hits[0] if len(hits) == 1 else None

    def without(self, hidden: dict[str, set[str]], denied: set[str]) -> Catalog:
        """The catalog as one user may see it. Hidden columns and tables are removed, not just refused."""
        tables = []
        for t in self.tables:
            if t.qualified.lower() in denied:
                continue
            drop = {c.lower() for c in hidden.get(t.qualified.lower(), set())}
            tables.append(replace(t, columns=tuple(c for c in t.columns if c.name.lower() not in drop)))
        seen = {(t.qualified, c.name) for t in tables for c in t.columns}
        joins = tuple(
            j for j in self.joins if (j.from_table, j.from_column) in seen and (j.to_table, j.to_column) in seen
        )
        return Catalog(self.dialect, tuple(tables), joins)

    def render(self) -> str:
        lines = [f"SQL dialect: {self.dialect}"]
        for t in self.tables:
            lines.append(f"\nTABLE {t.qualified} ({t.rows} rows)" + (f" -- {t.comment}" if t.comment else ""))
            for c in t.columns:
                facts = [c.type, f"{c.distinct} distinct"]
                if c.rows_filled < t.rows:
                    facts.append(f"{t.rows - c.rows_filled} blank")
                if c.low is not None:
                    facts.append(f"range {c.low} to {c.high}")
                if c.samples:
                    facts.append("values " + ", ".join(c.samples))
                if c.comment:
                    facts.append(c.comment)
                lines.append(f"  {c.name}: " + "; ".join(facts))
        if self.joins:
            lines.append("\nLIKELY JOINS (values tested; single-column only, so check composite keys yourself)")
            lines += [
                f"  {j.from_table}.{j.from_column} -> {j.to_table}.{j.to_column} ({j.coverage:.0%} of values found)"
                for j in self.joins
            ]
        return "\n".join(lines)


def _short(value: Any) -> str:
    return str(value)[:SAMPLE_CHARS]


def _comment(insp: sa.Inspector, name: str, schema: str | None) -> str | None:
    try:
        return insp.get_table_comment(name, schema=schema).get("text")
    except (NotImplementedError, sa.exc.SQLAlchemyError):
        return None


def _profile_column(conn: sa.Connection, table: sa.TableClause, info: Any) -> Column:
    col: Any = sa.column(info["name"])
    kind = str(info["type"])
    is_bool = "BOOL" in kind.upper()
    measures: list[Any] = [sa.func.count(col), sa.func.count(col.distinct())]
    if not is_bool:
        measures += [sa.func.min(col), sa.func.max(col)]
    row = conn.execute(sa.select(*measures).select_from(table)).one()
    low, high = (None, None) if is_bool else (row[2], row[3])
    samples: tuple[str, ...] = ()
    is_text = any(t in kind.upper() for t in ("CHAR", "TEXT", "STRING"))
    if (is_text or is_bool) and 0 < row[1] <= MAX_SAMPLED_DISTINCT:
        n = sa.func.count().label("n")
        top = sa.select(col, n).select_from(table).where(col.is_not(None)).group_by(col).order_by(n.desc(), col)
        samples = tuple(_short(r[0]) for r in conn.execute(top.limit(MAX_SAMPLES)))
    show_range = low is not None and not is_text
    return Column(
        name=info["name"],
        type=kind,
        rows_filled=row[0],
        distinct=row[1],
        low=_short(low) if show_range else None,
        high=_short(high) if show_range else None,
        samples=samples,
        comment=info.get("comment"),
    )


def _text_values(conn: sa.Connection, table: Table) -> dict[str, set[str]]:
    target = sa.table(table.name, schema=table.schema)
    values = {}
    for c in table.columns:
        if c.is_text and c.distinct > 1:
            col: Any = sa.column(c.name)
            query = sa.select(col).select_from(target).where(col.is_not(None)).distinct().limit(MAX_JOIN_VALUES)
            values[c.name] = {str(r[0]) for r in conn.execute(query)}
    return values


def _joins(conn: sa.Connection, tables: list[Table]) -> list[Join]:
    """Propose joins by testing values: the target must be unique and hold nearly all of the source values."""
    values = {t.qualified: _text_values(conn, t) for t in tables}
    found = []
    for target in tables:
        for key in target.columns:
            if key.name not in values[target.qualified] or key.distinct != target.rows:
                continue
            keys = values[target.qualified][key.name]
            for source in tables:
                if source is target:
                    continue
                for name, vals in values[source.qualified].items():
                    coverage = len(vals & keys) / len(vals)
                    if coverage >= MIN_JOIN_COVERAGE:
                        found.append(Join(source.qualified, name, target.qualified, key.name, coverage))
    return found


def discover(source: Source, *, exclude: frozenset[str] = frozenset()) -> Catalog:
    tables: list[Table] = []
    with source.engine.connect() as conn:
        insp = sa.inspect(conn)
        for schema in insp.get_schema_names():
            # DuckDB reports schemas as catalog.schema, so check each part.
            if SYSTEM_SCHEMAS & {part.lower().strip('"') for part in schema.split(".")}:
                continue
            for name in [*insp.get_table_names(schema=schema), *insp.get_view_names(schema=schema)]:
                if name in exclude:
                    continue
                target = sa.table(name, schema=schema)
                rows = conn.execute(sa.select(sa.func.count()).select_from(target)).scalar_one()
                columns = tuple(_profile_column(conn, target, c) for c in insp.get_columns(name, schema=schema))
                tables.append(Table(_visible_schema(schema, conn), name, rows, columns, _comment(insp, name, schema)))
        joins = _joins(conn, tables)
    return Catalog(source.dialect, tuple(tables), tuple(joins))


def _visible_schema(schema: str, conn: sa.Connection) -> str | None:
    short = schema.rsplit(".", 1)[-1].strip('"')
    return None if short == conn.dialect.default_schema_name else short
