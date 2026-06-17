from pathlib import Path
from typing import cast

from db.domain.rag_request import RagRequest
from db.infrastructure import DbBackend, make_backend


class RagRequestRepository:
    def __init__(self, target: Path | str | None = None) -> None:
        self._backend: DbBackend = make_backend(target)
        self._init_schema()

    def _init_schema(self) -> None:
        stmts = self._backend.schema_sql()
        if not stmts:  # Flyway owns the Postgres schema.
            return
        with self._backend.connect() as conn:
            for stmt in stmts:
                conn.execute(stmt)

    def save(self, rag: RagRequest) -> RagRequest:
        ph = self._backend.placeholder
        created_at = self._backend.now_value()
        sql = f"""
            INSERT INTO rag_request
                (request_id, created_at, query, config_json, total_cost_usd,
                 total_latency_ms, ttft_ms, faithfulness, status)
            VALUES ({", ".join([ph] * 9)})
        """
        params = (
            rag.request_id,
            created_at,
            rag.query,
            self._backend.dump_json(rag.config),
            rag.total_cost_usd,
            rag.total_latency_ms,
            rag.ttft_ms,
            rag.faithfulness,
            rag.status,
        )
        with self._backend.connect() as conn:
            conn.execute(sql, params)
        rag.created_at = self._backend.parse_created_at(created_at)
        return rag

    def get(self, request_id: str) -> RagRequest | None:
        ph = self._backend.placeholder
        with self._backend.connect() as conn:
            row = conn.execute(
                f"SELECT * FROM rag_request WHERE request_id = {ph}", (request_id,)
            ).fetchone()
        if row is None:
            return None
        return RagRequest(
            request_id=cast("str", row["request_id"]),
            query=cast("str", row["query"]),
            config=cast("dict[str, object]", self._backend.parse_json(row["config_json"]) or {}),
            total_cost_usd=cast("float", row["total_cost_usd"]),
            total_latency_ms=cast("float", row["total_latency_ms"]),
            ttft_ms=cast("float | None", row["ttft_ms"]),
            faithfulness=cast("float | None", row["faithfulness"]),
            status=cast("str", row["status"]),
            created_at=self._backend.parse_created_at(row["created_at"]),
        )

    def update(
        self,
        request_id: str,
        *,
        status: str | None = None,
        faithfulness: float | None = None,
        total_cost_usd: float | None = None,
        total_latency_ms: float | None = None,
        ttft_ms: float | None = None,
    ) -> None:
        ph = self._backend.placeholder
        updates = {
            "status": status,
            "faithfulness": faithfulness,
            "total_cost_usd": total_cost_usd,
            "total_latency_ms": total_latency_ms,
            "ttft_ms": ttft_ms,
        }
        sets = {col: val for col, val in updates.items() if val is not None}
        if not sets:
            return
        assignments = ", ".join(f"{col} = {ph}" for col in sets)
        sql = f"UPDATE rag_request SET {assignments} WHERE request_id = {ph}"
        with self._backend.connect() as conn:
            conn.execute(sql, [*sets.values(), request_id])
