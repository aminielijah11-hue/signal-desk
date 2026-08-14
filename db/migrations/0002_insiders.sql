-- Corporate insiders (Form 3/4/5) — PROMPT.md §4, §6.

CREATE TABLE insiders (
    owner_cik   INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    is_officer  BOOLEAN NOT NULL DEFAULT false,
    is_director BOOLEAN NOT NULL DEFAULT false,
    is_ten_pct  BOOLEAN NOT NULL DEFAULT false,
    first_seen  DATE NOT NULL,
    last_seen   DATE NOT NULL,
    CHECK (last_seen >= first_seen)
);

CREATE TABLE insider_roles (
    owner_cik  INTEGER NOT NULL REFERENCES insiders (owner_cik),
    issuer_cik INTEGER NOT NULL REFERENCES issuers (cik),
    title      TEXT,
    start_date DATE NOT NULL,
    end_date   DATE,
    PRIMARY KEY (owner_cik, issuer_cik, start_date),
    CHECK (end_date IS NULL OR end_date >= start_date)
);

CREATE INDEX idx_insider_roles_issuer ON insider_roles (issuer_cik);

CREATE TABLE form4_filings (
    accession        TEXT PRIMARY KEY,
    issuer_cik       INTEGER NOT NULL REFERENCES issuers (cik),
    filed_at         TIMESTAMPTZ NOT NULL,
    period_of_report DATE NOT NULL,
    raw_gz           BYTEA,
    is_amendment     BOOLEAN NOT NULL DEFAULT false,
    supersedes       TEXT REFERENCES form4_filings (accession),
    parser_variant   TEXT,
    parser_version   TEXT
);

CREATE INDEX idx_form4_filings_issuer ON form4_filings (issuer_cik);
CREATE INDEX idx_form4_filings_filed_at ON form4_filings (filed_at);

CREATE TABLE insider_trades (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    accession       TEXT NOT NULL REFERENCES form4_filings (accession),
    owner_cik       INTEGER NOT NULL REFERENCES insiders (owner_cik),
    issuer_cik      INTEGER NOT NULL REFERENCES issuers (cik),
    txn_date        DATE NOT NULL,
    code            TEXT NOT NULL,
    shares          NUMERIC NOT NULL CHECK (shares >= 0),
    price           NUMERIC NOT NULL CHECK (price >= 0),
    value_usd       NUMERIC,
    shares_after    NUMERIC,
    direct_indirect TEXT,
    is_plan         BOOLEAN NOT NULL DEFAULT false,
    plan_evidence   TEXT,
    is_derivative   BOOLEAN NOT NULL DEFAULT false,
    pct_of_holding  NUMERIC,
    footnotes       TEXT,
    provenance      TEXT NOT NULL CHECK (provenance IN ('xml', 'mirror', 'manual')),
    needs_review    BOOLEAN NOT NULL DEFAULT false,
    UNIQUE (accession, owner_cik, txn_date, code, shares, price, is_derivative)
);

CREATE INDEX idx_insider_trades_issuer_date ON insider_trades (issuer_cik, txn_date);
CREATE INDEX idx_insider_trades_owner ON insider_trades (owner_cik);
CREATE INDEX idx_insider_trades_needs_review ON insider_trades (needs_review) WHERE needs_review;
