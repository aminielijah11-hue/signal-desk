-- Reference data: issuers (SEC-registered companies) and ticker aliases
-- used to resolve free-text asset descriptions (e.g. congressional PTRs)
-- to a CIK. Referenced by almost every other table, so it comes first.

CREATE TABLE issuers (
    cik         INTEGER PRIMARY KEY,
    ticker      TEXT,
    name        TEXT NOT NULL,
    cusip       TEXT,
    sector      TEXT,
    industry    TEXT,
    exchange    TEXT,
    mcap        NUMERIC,
    shares_out  BIGINT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_issuers_ticker ON issuers (ticker);

CREATE TABLE ticker_aliases (
    alias       TEXT NOT NULL,
    cik         INTEGER NOT NULL REFERENCES issuers (cik),
    confidence  NUMERIC NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    source      TEXT NOT NULL,
    PRIMARY KEY (alias, cik, source)
);

CREATE INDEX idx_ticker_aliases_cik ON ticker_aliases (cik);
