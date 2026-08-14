-- Institutional positioning (13F, 13D/G) — PROMPT.md §4.

CREATE TABLE institutions (
    cik  INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT
);

CREATE TABLE holdings_13f (
    institution_cik  INTEGER NOT NULL REFERENCES institutions (cik),
    issuer_cik       INTEGER NOT NULL REFERENCES issuers (cik),
    quarter_end      DATE NOT NULL,
    shares           NUMERIC NOT NULL CHECK (shares >= 0),
    value_usd        NUMERIC NOT NULL CHECK (value_usd >= 0),
    pct_of_portfolio NUMERIC,
    PRIMARY KEY (institution_cik, issuer_cik, quarter_end)
);

CREATE INDEX idx_holdings_13f_issuer_quarter ON holdings_13f (issuer_cik, quarter_end);

CREATE TABLE stakes_13d (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    filer_cik       INTEGER NOT NULL REFERENCES institutions (cik),
    issuer_cik      INTEGER NOT NULL REFERENCES issuers (cik),
    filed_at        DATE NOT NULL,
    pct_of_class    NUMERIC NOT NULL CHECK (pct_of_class >= 0 AND pct_of_class <= 100),
    is_activist     BOOLEAN NOT NULL DEFAULT false,
    purpose_excerpt TEXT
);

CREATE INDEX idx_stakes_13d_issuer_date ON stakes_13d (issuer_cik, filed_at);
