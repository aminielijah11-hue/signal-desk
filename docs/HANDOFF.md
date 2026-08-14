# HANDOFF

Running state file per PROMPT.md §0.A.2 step 6. Written for a stranger —
assume the next phase is a different engineer with zero memory of this one.

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
