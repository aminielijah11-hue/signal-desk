#!/usr/bin/env python3
"""Mechanical contract enforcement — see CONTRACT.md and PROMPT.md §0.A.4.

Nine checks, each independent, each producing real violations from real
file contents (not simulated). Every check function is importable so
py/tests/test_guardrails.py can exercise it directly against synthetic
fixtures. `main()` is the CLI entrypoint `make guardrails` calls.

This script intentionally has zero third-party dependencies (stdlib +
`uv` subprocess only) so it can run before `uv sync` has ever completed.
"""
from __future__ import annotations

import ast
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY_ROOT = ROOT / "py"
GUARDED_PY_DIRS = ["ingest", "scoring", "research", "alerting"]
APP_SRC = ROOT / "app" / "src"
MAGIC_NUMBER_ALLOWLIST = {0, 1, -1, 2, 100}


@dataclass
class GuardrailResult:
    name: str
    passed: bool
    violations: list[str] = field(default_factory=list)
    note: str | None = None


def iter_python_files(dirs: list[str]) -> list[Path]:
    out: list[Path] = []
    for d in dirs:
        base = PY_ROOT / d
        if not base.exists():
            continue
        for p in sorted(base.rglob("*.py")):
            if "__pycache__" in p.parts:
                continue
            out.append(p)
    return out


def iter_ts_files() -> list[Path]:
    if not APP_SRC.exists():
        return []
    out: list[Path] = []
    for p in sorted(APP_SRC.rglob("*.ts")) + sorted(APP_SRC.rglob("*.tsx")):
        if p.name.endswith(".d.ts"):
            continue
        if "node_modules" in p.parts or ".next" in p.parts:
            continue
        out.append(p)
    return out


def rel(p: Path) -> str:
    return str(p.relative_to(ROOT))


# ---------------------------------------------------------------------------
# NO_PLACEHOLDER
# ---------------------------------------------------------------------------

_PLACEHOLDER_TEXT_RE = re.compile(
    r"\b(TODO|FIXME|XXX|NotImplementedError|raise\s+NotImplemented)\b"
)


def check_no_placeholder() -> GuardrailResult:
    violations: list[str] = []

    for f in iter_python_files(GUARDED_PY_DIRS):
        text = f.read_text(errors="replace")
        for i, line in enumerate(text.splitlines(), start=1):
            if _PLACEHOLDER_TEXT_RE.search(line):
                violations.append(f"{rel(f)}:{i}: placeholder marker in: {line.strip()}")
        try:
            tree = ast.parse(text, filename=str(f))
        except SyntaxError as e:
            violations.append(f"{rel(f)}: SyntaxError while scanning for ellipsis bodies: {e}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if len(node.body) == 1 and _is_ellipsis_expr(node.body[0]):
                    violations.append(
                        f"{rel(f)}:{node.lineno}: function '{node.name}' body is bare '...'"
                    )

    for f in iter_ts_files():
        text = f.read_text(errors="replace")
        for i, line in enumerate(text.splitlines(), start=1):
            if re.search(r"\b(TODO|FIXME|XXX)\b", line):
                violations.append(f"{rel(f)}:{i}: placeholder marker in: {line.strip()}")

    return GuardrailResult("NO_PLACEHOLDER", passed=not violations, violations=violations)


def _is_ellipsis_expr(stmt: ast.stmt) -> bool:
    return (
        isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Constant)
        and stmt.value.value is Ellipsis
    )


# ---------------------------------------------------------------------------
# NO_EMPTY_BODY
# ---------------------------------------------------------------------------


class _ClassStackVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.class_stack: list[ast.ClassDef] = []
        self.violations: list[str] = []
        self.filename = ""

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802 (ast API name)
        self.class_stack.append(node)
        self.generic_visit(node)
        self.class_stack.pop()

    def _enclosing_class_is_protocol(self) -> bool:
        if not self.class_stack:
            return False
        cls = self.class_stack[-1]
        for base in cls.bases:
            name = ast.unparse(base)
            if name == "Protocol" or name.endswith(".Protocol"):
                return True
        return False

    def _has_abstractmethod(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        for dec in node.decorator_list:
            name = ast.unparse(dec)
            if name == "abstractmethod" or name.endswith(".abstractmethod"):
                return True
        return False

    def _check_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        body = list(node.body)
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            body = body[1:]  # strip leading docstring
        is_empty = len(body) == 0 or all(isinstance(s, ast.Pass) for s in body)
        if is_empty and not self._has_abstractmethod(node) and not self._enclosing_class_is_protocol():
            self.violations.append(
                f"{self.filename}:{node.lineno}: '{node.name}' body is only pass/docstring "
                "(not @abstractmethod, not in a Protocol)"
            )
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        self._check_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        self._check_function(node)


def check_no_empty_body() -> GuardrailResult:
    violations: list[str] = []
    for f in iter_python_files(GUARDED_PY_DIRS):
        text = f.read_text(errors="replace")
        try:
            tree = ast.parse(text, filename=str(f))
        except SyntaxError as e:
            violations.append(f"{rel(f)}: SyntaxError: {e}")
            continue
        visitor = _ClassStackVisitor()
        visitor.filename = rel(f)
        visitor.visit(tree)
        violations.extend(visitor.violations)
    return GuardrailResult("NO_EMPTY_BODY", passed=not violations, violations=violations)


# ---------------------------------------------------------------------------
# NO_SILENT_EXCEPT
# ---------------------------------------------------------------------------


def _contains_logger_call(body: list[ast.stmt]) -> bool:
    for stmt in body:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                chain = ast.unparse(node.func)
                if re.search(r"\blog(ger|ging)?\b", chain, re.IGNORECASE):
                    return True
    return False


def check_no_silent_except() -> GuardrailResult:
    violations: list[str] = []
    for f in iter_python_files(GUARDED_PY_DIRS):
        text = f.read_text(errors="replace")
        try:
            tree = ast.parse(text, filename=str(f))
        except SyntaxError as e:
            violations.append(f"{rel(f)}: SyntaxError: {e}")
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            if node.type is None:
                violations.append(f"{rel(f)}:{node.lineno}: bare 'except:'")
                continue
            type_name = ast.unparse(node.type)
            body_is_pass_only = len(node.body) == 1 and isinstance(node.body[0], ast.Pass)
            if body_is_pass_only:
                violations.append(f"{rel(f)}:{node.lineno}: 'except {type_name}: pass'")
                continue
            if type_name == "Exception" and not _contains_logger_call(node.body):
                violations.append(
                    f"{rel(f)}:{node.lineno}: 'except Exception' with no logger call in handler"
                )
    return GuardrailResult("NO_SILENT_EXCEPT", passed=not violations, violations=violations)


# ---------------------------------------------------------------------------
# NO_ANY
# ---------------------------------------------------------------------------

_TS_ANY_RE = re.compile(r"(:\s*any\b)|(\bas\s+any\b)")


def check_no_any() -> GuardrailResult:
    violations: list[str] = []
    for f in iter_ts_files():
        for i, line in enumerate(f.read_text(errors="replace").splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("//"):
                continue
            if _TS_ANY_RE.search(line):
                violations.append(f"{rel(f)}:{i}: {stripped}")

    mypy_dirs = [d for d in GUARDED_PY_DIRS if (PY_ROOT / d).exists()]
    if mypy_dirs and (PY_ROOT / "pyproject.toml").exists():
        proc = subprocess.run(
            ["uv", "run", "mypy", "--strict", *mypy_dirs],
            cwd=PY_ROOT,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            tail = "\n".join((proc.stdout + proc.stderr).splitlines()[-25:])
            violations.append(f"mypy --strict failed (exit {proc.returncode}):\n{tail}")

    return GuardrailResult("NO_ANY", passed=not violations, violations=violations)


# ---------------------------------------------------------------------------
# NO_MAGIC_NUMBERS
# ---------------------------------------------------------------------------


def check_no_magic_numbers() -> GuardrailResult:
    violations: list[str] = []
    for f in iter_python_files(["scoring"]):
        text = f.read_text(errors="replace")
        try:
            tree = ast.parse(text, filename=str(f))
        except SyntaxError as e:
            violations.append(f"{rel(f)}: SyntaxError: {e}")
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant):
                continue
            if isinstance(node.value, bool):
                continue
            if isinstance(node.value, (int, float)) and node.value not in MAGIC_NUMBER_ALLOWLIST:
                violations.append(
                    f"{rel(f)}:{node.lineno}: literal {node.value!r} not in allowlist "
                    f"{sorted(MAGIC_NUMBER_ALLOWLIST)} — pull from config/*.yml"
                )
    return GuardrailResult("NO_MAGIC_NUMBERS", passed=not violations, violations=violations)


# ---------------------------------------------------------------------------
# NO_FIXTURE_MUTATION
# ---------------------------------------------------------------------------


def check_no_fixture_mutation() -> GuardrailResult:
    tag_check = subprocess.run(
        ["git", "rev-parse", "-q", "--verify", "refs/tags/fixtures-frozen"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if tag_check.returncode != 0:
        return GuardrailResult(
            "NO_FIXTURE_MUTATION",
            passed=True,
            note="'fixtures-frozen' tag does not exist yet (expected before Phase 4/§6.2)",
        )
    diff = subprocess.run(
        ["git", "diff", "--stat", "fixtures-frozen", "--", "py/tests/fixtures/"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if diff.stdout.strip():
        return GuardrailResult(
            "NO_FIXTURE_MUTATION",
            passed=False,
            violations=diff.stdout.strip().splitlines(),
        )
    return GuardrailResult("NO_FIXTURE_MUTATION", passed=True)


# ---------------------------------------------------------------------------
# NO_COVERAGE_REGRESSION
# ---------------------------------------------------------------------------

COVERAGE_FLOOR_FILE = ROOT / ".coverage-floor"
COVERAGE_TARGET_DIRS = ["ingest/parsers", "scoring"]


def _coverage_targets_have_code() -> bool:
    for d in COVERAGE_TARGET_DIRS:
        base = PY_ROOT / d
        if not base.exists():
            continue
        for p in base.rglob("*.py"):
            if p.name != "__init__.py":
                return True
    return False


def check_no_coverage_regression() -> GuardrailResult:
    if not COVERAGE_FLOOR_FILE.exists():
        COVERAGE_FLOOR_FILE.write_text("0.0\n")
    floor = float(COVERAGE_FLOOR_FILE.read_text().strip())

    if not _coverage_targets_have_code():
        return GuardrailResult(
            "NO_COVERAGE_REGRESSION",
            passed=True,
            note=f"no code yet in {COVERAGE_TARGET_DIRS}; floor stays at {floor}%",
        )

    run = subprocess.run(
        ["uv", "run", "coverage", "run", "-m", "pytest", "-q"],
        cwd=PY_ROOT,
        capture_output=True,
        text=True,
    )
    include = ",".join(f"{d}/*" for d in COVERAGE_TARGET_DIRS)
    report = subprocess.run(
        ["uv", "run", "coverage", "report", f"--include={include}"],
        cwd=PY_ROOT,
        capture_output=True,
        text=True,
    )
    match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", report.stdout)
    if not match:
        return GuardrailResult(
            "NO_COVERAGE_REGRESSION",
            passed=False,
            violations=[
                "could not parse coverage report",
                f"pytest exit={run.returncode}",
                report.stdout.strip() or "(empty coverage report)",
            ],
        )
    current = float(match.group(1))
    if current < floor:
        return GuardrailResult(
            "NO_COVERAGE_REGRESSION",
            passed=False,
            violations=[f"coverage {current}% dropped below floor {floor}%"],
        )
    if current > floor:
        COVERAGE_FLOOR_FILE.write_text(f"{current}\n")
        return GuardrailResult(
            "NO_COVERAGE_REGRESSION",
            passed=True,
            note=f"coverage {current}% — floor ratcheted up from {floor}% to {current}%",
        )
    return GuardrailResult("NO_COVERAGE_REGRESSION", passed=True, note=f"coverage {current}% == floor")


# ---------------------------------------------------------------------------
# NO_UNSCORED_REVIEW_LEAK
# ---------------------------------------------------------------------------

_REVIEW_GATED_TABLES = re.compile(r"\b(congress_trades|insider_trades)\b", re.IGNORECASE)


def _chunk_is_unguarded(chunk: str) -> bool:
    if not _REVIEW_GATED_TABLES.search(chunk):
        return False
    low = chunk.lower()
    return "needs_review" not in low or "false" not in low


def check_no_unscored_review_leak() -> GuardrailResult:
    violations: list[str] = []
    if not (PY_ROOT / "scoring").exists():
        return GuardrailResult("NO_UNSCORED_REVIEW_LEAK", passed=True)

    # .py files: scope each check to a single string literal (AST), not the
    # whole file — a semicolon-free file with two separate queries must not
    # let one guarded query's "needs_review = false" text vouch for an
    # unrelated unguarded query elsewhere in the same file.
    for f in iter_python_files(["scoring"]):
        text = f.read_text(errors="replace")
        try:
            tree = ast.parse(text, filename=str(f))
        except SyntaxError as e:
            violations.append(f"{rel(f)}: SyntaxError: {e}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if _chunk_is_unguarded(node.value):
                    first_line = node.value.strip().splitlines()[0] if node.value.strip() else ""
                    violations.append(
                        f"{rel(f)}:{node.lineno}: query touching congress_trades/insider_trades "
                        f"without a 'needs_review = false' predicate: {first_line[:100]}"
                    )

    # .sql files: real semicolon-terminated statements, splitting is correct.
    for f in sorted((PY_ROOT / "scoring").rglob("*.sql")):
        text = f.read_text(errors="replace")
        for stmt in text.split(";"):
            if _chunk_is_unguarded(stmt):
                first_line = stmt.strip().splitlines()[0] if stmt.strip() else ""
                violations.append(
                    f"{rel(f)}: statement touching congress_trades/insider_trades without a "
                    f"'needs_review = false' predicate: {first_line[:100]}"
                )

    return GuardrailResult("NO_UNSCORED_REVIEW_LEAK", passed=not violations, violations=violations)


# ---------------------------------------------------------------------------
# NO_OCR_IN_SCORING
# ---------------------------------------------------------------------------

_OCR_LITERAL_RE = re.compile(r"""['"]ocr(_low_conf)?['"]""")
_EXCLUSION_MARKERS = ("!=", "<>", "not in", "not_in", "exclude", "<> ")


def check_no_ocr_in_scoring() -> GuardrailResult:
    violations: list[str] = []
    if not (PY_ROOT / "scoring").exists():
        return GuardrailResult("NO_OCR_IN_SCORING", passed=True)
    for f in iter_python_files(["scoring"]) + sorted((PY_ROOT / "scoring").rglob("*.sql")):
        for i, line in enumerate(f.read_text(errors="replace").splitlines(), start=1):
            if not _OCR_LITERAL_RE.search(line):
                continue
            low = line.lower()
            if not any(marker in low for marker in _EXCLUSION_MARKERS):
                violations.append(
                    f"{rel(f)}:{i}: OCR provenance literal with no visible exclusion marker: "
                    f"{line.strip()}"
                )
    return GuardrailResult("NO_OCR_IN_SCORING", passed=not violations, violations=violations)


# ---------------------------------------------------------------------------
# runner
# ---------------------------------------------------------------------------

ALL_CHECKS = [
    check_no_placeholder,
    check_no_empty_body,
    check_no_silent_except,
    check_no_any,
    check_no_magic_numbers,
    check_no_fixture_mutation,
    check_no_coverage_regression,
    check_no_unscored_review_leak,
    check_no_ocr_in_scoring,
]


def run_all() -> list[GuardrailResult]:
    return [check() for check in ALL_CHECKS]


def main() -> int:
    results = run_all()
    name_w = max(len(r.name) for r in results)
    print(f"{'CHECK':<{name_w}}  RESULT")
    print("-" * (name_w + 10))
    any_failed = False
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        if not r.passed:
            any_failed = True
        print(f"{r.name:<{name_w}}  {status}")
        if r.note:
            print(f"{'':<{name_w}}  note: {r.note}")
        for v in r.violations:
            print(f"{'':<{name_w}}  - {v}")
    print()
    if any_failed:
        print("GUARDRAILS: FAILED — fix every violation above before proceeding.")
        return 1
    print("GUARDRAILS: all checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
