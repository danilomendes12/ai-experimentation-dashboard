-- Initial schema for the LLM-call store and the RAG request pipeline.
-- Applied to Postgres by the `flyway` service in docker-compose.yml.
-- NOTE: the SQLite test backend keeps an equivalent DDL in
-- src/db/infrastructure/sqlite.py — keep the two in sync.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE llm_calls (
    id            BIGSERIAL PRIMARY KEY,
    created_at    TIMESTAMPTZ      NOT NULL,
    provider      TEXT             NOT NULL,
    model         TEXT             NOT NULL,
    input_tokens  INTEGER          NOT NULL,
    output_tokens INTEGER          NOT NULL,
    cost          DOUBLE PRECISION NOT NULL,
    latency       DOUBLE PRECISION NOT NULL,
    prompt        TEXT             NOT NULL,
    answer        TEXT             NOT NULL,
    max_tokens       INTEGER,
    temperature      DOUBLE PRECISION,
    top_p            DOUBLE PRECISION,
    top_k            INTEGER,
    ttft_ms          DOUBLE PRECISION,
    response_status  TEXT,
    error_message    TEXT,
    system_prompt    TEXT,
    ignored_params   JSONB,
    request_id       TEXT,
    stage            TEXT CHECK (stage IN ('embed', 'rerank', 'generate'))
);

CREATE INDEX idx_llm_calls_model ON llm_calls (model);
CREATE INDEX idx_llm_calls_request_id ON llm_calls (request_id);

CREATE TABLE rag_request (
    request_id        TEXT PRIMARY KEY,
    created_at        TIMESTAMPTZ      NOT NULL,
    query             TEXT             NOT NULL,
    config_json       JSONB,
    total_cost_usd    DOUBLE PRECISION NOT NULL,
    total_latency_ms  DOUBLE PRECISION NOT NULL,
    ttft_ms           DOUBLE PRECISION,
    faithfulness      DOUBLE PRECISION,
    status            TEXT             NOT NULL
);
