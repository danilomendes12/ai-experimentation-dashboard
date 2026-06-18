-- Vector store for the chunking-algorithm comparison module (src/chunking/).
-- One row per chunk. The `algorithm` + `dataset` columns let several chunking
-- strategies coexist in the same table and be indexed / queried / compared
-- independently (e.g. WHERE algorithm = 'recursive' AND dataset = 'k8s').
--
-- Postgres-only: it needs pgvector, so the SQLite test backend does NOT mirror
-- this table (the chunking module is a runtime/experimental layer, not part of
-- the cross-backend db/ domain exercised by the test suite).
-- `vector` extension is already created by V1.

CREATE TABLE doc_chunks (
    id           BIGSERIAL    PRIMARY KEY,
    algorithm    TEXT         NOT NULL,
    dataset      TEXT         NOT NULL,
    source_path  TEXT         NOT NULL,
    chunk_index  INTEGER      NOT NULL,
    content      TEXT         NOT NULL,
    n_tokens     INTEGER      NOT NULL,
    embedding    vector(1536) NOT NULL,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- Comparison queries always filter by strategy + corpus first.
CREATE INDEX idx_doc_chunks_algo_dataset ON doc_chunks (algorithm, dataset);
