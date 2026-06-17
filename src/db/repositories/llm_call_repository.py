from pathlib import Path
from typing import Any, cast

from db.domain.llm_call import LlmCall
from db.infrastructure import DbBackend, SqliteBackend, make_backend


class LlmCallRepository:
    def __init__(self, target: Path | str | None = None) -> None:
        self._backend: DbBackend = make_backend(target)
        # Exposed for tests that insert rows with custom timestamps (SQLite only).
        self._db_path: Path | None = (
            self._backend.path if isinstance(self._backend, SqliteBackend) else None
        )
        self._init_schema()

    def _init_schema(self) -> None:
        stmts = self._backend.schema_sql()
        if not stmts:  # Flyway owns the Postgres schema.
            return
        with self._backend.connect() as conn:
            for stmt in stmts:
                conn.execute(stmt)

    def save(self, call: LlmCall) -> LlmCall:
        ph = self._backend.placeholder
        created_at = self._backend.now_value()
        sql = f"""
            INSERT INTO llm_calls
                (created_at, provider, model, input_tokens, output_tokens,
                 cost, latency, prompt, answer, max_tokens, temperature, top_p, top_k,
                 ttft_ms, response_status, error_message, system_prompt, ignored_params,
                 request_id, stage)
            VALUES ({", ".join([ph] * 20)})
        """
        params = (
            created_at,
            call.provider,
            call.model,
            call.input_tokens,
            call.output_tokens,
            call.cost,
            call.latency,
            call.prompt,
            call.answer,
            call.max_tokens,
            call.temperature,
            call.top_p,
            call.top_k,
            call.ttft_ms,
            call.response_status,
            call.error_message,
            call.system_prompt,
            self._backend.dump_json(call.ignored_params),
            call.request_id,
            call.stage,
        )
        with self._backend.connect() as conn:
            call.id = self._backend.insert_returning_id(conn, sql, params)
        call.created_at = self._backend.parse_created_at(created_at)
        return call

    def get(self, call_id: int) -> LlmCall | None:
        ph = self._backend.placeholder
        with self._backend.connect() as conn:
            row = conn.execute(f"SELECT * FROM llm_calls WHERE id = {ph}", (call_id,)).fetchone()
        return self._row_to_llm_call(row) if row is not None else None

    def list_all(
        self, limit: int = 100, offset: int = 0, model: str | None = None
    ) -> list[LlmCall]:
        ph = self._backend.placeholder
        sql = "SELECT * FROM llm_calls"
        params: list[int | str] = []
        if model is not None:
            sql += f" WHERE model = {ph}"
            params.append(model)
        sql += f" ORDER BY created_at DESC LIMIT {ph} OFFSET {ph}"
        params.extend([limit, offset])
        with self._backend.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_llm_call(r) for r in rows]

    def _row_to_llm_call(self, row: Any) -> LlmCall:
        return LlmCall(
            id=cast("int", row["id"]),
            created_at=self._backend.parse_created_at(row["created_at"]),
            provider=cast("str", row["provider"]),
            model=cast("str", row["model"]),
            input_tokens=cast("int", row["input_tokens"]),
            output_tokens=cast("int", row["output_tokens"]),
            cost=cast("float", row["cost"]),
            latency=cast("float", row["latency"]),
            prompt=cast("str", row["prompt"]),
            answer=cast("str", row["answer"]),
            max_tokens=cast("int | None", row["max_tokens"]),
            temperature=cast("float | None", row["temperature"]),
            top_p=cast("float | None", row["top_p"]),
            top_k=cast("int | None", row["top_k"]),
            ttft_ms=cast("float | None", row["ttft_ms"]),
            response_status=cast("str | None", row["response_status"]),
            error_message=cast("str | None", row["error_message"]),
            system_prompt=cast("str | None", row["system_prompt"]),
            ignored_params=self._backend.parse_json(row["ignored_params"]) or [],
            request_id=cast("str | None", row["request_id"]),
            stage=row["stage"],
        )
