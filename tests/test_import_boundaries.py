"""Checks that copilot code cannot reach the ground truth through imports.

The eval is only honest if the copilot never sees the correct answer.
Network rules stop it while the system runs; this test stops it in the code.
"""

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
COPILOT_DIR = REPO_ROOT / "copilot"

# Python packages that know which failure was started, or the correct answer.
FORBIDDEN_PACKAGES = frozenset({"chaos", "evalrunner"})


def imported_top_level_modules(source: str) -> set[str]:
    """Return the first part of every module name that the source code imports."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        # level > 0 is a relative import ("from . import x"), which stays inside the package.
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def forbidden_imports(source: str) -> set[str]:
    return imported_top_level_modules(source) & FORBIDDEN_PACKAGES


def test_copilot_does_not_import_chaos_or_eval() -> None:
    violations = {
        str(path.relative_to(REPO_ROOT)): sorted(found)
        for path in COPILOT_DIR.rglob("*.py")
        if (found := forbidden_imports(path.read_text(encoding="utf-8")))
    }
    assert violations == {}, f"copilot code imports forbidden packages: {violations}"


# The checker itself must be right, or the test above passes for the wrong reason.
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("import chaos", {"chaos"}),
        ("import chaos.replica_lag as rl", {"chaos"}),
        ("from evalrunner.ground_truth import load", {"evalrunner"}),
        ("import os, evalrunner", {"evalrunner"}),
        ("def f() -> None:\n    import chaos", {"chaos"}),
        ("from . import chaos", set()),
        ("import chaostoolkit", set()),
        ("import json", set()),
    ],
)
def test_forbidden_imports_checker(source: str, expected: set[str]) -> None:
    assert forbidden_imports(source) == expected
