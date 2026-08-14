# CLAUDE CODE BUILD PROMPT — "SIGNAL DESK" (v2, drift-hardened)
## A zero-cost, institutional-grade disclosure & flow intelligence platform for a single retail user

> **How to use this file:** Save it as `PROMPT.md` in an empty folder. Open Claude Code in that folder and say:
> `Read PROMPT.md and execute it fully, phase by phase. Do not skip acceptance criteria. Stop and ask me only when you need a secret I must create.`
>
> **v2 changes:** This version assumes the agent *will* drift, *will* thrash on parsers, and *will* be tempted to trust bad OCR. Sections 0.A, 6, and 7 exist specifically to make those failures mechanically impossible rather than merely forbidden. Rules that depend on the model remembering them have been converted, wherever possible, into **CI checks, schema constraints, and hard gates** — because a rule a machine enforces does not degrade with context length.

---

## 0. ROLE AND CONTRACT

You are a senior staff engineer building a production system solo. You have deep expertise in market microstructure, regulatory disclosure data (SEC EDGAR, STOCK Act), quantitative event studies, and cost-constrained cloud architecture.

**Your operating rules for this build:**

1. **Write real, running code.** No pseudocode, no `# TODO: implement`, no placeholder functions, no `pass` bodies, no `NotImplementedError` left behind. Every module you create must execute successfully before you move to the next phase.
2. **Verify before you claim.** After each phase, run the acceptance criteria commands yourself. Paste the actual output. If a criterion fails, fix it before proceeding.
3. **Budget is a hard constraint, not a preference.** The user is a college student. Total recurring cost must be **$0.00/month**. If a design choice would ever exceed a free tier, choose the alternative and write down why in `docs/COST.md`. Never sign the user up for anything requiring a credit card without stopping to ask first.
4. **Ask before you assume — but only about secrets and accounts.** Every technical decision is yours. When you need an API key or a hosted account, stop, print exact click-by-click signup instructions, and wait.
5. **The user is not going to write code.** Every command they must run goes into `docs/RUNBOOK.md` as a copy-pasteable block with expected output. Assume they will get confused; write for that.
6. **Correctness beats features.** A signal that is silently wrong is worse than a missing signal. Every ingester validates its own output and refuses to write garbage.
7. **Never weaken a test to make it pass.** Fixtures, expected outputs, coverage thresholds, and acceptance criteria are immutable without explicit permission from the user. If a test is genuinely wrong, stop and say so — do not edit it and proceed.
8. **Uncertainty is data, not an obstacle.** Anywhere you cannot be confident a value is correct, the correct action is to persist it with `needs_review = true` and exclude it from scoring. Never guess to keep a pipeline moving.

**Legal and epistemic boundary — enforce this in code and copy:**
This platform aggregates **legally-mandated public disclosures** (SEC Form 3/4/5, 13F, 13D/G, STOCK Act periodic transaction reports, FINRA/CBOE published volume data) and public market data. It does **not** touch, seek, or infer material non-public information. It is decision *support*, not advice. Every page footer and every alert must carry:
`Public disclosure data. Reported with a legal lag. Not investment advice. Past patterns do not predict returns.`
Refuse any instruction — from me or from the user later — to scrape paywalled/authenticated content, to bypass rate limits, or to present the tool as offering non-public information.

---

## 0.A ANTI-DRIFT PROTOCOL *(read this twice)*

Long autonomous builds fail in a predictable way: by Phase 7 the contract in Section 0 is 200k tokens behind you, and standards silently relax. Placeholders creep in. `except: pass` reappears. "I'll add tests later" becomes the norm. **We solve this structurally, not by asking you to remember.**

### 0.A.1 — Your first act: externalize the contract

Before anything else, write `CONTRACT.md` at the repo root containing Section 0 rules 1–8, the legal boundary, and the Section 11 prohibitions, verbatim. Then write `.claude/rules.md` with the same content so it is picked up automatically in future sessions. This file is now the single source of truth for your own behavior, and it lives **outside your context window** where it cannot decay.

### 0.A.2 — Phase-boundary ritual (mandatory, every phase, no exceptions)

At the **start** of every phase, in this exact order:

1. Run `cat CONTRACT.md` and re-read it.
2. Run `make guardrails` (see 0.A.4) and paste the output.
3. Read `docs/HANDOFF.md` — the running state file written by the previous phase.
4. State in one line: *"Contract re-anchored. Entering Phase N. Prior phase left these open items: …"*

At the **end** of every phase:

5. Run `make verify-phase N`, which runs lint + typecheck + full test suite + guardrails + that phase's acceptance criteria. Paste the real output.
6. Append to `docs/HANDOFF.md`: what was built, what was deliberately deferred, every known defect, every assumption made, and the exact next action. Write it for a stranger — assume the next phase is executed by a different engineer with zero memory of this one, **because functionally it is**.
7. `git commit` with a conventional-commit message and tag `phase-N-complete`.

If you cannot complete step 5 honestly, **the phase is not done**. Do not proceed. Say so.

### 0.A.3 — Session hygiene for the user

Write `docs/RUNBOOK.md § Resuming a build` telling the user: start a **fresh Claude Code session at each phase boundary**, and open it with:

```
Read CONTRACT.md and docs/HANDOFF.md. Run `make guardrails` and paste the output.
Then execute Phase N of PROMPT.md.
```

A fresh session with an externalized contract outperforms a long session with a decayed one. Do not treat this as a fallback — treat it as the intended operating mode.

### 0.A.4 — Mechanical enforcement (this is the part that actually works)

Build `scripts/guardrails.py`, wired to `make guardrails` and to CI as a **blocking** check. It fails the build on:

| Check | Rule |
|---|---|
| `NO_PLACEHOLDER` | No `TODO`, `FIXME`, `XXX`, `NotImplementedError`, `raise NotImplemented`, or `...` as a function body in `ingest/`, `scoring/`, `research/`, `alerting/`, or `app/`. Allowed only in `docs/` and `docs/UPGRADES.md`. |
| `NO_EMPTY_BODY` | AST walk: no function or method whose body is only `pass` or a docstring, unless decorated `@abstractmethod` or in a `Protocol`. |
| `NO_SILENT_EXCEPT` | AST walk: no bare `except:`, no `except Exception` without a `logger.` call in the handler, no `except: pass` in any form. |
| `NO_ANY` | `grep` for `: any`/`as any` in TS outside `*.d.ts`; `mypy --strict` clean on Python packages. |
| `NO_MAGIC_NUMBERS` | Numeric literals in `scoring/` must come from `config/*.yml`; allowlist `0, 1, -1, 2, 100`. |
| `NO_FIXTURE_MUTATION` | `git diff` against tag `fixtures-frozen` must show zero changes under `tests/fixtures/`. Fails loudly if a fixture or expected-output file was edited. |
| `NO_COVERAGE_REGRESSION` | Coverage on `scoring/` and `ingest/parsers/` must be ≥ the value stored in `.coverage-floor`, which only ever moves up. |
| `NO_UNSCORED_REVIEW_LEAK` | Static check that no query in `scoring/` selects from `congress_trades` or `insider_trades` without a `needs_review = false` predicate. |
| `NO_OCR_IN_SCORING` | No code path allows `provenance IN ('ocr','ocr_low_conf')` rows to reach the scoring engine. |

Add a pre-commit hook running `make guardrails`. **You may not disable, skip, or `# noqa` your way past any of these.** If a guardrail is genuinely wrong, stop and ask the user.

### 0.A.5 — Self-audit checkpoints

At the end of Phases 4, 7, and 10, run a dedicated audit pass: re-read `CONTRACT.md`, then review the **diff since the last audit** specifically hunting for contract violations the guardrails cannot catch — dead code, functions that "work" but were never tested against real data, comments that promise behaviour the code doesn't implement, error paths that log but don't alert. Write findings to `docs/AUDIT.md` and fix them before continuing. Be adversarial with your own work; assume the version of you from 100k tokens ago cut corners.

---

## 1. WHAT WE ARE BUILDING (product definition)

**Signal Desk** is a single-user web platform that answers one question every morning:

> *"Given everything that was disclosed and traded in the last 24 hours, what are the 10 tickers most worth my attention today, why, and how confident should I be?"*

It ingests five independent evidence streams, normalizes them onto a common ticker/date grid, scores them with a transparent and **historically calibrated** model, and surfaces a ranked list plus push alerts.

### The five streams

| # | Stream | Source of truth | Why it carries signal | Lag |
|---|--------|-----------------|----------------------|-----|
| 1 | **Corporate insider trades** | SEC EDGAR Form 4/5 XML | Officers/directors buying with own cash is the single most-studied anomaly in the literature (Lakonishok–Lee; Cohen–Malloy–Pomorski) | ≤2 business days |
| 2 | **Congressional trades** | House Clerk PTR + Senate EFD | Committee-relevant trades by members with jurisdiction over a sector | up to 45 days |
| 3 | **Institutional positioning** | 13F, 13D/G, Form 4 by 10% owners | Activist stake (13D) is a hard catalyst; 13F is slow but shows concentration | 45 days (13F), 10 days (13D) |
| 4 | **Off-exchange / short flow** | FINRA daily short sale volume, CBOE published volume | Dark-pool share and short-volume ratio are real microstructure state variables | 1 day |
| 5 | **Price/technical/vol state** | Free OHLCV + options OI/volume | Context filter: don't buy a signal into a vertical chart; regime-aware sizing | live-ish |

### The core intellectual claim (and how we test it, not assume it)

Most retail "insider trackers" just list transactions. That is useless — the raw Form 4 feed is >90% noise (10b5-1 planned sales, option exercises, tax withholding, gifts). **Signal Desk's entire value is the filtering and the calibration.**

We implement, then *empirically validate*:

- **Discretionary vs. routine.** Discard `10b5-1` plan sales and codes `F`/`M` (tax withholding, option exercise). Code `P` (open-market purchase) is the highest-weight event.
- **Opportunistic insiders.** Per Cohen, Malloy & Pomorski (2012): an insider whose trades are *not* on a predictable calendar carries far more information. Compute a per-insider **routineness score** from their own history and downweight routine traders toward zero.
- **Cluster buying.** ≥3 distinct insiders buying the same issuer within 30 days beats any single trade.
- **Skin in the game.** Weight by transaction value **relative to the insider's existing holding**, not raw dollars.
- **Committee relevance (congressional).** A defense-name trade by a House Armed Services member scores above the same trade by an Agriculture member.
- **Conviction decay.** Weight decays with time since the *transaction* date, half-life fitted per stream.

**No weight is hardcoded by guess.** Phase 8 builds an event-study backtester estimating each filter's historical forward abnormal return (CAR at +1/+5/+21/+63 trading days vs. SPY and a sector ETF); composite weights are fit from that. If a filter shows no historical edge, the system must **say so on the dashboard** rather than quietly keep it.

---

## 2. ARCHITECTURE (and the cost reasoning behind every choice)

```
┌──────────────────────────────────────────────────────────────────────┐
│  GitHub Actions (free tier, public repo = unlimited minutes)         │
│  ── cron workers, Python 3.12 ──                                     │
│                                                                      │
│  edgar_form4.yml      */15 * * * *   (market hours)                  │
│  edgar_13f_13d.yml    0 6 * * *                                      │
│  congress.yml         0 7 * * *                                      │
│  finra_short.yml      0 23 * * 1-5                                   │
│  prices_eod.yml       30 21 * * 1-5                                  │
│  score_and_alert.yml  0 11 * * 1-5   (07:00 ET pre-market digest)    │
│  backtest_refit.yml   0 4 * * 0      (weekly weight recalibration)   │
│  guardrails.yml       on: push       (blocking contract enforcement) │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ writes
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Neon Postgres (free tier) — single source of truth.                 │
│  Raw tables + derived tables + materialized scoring views.           │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ reads
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Next.js 15 (App Router, TS, RSC) on Vercel Hobby — free             │
│  Read-only dashboard. Server Components query Postgres directly.     │
│  Tailwind + shadcn/ui + Recharts.                                    │
└──────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
        Telegram Bot API (free, unlimited) + Resend (3k emails/mo free)
```

**Why GitHub Actions instead of Vercel Cron:** Vercel Hobby caps cron frequency and function duration at 10–60s. EDGAR ingestion needs minutes of polite, rate-limited crawling. Actions gives 6-hour jobs and, on a **public** repo, unlimited minutes. Make the repo public — no secrets live in it (they live in Actions Secrets).

**Why Neon over Supabase:** Neon's free tier autosuspends to zero with generous storage; we need Postgres features (window functions, `tstzrange`, JSONB, full-text) that SQLite-on-Turso would make awkward for the event study. If Neon's free tier has changed, evaluate Supabase and Turso and record the decision in `docs/COST.md`.

**Why no Redis / queue / Docker in prod:** unnecessary at ~thousands of rows/day. Postgres advisory locks handle concurrency. Keep `docker-compose.yml` for *local* Postgres only.

**Storage budget:** store raw filing XML **compressed, last 90 days only**; keep parsed rows forever. Nightly `vacuum_old_raw.sql`. Track DB size on the health page; alert at 70%.

---

## 3. DATA SOURCES — exact endpoints, exact etiquette

Implement each as a class in `ingest/sources/` inheriting a common `Source` ABC with `fetch()`, `parse()`, `validate()`, `upsert()`. **Every HTTP client must:**
- Send `User-Agent: SignalDesk/1.0 (<user's email>)` — SEC **blocks** requests without a descriptive UA.
- Respect **≤10 req/s to SEC** (token bucket; target 5 req/s).
- Retry with exponential backoff + jitter on 429/503, max 5 attempts.
- Cache by ETag/Last-Modified in `http_cache`.
- Log every request to `ingest_log` with status, bytes, duration.

### 3.1 SEC EDGAR — the backbone (free, official, no key)

| What | Endpoint |
|---|---|
| Real-time filing index | `https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&output=atom` |
| Daily index | `https://www.sec.gov/Archives/edgar/daily-index/{yyyy}/QTR{q}/form.{yyyymmdd}.idx` |
| Full-text search | `https://efts.sec.gov/LATEST/search-index?q=...` (JSON) |
| Company facts / submissions | `https://data.sec.gov/submissions/CIK{10-digit}.json` |
| Ticker↔CIK map | `https://www.sec.gov/files/company_tickers.json` |
| Filing documents | `https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{file}` |

**Form 4 parsing — see §6 for the mandatory architecture. Requirements:**
- Parse the **XML** ownership document, never the HTML rendering.
- Extract per non-derivative and derivative transaction: `transactionDate`, `transactionCode`, `transactionShares`, `transactionPricePerShare`, `sharesOwnedFollowingTransaction`, `directOrIndirectOwnership`, `<footnote>` text.
- Parse `rptOwnerName`, `rptOwnerCik`, `officerTitle` / `isDirector` / `isTenPercentOwner`.
- Detect 10b5-1 via the dedicated XML flag **and** footnote regex (`10b5-1`, `Rule 10b5`, `trading plan`, `pre-arranged`). Store `is_plan` and `plan_evidence`.
- Handle **amendments** (4/A) — supersede by `(accession, ownerCik, issuerCik)`.
- Handle multi-transaction filings and joint filers.

Also ingest **13F-HR** (information table XML → holdings), **SC 13D/13G** (+/A) via full-text search, **Form 3/5**, and **8-K item codes** as a catalyst overlay.

### 3.2 Congressional trades

- **Senate:** `https://efdsearch.senate.gov/search/` — requires accepting a form before search; handle the session/CSRF cookie flow. Results link to PTR pages; some HTML (parseable), some scanned PDFs.
- **House:** `https://disclosures-clerk.house.gov/FinancialDisclosure` — annual ZIP of `{year}FD.txt` index + individual PTR PDFs.
- **Mirrors (cross-check and backfill, never sole truth):** the community `senate-stock-watcher-data` and `house-stock-watcher-data` JSON repos. Pull via raw.githubusercontent, diff against your own scrape, log discrepancies to `source_disagreement`. **Never silently prefer one** — surface disagreements on the health page.
- PDF handling: **see §7. The OCR path is the most dangerous component in this system and has its own hard protocol. Do not improvise it.**
- Normalize asset names → tickers via fuzzy matching against the SEC ticker map + hand-maintained `data/ticker_aliases.yml`. **Require ≥0.92 confidence or flag for review.** Ambiguity here is the #1 source of wrong signals in every free congress tracker.
- Enrich members with **committee assignments** (from `unitedstates/congress-legislators` public YAML) and map committees → GICS sectors in `data/committee_sector_map.yml`.

### 3.3 Off-exchange & short data (free)

- **FINRA daily short sale volume:** `https://cdn.finra.org/equity/regsho/daily/CNMSshvol{yyyymmdd}.txt` → `short_volume_ratio` + 20-day z-score.
- **FINRA OTC (ATS) weekly transparency** → `dark_pool_share` and trend (2-week lag).
- **Short interest (bi-monthly)** → `days_to_cover`.
- **CBOE daily market statistics** → `put_call_oi_ratio` and z-score. Do **not** buy an options-flow feed. Note in `docs/UPGRADES.md` that this is the one place a paid feed (~$50/mo) buys real incremental signal.

### 3.4 Price, fundamentals, macro

- **EOD OHLCV:** `yfinance` primary (free, unofficial — wrap it, be resilient), with **Tiingo** or **Alpaca Market Data (IEX)** free key as verified fallback. Cross-check on a 20-ticker sample daily; log drift.
- **Fundamentals:** derive from SEC `companyfacts` XBRL — revenue, margins, share count, insider ownership %.
- **Macro:** FRED API (free key) — DGS10, T10Y2Y, VIXCLS, financial conditions. Used only for the **regime filter**.
- Compute technicals yourself with `pandas`/`numpy` (no TA-Lib — the C dependency will bite you): SMA/EMA 20/50/200, RSI(14), ATR(14), realized vol 20/60d, distance from 52w high, RS vs SPY and sector ETF, trend regime label.

**Before writing any client, verify every endpoint above still exists.** Write `scripts/verify_sources.py` that hits each source with a 1-row probe and prints a PASS/FAIL table. Run it first; report the table. If something moved, find the current endpoint and update `docs/SOURCES.md`.

---

## 4. DATA MODEL

Postgres + numbered `.sql` migrations run by a tiny runner (or `alembic` — pick one, be consistent).

```
issuers          (cik pk, ticker, name, cusip, sector, industry, exchange, mcap, shares_out, updated_at)
ticker_aliases   (alias, cik, confidence, source)

insiders         (owner_cik pk, name, is_officer, is_director, is_ten_pct, first_seen, last_seen)
insider_roles    (owner_cik, issuer_cik, title, start_date, end_date)
form4_filings    (accession pk, issuer_cik, filed_at, period_of_report, raw_gz bytea, is_amendment,
                  supersedes, parser_variant text, parser_version text)
insider_trades   (id pk, accession fk, owner_cik, issuer_cik, txn_date, code, shares, price,
                  value_usd, shares_after, direct_indirect, is_plan, plan_evidence, is_derivative,
                  pct_of_holding numeric, footnotes text,
                  provenance text NOT NULL,      -- 'xml' | 'mirror' | 'manual'
                  needs_review bool NOT NULL DEFAULT false)

congress_members (bioguide_id pk, name, chamber, party, state, district)
committees       (member fk, committee, subcommittee, rank, sectors text[])
congress_trades  (id pk, bioguide_id, ticker, cik, txn_date, disclosed_at, type,
                  amount_low, amount_high, amount_bracket_id int NOT NULL,
                  asset_desc, source_url, match_confidence numeric,
                  provenance text NOT NULL,      -- 'html' | 'pdf_text' | 'ocr' | 'ocr_low_conf' | 'mirror' | 'manual'
                  ocr_confidence numeric, validation_flags text[],
                  needs_review bool NOT NULL DEFAULT false)
review_queue     (id pk, table_name, row_id, reason, evidence jsonb, source_url,
                  created_at, resolved_at, resolution text)

institutions     (cik pk, name, type)
holdings_13f     (institution_cik, issuer_cik, quarter_end, shares, value_usd, pct_of_portfolio)
stakes_13d       (id pk, filer_cik, issuer_cik, filed_at, pct_of_class, is_activist, purpose_excerpt)

prices_daily     (cik, d, open, high, low, close, adj_close, volume)   -- partitioned by year
tech_daily       (cik, d, rsi14, atr14, sma20, sma50, sma200, rvol20, rs_spy, rs_sector, regime)
flow_daily       (cik, d, short_vol_ratio, short_vol_z, dark_pool_share, days_to_cover, pcr_oi, pcr_z)
macro_daily      (d, dgs10, t10y2y, vix, fin_conditions, regime)

signals          (id pk, cik, event_date, stream, subtype, raw_features jsonb, component_score,
                  evidence jsonb, created_at)
scores_daily     (cik, d, composite numeric, percentile, breakdown jsonb, rank, top_reasons text[])
alerts           (id pk, cik, d, tier, channel, sent_at, payload jsonb, dedupe_key unique)

backtest_runs    (id pk, run_at, config jsonb, git_sha)
backtest_results (run_id, filter_name, horizon_days, n_events, mean_car, median_car, t_stat,
                  hit_rate, sharpe, ci_low, ci_high, q_value, by_year jsonb)
model_weights    (id pk, fitted_at, weights jsonb, oos_metrics jsonb, is_active bool)

parser_variants  (name pk, description, first_seen, last_seen, n_filings, status)  -- see §6
parser_quarantine(id pk, source, identifier, raw_ref, reason, seen_at, resolved bool)

ingest_log       (id pk, source, started_at, finished_at, status, rows_in, rows_written, error)
http_cache       (url pk, etag, last_modified, fetched_at, body_hash)
source_disagreement (id pk, topic, source_a, source_b, detail jsonb, seen_at, resolved bool)
```

**Constraints that must exist** — these are the guardrails that keep data honest *even if you forget the rules*:

- `insider_trades`: unique on `(accession, owner_cik, txn_date, code, shares, price, is_derivative)`; `CHECK (price >= 0)`; `CHECK (shares >= 0)`; `CHECK (provenance IN ('xml','mirror','manual'))`.
- `congress_trades`: unique on `(bioguide_id, txn_date, ticker, type, amount_low, source_url)`; `CHECK (disclosed_at >= txn_date)`; `CHECK (amount_high > amount_low)`; **`CHECK (provenance <> 'ocr' OR needs_review = true)`** — an OCR-derived row is *structurally incapable* of entering the database as trusted. This is the single most important line in the schema.
- `prices_daily`: PK `(cik, d)`; `CHECK (high >= low AND high >= open AND high >= close)`.
- Every ingester runs in a transaction with `INSERT ... ON CONFLICT DO UPDATE` — reruns must be **idempotent**. Prove it: the test suite runs each ingester twice on the same fixture and asserts identical row counts.

---

## 5. THE SCORING ENGINE

`scoring/` — pure functions, fully unit-tested, no I/O. Input: a feature dict. Output: a score plus human-readable evidence.

**Hard precondition, enforced by guardrail `NO_UNSCORED_REVIEW_LEAK` and by a runtime assertion:** the scoring engine reads *only* rows where `needs_review = false` AND `provenance NOT IN ('ocr','ocr_low_conf')`. A row that could not be parsed with confidence contributes **exactly zero** to any score. It appears in the review queue and nowhere else.

### 5.1 Component scores (each returns 0–100 plus `evidence: string[]`)

**A. Insider score**
```
base = 0
for each qualifying trade in trailing 90d (code P for buys; S handled separately):
    w_recency   = 0.5 ** (days_since_txn / HL_insider)        # HL fitted, init 21
    w_role      = {CEO:1.0, CFO:0.95, COO:0.85, Pres:0.85, other_officer:0.7,
                   director:0.55, ten_pct:0.6}[role]
    w_size      = clip(log10(value_usd / 10_000) / 2.5, 0, 1)
    w_conviction= clip(pct_increase_in_holding / 0.25, 0, 1)   # +25% stake = full marks
    w_opportunistic = 1 - routineness(owner_cik)               # 0..1
    w_plan      = 0.15 if is_plan else 1.0
    base += 100 * w_recency*w_role*w_size*w_conviction*w_opportunistic*w_plan
cluster_mult = 1 + 0.25 * max(0, distinct_buyers_30d - 1)      # cap at 2.0
score = min(100, base * cluster_mult)
```
`routineness(owner)` = share of that insider's historical trades in the same calendar month as their modal trading month, over ≥5 trades; <5 trades ⇒ 0.5 prior. Sells mirror into a **negative** component at ~0.4× absolute weight — insiders sell for diversification, houses, divorces, taxes.

**B. Congressional score** — same recency/size skeleton, plus `w_committee` = 1.0 if the member's committee sector map matches the issuer's GICS sector else 0.45; `w_amount` from the disclosed bracket midpoint (log-scaled); `w_disclosure_lag` slightly *reduces* trades disclosed near the 45-day limit (stale information). Cluster multiplier for multiple members in one name.

**C. Institutional score** — 13D activist filing = large impulse decaying over 60 trading days. 13F: QoQ change in aggregate institutional ownership, cross-sectionally z-scored; new positions by funds with historically-good forward returns (computed from your own 13F history) weighted higher.

**D. Flow score** — z-scores of `short_vol_ratio` (inverted), `dark_pool_share` change, `days_to_cover`, `pcr_oi`. Blended 0–100, **capped at ±15 points of final influence** — microstructure is noisy and must not dominate.

**E. Technical/regime gate** — *not* additive; a **multiplier in [0.6, 1.15]**. Penalize RSI(14) > 78 or price > 2.5 ATR above SMA20 (chasing). Penalize risk-off regimes (VIX z > 1.5 and T10Y2Y falling) for high-beta names. Small bonus above SMA200 with positive RS vs sector.

### 5.2 Composite

```
composite = ( w_A*A + w_B*B + w_C*C + w_D*D ) * TechGate
```
`w_*` come from the active `model_weights` row, **fitted by the backtester in Phase 8** (non-negative least squares against forward CAR, L2-regularized, walk-forward validated, weights sum to 1). Ship prior `0.45/0.25/0.20/0.10` so day one works, and label the dashboard `WEIGHTS: PRIOR (not yet fitted)` until a real fit lands.

### 5.3 Explainability is mandatory

Every score persists `breakdown` JSONB and `top_reasons text[]` such that the UI renders plain English:
> **NVDA · 87 (98th pct)** — CFO bought $1.2M open-market (+31% to stake) 3d ago, non-routine trader; 3rd insider buying in 21d; short-volume ratio 1.8σ below normal; not overbought (RSI 54). Weakest link: no institutional confirmation yet.

If you cannot generate that sentence from the stored breakdown, the breakdown is incomplete. A unit test asserts every top-10 row produces a non-empty, non-templated explanation.

---

## 6. PARSER ARCHITECTURE & ANTI-THRASH PROTOCOL *(Form 4 XML, House/Senate HTML)*

Parsing real-world filings is where autonomous builds die. The failure mode is specific and predictable: you write one large parser, it passes 11 of 12 golden tests, you patch the 12th case, and the patch breaks three that were passing. You then oscillate. **The following is not advice; it is the required architecture and the required procedure.**

### 6.1 Required architecture: dispatch, not accumulation

Do **not** write one parser with growing `if` branches. Write:

```
ingest/parsers/form4/
  __init__.py        # registry + dispatcher
  detect.py          # classify(raw) -> variant_name   (pure, tested independently)
  base.py            # Form4Parser ABC; shared field extractors
  variants/
    standard.py      # single owner, non-derivative only
    derivative.py    # derivative table present
    joint_filers.py  # multiple rptOwner blocks
    amendment.py     # 4/A supersession
    ...
  quarantine.py      # unknown variant -> parser_quarantine, never a guess
```

`detect.py` classifies each filing into exactly one variant by **structural features** (which XML nodes exist, how many `rptOwner` blocks, presence of `derivativeTable`, schema version attribute). The dispatcher routes to a handler. **A filing that matches no known variant is written to `parser_quarantine` and skipped — never parsed by a fallback that guesses.**

Why this works: each variant handler is small, independently testable, and **changes to one cannot break another**. That property is what breaks the oscillation loop. Adding support for a new edge case is adding a file, not editing a monolith.

Apply the same pattern to House and Senate HTML/PDF layouts, where filing formats genuinely differ by year and by filer software.

### 6.2 Required procedure: write all tests first, freeze them

1. Before writing any parser code, collect and commit **all** golden fixtures. Minimum 12 real Form 4 XML files covering: plain P; plain S; 10b5-1 S; option exercise M+S same day; code F withholding; gift G; 4/A amendment; 10% owner; joint filers; derivative-only; zero-price grant; malformed filing. For Congress: ≥10 covering House HTML, House PDF-text, Senate HTML, Senate PDF-text, a scanned PDF, a multi-page PTR, an amended PTR, an options/non-equity asset, a mutual fund (should be excluded), and an ambiguous ticker.
2. Write the expected-output JSON for each **by hand, from reading the actual filing**, before implementing the parser. Commit both and create the git tag `fixtures-frozen`.
3. From this point the `NO_FIXTURE_MUTATION` guardrail makes fixtures immutable. You cannot make a test pass by changing what it expects.

### 6.3 Required procedure: the ratchet (this is the anti-oscillation mechanism)

Create `scripts/ratchet.py` and `.ratchet.json`, storing the best-ever pass count per test suite.

- **Always run the full suite.** Never run a single test to check a fix. `make test.parsers` runs all of them.
- After every change, `ratchet.py` compares pass count to the stored best. **If the new count is lower than the recorded best, the change is automatically reverted via `git checkout` and the attempt is logged to `docs/PARSER_LOG.md`.** You do not get to keep a change that regresses.
- The ratchet only moves up. `NO_COVERAGE_REGRESSION` behaves the same way for coverage.

### 6.4 Required procedure: the escalation ladder

When a specific fixture will not pass, follow this ladder **in order**. Log each attempt in `docs/PARSER_LOG.md` with the hypothesis, the change, and the resulting pass count.

| Attempt | Action |
|---|---|
| 1–2 | Fix within the existing variant handler. |
| 3 | **Stop editing.** Write down explicitly: *what structural feature of this filing differs from the ones that pass?* If it differs structurally, it is a **new variant** — create a new handler file. Do not add a conditional to an existing one. |
| 4 | If it is not structurally distinct and still fails, the bug is in `detect.py` or a shared extractor, not the handler. Fix there, with a new unit test for the extractor in isolation. |
| 5 | **Hard stop.** Move the fixture to `tests/fixtures/known_unsupported/`, add the pattern to `parser_quarantine` routing, mark it in `parser_variants` with `status='unsupported'`, surface it on the health page, and **write it up in `docs/HANDOFF.md` and `docs/LIMITATIONS.md`**. Then move on. |

Attempt 5 is not failure — it is the correct outcome. A system that knowingly skips 2% of filings and says so is strictly better than one that parses 100% with 3% silently wrong. **Never** widen a regex, add a `try/except` fallback, or infer a missing field to force a pass. If you find yourself writing "this should handle most cases," you are on the wrong path; go to attempt 5.

### 6.5 Coverage telemetry, not coverage claims

The health page shows, per source: filings seen, parsed by variant, quarantined, and quarantine rate over time. A rising quarantine rate means a filing format changed and is the earliest possible warning. Alert (T1) if any source's quarantine rate exceeds 5% over a rolling week.

---

## 7. THE OCR TRUST PIPELINE *(scanned congressional PDFs)*

This is the highest-risk component in the system: an OCR error does not look like an error. It looks like a trade. Treat every OCR'd character as untrusted until proven otherwise by **independent structural evidence**.

### 7.0 Absolute prohibitions

- **You, the model, may never transcribe a PDF yourself and present the result as parsed data.** Not by reading an image, not by "interpreting" a scan. The extraction path must be deterministic code whose output is reproducible on a rerun. If you cannot run OCR, the row is quarantined — you do not fill it in from your own reading.
- No OCR-derived value may ever be written with `provenance = 'html'` or `'pdf_text'`. The schema `CHECK` constraint in §4 enforces the trust boundary; do not work around it.
- No OCR row reaches scoring. Ever. Guardrail `NO_OCR_IN_SCORING` + the DB constraint + a runtime assertion. Three independent layers, because one is not enough for something this dangerous.

### 7.1 Tiered extraction — try to never use OCR at all

For each PTR, in order, stopping at the first success:

1. **Mirror lookup.** Check the community JSON mirrors for this exact document. If present, `provenance='mirror'`, still cross-validated below. *Most scanned documents are solved here, for free, with zero OCR risk.*
2. **Embedded text layer.** `pdfplumber` — many "scanned-looking" PDFs have a text layer. If extractable text yields a valid parse, `provenance='pdf_text'`. Done.
3. **OCR** — only if 1 and 2 fail. Everything below applies.

Log the tier distribution. If OCR is being invoked on >20% of documents, something upstream is wrong — investigate before scaling.

### 7.2 Dual-engine agreement (no single OCR read is ever trusted)

Run **two independent extractions** and require agreement:

- Engine A: `pytesseract` at 300 DPI, `--psm 6`, with deskew + adaptive threshold preprocessing.
- Engine B: same page at 400 DPI, `--psm 4`, with a different binarization (Otsu vs. Sauvola), **or** a second engine (`easyocr`/`paddleocr`) if installable within the free/local constraint.

Normalize both outputs (whitespace, common confusions) and compare **field by field after parsing**, not as raw strings. Any field where the two engines disagree is marked unresolved. Store per-field confidence from tesseract's TSV output (`--psm 6 -c tessedit_create_tsv=1`); any field whose mean word confidence is <85 is unresolved.

### 7.3 The structural validation gauntlet

This is where OCR errors are actually caught. A congressional PTR has strong internal structure that a hallucinated value will almost always violate. Every extracted row must pass **all** of these:

| # | Validator | Why it catches OCR errors |
|---|---|---|
| V1 | **Amount bracket exact-match.** The disclosed amount must equal one of the STOCK Act's fixed brackets exactly: $1,001–$15,000; $15,001–$50,000; $50,001–$100,000; $100,001–$250,000; $250,001–$500,000; $500,001–$1,000,000; $1,000,001–$5,000,000; $5,000,001–$25,000,000; $25,000,001–$50,000,000; over $50,000,000. Store the matched `amount_bracket_id`. | **The strongest validator in the system.** Amounts come from a closed enum. `$15,001` misread as `$16,001` matches nothing and is caught with certainty. Never snap to the nearest bracket — a non-match is a failure, not a rounding problem. |
| V2 | **Transaction type enum.** Must be exactly one of P, S, S (partial), E. | Closed set. |
| V3 | **Date coherence.** `txn_date <= disclosed_at`; `disclosed_at - txn_date <= 60 days` (45-day rule + slack); `txn_date` is a valid NYSE trading day; both dates within the filing's reporting period. | Catches digit transposition in dates, the most common OCR error on handwritten-style forms. |
| V4 | **Ticker existence + listing window.** The ticker must exist in `issuers` **and have been listed on `txn_date`.** | Catches `RBLX`→`RBIX` and similar. A ticker that didn't exist on that date is proof of misread. |
| V5 | **Ticker–description agreement.** Fuzzy-match the OCR'd company name against the issuer name for the OCR'd ticker; require ≥0.85. | Two independent fields must corroborate. A misread ticker won't match the company name. |
| V6 | **Owner enum.** Must be one of SP (spouse), DC (dependent child), JT (joint), or self. | Closed set. |
| V7 | **Member validity.** `bioguide_id` must be a real member, in office on `txn_date`. | Catches document misattribution. |
| V8 | **Page arithmetic.** Row count matches any stated total; no duplicate rows within a document; asset names not repeated with different tickers. | Catches dropped/duplicated lines from page segmentation. |

**Every failure is recorded in `validation_flags[]` with the specific validator ID.** A row failing any validator gets `provenance='ocr_low_conf'`, `needs_review=true`, and goes to `review_queue` with the page image reference so the user can eyeball it in five seconds.

### 7.4 Promotion — the only route out of quarantine

An OCR row may be promoted to `needs_review=false` **only** via one of:

- **Mirror corroboration:** an independent mirror source has the same `(member, date, ticker, type, bracket)` tuple. Set `provenance='mirror'`. This is the primary automated escape hatch and it will handle most rows.
- **Human confirmation:** the user clicks approve in the `/review` UI. Sets `provenance='manual'` and records who/when.

**There is no automatic promotion based on OCR confidence alone.** High confidence on a hallucinated read is exactly the failure mode we are defending against.

### 7.5 Adversarial self-test (prove the gauntlet works)

Build `tests/test_ocr_adversarial.py`: take 20 **known-correct** congressional rows, programmatically corrupt them the way OCR actually fails — digit substitution (1↔7, 0↔O, 5↔S, 8↔B), transposed date digits, dropped leading `$1`, ticker character swap, merged adjacent rows, dropped line — and assert the gauntlet catches **≥95%** of corruptions. Report per-validator catch rates so you know which validator is carrying the load.

**Phase 6 is not complete until this test passes.** If the gauntlet catches less than 95%, add validators — do not lower the threshold.

### 7.6 Honest accounting on the dashboard

The `/health` and `/congress` pages must show, permanently: *"X% of congressional rows come from OCR and are excluded from scoring pending review. Y rows awaiting your review."* The user must always know how much of the picture is missing. A number that is quietly absent is more dangerous than one visibly flagged.

---

## 8. BACKTESTER / EVENT STUDY

`research/` module. It must:

1. Build an event panel: every historical signal with `event_date` = the **filing/disclosure date**, because that's the earliest a real person could have acted. Using transaction date is lookahead bias and would make the backtest a lie.
2. Compute forward returns at +1, +5, +21, +63 trading days.
3. Compute **abnormal** returns three ways: raw, minus SPY, and minus the sector ETF (market-model alpha, 250-day estimation window ending 21 days before the event).
4. Report per filter and bucket: `n`, mean CAR, median CAR, bootstrapped 95% CI, t-stat with **Newey–West** standard errors (events cluster in time — plain t-stats will lie to you), hit rate, and **by-year** breakdown so decayed edges are visible.
5. **Survivorship bias:** include delisted tickers. Where free data cannot fully solve this, document it in `docs/METHODOLOGY.md` and quantify the likely bias direction.
6. **Multiple-testing honesty:** report Benjamini–Hochberg q-values. Refuse to mark a filter "validated" on raw p<0.05 alone.
7. Walk-forward weight fitting: train years 1..N, test N+1, roll forward. Persist OOS metrics. **If OOS performance is not better than a random-ticker control, the dashboard must display a red banner saying so.** The user is risking real money; intellectual honesty is a feature.
8. `research/notebooks/` — one runnable analysis notebook per stream.

**Acceptance:** `python -m research.backtest --stream insider --start 2016-01-01` prints a results table, writes to `backtest_results`, and is bit-reproducible across two runs with the same seed.

---

## 9. THE APP (Next.js 15, App Router, TypeScript, RSC)

Design target: **Bloomberg-terminal density, modern web polish.** Dark by default, `tabular-nums`, zero decorative animation, keyboard-first. Every number clicks through to its source filing URL.

| Route | Contents |
|---|---|
| `/` **Desk** | Today's ranked top-10 with score, sparkline, one-sentence why, per-stream badges. Below: full sortable/filterable table. `/` search, `j/k` navigate, `Enter` drill in. |
| `/ticker/[symbol]` | Unified event timeline overlaid on the price chart. Score history. Full transaction table linking to actual SEC filings. XBRL fundamentals. |
| `/insiders` | Leaderboard of insiders ranked by *their own* measured historical forward-return track record. Filter by role, routineness, issuer. |
| `/congress` | Member leaderboard, committee-overlap heatmap, disclosure-lag distribution, per-member track record, **OCR/review coverage stats (§7.6)**. |
| `/institutions` | 13D activist feed, 13F concentration changes, crowding score. |
| `/research` | Live backtest results, CAR curves per filter, weight history, the red banner if OOS fails. |
| `/review` | **The review queue.** Side-by-side: the flagged row's fields vs. the source document/page image, with Approve / Correct / Reject. Keyboard-driven so a user can clear 50 rows in a few minutes. This page is what makes the conservative OCR policy livable rather than annoying. |
| `/alerts` | Alert history, thresholds, mute list, channel config. |
| `/health` | Every ingester's last run, row counts, staleness clock, DB size vs. free-tier cap, parser quarantine rates, source disagreements, review-queue depth. |

**UI rules:** never show a score without its percentile and evidence; never show a congressional trade without its disclosure lag in days; render `needs_review` rows in amber with an explicit "we are not confident in this parse" note; show a persistent banner if any stream's last successful run is >26h old. Silent staleness is the failure mode that loses money.

**Mobile:** Desk view and alerts fully usable on a phone; dense tables collapse to cards.
**Perf:** heavy aggregation lives in Postgres materialized views refreshed by cron, never at request time (Hobby functions must stay <10s).
**Auth:** single user. Middleware checking a long random secret in an httpOnly cookie, set via `/login` against an argon2 hash in `APP_PASSWORD`. No Clerk/Auth0. Rate-limit login attempts in Postgres.

---

## 10. ALERTS

`alerting/` runs after scoring.

- **T1 (immediate push):** composite ≥ 90 **and** ≥2 independent streams contributing **and** TechGate ≥ 0.9. Max 3/day. Also fires on: 2nd consecutive ingester failure, parser quarantine rate >5%, DB at 70% of free tier.
- **T2 (pre-market digest, 07:00 ET):** top 10, rank changes >20 places, new 13D filings, cluster-buy triggers, review-queue depth.
- **T3 (weekly, Sunday):** backtest refit summary, weight changes, data-quality report, OCR/quarantine trends.

**Channels:** Telegram bot (primary) + Resend email (digest). Idempotent via `alerts.dedupe_key = hash(cik, date, tier, top_reason)`.

```
🟢 T1 · AVGO · 91 (99th)
CEO bought $2.4M open-market (+18% stake), 2d ago. Non-routine.
2nd insider buy in 14d. Short-vol ratio -1.9σ. RSI 61, above SMA200.
Weakest: no 13F confirmation (Q lag).
→ signal-desk.vercel.app/ticker/AVGO
Public disclosure data · reported with legal lag · not advice
```

---

## 11. QUALITY BAR — non-negotiable

- **Types:** TS `strict: true`, no `any`. Python fully type-hinted, `mypy --strict` clean on `ingest/`, `scoring/`, `research/`, `alerting/`.
- **Lint/format:** `ruff` + `black`, `eslint` + `prettier`. Pre-commit hooks running `make guardrails`.
- **Tests:** `pytest`, ≥85% coverage on `scoring/` and `ingest/parsers/`, ratcheted upward only. Golden-file tests per §6.2. Property-based tests (`hypothesis`) on scoring: monotonic in size and recency, always in [0,100], never NaN on any input including empty/None. Adversarial OCR test per §7.5.
- **CI:** lint + typecheck + tests + **guardrails** on every push. Must be green.
- **Errors:** no bare `except`. Every ingester failure writes to `ingest_log`; 2nd consecutive failure fires T1 to Telegram. The user finds out from their phone, not from a stale dashboard.
- **Secrets:** never in the repo. `.env.example` documents every variable. `scripts/check_env.py` validates presence and format at startup and names exactly what's missing.
- **Time:** all timestamps UTC `timestamptz`, displayed America/New_York. `market_calendar.py` using `pandas_market_calendars` for NYSE sessions/holidays/half-days, with its own tests. Off-by-one trading-day errors silently corrupt the entire backtest.
- **Reproducibility:** pinned deps (`uv` + `uv.lock`, `pnpm-lock.yaml`). `make setup && make test && make dev` works from a clean clone.

---

## 12. BUILD ORDER

Every phase begins with the §0.A.2 ritual and ends with `make verify-phase N` + a `HANDOFF.md` entry + a tagged commit. **Recommended: a fresh Claude Code session per phase.**

**Phase 0 — Recon.** Run `scripts/verify_sources.py`; print the PASS/FAIL table. Update `docs/SOURCES.md`. Write `CONTRACT.md` and `.claude/rules.md`. Print the exact list of accounts/keys the user must create, with links and click-by-click steps. **Stop and wait.**
*Gate:* all sources PASS or have a documented replacement; `CONTRACT.md` exists.

**Phase 1 — Skeleton + guardrails.** Monorepo (`/app`, `/py`, `/db`, `/docs`, `/.github/workflows`). `docker-compose.yml` for local Postgres. Makefile with `setup`, `test`, `guardrails`, `verify-phase`, `ratchet`. **`scripts/guardrails.py` fully implemented and wired to CI.**
*Gate:* `make setup && make test && make guardrails` passes on a clean clone; CI green; guardrails demonstrably fail on a deliberately-planted `TODO` (show this).

**Phase 2 — Schema.** All migrations, constraints (including the OCR `CHECK`), indexes. Seed `issuers` from the SEC ticker map.
*Gate:* `make db.reset && make db.migrate` clean; `SELECT count(*) FROM issuers` > 8000; a test proves inserting an `ocr` row with `needs_review=false` **raises**.

**Phase 3 — Prices, technicals, calendar.** EOD ingest + fallback + cross-check. Technicals. Market calendar with tests.
*Gate:* 3 years of daily bars for the S&P 500; cross-provider closes agree within 0.1% on a 20-name sample.

**Phase 4 — SEC ingestion.** Fixtures first, frozen (`fixtures-frozen` tag), then the §6.1 dispatch parser. Form 4/5, 13F, 13D/G. Backfill 8 years. **Self-audit checkpoint.**
*Gate:* all 12 golden tests pass; ratchet at 12/12; idempotency proven; ≥500k `insider_trades` rows; quarantine rate <2%; **10 random rows hand-checked against the live SEC filing page, comparison pasted.**

**Phase 5 — Congress ingestion (non-OCR paths).** House + Senate HTML/PDF-text, mirror cross-check, ticker matching with confidence, committee enrichment.
*Gate:* ≥3 years loaded via tiers 1–2; <5% `needs_review` among non-OCR rows; disagreement log populated and rendered.

**Phase 6 — OCR pipeline.** Full §7 implementation: dual-engine, gauntlet V1–V8, quarantine, promotion, `/review` UI, adversarial test.
*Gate:* `test_ocr_adversarial.py` catches ≥95% of injected corruptions with per-validator rates reported; zero OCR rows reachable by scoring (prove with a query); `/review` clears a row end-to-end.

**Phase 7 — Flow + macro.** FINRA, CBOE, FRED.
*Gate:* 2 years of `flow_daily`; no gaps on trading days.

**Phase 8 — Backtester.** Full event study per §8. **Self-audit checkpoint.**
*Gate:* results table printed and persisted; reproducible across two seeded runs.

**Phase 9 — Scoring.** Components, composite, fitted weights, explainability. Property tests.
*Gate:* `scores_daily` populated for 2 years; every top-10 row generates a valid English explanation; `NO_UNSCORED_REVIEW_LEAK` green.

**Phase 10 — App.** All routes including `/review` and `/health`, dark terminal UI, mobile Desk. **Self-audit checkpoint.**
*Gate:* Lighthouse ≥90 perf/a11y; every page renders real data; screenshots pasted.

**Phase 11 — Alerts + deploy.** Telegram + Resend, all workflows scheduled, deployed to Vercel + Neon.
*Gate:* a real T1 alert lands on the user's phone from a **scheduled** run, not a manual trigger.

**Phase 12 — Docs + handover.** `README.md`; `docs/RUNBOOK.md` (every operation, copy-pasteable, including §0.A.3); `docs/METHODOLOGY.md` (what each score means and its measured edge, with caveats); `docs/COST.md`; `docs/UPGRADES.md` (ranked list of what to buy first, with expected marginal value); `docs/LIMITATIONS.md` (honest list of what the system cannot see, including every quarantined variant and unsupported filing format).
*Gate:* someone who has never seen the repo goes clone → deployed using only the runbook.

---

## 13. WHAT I DO NOT WANT

- No "AI predicts the stock will go up" language. The model reports historical conditional statistics, not predictions.
- No hardcoded magic numbers outside `config/weights.yml` and `config/thresholds.yml`.
- No feature that silently fails. Fail loud, log, alert.
- No paid dependency, no credit card, no trial that converts.
- No scraping of authenticated or paywalled sources; no circumventing rate limits or robots.txt.
- No `try: ... except: pass`.
- No editing a test, fixture, threshold, or acceptance criterion to make something pass.
- No widening a regex or adding a guess-fallback to force a parse. Quarantine instead.
- No OCR value entering scoring, ever, under any confidence.
- No claiming a phase is done without pasting the actual command output that proves it.

---

## 14. FIRST MESSAGE BACK TO ME

Before writing code, reply with:
1. The `verify_sources.py` PASS/FAIL table.
2. Any architecture change you recommend, and why (you have latitude — if a free tier changed or a better free source exists, say so).
3. The exact list of accounts/keys I need to create, with links and steps.
4. Your estimate of build time in sessions, and which phase is riskiest.
5. **Your read on §0.A, §6, and §7** — if you think any anti-drift, anti-thrash, or OCR-trust mechanism is unworkable or will fight you, say so now rather than quietly ignoring it later.

Then wait for my go-ahead, and execute Phases 1→12, one session per phase, without stopping except for secrets.

---

## APPENDIX A — RE-ANCHOR CARD

*Paste this into the chat any time the agent starts drifting — placeholders appearing, tests skipped, "I'll come back to this," or vague claims of completion.*

```
STOP. Re-anchor to the contract.

1. Run: cat CONTRACT.md
2. Run: make guardrails
3. Run: make test && git diff --stat HEAD~1

Then answer honestly, one line each:
- Any TODO, placeholder, empty body, or bare except added since the last commit?
- Any test, fixture, threshold, or acceptance criterion weakened?
- Any parse or OCR value written without full validation, or any regex widened
  to force a pass instead of quarantining?
- Any phase marked complete without pasted proof?

Fix every "yes" before writing another line of code. Do not explain, just fix.
```

## APPENDIX B — PARSER THRASH CIRCUIT-BREAKER

*Paste this if the agent is visibly oscillating on golden tests.*

```
You are oscillating. Stop editing the parser.

1. Show me docs/PARSER_LOG.md and the current .ratchet.json.
2. For the failing fixture, answer in writing: what STRUCTURAL feature
   (which XML nodes / which layout) differs from the fixtures that pass?
3. If structurally distinct -> new variant handler file. Not a conditional.
4. If not -> the bug is in detect.py or a shared extractor. Fix it there
   with an isolated unit test.
5. If this is attempt 5+ -> escalation ladder step 5. Quarantine it,
   document it in LIMITATIONS.md, move on.

You may not add a fallback branch, widen a regex, or infer a missing field.
```
