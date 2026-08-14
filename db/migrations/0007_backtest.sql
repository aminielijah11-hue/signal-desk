-- Event-study backtester outputs — PROMPT.md §4, §8.

CREATE TABLE backtest_runs (
    id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    config  JSONB NOT NULL,
    git_sha TEXT NOT NULL
);

CREATE TABLE backtest_results (
    run_id       BIGINT NOT NULL REFERENCES backtest_runs (id),
    filter_name  TEXT NOT NULL,
    horizon_days INTEGER NOT NULL,
    n_events     INTEGER NOT NULL CHECK (n_events >= 0),
    mean_car     NUMERIC,
    median_car   NUMERIC,
    t_stat       NUMERIC,
    hit_rate     NUMERIC,
    sharpe       NUMERIC,
    ci_low       NUMERIC,
    ci_high      NUMERIC,
    q_value      NUMERIC,
    by_year      JSONB,
    PRIMARY KEY (run_id, filter_name, horizon_days)
);

CREATE TABLE model_weights (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fitted_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    weights     JSONB NOT NULL,
    oos_metrics JSONB,
    is_active   BOOLEAN NOT NULL DEFAULT false
);

-- At most one active weight set at a time — the scoring engine (§5.2)
-- reads "the active model_weights row" as a single, unambiguous source.
CREATE UNIQUE INDEX idx_model_weights_single_active
    ON model_weights ((is_active)) WHERE is_active;
