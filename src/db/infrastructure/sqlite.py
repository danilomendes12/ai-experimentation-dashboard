"""SQLite backend — used by the test suite.

The DDL lives here (not in Flyway) because Flyway only manages Postgres. This is
the second, intentional source of truth for the schema: keep it in sync with the
Postgres migrations under `migrations/`.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from .base import DbBackend

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from pathlib import Path

_LLM_CALLS_DDL = """
    CREATE TABLE IF NOT EXISTS llm_calls (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at    TEXT    NOT NULL,
        provider      TEXT    NOT NULL,
        model         TEXT    NOT NULL,
        input_tokens  INTEGER NOT NULL,
        output_tokens INTEGER NOT NULL,
        cost          REAL    NOT NULL,
        latency       REAL    NOT NULL,
        prompt        TEXT    NOT NULL,
        answer        TEXT    NOT NULL,
        max_tokens       INTEGER,
        temperature      REAL,
        top_p            REAL,
        top_k            INTEGER,
        ttft_ms          REAL,
        response_status  TEXT,
        error_message    TEXT,
        system_prompt    TEXT,
        ignored_params   TEXT,
        request_id       TEXT,
        stage            TEXT CHECK (stage IN ('embed', 'rerank', 'generate'))
    )
"""

_RAG_REQUEST_DDL = """
    CREATE TABLE IF NOT EXISTS rag_request (
        request_id        TEXT PRIMARY KEY,
        created_at        TEXT NOT NULL,
        query             TEXT NOT NULL,
        config_json       TEXT,
        total_cost_usd    REAL NOT NULL,
        total_latency_ms  REAL NOT NULL,
        ttft_ms           REAL,
        faithfulness      REAL,
        status            TEXT NOT NULL
    )
"""


class SqliteBackend(DbBackend):
    placeholder = "?"

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def schema_sql(self) -> list[str]:
        return [_LLM_CALLS_DDL, _RAG_REQUEST_DDL]

    def insert_returning_id(self, conn: Any, sql: str, params: Sequence[Any]) -> int:
        cursor = conn.execute(sql, params)
        return int(cursor.lastrowid)

    def now_value(self) -> str:
        return datetime.now(tz=UTC).isoformat()

    def daily_spend_sql(self) -> str:
        return """
            SELECT DATE(created_at) AS day, SUM(cost) AS total, COUNT(*) AS cnt
            FROM llm_calls
            WHERE response_status IN ('success', 'cancelled')
              AND created_at >= DATE('now', ?)
            GROUP BY day
            ORDER BY day DESC
        """

    def daily_spend_param(self, days: int) -> str:
        return f"-{days} days"

    def dump_json(self, value: Any) -> str | None:
        return json.dumps(value) if value else None

    def parse_json(self, value: Any) -> Any:
        return json.loads(value) if value else None
