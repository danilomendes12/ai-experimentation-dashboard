"""Postgres backend — used at runtime.

The schema is owned by Flyway (see `migrations/` and the `flyway` service in
`docker-compose.yml`), so `schema_sql()` returns nothing: the app never issues DDL.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .base import DbBackend

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence


class PostgresBackend(DbBackend):
    placeholder = "%s"

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    @contextmanager
    def connect(self) -> Iterator[Any]:
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            yield conn

    def schema_sql(self) -> list[str]:
        return []  # Flyway owns the Postgres schema.

    def insert_returning_id(self, conn: Any, sql: str, params: Sequence[Any]) -> int:
        row = conn.execute(sql + " RETURNING id", params).fetchone()
        return int(row["id"])

    def now_value(self) -> datetime:
        return datetime.now(tz=UTC)

    def daily_spend_sql(self) -> str:
        return """
            SELECT created_at::date AS day, SUM(cost) AS total, COUNT(*) AS cnt
            FROM llm_calls
            WHERE response_status IN ('success', 'cancelled')
              AND created_at >= now() - make_interval(days => %s)
            GROUP BY day
            ORDER BY day DESC
        """

    def daily_spend_param(self, days: int) -> int:
        return days

    def dump_json(self, value: Any) -> Any:
        return Jsonb(value) if value else None

    def parse_json(self, value: Any) -> Any:
        # psycopg already decodes JSONB into Python objects.
        return value or None
