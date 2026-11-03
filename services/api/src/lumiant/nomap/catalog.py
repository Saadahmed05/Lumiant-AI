"""What the agent knows about a database: tables, columns, their profiles and what was checked.

Discovery (discovery.py) fills this in. Large ERPs have tens of thousands of tables, so a table may be known by
structure only until the agent asks about it; `render` then lists names and points the agent to `search`.
Only low-cardinality columns (codes and statuses) keep sample values, so free text never reaches the model here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

RENDER_BUDGET = 60_000  # characters, about 15,000 tokens


@dataclass(frozen=True)
class Column:
    name: str
    type: str
    rows_filled: int | None = None
    distinct: int | None = None
    low: str | None = None
    high: str | None = None
    samples: tuple[str, ...] = ()
    comment: str | None = None
    meaning: str | None = None  # from a knowledge pack: what this field means in a known system

    @property
    def is_text(self) -> bool:
        return any(t in self.type.upper() for t in ("CHAR", "TEXT", "STRING"))

    @property
    def is_bool(self) -> bool:
        return "BOOL" in self.type.upper()


@dataclass(frozen=True)
class Table:
    schema: str | None
    name: str
    rows: int | None
    columns: tuple[Column, ...]
    comment: str | None = None
    checks: tuple[str, ...] = ()  # data health findings, such as duplicate or total rows
    meaning: str | None = None

    @property
    def qualified(self) -> str:
        return f"{self.schema}.{self.name}" if self.schema else self.name

    @property
    def profiled(self) -> bool:
        return self.rows is not None

    def column(self, name: str) -> Column | None:
        return next((c for c in self.columns if c.name.lower() == name.lower()), None)

    def structure_only(self) -> Table:
        return replace(
            self,
            rows=None,
            checks=(),
            columns=tuple(Column(c.name, c.type, comment=c.comment, meaning=c.meaning) for c in self.columns),
        )


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
    packs: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()  # rules from knowledge packs that apply to this database

    def find(self, name: str, schema: str | None = None) -> Table | None:
        """Resolve a table case-insensitively. A bare name that exists in two schemas resolves to nothing."""
        hits = [t for t in self.tables if t.name.lower() == name.lower()]
        if schema is not None:
            hits = [t for t in hits if (t.schema or "").lower() == schema.lower()]
        return hits[0] if len(hits) == 1 else None

    def lookup(self, ref: str) -> Table | None:
        return self.find(*reversed(ref.rsplit(".", 1)))

    def with_table(self, table: Table) -> Catalog:
        return replace(self, tables=tuple(table if t.qualified == table.qualified else t for t in self.tables))

    def without(self, hidden: dict[str, set[str]], denied: set[str], scoped: frozenset[str] = frozenset()) -> Catalog:
        """The catalog as one user may see it. Hidden columns and tables are removed, not just refused.

        Tables in `scoped` lose their statistics, which were gathered over every row: they are profiled again
        under the user's limits when asked about.
        """
        tables = []
        for t in self.tables:
            key = t.qualified.lower()
            if key in denied:
                continue
            drop = {c.lower() for c in hidden.get(key, set())}
            t = replace(t, columns=tuple(c for c in t.columns if c.name.lower() not in drop))
            tables.append(t.structure_only() if key in scoped else t)
        seen = {(t.qualified, c.name) for t in tables for c in t.columns}
        joins = tuple(
            j for j in self.joins if (j.from_table, j.from_column) in seen and (j.to_table, j.to_column) in seen
        )
        return replace(self, tables=tuple(tables), joins=joins)

    def search(self, text: str, limit: int = 15) -> list[Table]:
        """Tables whose names, comments, columns or known meanings match the words in `text`."""
        words = [w for w in re.findall(r"[a-z0-9_]+", text.lower()) if len(w) >= 2]
        scored = []
        for t in self.tables:
            score = 0
            name = t.name.lower()
            about = " ".join(filter(None, [t.comment, t.meaning])).lower()
            columns = " ".join(c.name.lower() for c in t.columns)  # part words count: ERP fields join words
            meanings = " ".join(filter(None, [c.meaning or c.comment for c in t.columns])).lower()
            for w in words:
                score += 5 * (w in name) + 3 * (w in columns) + 2 * (w in about) + (w in meanings)
            if score:
                scored.append((score, t.rows or 0, t.qualified, t))
        scored.sort(key=lambda s: (-s[0], -s[1], s[2]))
        return [s[3] for s in scored[:limit]]

    def _header(self) -> list[str]:
        lines = [f"SQL dialect: {self.dialect}"]
        if self.packs:
            lines.append(
                f"Recognised system: {', '.join(self.packs)}. Field meanings marked 'known' are the system's standard ones; confirm them against the data."
            )
        lines += [f"Rule: {n}" for n in self.notes]
        return lines

    def render(self, budget: int = RENDER_BUDGET) -> str:
        full = "\n".join([*self._header(), *(render_table(t) for t in self.tables), *self._render_joins()])
        if len(full) <= budget:
            return full
        brief = [*self._header(), f"\n{len(self.tables)} tables. Profiles are loaded when you describe a table."]
        brief += [f"{t.qualified}: " + ", ".join(c.name for c in t.columns) for t in self.tables]
        text = "\n".join(brief)
        if len(text) <= budget:
            return text
        return "\n".join(
            [
                *self._header(),
                f"\n{len(self.tables)} tables: too many to list. Use find_tables with words from the question, then describe_table.",
            ]
        )

    def _render_joins(self) -> list[str]:
        if not self.joins:
            return []
        lines = ["\nLIKELY JOINS (values tested; single-column only, so check composite keys yourself)"]
        lines += [
            f"  {j.from_table}.{j.from_column} -> {j.to_table}.{j.to_column} ({j.coverage:.0%} of values found)"
            for j in self.joins
        ]
        return lines


def render_table(t: Table) -> str:
    head = f"\nTABLE {t.qualified} ({t.rows if t.profiled else 'not yet profiled'} rows)"
    head += "".join(f" -- {x}" for x in (t.meaning, t.comment) if x)
    lines = [head]
    for c in t.columns:
        facts = [c.type]
        if c.distinct is not None:
            facts.append(f"{c.distinct} distinct")
        if t.rows is not None and c.rows_filled is not None and c.rows_filled < t.rows:
            facts.append(f"{t.rows - c.rows_filled} blank")
        if c.low is not None:
            facts.append(f"range {c.low} to {c.high}")
        if c.samples:
            facts.append("values " + ", ".join(c.samples))
        if c.meaning:
            facts.append(f"known: {c.meaning}")
        if c.comment:
            facts.append(c.comment)
        lines.append(f"  {c.name}: " + "; ".join(facts))
    lines += [f"  CHECK: {x}" for x in t.checks]
    return "\n".join(lines)
