#!/usr/bin/env python3
"""Anti-oscillation ratchet — PROMPT.md §6.3.

Runs a named test suite, compares its passing-test count against the
best-ever count recorded in `.ratchet.json`, and auto-reverts the working
tree under a given path via `git checkout` if the count regressed. The
ratchet only ever moves up.

This is a general mechanism usable by any suite (not just parsers) — Phase
6 will point it at `py/tests/parsers/`, but nothing about the tool is
parser-specific.

Usage:
    scripts/ratchet.py check <suite-name> <revert-path> -- <pytest-args...>

Example (once parser tests exist):
    scripts/ratchet.py check parsers py/ingest/parsers -- py/tests/parsers -q
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RATCHET_FILE = ROOT / ".ratchet.json"
PARSER_LOG = ROOT / "docs" / "PARSER_LOG.md"

_SUMMARY_RE = re.compile(r"(\d+)\s+passed")


def load_state() -> dict[str, int]:
    if not RATCHET_FILE.exists():
        return {}
    return json.loads(RATCHET_FILE.read_text())


def save_state(state: dict[str, int]) -> None:
    RATCHET_FILE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def run_suite(pytest_args: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        ["uv", "run", "pytest", *pytest_args],
        cwd=ROOT / "py",
        capture_output=True,
        text=True,
    )
    output = proc.stdout + proc.stderr
    match = _SUMMARY_RE.search(output)
    passed = int(match.group(1)) if match else 0
    return passed, output


def log_attempt(suite: str, hypothesis: str, passed: int, best: int, reverted: bool) -> None:
    PARSER_LOG.parent.mkdir(parents=True, exist_ok=True)
    header = "# Parser ratchet log\n\nEvery ratchet attempt, in order, per PROMPT.md §6.3/§6.4.\n\n"
    if not PARSER_LOG.exists():
        PARSER_LOG.write_text(header)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = (
        f"## {ts} — suite `{suite}`\n\n"
        f"- passed: {passed} (best-ever: {best})\n"
        f"- outcome: {'REVERTED — regression' if reverted else 'kept — no regression'}\n"
        f"- hypothesis/note: {hypothesis}\n\n"
    )
    with PARSER_LOG.open("a") as f:
        f.write(entry)


def check(suite: str, revert_path: str, pytest_args: list[str], hypothesis: str) -> int:
    state = load_state()
    best = state.get(suite, 0)
    passed, output = run_suite(pytest_args)
    print(output)

    if passed < best:
        subprocess.run(["git", "checkout", "--", revert_path], cwd=ROOT, check=False)
        log_attempt(suite, hypothesis, passed, best, reverted=True)
        print(
            f"RATCHET: suite '{suite}' regressed ({passed} < best {best}). "
            f"Reverted '{revert_path}' via git checkout. See docs/PARSER_LOG.md."
        )
        return 1

    if passed > best:
        state[suite] = passed
        save_state(state)
        print(f"RATCHET: suite '{suite}' improved ({best} -> {passed}). New best recorded.")
    else:
        print(f"RATCHET: suite '{suite}' unchanged at {passed}/{best}.")
    log_attempt(suite, hypothesis, passed, best, reverted=False)
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 4 or argv[0] != "check" or "--" not in argv:
        print(__doc__)
        return 2
    sep = argv.index("--")
    suite, revert_path = argv[1], argv[2]
    pytest_args = argv[sep + 1 :]
    if not pytest_args:
        print("error: no pytest args given after '--'")
        return 2
    return check(suite, revert_path, pytest_args, hypothesis="(no hypothesis text supplied)")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
