"""Read-only access to one customer database, through any SQLAlchemy dialect."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import sqlalchemy as sa

# SQLAlchemy dialect name -> sqlglot dialect name.
SQLGLOT_DIALECTS = {
    "duckdb": "duckdb",
    "postgresql": "postgres",
    "mssql": "tsql",
    "oracle": "oracle",
    "mysql": "mysql",
    "snowflake": "snowflake",
}


class SourceError(Exception):
    """A query failed. The message is safe to show to the model, so it can correct its SQL."""


@dataclass(frozen=True)
class QueryResult:
    columns: list[str]
    rows: list[tuple[Any, ...]]
    truncated: bool


class Source:
    def __init__(
        self, url: str, *, connect_args: dict[str, Any] | None = None, max_rows: int = 1000, timeout_s: float = 15
    ) -> None:
        self.engine = sa.create_engine(url, connect_args=connect_args or {})
        self.max_rows = max_rows
        self.timeout_s = timeout_s

    @classmethod
    def duckdb(cls, path: Path, **kwargs: Any) -> Source:
        """Read-only at the database level, with file and network access switched off."""
        config = {"enable_external_access": "false"}
        return cls(f"duckdb:///{path.as_posix()}", connect_args={"read_only": True, "config": config}, **kwargs)

    @property
    def dialect(self) -> str:
        return SQLGLOT_DIALECTS[self.engine.dialect.name]

    def execute(self, sql: str) -> QueryResult:
        with self.engine.connect() as conn:
            driver: Any = conn.connection.driver_connection
            timer = None
            if hasattr(driver, "interrupt"):
                timer = threading.Timer(self.timeout_s, driver.interrupt)
                timer.daemon = True
                timer.start()
            try:
                result = conn.exec_driver_sql(sql)
                columns = list(result.keys())
                rows = [tuple(r) for r in result.fetchmany(self.max_rows + 1)]
                result.close()
            except sa.exc.DBAPIError as exc:
                raise SourceError(str(exc.orig).split("\n")[0][:300]) from exc
            finally:
                if timer is not None:
                    timer.cancel()
                conn.rollback()
        return QueryResult(columns, rows[: self.max_rows], len(rows) > self.max_rows)

    def dispose(self) -> None:
        self.engine.dispose()
