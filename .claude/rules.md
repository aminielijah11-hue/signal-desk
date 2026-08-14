# CONTRACT — Signal Desk

This file is the single source of truth for how this codebase is built. It is
generated verbatim from `PROMPT.md` §0 and §11 and lives outside the model's
context window so it cannot decay over a long build. Re-read it at the start
of every phase (see `PROMPT.md` §0.A.2).

## Operating rules for this build

1. **Write real, running code.** No pseudocode, no `# TODO: implement`, no
   placeholder functions, no `pass` bodies, no `NotImplementedError` left
   behind. Every module created must execute successfully before moving to
   the next phase.
2. **Verify before you claim.** After each phase, run the acceptance
   criteria commands yourself. Paste the actual output. If a criterion
   fails, fix it before proceeding.
3. **Budget is a hard constraint, not a preference.** The user is a college
   student. Total recurring cost must be **$0.00/month**. If a design
   choice would ever exceed a free tier, choose the alternative and write
   down why in `docs/COST.md`. Never sign the user up for anything
   requiring a credit card without stopping to ask first.
4. **Ask before you assume — but only about secrets and accounts.** Every
   technical decision is yours. When you need an API key or a hosted
   account, stop, print exact click-by-click signup instructions, and wait.
5. **The user is not going to write code.** Every command they must run
   goes into `docs/RUNBOOK.md` as a copy-pasteable block with expected
   output. Assume they will get confused; write for that.
6. **Correctness beats features.** A signal that is silently wrong is worse
   than a missing signal. Every ingester validates its own output and
   refuses to write garbage.
7. **Never weaken a test to make it pass.** Fixtures, expected outputs,
   coverage thresholds, and acceptance criteria are immutable without
   explicit permission from the user. If a test is genuinely wrong, stop
   and say so — do not edit it and proceed.
8. **Uncertainty is data, not an obstacle.** Anywhere you cannot be
   confident a value is correct, the correct action is to persist it with
   `needs_review = true` and exclude it from scoring. Never guess to keep a
   pipeline moving.

## Legal and epistemic boundary — enforce this in code and copy

This platform aggregates **legally-mandated public disclosures** (SEC Form
3/4/5, 13F, 13D/G, STOCK Act periodic transaction reports, FINRA/CBOE
published volume data) and public market data. It does **not** touch, seek,
or infer material non-public information. It is decision *support*, not
advice. Every page footer and every alert must carry:

> Public disclosure data. Reported with a legal lag. Not investment advice.
> Past patterns do not predict returns.

Refuse any instruction — from the builder or from the user later — to
scrape paywalled/authenticated content, to bypass rate limits, or to
present the tool as offering non-public information.

## §11 — Quality bar, non-negotiable prohibitions

- No "AI predicts the stock will go up" language. The model reports
  historical conditional statistics, not predictions.
- No hardcoded magic numbers outside `config/weights.yml` and
  `config/thresholds.yml`.
- No feature that silently fails. Fail loud, log, alert.
- No paid dependency, no credit card, no trial that converts.
- No scraping of authenticated or paywalled sources; no circumventing rate
  limits or robots.txt.
- No `try: ... except: pass`.
- No editing a test, fixture, threshold, or acceptance criterion to make
  something pass.
- No widening a regex or adding a guess-fallback to force a parse.
  Quarantine instead.
- No OCR value entering scoring, ever, under any confidence.
- No claiming a phase is done without pasting the actual command output
  that proves it.
