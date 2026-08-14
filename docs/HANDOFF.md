# HANDOFF

Running state file per PROMPT.md §0.A.2 step 6. Written for a stranger —
assume the next phase is a different engineer with zero memory of this one.

---

## Phase 2 — Schema (complete)

**What was built:**

- Real Postgres, not Docker: the build machine has no Docker/Homebrew.
  User chose to create a Neon (free tier) project now rather than install
  Docker Desktop or Postgres.app — connection string lives in a local
  `.env` (gitignored, confirmed via `git check-ignore` before anything
  touched it), never in a committed file. `.env.example` documents the
  two required variables (`DATABASE_URL`, `SIGNAL_DESK_CONTACT_EMAIL` —
  the latter for the SEC-mandated descriptive User-Agent, §3) with
  placeholder values only.
- `py/config/env.py`: minimal `.env` loader (no python-dotenv dependency —
  one job, doesn't need a library).
- `py/ingest/db.py`: shared `get_connection()` context manager.
- `db/migrations/0001..0008.sql`: the full §4 data model — all ~27
  logical tables (issuers through source_disagreement), every constraint
  §4 specifies by name (insider_trades provenance/price/shares checks,
  congress_trades disclosed_at/amount_high/amount_low/UNIQUE, prices_daily
  high≥low/open/close), all named indexes. `prices_daily` is genuinely
  partitioned by year (`PARTITION BY RANGE (d)`, 2014–2027 partitions),
  not just commented as if it were.
- **Strengthened one constraint beyond the spec's literal text**: §4
  writes the OCR gate as `CHECK (provenance <> 'ocr' OR needs_review =
  true)`, but §7.3 constructs `'ocr_low_conf'` rows the same way (always
  paired with `needs_review=true`) and `NO_OCR_IN_SCORING` treats both
  values as equally untrusted. Widened to
  `CHECK (provenance NOT IN ('ocr', 'ocr_low_conf') OR needs_review =
  true)` — caught by my own test (`test_ocr_low_conf_without_review_is_
  also_rejected` failed against the literal-spec version, which is what
  surfaced the gap rather than a hunch).
- `py/ingest/migrate.py`: tiny numbered-`.sql` runner (`schema_migrations`
  tracking table, apply-in-filename-order, one transaction per file,
  idempotent — proven by running `migrate` twice in a row with 0 pending
  the second time) plus `reset` (`DROP SCHEMA public CASCADE`).
- `py/ingest/sources/sec_tickers.py`: seeds `issuers` from
  `sec.gov/files/company_tickers.json` (§3.1). Fetch/parse/validate are
  separated so parse+validate are unit-tested without hitting the
  network (`py/tests/test_sec_tickers.py`, 5 tests). Writes to
  `ingest_log` (running → success/failed) per §11. **Performance fix
  during this phase**: the first real run did one `INSERT` per row
  (~7,995 individual round trips to Neon) and took over two minutes;
  rewrote `upsert_issuers` to batch in chunks of 500 (one multi-row
  `INSERT ... ON CONFLICT` per chunk), now ~4 seconds. Also cut per-row
  duplicate-rejection logging (2,401 individual WARNING lines) down to a
  single summary line with a 5-row sample.
- `py/tests/test_schema_constraints.py`: 6 live-DB tests against
  `DATABASE_URL` (Neon locally, CI's own throwaway Postgres in Actions),
  each on its own connection that rolls back unconditionally in teardown
  so nothing persists. Covers the mandated OCR-CHECK proof plus its
  positive control (ocr + needs_review=true must NOT raise), the
  `ocr_low_conf` case, insider_trades price≥0, and prices_daily
  high≥low.
- `.github/workflows/guardrails.yml`: added a `postgres:16-alpine`
  **service container** (not Neon — CI gets its own ephemeral throwaway
  DB, so Actions runs never touch the real Neon project or need its
  secret) plus a `make db.migrate` step before lint/typecheck/test.
- `Makefile`: `db.migrate`, `db.reset`, `db.seed` — all Python-based
  (`ingest.migrate`, `ingest.sources.sec_tickers`), no dependency on
  Docker being installed locally.

**Gate proof (PROMPT.md §12, Phase 2) — with one number changed, see
"A real acceptance-criterion conflict" below:**

`make verify-phase PHASE=2` runs the full sequence for real against Neon:
`make db.reset` → `make db.migrate` (8/8 migrations, clean) → `make
db.seed` → issuers count check → `test_schema_constraints.py`. All five
steps pass. Full output pasted in the session transcript.

**A real acceptance-criterion conflict (not a bug, resolved with the
user):** PROMPT.md's literal gate is `SELECT count(*) FROM issuers >
8000`. Seeding from the exact endpoint §3.1 names produced **7,995–7,998**
(fluctuates slightly run to run as SEC's live file changes). Verified
this against the raw unique-CIK count directly (bypassing all of my own
parsing code) before concluding anything — not a validate()/dedup bug,
the live source genuinely has fewer entries than whenever the spec text
was written. Per CONTRACT rule 7 ("acceptance criteria are immutable
without explicit permission from the user... if a test is genuinely
wrong, stop and say so"), this was brought to the user rather than
silently adjusted or worked around (e.g. by padding data, which would
have violated rule 6 just as badly). **User's explicit decision: lower
the threshold to `> 7500`.** Encoded as `ISSUER_COUNT_THRESHOLD` in
`scripts/verify_phase.py` with the reasoning inline, not silently.

**Known defects:** none found this phase beyond the two already fixed
above (batch upsert, log volume) — both were caught and corrected before
this HANDOFF entry was written, not left as open items.

**Deliberately deferred:**

- `config/weights.yml` / `config/thresholds.yml` still don't exist —
  still correctly Phase 9's job.
- `ticker_aliases` table exists but is empty — §3.2 needs it for
  congressional asset-name matching, but that's Phase 5, not Phase 2.
- Docker still isn't installed locally; `docker-compose.yml` remains
  unexercised. Not needed now that Neon is the answer for both local dev
  and (eventually) production, per the architecture in §2.
- Neon/Vercel/Telegram/Resend/Tiingo accounts: only Neon has been created
  so far (this phase). The rest block later phases only.

**Assumptions made:**

- Table PKs/uniques not explicitly specified in §4's informal notation
  were chosen directly (e.g. `insider_roles` PK on
  `(owner_cik, issuer_cik, start_date)`, `ticker_aliases` PK on
  `(alias, cik, source)`) — reasonable technical decisions per CONTRACT
  rule 4, not scope creep, since some primary key had to exist and §4
  didn't specify one for every table.
- `model_weights` got a partial unique index enforcing at most one
  `is_active=true` row, because §5.2 refers to "the active model_weights
  row" as if it's singular — a real constraint the spec's prose implies
  but the table definition didn't spell out.
- Migration runner and connection helper live under `ingest/` (not a new
  top-level `db/` Python package) specifically so they fall under
  guardrails' `NO_PLACEHOLDER`/`NO_EMPTY_BODY`/`NO_SILENT_EXCEPT`
  coverage, which CONTRACT.md scopes to `ingest/, scoring/, research/,
  alerting/, app/` only. A separate `db/` package would have sat outside
  mechanical enforcement — judged worse given §0.A's whole thesis is
  "mechanical enforcement over memory."

**Exact next action:** tag `phase-2-complete`, push, confirm CI green
with the new Postgres service, then start Phase 3 (Prices, technicals,
calendar).

---

## Phase 1 — Skeleton + guardrails (complete)

**What was built:**

- Monorepo skeleton: `/app` (Next.js 15, TypeScript `strict: true`,
  Tailwind, ESLint, App Router, created via `create-next-app`), `/py`
  (uv-managed, pinned Python 3.12, packages `ingest/` [with `sources/` and
  `parsers/` subpackages], `scoring/`, `research/`, `alerting/`,
  `config/`, `tests/`), `/db/migrations` (empty, Phase 2 populates),
  `/docs`, `/.github/workflows`.
- `scripts/guardrails.py` — all 9 checks from CONTRACT.md/§0.A.4
  implemented as real, independently-callable functions:
  `NO_PLACEHOLDER`, `NO_EMPTY_BODY`, `NO_SILENT_EXCEPT`, `NO_ANY`,
  `NO_MAGIC_NUMBERS`, `NO_FIXTURE_MUTATION`, `NO_COVERAGE_REGRESSION`,
  `NO_UNSCORED_REVIEW_LEAK`, `NO_OCR_IN_SCORING`. Zero third-party deps
  (stdlib + subprocess calls to `uv run mypy`/`uv run coverage`), so it
  runs even before `uv sync`.
- `py/tests/test_guardrails.py` — 19 tests, each check exercised against
  a synthetic violation fixture (proving it catches the bad case) and a
  clean fixture (proving no false positive). Loads `scripts/guardrails.py`
  via `importlib` since it lives outside the `py/` package.
- `scripts/verify_phase.py` — phase-specific acceptance criteria runner.
  Phase 1's checks include an automated planted-TODO-and-remove-it cycle
  (writes a canary file with a TODO under `py/ingest/`, confirms
  `guardrails.py` fails and names the file, deletes it, confirms
  `guardrails.py` passes again) so the gate's "guardrails demonstrably
  fail on a deliberately-planted TODO" criterion is proven on every run,
  not just once by hand. Phases 2+ are NOT implemented yet — running
  `verify_phase.py <n>` for an unbuilt phase prints "not implemented" and
  exits 1, deliberately, so nothing can claim a false pass.
- `scripts/ratchet.py` — general auto-revert-on-regression mechanism per
  §6.3. Not yet exercised against real parser fixtures (none exist until
  Phase 6) but the mechanism itself (`.ratchet.json` best-count tracking,
  `git checkout` revert, `docs/PARSER_LOG.md` logging) is real and
  functional now.
- `Makefile`: `setup`, `lint`, `typecheck`, `test`, `guardrails`,
  `verify-phase`, `ratchet`, `db.up`/`db.down`.
- `docker-compose.yml`: local Postgres 16 (not yet started — Docker isn't
  installed on the build machine; see "Known defects" below).
- `.github/workflows/guardrails.yml`: runs lint + typecheck + test +
  guardrails on every push/PR, per §11. **Exercised for real on GitHub
  Actions — green as of run
  https://github.com/aminielijah11-hue/signal-desk/actions/runs/31777788778**
  (took two real failed runs to get there, see "Known defects" below —
  both are genuine bugs that were found and fixed, not flaked past).
- Pre-commit hook installed by `make setup`, proven working (it ran and
  passed during every actual `git commit` in this phase, including the
  two fix commits below).

**Gate proof (PROMPT.md §12, Phase 1) — all four criteria met:**

1. `make setup && make test && make guardrails` passes both in the
   working tree and on a genuinely fresh `git clone` to `/tmp` (cloned,
   ran all three from scratch, cleaned up).
2. `make verify-phase PHASE=1` — lint → typecheck → test → guardrails →
   phase-1 structural checks — exits 0.
3. **CI green**: real push to `github.com/aminielijah11-hue/signal-desk`
   (public), Actions run `31777788778` green end to end.
4. **Guardrails demonstrably fail on a planted TODO**: automated inside
   `verify_phase.py` (writes a canary file with a `TODO` under
   `py/ingest/`, confirms `guardrails.py` exits nonzero and names the
   file, deletes it, confirms `guardrails.py` passes again) — proven on
   every local run and would equally fail CI if committed, since CI runs
   the same `make guardrails`.

**Known defects (found via real CI failures, both fixed and re-verified):**

- **Makefile hardcoded `UV := $(HOME)/.local/bin/uv`.** Worked locally
  only because that happens to be where this machine's `uv` installer put
  it; `astral-sh/setup-uv` on the GitHub runner puts it somewhere else on
  `PATH`. First CI run failed at the `lint` step with `uv: not found`.
  Fixed to `UV := uv`, relying on `PATH` in both environments — and added
  `~/.local/bin` to this machine's `~/.zshrc` so local shells match CI's
  assumption (`uv` on `PATH`, not a guessed absolute path).
- **`tsc --noEmit` depended on stale local build artifacts.**
  `app/tsconfig.json` includes `.next/types/**/*.ts`, which is
  Next-generated and gitignored. Locally it existed only because the
  initial `create-next-app` scaffold happened to generate it once; CI
  never had it and failed with `Cannot find name 'LayoutProps'`. Fixed by
  adding `next typegen` (Next 16's dedicated lightweight route-type
  generator) as a prerequisite step in `make typecheck`, and re-verified
  locally after deleting `app/.next` to rule out hiding behind the same
  stale-artifact trap that caused the bug in the first place.
- **Docker is not installed on this machine.** `docker-compose.yml`
  exists and is believed correct (standard Postgres 16 service,
  healthcheck, named volume) but has never actually been run. Phase 2
  needs `docker compose up -d` to work before migrations can be tested
  locally — installing Docker Desktop is a heavier, more invasive action
  (system daemon/VM) than installing `uv` was, so it wasn't done without
  asking. Whoever picks up Phase 2 should either get Docker installed on
  this machine or point `DATABASE_URL` at the real Neon instance for
  local dev too (once that account exists).

**Deliberately deferred:**

- Accounts not yet created by the user: Neon, Vercel, Telegram bot,
  Resend, Tiingo (list + signup steps were given in the Phase-0
  first-message-back). None of them block Phase 2's start, only later
  gates (DB connection, deploy, alerts).
- `config/weights.yml` / `config/thresholds.yml` don't exist yet —
  correctly deferred to Phase 9 (scoring), since `NO_MAGIC_NUMBERS` only
  applies to `scoring/`, which is still empty.

**Assumptions made:**

- Project moved from the original `~/Downloads/PROMP flder/` to
  `~/Documents/signal-desk/` (matches the sibling `sentinel-data` project
  layout) — a filing/location decision, not a technical architecture one.
  `PROMPT.md` was copied there and is the copy being executed from.
  Original stays untouched in Downloads.
- `NO_MAGIC_NUMBERS`'s allowlist entry `-1` is effectively unreachable via
  `ast.Constant` (Python parses negative literals as `UnaryOp(USub,
  Constant(1))`, so the visible constant is always `1`, which is already
  allowlisted). Kept `-1` in the allowlist to match CONTRACT.md's literal
  text; it just never fires as its own branch. Not a bug, just worth a
  future reader not being confused by it.

**Exact next action:** tag `phase-1-complete`, push the tag, then start
Phase 2 (Schema) — migrations, constraints including the OCR `CHECK`,
indexes, seed `issuers` from the SEC ticker map. Phase 2 will need either
Docker working locally or a Neon connection string (see "Known defects").
