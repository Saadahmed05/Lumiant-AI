"""Discover a database from its own metadata and contents: no mapping file is read.

Structure comes from the database catalog in one pass. Profiles and health checks run per table, through the same
guard and user limits as the agent's own queries, so a restricted user never sees statistics over rows outside
their scope. Small databases are profiled up front; large ones table by table, when the agent asks.
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

import sqlalchemy as sa
from sqlglot import exp

from lumiant.nomap.catalog import Catalog, Column, Join, Table
from lumiant.nomap.packs import apply_packs
from lumiant.nomap.safe_sql import AccessPolicy, UnsafeSqlError, prepare
from lumiant.nomap.source import Source, SourceError

SYSTEM_SCHEMAS = {"information_schema", "pg_catalog", "sys", "system", "temp"}
PROFILE_UP_TO = 60  # tables; above this, profile on demand
MAX_SAMPLED_DISTINCT = 30
MAX_SAMPLES = 12
MAX_JOIN_VALUES = 20_000
MIN_JOIN_COVERAGE = 0.9
SAMPLE_CHARS = 40
DUPLICATE_CHECK_MAX_ROWS = 2_000_000
CANCEL_SHARE = 0.01  # a net under 1% of the gross means positive and negative rows cancel
CURRENCY = re.compile(r"(?:^|_)(?:curr|currency|currency_code|waers|waehr)$", re.I)
UNIT = re.compile(r"(?:^|_)(?:uom|meins|unit|units|einheit)$", re.I)
NOT_UNIT = re.compile(r"business|org|price|cost|value", re.I)
PRICE_UNIT = re.compile(r"price_?unit|peinh|per_?qty", re.I)
TOTAL_NAME = re.compile(r"total|summary|subtotal|footer", re.I)
ROW_NUMBER = re.compile(r"row|seq|line_?no|idx", re.I)  # export row numbers, unique or not
ROW_ID = re.compile(r"(?:^|_)id$", re.I)  # a generated id counts only when unique per row


def _short(value: Any) -> str:
    return str(value)[:SAMPLE_CHARS]


def _ref(table: Table) -> exp.Table:
    return exp.table_(
        exp.to_identifier(table.name, quoted=True),
        db=exp.to_identifier(table.schema, quoted=True) if table.schema else None,
    )


def _col(name: str) -> exp.Column:
    return exp.column(name, quoted=True)


def _run(source: Source, catalog: Catalog, access: AccessPolicy, query: exp.Expression) -> list[tuple[Any, ...]]:
    return source.execute(prepare(query.sql(dialect=catalog.dialect), catalog, access, max_rows=source.max_rows)).rows


def profile_table(source: Source, catalog: Catalog, table: Table, access: AccessPolicy | None = None) -> Table:
    """Statistics, sample values and health checks for one table, within the user's limits."""
    access = access or AccessPolicy()
    measures: list[exp.Expression] = [exp.Count(this=exp.Star())]
    for c in table.columns:
        measures.append(exp.Count(this=_col(c.name)))
        if c.is_comparable:
            measures.append(exp.Count(this=exp.Distinct(expressions=[_col(c.name)])))
        if c.is_ordered:
            measures += [exp.Min(this=_col(c.name)), exp.Max(this=_col(c.name))]
    stats = _run(source, catalog, access, exp.select(*measures).from_(_ref(table)))[0]
    rows, i, columns = int(stats[0]), 1, []
    for c in table.columns:
        filled, distinct = int(stats[i]), None
        i += 1
        if c.is_comparable:
            distinct = int(stats[i])
            i += 1
        low = high = None
        if c.is_ordered:
            low, high = stats[i], stats[i + 1]
            i += 2
        samples: tuple[str, ...] = ()
        if (c.is_text or c.is_bool) and distinct is not None and 0 < distinct <= MAX_SAMPLED_DISTINCT:
            n = exp.alias_(exp.Count(this=exp.Star()), "n")
            top = (
                exp.select(_col(c.name), n)
                .from_(_ref(table))
                .where(exp.Not(this=exp.Is(this=_col(c.name), expression=exp.Null())))
                .group_by(_col(c.name))
                .order_by(exp.Ordered(this=exp.column("n"), desc=True), _col(c.name))
                .limit(MAX_SAMPLES)
            )
            samples = tuple(_short(r[0]) for r in _run(source, catalog, access, top))
        columns.append(
            replace(
                c,
                rows_filled=filled,
                distinct=distinct,
                low=None if low is None else _short(low),
                high=None if high is None else _short(high),
                samples=samples,
            )
        )
    profiled = replace(table, rows=rows, columns=tuple(columns))
    return replace(profiled, checks=tuple(_health(source, catalog, access, profiled)))


def _health(source: Source, catalog: Catalog, access: AccessPolicy, t: Table) -> list[str]:
    """Problems that silently distort totals. Each check that cannot run says so instead of passing."""
    found: list[str] = []
    rows = t.rows or 0
    # A row number added by an export makes duplicates look different, so compare without such columns.
    row_ids = [
        c.name
        for c in t.columns
        if c.is_number and (ROW_NUMBER.search(c.name) or (c.distinct == rows and ROW_ID.search(c.name)))
    ]
    compared = [c.name for c in t.columns if c.name not in row_ids and c.is_comparable]
    if rows and compared and rows <= DUPLICATE_CHECK_MAX_ROWS:
        try:
            distinct_rows = exp.select(*[_col(n) for n in compared]).from_(_ref(t)).distinct().subquery("d")
            unique = _run(source, catalog, access, exp.select(exp.Count(this=exp.Star())).from_(distinct_rows))[0][0]
            if int(unique) < rows:
                ignoring = f", ignoring row number {', '.join(row_ids)}" if row_ids else ""
                found.append(
                    f"{rows - int(unique)} duplicate rows{ignoring}: decide whether to remove them, and say so"
                )
        except (UnsafeSqlError, SourceError):
            found.append("duplicate check could not run on this table")
    # Total rows usually blank the key columns but keep a unit or currency code.
    texts = [c for c in t.columns if c.is_text and not UNIT.search(c.name) and not CURRENCY.search(c.name)]
    numbers = [c for c in t.columns if c.is_number and c.name not in row_ids]
    if rows and len(texts) >= 2 and numbers:
        blank = exp.and_(*[exp.Is(this=_col(c.name), expression=exp.Null()) for c in texts])
        filled = exp.or_(*[exp.Not(this=exp.Is(this=_col(c.name), expression=exp.Null())) for c in numbers])
        try:
            totals = _run(
                source,
                catalog,
                access,
                exp.select(exp.Count(this=exp.Star())).from_(_ref(t)).where(exp.and_(blank, filled)),
            )[0][0]
            if int(totals):
                found.append(
                    f"{int(totals)} rows have every text column blank but numbers filled: likely total rows, never add them to detail rows"
                )
        except (UnsafeSqlError, SourceError):
            found.append("total-row check could not run on this table")
    # Double-entry and mirror records (Odoo's virtual locations, debit/credit pairs) make a column add up to zero.
    signed = [c for c in numbers if c.low is not None and _number(c.low) < 0 < _number(c.high or "0")]
    for c in signed:
        try:
            net, gross = _run(
                source,
                catalog,
                access,
                exp.select(exp.Sum(this=_col(c.name)), exp.Sum(this=exp.Abs(this=_col(c.name)))).from_(_ref(t)),
            )[0]
            if gross and abs(float(net)) <= CANCEL_SHARE * float(gross):
                found.append(
                    f"{c.name} adds up to about zero over all rows ({float(net):g} net of {float(gross):g}): positive and negative rows cancel, so they are likely mirror or paired entries. Filter to the records that matter before adding"
                )
        except (UnsafeSqlError, SourceError):
            found.append(f"cancel-out check could not run on {c.name}")
    if TOTAL_NAME.search(t.name):
        found.append("the name suggests a totals or summary table: never add it to the detail table it summarises")
    for c in t.columns:
        many = c.is_text and 1 < (c.distinct or 0) <= MAX_SAMPLED_DISTINCT
        if many and CURRENCY.search(c.name):
            found.append(
                f"{c.name} holds {c.distinct} currencies ({', '.join(c.samples)}): never add amounts across them"
            )
        elif many and UNIT.search(c.name) and not NOT_UNIT.search(c.name):
            found.append(
                f"{c.name} holds {c.distinct} units ({', '.join(c.samples)}): never add quantities across them"
            )
        if PRICE_UNIT.search(c.name) and c.high is not None and _number(c.high) > 1:
            found.append(
                f"{c.name} goes up to {c.high}: prices may be per that many units, so divide before multiplying by quantity"
            )
    return found


def _number(text: str) -> float:
    try:
        return float(text)
    except ValueError:
        return 0.0


def _text_values(conn: sa.Connection, table: Table) -> dict[str, set[str]]:
    target = sa.table(table.name, schema=table.schema)
    values = {}
    for c in table.columns:
        if c.is_text and (c.distinct or 0) > 1:
            col: Any = sa.column(c.name)
            query = sa.select(col).select_from(target).where(col.is_not(None)).distinct().limit(MAX_JOIN_VALUES)
            values[c.name] = {str(r[0]) for r in conn.execute(query)}
    return values


def _joins(source: Source, tables: list[Table]) -> list[Join]:
    """Propose joins by testing values: the target must be unique and hold nearly all of the source values."""
    with source.engine.connect() as conn:
        values = {t.qualified: _text_values(conn, t) for t in tables}
    found = []
    for target in tables:
        for key in target.columns:
            if key.name not in values[target.qualified] or key.distinct != target.rows:
                continue
            keys = values[target.qualified][key.name]
            for other in tables:
                if other is target:
                    continue
                for name, vals in values[other.qualified].items():
                    coverage = len(vals & keys) / len(vals)
                    if coverage >= MIN_JOIN_COVERAGE:
                        found.append(Join(other.qualified, name, target.qualified, key.name, coverage))
    return found


def _structure(source: Source, exclude: frozenset[str]) -> list[Table]:
    tables: list[Table] = []
    with source.engine.connect() as conn:
        insp = sa.inspect(conn)
        for schema in insp.get_schema_names():
            # DuckDB reports schemas as catalog.schema, so check each part.
            if SYSTEM_SCHEMAS & {part.lower().strip('"') for part in schema.split(".")}:
                continue
            visible = _visible_schema(schema, conn)
            try:
                everything: Any = insp.get_multi_columns(schema=schema, kind=sa.engine.reflection.ObjectKind.ANY)
            except NotImplementedError:
                names = [*insp.get_table_names(schema=schema), *insp.get_view_names(schema=schema)]
                everything = {(schema, n): insp.get_columns(n, schema=schema) for n in names}
            try:
                comments: Any = insp.get_multi_table_comment(schema=schema, kind=sa.engine.reflection.ObjectKind.ANY)
            except (NotImplementedError, sa.exc.SQLAlchemyError):
                comments = {}
            for (_, name), cols in sorted(everything.items(), key=lambda kv: kv[0][1]):
                if name in exclude:
                    continue
                columns = tuple(Column(c["name"], str(c["type"]), comment=c.get("comment")) for c in cols)
                comment = (comments.get((schema, name)) or {}).get("text")
                tables.append(Table(visible, name, None, columns, comment))
    return tables


def discover(source: Source, *, exclude: frozenset[str] = frozenset(), profile_up_to: int = PROFILE_UP_TO) -> Catalog:
    catalog = apply_packs(Catalog(source.dialect, tuple(_structure(source, exclude))))
    if len(catalog.tables) > profile_up_to:
        return catalog
    for table in catalog.tables:
        catalog = catalog.with_table(profile_table(source, catalog, table))
    return replace(catalog, joins=tuple(_joins(source, list(catalog.tables))))


def _visible_schema(schema: str, conn: sa.Connection) -> str | None:
    short = schema.rsplit(".", 1)[-1].strip('"')
    return None if short == conn.dialect.default_schema_name else short
