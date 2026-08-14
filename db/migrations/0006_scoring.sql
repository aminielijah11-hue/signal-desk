-- Scoring engine outputs — PROMPT.md §4, §5. scoring/ reads only rows
-- with needs_review = false and provenance not in ('ocr','ocr_low_conf')
-- from the upstream tables; this migration doesn't need to re-encode that
-- rule itself (it's enforced by NO_UNSCORED_REVIEW_LEAK / NO_OCR_IN_SCORING
-- guardrails plus the scoring/ code in Phase 9), only store the results.

CREATE TABLE signals (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cik             INTEGER NOT NULL REFERENCES issuers (cik),
    event_date      DATE NOT NULL,
    stream          TEXT NOT NULL,
    subtype         TEXT,
    raw_features    JSONB NOT NULL,
    component_score NUMERIC NOT NULL,
    evidence        JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_signals_cik_date ON signals (cik, event_date);
CREATE INDEX idx_signals_stream ON signals (stream);

CREATE TABLE scores_daily (
    cik         INTEGER NOT NULL REFERENCES issuers (cik),
    d           DATE NOT NULL,
    composite   NUMERIC NOT NULL,
    percentile  NUMERIC,
    breakdown   JSONB NOT NULL,
    rank        INTEGER,
    top_reasons TEXT[] NOT NULL DEFAULT '{}',
    PRIMARY KEY (cik, d)
);

CREATE INDEX idx_scores_daily_date_rank ON scores_daily (d, rank);

CREATE TABLE alerts (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cik         INTEGER NOT NULL REFERENCES issuers (cik),
    d           DATE NOT NULL,
    tier        TEXT NOT NULL CHECK (tier IN ('T1', 'T2', 'T3')),
    channel     TEXT NOT NULL,
    sent_at     TIMESTAMPTZ,
    payload     JSONB NOT NULL,
    dedupe_key  TEXT NOT NULL UNIQUE
);

CREATE INDEX idx_alerts_cik_date ON alerts (cik, d);
