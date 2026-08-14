"""Proves each guardrail check actually catches what it claims to, against
synthetic fixtures, and doesn't false-positive on clean code. This is the
test suite Phase 1's gate demands ("guardrails demonstrably fail on a
deliberately-planted TODO") generalized to all nine checks.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_GUARDRAILS_PATH = Path(__file__).resolve().parents[2] / "scripts" / "guardrails.py"
_spec = importlib.util.spec_from_file_location("guardrails", _GUARDRAILS_PATH)
assert _spec and _spec.loader
guardrails = importlib.util.module_from_spec(_spec)
sys.modules["guardrails"] = guardrails
_spec.loader.exec_module(guardrails)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    py_root = tmp_path / "py"
    app_src = tmp_path / "app" / "src"
    py_root.mkdir(parents=True)
    app_src.mkdir(parents=True)
    monkeypatch.setattr(guardrails, "ROOT", tmp_path)
    monkeypatch.setattr(guardrails, "PY_ROOT", py_root)
    monkeypatch.setattr(guardrails, "APP_SRC", app_src)
    monkeypatch.setattr(guardrails, "COVERAGE_FLOOR_FILE", tmp_path / ".coverage-floor")
    return tmp_path


def _write(base: Path, rel_path: str, content: str) -> Path:
    p = base / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p


# --- NO_PLACEHOLDER ---------------------------------------------------------


def test_no_placeholder_catches_todo_and_ellipsis_body(repo):
    _write(
        repo,
        "py/ingest/foo.py",
        "def f():\n    # TODO: fix this\n    return 1\n\n\ndef g():\n    ...\n",
    )
    result = guardrails.check_no_placeholder()
    assert not result.passed
    assert any("TODO" in v for v in result.violations)
    assert any("bare '...'" in v for v in result.violations)


def test_no_placeholder_catches_not_implemented_error(repo):
    _write(repo, "py/scoring/bar.py", "def f():\n    raise NotImplementedError\n")
    result = guardrails.check_no_placeholder()
    assert not result.passed


def test_no_placeholder_clean_code_passes(repo):
    _write(repo, "py/ingest/foo.py", "def f():\n    return 1\n")
    result = guardrails.check_no_placeholder()
    assert result.passed


def test_no_placeholder_catches_todo_in_ts(repo):
    _write(repo, "app/src/x.ts", "// TODO: wire this up\nexport const x = 1;\n")
    result = guardrails.check_no_placeholder()
    assert not result.passed


# --- NO_EMPTY_BODY -----------------------------------------------------------


def test_no_empty_body_flags_pass_and_docstring_only_but_allows_abstract_and_protocol(repo):
    _write(
        repo,
        "py/ingest/base.py",
        (
            "from abc import abstractmethod\n"
            "from typing import Protocol\n\n"
            "class Base:\n"
            "    def bad_pass(self):\n"
            "        pass\n\n"
            "    def bad_docstring(self):\n"
            "        '''just a docstring'''\n\n"
            "    @abstractmethod\n"
            "    def ok_abstract(self):\n"
            "        pass\n\n"
            "class Iface(Protocol):\n"
            "    def ok_protocol_method(self):\n"
            "        pass\n"
        ),
    )
    result = guardrails.check_no_empty_body()
    assert not result.passed
    joined = "\n".join(result.violations)
    assert "bad_pass" in joined
    assert "bad_docstring" in joined
    assert "ok_abstract" not in joined
    assert "ok_protocol_method" not in joined


def test_no_empty_body_real_implementation_passes(repo):
    _write(repo, "py/ingest/real.py", "def f(x):\n    return x + 1\n")
    result = guardrails.check_no_empty_body()
    assert result.passed


# --- NO_SILENT_EXCEPT ---------------------------------------------------------


def test_no_silent_except_catches_bare_and_pass_variants_but_allows_logged_exception(repo):
    _write(
        repo,
        "py/ingest/err.py",
        (
            "import logging\n"
            "logger = logging.getLogger(__name__)\n\n"
            "def a():\n"
            "    try:\n"
            "        x = 1\n"
            "    except:\n"
            "        pass\n\n"
            "def b():\n"
            "    try:\n"
            "        x = 1\n"
            "    except Exception:\n"
            "        pass\n\n"
            "def c():\n"
            "    try:\n"
            "        x = 1\n"
            "    except Exception as e:\n"
            "        logger.error('boom %s', e)\n\n"
            "def d():\n"
            "    try:\n"
            "        x = 1\n"
            "    except ValueError:\n"
            "        pass\n"
        ),
    )
    result = guardrails.check_no_silent_except()
    assert not result.passed
    assert len(result.violations) == 3
    joined = "\n".join(result.violations)
    assert "bare 'except:'" in joined
    assert "except Exception: pass" in joined
    assert "except ValueError: pass" in joined


def test_no_silent_except_clean_passes(repo):
    _write(
        repo,
        "py/ingest/err_ok.py",
        (
            "import logging\n"
            "logger = logging.getLogger(__name__)\n\n"
            "def a():\n"
            "    try:\n"
            "        x = 1\n"
            "    except ValueError as e:\n"
            "        logger.warning('bad value: %s', e)\n"
        ),
    )
    result = guardrails.check_no_silent_except()
    assert result.passed


# --- NO_ANY --------------------------------------------------------------------


def test_no_any_catches_ts_any(repo):
    _write(repo, "app/src/x.ts", "function f(a: any): any {\n  return a as any;\n}\n")
    result = guardrails.check_no_any()
    assert not result.passed
    assert any("x.ts" in v for v in result.violations)


def test_no_any_clean_ts_passes(repo):
    _write(repo, "app/src/x.ts", "function f(a: number): number {\n  return a;\n}\n")
    result = guardrails.check_no_any()
    assert result.passed


# --- NO_MAGIC_NUMBERS ------------------------------------------------------------


def test_no_magic_numbers_flags_unlisted_literal(repo):
    _write(repo, "py/scoring/s.py", "def f(x):\n    return x * 0.45 + 21\n")
    result = guardrails.check_no_magic_numbers()
    assert not result.passed
    joined = "\n".join(result.violations)
    assert "0.45" in joined
    assert "21" in joined


def test_no_magic_numbers_allows_allowlisted_literals(repo):
    _write(repo, "py/scoring/s.py", "def f(x):\n    return x * 2 + 100 - 1\n")
    result = guardrails.check_no_magic_numbers()
    assert result.passed


# --- NO_FIXTURE_MUTATION -------------------------------------------------------


def test_no_fixture_mutation_passes_when_tag_absent():
    # Deliberately NOT using the `repo` fixture — this exercises the real
    # repo's git state, where the fixtures-frozen tag genuinely doesn't
    # exist yet (created in Phase 4 per §6.2).
    result = guardrails.check_no_fixture_mutation()
    assert result.passed
    assert result.note and "does not exist yet" in result.note


# --- NO_COVERAGE_REGRESSION ------------------------------------------------------


def test_no_coverage_regression_skips_when_no_code_yet(repo):
    result = guardrails.check_no_coverage_regression()
    assert result.passed
    assert result.note and "no code yet" in result.note
    assert (repo / ".coverage-floor").exists()


# --- NO_UNSCORED_REVIEW_LEAK ------------------------------------------------------


def test_no_unscored_review_leak_flags_unguarded_but_not_guarded_query(repo):
    _write(
        repo,
        "py/scoring/q.py",
        (
            'BAD = "SELECT * FROM insider_trades WHERE cik = %s"\n'
            'GOOD = "SELECT * FROM insider_trades WHERE needs_review = false AND cik = %s"\n'
        ),
    )
    result = guardrails.check_no_unscored_review_leak()
    assert not result.passed
    assert len(result.violations) == 1
    assert "BAD" not in result.violations[0]  # message doesn't echo var name, just the SQL
    assert "insider_trades" in result.violations[0]


def test_no_unscored_review_leak_clean_passes(repo):
    _write(
        repo,
        "py/scoring/q.py",
        'GOOD = "SELECT * FROM insider_trades WHERE needs_review = false"\n',
    )
    result = guardrails.check_no_unscored_review_leak()
    assert result.passed


# --- NO_OCR_IN_SCORING ------------------------------------------------------------


def test_no_ocr_in_scoring_flags_unexcluded_but_not_excluded(repo):
    _write(
        repo,
        "py/scoring/ocr.py",
        (
            "BAD = \"SELECT * FROM x WHERE provenance = 'ocr'\"\n"
            "GOOD = \"SELECT * FROM x WHERE provenance != 'ocr'\"\n"
        ),
    )
    result = guardrails.check_no_ocr_in_scoring()
    assert not result.passed
    assert len(result.violations) == 1
    assert "BAD" in result.violations[0] or "provenance = 'ocr'" in result.violations[0]


def test_no_ocr_in_scoring_clean_passes(repo):
    _write(
        repo,
        "py/scoring/ocr.py",
        "GOOD = \"SELECT * FROM x WHERE provenance != 'ocr'\"\n",
    )
    result = guardrails.check_no_ocr_in_scoring()
    assert result.passed


# --- end-to-end -------------------------------------------------------------------


def test_run_all_on_clean_empty_repo_passes(repo):
    results = guardrails.run_all()
    assert all(r.passed for r in results), [r for r in results if not r.passed]
