-- Congressional trades (STOCK Act PTRs) — PROMPT.md §4, §7. The
-- provenance <> 'ocr' OR needs_review = true CHECK is, per §4, "the single
-- most important line in the schema": an OCR-derived row is structurally
-- incapable of entering the database as trusted.

CREATE TABLE congress_members (
    bioguide_id TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    chamber     TEXT NOT NULL CHECK (chamber IN ('house', 'senate')),
    party       TEXT,
    state       TEXT,
    district    TEXT
);

CREATE TABLE committees (
    member       TEXT NOT NULL REFERENCES congress_members (bioguide_id),
    committee    TEXT NOT NULL,
    subcommittee TEXT,
    rank         INTEGER,
    sectors      TEXT[] NOT NULL DEFAULT '{}',
    PRIMARY KEY (member, committee, subcommittee)
);

CREATE TABLE congress_trades (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    bioguide_id      TEXT NOT NULL REFERENCES congress_members (bioguide_id),
    ticker           TEXT,
    cik              INTEGER REFERENCES issuers (cik),
    txn_date         DATE NOT NULL,
    disclosed_at     DATE NOT NULL,
    type             TEXT NOT NULL,
    amount_low       NUMERIC NOT NULL,
    amount_high      NUMERIC NOT NULL,
    amount_bracket_id INTEGER NOT NULL,
    asset_desc       TEXT,
    source_url       TEXT NOT NULL,
    match_confidence NUMERIC,
    provenance       TEXT NOT NULL
        CHECK (provenance IN ('html', 'pdf_text', 'ocr', 'ocr_low_conf', 'mirror', 'manual')),
    ocr_confidence   NUMERIC,
    validation_flags TEXT[] NOT NULL DEFAULT '{}',
    needs_review     BOOLEAN NOT NULL DEFAULT false,
    UNIQUE (bioguide_id, txn_date, ticker, type, amount_low, source_url),
    CHECK (disclosed_at >= txn_date),
    CHECK (amount_high > amount_low),
    -- PROMPT.md §4 writes this literally as `provenance <> 'ocr'`, but
    -- §7.3 constructs 'ocr_low_conf' rows exactly the same way (always
    -- paired with needs_review=true) and the NO_OCR_IN_SCORING guardrail
    -- treats both values as equally untrusted. A CHECK naming only 'ocr'
    -- would leave 'ocr_low_conf' as a silent gap in the one constraint
    -- the spec calls "the single most important line in the schema" —
    -- widened to cover both, strictly safer, same intent.
    CHECK (provenance NOT IN ('ocr', 'ocr_low_conf') OR needs_review = true)
);

CREATE INDEX idx_congress_trades_cik_date ON congress_trades (cik, txn_date);
CREATE INDEX idx_congress_trades_member ON congress_trades (bioguide_id);
CREATE INDEX idx_congress_trades_needs_review ON congress_trades (needs_review) WHERE needs_review;

CREATE TABLE review_queue (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    table_name  TEXT NOT NULL,
    row_id      BIGINT NOT NULL,
    reason      TEXT NOT NULL,
    evidence    JSONB,
    source_url  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ,
    resolution  TEXT
);

CREATE INDEX idx_review_queue_unresolved ON review_queue (table_name) WHERE resolved_at IS NULL;
