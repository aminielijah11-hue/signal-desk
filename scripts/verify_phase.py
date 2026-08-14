#!/usr/bin/env python3
"""Phase-specific acceptance criteria from PROMPT.md §12.

`make verify-phase PHASE=N` runs lint + typecheck + test + guardrails as
separate Makefile prerequisites, then this script for the criteria that
are specific to phase N and can't be expressed as a single blanket
command. Only implement a phase's checks when that phase's PROMPT.md gate
has actually been built — a phase with no checks here is not "verified,"
it's unimplemented, and this script says so honestly rather than passing.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _exists(*rel_parts: str) -> tuple[bool, str]:
    p = ROOT.joinpath(*rel_parts)
    return p.exists(), str(p.relative_to(ROOT))


def check_phase_1() -> list[tuple[str, bool, str]]:
    results: list[tuple[str, bool, str]] = []

    makefile = ROOT / "Makefile"
    makefile_text = makefile.read_text() if makefile.exists() else ""
    for target in ["setup", "test", "guardrails", "verify-phase", "ratchet"]:
        ok = f"\n{target}:" in ("\n" + makefile_text) or makefile_text.startswith(f"{target}:")
        results.append((f"Makefile has '{target}' target", ok, "Makefile"))

    for parts in [
        ("scripts", "guardrails.py"),
        ("docker-compose.yml",),
        (".github", "workflows", "guardrails.yml"),
        ("scripts", "hooks", "pre-commit"),
    ]:
        ok, relp = _exists(*parts)
        results.append((f"{relp} exists", ok, relp))

    ci_text = (ROOT / ".github" / "workflows" / "guardrails.yml").read_text() \
        if (ROOT / ".github" / "workflows" / "guardrails.yml").exists() else ""
    ci_calls_guardrails = "guardrails.py" in ci_text or "make guardrails" in ci_text
    results.append(("CI workflow invokes guardrails", ci_calls_guardrails, ".github/workflows/guardrails.yml"))

    # A clean planted-TODO regression test: write a temp file with a TODO
    # under py/ingest/, confirm guardrails.py fails, then remove it and
    # confirm guardrails.py passes again. This directly proves the gate's
    # "guardrails demonstrably fail on a deliberately-planted TODO"
    # criterion on every run, not just once by hand.
    canary = ROOT / "py" / "ingest" / "_verify_phase_1_canary.py"
    try:
        canary.write_text("def f():\n    # TODO: this file should make guardrails fail\n    return 1\n")
        proc = subprocess.run(
            [sys.executable, "scripts/guardrails.py"], cwd=ROOT, capture_output=True, text=True
        )
        canary_caught = proc.returncode != 0 and "_verify_phase_1_canary.py" in proc.stdout
        results.append(("guardrails fails on a planted TODO", canary_caught, str(canary.relative_to(ROOT))))
    finally:
        canary.unlink(missing_ok=True)

    proc = subprocess.run(
        [sys.executable, "scripts/guardrails.py"], cwd=ROOT, capture_output=True, text=True
    )
    results.append(("guardrails passes again after canary removed", proc.returncode == 0, "scripts/guardrails.py"))

    return results


# Lowered from PROMPT.md §12's literal ">8000" by explicit user decision
# (see docs/HANDOFF.md Phase 2 entry). The live SEC company_tickers.json
# endpoint the spec itself names now returns ~7,998 unique CIKs — verified
# against the raw unique-CIK count directly, not a parsing bug. ">8000"
# was accurate when the spec text was written and has drifted down since;
# this is not a weakened acceptance criterion in the sense CONTRACT rule 7
# forbids (silently editing a test to force a pass) — it's the user
# explicitly setting a new number after seeing the real data.
ISSUER_COUNT_THRESHOLD = 7500

_COUNT_ISSUERS_SCRIPT = (
    "from ingest.db import get_connection\n"
    "with get_connection() as conn:\n"
    "    with conn.cursor() as cur:\n"
    "        cur.execute('SELECT count(*) FROM issuers')\n"
    "        print(cur.fetchone()[0])\n"
)


def check_phase_2() -> list[tuple[str, bool, str]]:
    results: list[tuple[str, bool, str]] = []

    for target in ["db.reset", "db.migrate", "db.seed"]:
        proc = subprocess.run(["make", target], cwd=ROOT, capture_output=True, text=True)
        detail = target if proc.returncode == 0 else (proc.stdout + proc.stderr)[-500:]
        results.append((f"make {target} succeeds", proc.returncode == 0, detail))

    count_proc = subprocess.run(
        ["uv", "run", "python", "-c", _COUNT_ISSUERS_SCRIPT],
        cwd=ROOT / "py",
        capture_output=True,
        text=True,
    )
    count = (
        int(count_proc.stdout.strip())
        if count_proc.returncode == 0 and count_proc.stdout.strip().isdigit()
        else -1
    )
    results.append(
        (
            f"issuers count > {ISSUER_COUNT_THRESHOLD}",
            count > ISSUER_COUNT_THRESHOLD,
            f"got {count}" if count >= 0 else (count_proc.stdout + count_proc.stderr)[-500:],
        )
    )

    constraint_proc = subprocess.run(
        ["uv", "run", "pytest", "tests/test_schema_constraints.py", "-q"],
        cwd=ROOT / "py",
        capture_output=True,
        text=True,
    )
    results.append(
        (
            "test_schema_constraints.py passes (incl. OCR CHECK proof)",
            constraint_proc.returncode == 0,
            "py/tests/test_schema_constraints.py",
        )
    )

    return results


PHASE_CHECKS = {
    1: check_phase_1,
    2: check_phase_2,
}


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: verify_phase.py <phase-number>")
        return 2
    try:
        phase = int(argv[0])
    except ValueError:
        print(f"'{argv[0]}' is not a phase number")
        return 2

    if phase not in PHASE_CHECKS:
        print(
            f"PHASE {phase}: no acceptance checks implemented in verify_phase.py yet — "
            "this phase has not been built. This is not a pass."
        )
        return 1

    results = PHASE_CHECKS[phase]()
    name_w = max(len(n) for n, _, _ in results)
    print(f"Phase {phase} acceptance criteria:")
    any_failed = False
    for name, ok, detail in results:
        status = "PASS" if ok else "FAIL"
        if not ok:
            any_failed = True
        print(f"  [{status}] {name}  ({detail})")

    print()
    if any_failed:
        print(f"PHASE {phase}: NOT verified.")
        return 1
    print(f"PHASE {phase}: verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
