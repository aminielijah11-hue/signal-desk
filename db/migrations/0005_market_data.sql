-- Price, technicals, flow, macro — PROMPT.md §4, §3.3, §3.4.
-- prices_daily is "partitioned by year" per spec: declarative range
-- partitioning on d, one partition per calendar year. Research (§8)
-- starts backtests at 2016-01-01, so partitions start a little earlier
-- to leave room for the 250-trading-day market-model estimation window
-- before the first event date, through a few years of headroom forward.

CREATE TABLE prices_daily (
    cik       INTEGER NOT NULL REFERENCES issuers (cik),
    d         DATE NOT NULL,
    open      NUMERIC NOT NULL,
    high      NUMERIC NOT NULL,
    low       NUMERIC NOT NULL,
    close     NUMERIC NOT NULL,
    adj_close NUMERIC NOT NULL,
    volume    BIGINT NOT NULL CHECK (volume >= 0),
    PRIMARY KEY (cik, d),
    CHECK (high >= low AND high >= open AND high >= close)
) PARTITION BY RANGE (d);

CREATE TABLE prices_daily_2014 PARTITION OF prices_daily
    FOR VALUES FROM ('2014-01-01') TO ('2015-01-01');
CREATE TABLE prices_daily_2015 PARTITION OF prices_daily
    FOR VALUES FROM ('2015-01-01') TO ('2016-01-01');
CREATE TABLE prices_daily_2016 PARTITION OF prices_daily
    FOR VALUES FROM ('2016-01-01') TO ('2017-01-01');
CREATE TABLE prices_daily_2017 PARTITION OF prices_daily
    FOR VALUES FROM ('2017-01-01') TO ('2018-01-01');
CREATE TABLE prices_daily_2018 PARTITION OF prices_daily
    FOR VALUES FROM ('2018-01-01') TO ('2019-01-01');
CREATE TABLE prices_daily_2019 PARTITION OF prices_daily
    FOR VALUES FROM ('2019-01-01') TO ('2020-01-01');
CREATE TABLE prices_daily_2020 PARTITION OF prices_daily
    FOR VALUES FROM ('2020-01-01') TO ('2021-01-01');
CREATE TABLE prices_daily_2021 PARTITION OF prices_daily
    FOR VALUES FROM ('2021-01-01') TO ('2022-01-01');
CREATE TABLE prices_daily_2022 PARTITION OF prices_daily
    FOR VALUES FROM ('2022-01-01') TO ('2023-01-01');
CREATE TABLE prices_daily_2023 PARTITION OF prices_daily
    FOR VALUES FROM ('2023-01-01') TO ('2024-01-01');
CREATE TABLE prices_daily_2024 PARTITION OF prices_daily
    FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');
CREATE TABLE prices_daily_2025 PARTITION OF prices_daily
    FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');
CREATE TABLE prices_daily_2026 PARTITION OF prices_daily
    FOR VALUES FROM ('2026-01-01') TO ('2027-01-01');
CREATE TABLE prices_daily_2027 PARTITION OF prices_daily
    FOR VALUES FROM ('2027-01-01') TO ('2028-01-01');

CREATE TABLE tech_daily (
    cik    INTEGER NOT NULL REFERENCES issuers (cik),
    d      DATE NOT NULL,
    rsi14  NUMERIC,
    atr14  NUMERIC,
    sma20  NUMERIC,
    sma50  NUMERIC,
    sma200 NUMERIC,
    rvol20 NUMERIC,
    rs_spy NUMERIC,
    rs_sector NUMERIC,
    regime TEXT,
    PRIMARY KEY (cik, d)
);

CREATE TABLE flow_daily (
    cik              INTEGER NOT NULL REFERENCES issuers (cik),
    d                DATE NOT NULL,
    short_vol_ratio  NUMERIC,
    short_vol_z      NUMERIC,
    dark_pool_share  NUMERIC,
    days_to_cover    NUMERIC,
    pcr_oi           NUMERIC,
    pcr_z            NUMERIC,
    PRIMARY KEY (cik, d)
);

CREATE TABLE macro_daily (
    d              DATE PRIMARY KEY,
    dgs10          NUMERIC,
    t10y2y         NUMERIC,
    vix            NUMERIC,
    fin_conditions NUMERIC,
    regime         TEXT
);
