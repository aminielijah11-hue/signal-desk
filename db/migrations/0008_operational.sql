-- Parser telemetry and ingest operations — PROMPT.md §4, §6.5, §11.

CREATE TABLE parser_variants (
    name        TEXT PRIMARY KEY,
    description TEXT,
    first_seen  TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen   TIMESTAMPTZ NOT NULL DEFAULT now(),
    n_filings   BIGINT NOT NULL DEFAULT 0 CHECK (n_filings >= 0),
    status      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'unsupported'))
);

CREATE TABLE parser_quarantine (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source     TEXT NOT NULL,
    identifier TEXT NOT NULL,
    raw_ref    TEXT,
    reason     TEXT NOT NULL,
    seen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved   BOOLEAN NOT NULL DEFAULT false
);

CREATE INDEX idx_parser_quarantine_unresolved ON parser_quarantine (source) WHERE NOT resolved;

CREATE TABLE ingest_log (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source        TEXT NOT NULL,
    started_at    TIMESTAMPTZ NOT NULL,
    finished_at   TIMESTAMPTZ,
    status        TEXT NOT NULL CHECK (status IN ('running', 'success', 'failed')),
    rows_in       BIGINT,
    rows_written  BIGINT,
    error         TEXT
);

CREATE INDEX idx_ingest_log_source_started ON ingest_log (source, started_at DESC);

CREATE TABLE http_cache (
    url           TEXT PRIMARY KEY,
    etag          TEXT,
    last_modified TEXT,
    fetched_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    body_hash     TEXT
);

CREATE TABLE source_disagreement (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    topic      TEXT NOT NULL,
    source_a   TEXT NOT NULL,
    source_b   TEXT NOT NULL,
    detail     JSONB NOT NULL,
    seen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved   BOOLEAN NOT NULL DEFAULT false
);

CREATE INDEX idx_source_disagreement_unresolved ON source_disagreement (topic) WHERE NOT resolved;
