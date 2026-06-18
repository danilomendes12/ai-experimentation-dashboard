"""Repository over the ``doc_chunks`` pgvector table.

Unlike the other repositories, this one is **Postgres-only**: it needs pgvector
(``register_vector`` + ``<=>`` distance), which the SQLite backend cannot
provide. It therefore manages its own psycopg connection instead of going
through the ``DbBackend`` dialect abstraction. Schema is still owned by Flyway
(``migrations/V2__doc_chunks.sql``); this layer never issues DDL.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

import psycopg
from pgvector.psycopg import register_vector  # type: ignore[import-untyped]

from db.domain.chunk_record import ChunkRecord
from db.domain.search_hit import SearchHit

if TYPE_CHECKING:
    from collections.abc import Iterator

_INSERT_SQL = (
    "INSERT INTO doc_chunks "
    "(algorithm, dataset, source_path, chunk_index, content, n_tokens, embedding) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s::vector)"
)
_SEARCH_SQL = (
    "SELECT source_path, chunk_index, content, n_tokens, "
    "embedding <=> %s::vector AS distance "
    "FROM doc_chunks WHERE algorithm = %s AND dataset = %s "
    "ORDER BY distance LIMIT %s"
)


class ChunkVectorStore:
    def __init__(self, dsn: str | None = None) -> None:
        self.dsn = dsn or os.environ["DATABASE_URL"]

    @contextmanager
    def _connect(self) -> Iterator[Any]:
        with psycopg.connect(self.dsn, autocommit=True) as conn:
            register_vector(conn)
            yield conn

    def delete(self, algorithm: str, dataset: str) -> int:
        """Remove every chunk for one (algorithm, dataset); returns rows deleted."""
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM doc_chunks WHERE algorithm = %s AND dataset = %s",
                (algorithm, dataset),
            )
            return int(cur.rowcount)

    def add(self, records: list[ChunkRecord]) -> None:
        rows = [
            (
                r.algorithm,
                r.dataset,
                r.source_path,
                r.chunk_index,
                r.content,
                r.n_tokens,
                r.embedding,
            )
            for r in records
        ]
        with self._connect() as conn:
            conn.cursor().executemany(_INSERT_SQL, rows)

    def count(self, algorithm: str, dataset: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT count(*) FROM doc_chunks WHERE algorithm = %s AND dataset = %s",
                (algorithm, dataset),
            ).fetchone()
        return int(row[0])

    def search(
        self, query_vector: list[float], algorithm: str, dataset: str, k: int = 5
    ) -> list[SearchHit]:
        with self._connect() as conn:
            rows = conn.execute(_SEARCH_SQL, (query_vector, algorithm, dataset, k)).fetchall()
        return [
            SearchHit(
                source_path=row[0],
                chunk_index=int(row[1]),
                content=row[2],
                n_tokens=int(row[3]),
                distance=float(row[4]),
            )
            for row in rows
        ]
