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
    "sqlite": "sqlite",
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
        if self.engine.dialect.name == "duckdb":
            return self._execute_duckdb(sql)
        return self._execute_dbapi(sql)

    def _execute_duckdb(self, sql: str) -> QueryResult:
        with self.engine.connect() as conn:
            driver: Any = conn.connection.driver_connection
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
                timer.cancel()
                conn.rollback()
        return QueryResult(columns, rows[: self.max_rows], len(rows) > self.max_rows)

    def _execute_dbapi(self, sql: str) -> QueryResult:
        """Run on the driver's own cursor with no parameters, so a '%' in the SQL is never read as a placeholder."""
        errors: Any = self.engine.dialect.loaded_dbapi.Error
        with self.engine.connect() as conn:
            raw: Any = conn.connection
            driver: Any = raw.driver_connection
            # Stop a runaway query from the client side, and on PostgreSQL from the server side as well.
            stop = next(
                (getattr(driver, n) for n in ("cancel_safe", "cancel", "interrupt") if hasattr(driver, n)), None
            )
            timer = threading.Timer(self.timeout_s, stop) if stop else None
            cursor = raw.cursor()
            try:
                if self.engine.dialect.name == "postgresql":
                    cursor.execute(f"SET statement_timeout = {int(self.timeout_s * 1000)}")
                if timer is not None:
                    timer.daemon = True
                    timer.start()
                cursor.execute(sql)
                columns = [d[0] for d in cursor.description or []]
                rows = [tuple(r) for r in cursor.fetchmany(self.max_rows + 1)]
            except errors as exc:
                raise SourceError(str(exc).split("\n")[0][:300]) from exc
            finally:
                if timer is not None:
                    timer.cancel()
                cursor.close()
                raw.rollback()
        return QueryResult(columns, rows[: self.max_rows], len(rows) > self.max_rows)

    def dispose(self) -> None:
        self.engine.dispose()
