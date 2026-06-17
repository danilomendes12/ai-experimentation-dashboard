"""Dialect abstraction so the DB layer runs on both Postgres (runtime) and SQLite (tests).

Each concrete backend hides every SQL-dialect difference (placeholders,
auto-increment, timestamp/JSON handling, schema bootstrap) behind this interface
so the repositories and analytics stay dialect-agnostic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import contextmanager
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence


class DbBackend(ABC):
    """Common interface implemented per SQL dialect."""

    placeholder: str

    @contextmanager
    @abstractmethod
    def connect(self) -> Iterator[Any]:
        """Yield a connection whose rows are accessible by column name."""
        raise NotImplementedError

    @abstractmethod
    def schema_sql(self) -> list[str]:
        """DDL statements applied at startup.

        Empty when an external tool (Flyway) owns the schema.
        """
        raise NotImplementedError

    @abstractmethod
    def insert_returning_id(self, conn: Any, sql: str, params: Sequence[Any]) -> int:
        """Run an INSERT and return the generated integer primary key."""
        raise NotImplementedError

    @abstractmethod
    def now_value(self) -> Any:
        """Value to store for a `created_at` column."""
        raise NotImplementedError

    @abstractmethod
    def daily_spend_sql(self) -> str:
        """Daily-spend aggregation; the only analytics query with a date function."""
        raise NotImplementedError

    @abstractmethod
    def daily_spend_param(self, days: int) -> Any:
        """Bound parameter for the window in `daily_spend_sql`."""
        raise NotImplementedError

    @abstractmethod
    def dump_json(self, value: Any) -> Any:
        """Serialize a Python value for a JSON column."""
        raise NotImplementedError

    @abstractmethod
    def parse_json(self, value: Any) -> Any:
        """Deserialize a JSON column value back into Python."""
        raise NotImplementedError

    @staticmethod
    def parse_created_at(value: Any) -> datetime:
        """Normalize a stored `created_at` to a `datetime` (handles str or datetime)."""
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(str(value))
