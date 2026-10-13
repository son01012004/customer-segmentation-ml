"""Runtime dependency / forbidden-import runtime tests for DEV-05.

Ensures DEV-05 source code does not import any forbidden third-party
library at runtime (e.g. matplotlib / seaborn / plotly for plotting,
which is out of scope for DEV-05). Uses ``sys.modules`` after import
to detect.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_DIR = _REPO_ROOT / "src" / "customer_segmentation" / "prototype" / "evaluation"


FORBIDDEN_RUNTIME_LIBS = (
    "matplotlib",
    "seaborn",
    "plotly",
    "bokeh",
    "dash",
)


@pytest.fixture
def evaluation_modules_snapshot():
    """Snapshot/restore ``sys.modules`` for the evaluation namespace.

    The runtime-dependency tests intentionally delete entries from
    ``sys.modules`` and re-import the package to verify that no
    forbidden library is pulled in on a fresh import. Without this
    fixture, the in-place mutation persists across tests in the same
    pytest process and pollutes downstream test modules (notably
    DEV-08 ``pytest.raises`` matches), causing pre-existing failures
    when running the full DEV-02..09 suite.

    The fixture restores ``sys.modules`` to the exact state observed
    at fixture entry: any module that was present at entry is restored
    to the same object, and any module that was added during the test is
    removed on exit.
    """
    snapshot: dict[str, object] = {
        name: module
        for name, module in sys.modules.items()
        if name.startswith("customer_segmentation.prototype.evaluation")
    }
    try:
        yield snapshot
    finally:
        current = {
            name: module
            for name, module in sys.modules.items()
            if name.startswith("customer_segmentation.prototype.evaluation")
        }
        # Remove any module added by the test body.
        for name in list(current.keys()):
            if name not in snapshot:
                del sys.modules[name]
        # Restore any module that was mutated in place.
        for name, original_module in snapshot.items():
            current_module = sys.modules.get(name)
            if current_module is not original_module:
                sys.modules[name] = original_module


class TestRuntimeImports:
    def test_importing_dev05_does_not_load_matplotlib(self, evaluation_modules_snapshot) -> None:
        """Importing the dev05 package must not pull in matplotlib."""
        # Snapshot the current set of loaded top-level modules.
        before = set(sys.modules.keys())
        # Force a re-import by removing the package and its submodules.
        for name in list(sys.modules.keys()):
            if name.startswith("customer_segmentation.prototype.evaluation"):
                del sys.modules[name]
        import customer_segmentation.prototype.evaluation  # noqa: F401

        after = set(sys.modules.keys())
        new_modules = after - before
        forbidden_loaded = [m for m in new_modules if m.split(".")[0] in FORBIDDEN_RUNTIME_LIBS]
        assert (
            forbidden_loaded == []
        ), f"Importing DEV-05 pulled in forbidden runtime libs: {forbidden_loaded}"

    def test_importing_dev05_does_not_load_research_evaluation(
        self, evaluation_modules_snapshot
    ) -> None:
        """R-EVAL-15: must not import research core evaluation package."""
        for name in list(sys.modules.keys()):
            if name.startswith("customer_segmentation.prototype.evaluation"):
                del sys.modules[name]
        # We need to ensure that importing DEV-05 does NOT cause
        # customer_segmentation.evaluation to be loaded.
        # But research evaluation might be loaded as a dependency of other
        # modules. So we use a runtime probe: after import, check whether
        # the package was loaded AS A RESULT of the DEV-05 import.
        before = set(sys.modules.keys())
        import customer_segmentation.prototype.evaluation  # noqa: F401

        after = set(sys.modules.keys())
        new_research_eval = [
            m
            for m in (after - before)
            if m == "customer_segmentation.evaluation"
            or m.startswith("customer_segmentation.evaluation.")
        ]
        assert (
            new_research_eval == []
        ), f"Importing DEV-05 loaded research evaluation modules: {new_research_eval}"


class TestPinnedDependencies:
    def test_only_declared_deps_used(self) -> None:
        """DEV-05 should only import from declared dependencies."""
        # Declared runtime dependencies per pyproject.toml + stdlib.
        declared = {
            # Project deps
            "numpy",
            "pandas",
            "scipy",
            "scikit-learn",
            "sklearn",  # alias of scikit-learn
            "pyarrow",
            # Stdlib (always allowed)
            "__future__",
            "yaml",  # PyYAML (declared)
            "json",
            "logging",
            "argparse",
            "pathlib",
            "dataclasses",
            "datetime",
            "hashlib",
            "contextlib",
            "enum",
            "typing",
            "os",
            "re",
            "sys",
            "platform",
            "shutil",
            "uuid",
            "csv",
            "collections",
            "collections.abc",
            "dataclasses",
            "itertools",
            "functools",
            "abc",
            "io",
            "tempfile",
            "warnings",
            "copy",
            "ast",
            "time",
            "textwrap",
        }
        import ast

        offenders: list[tuple[Path, str, str]] = []
        for p in _SRC_DIR.rglob("*.py"):
            if "__pycache__" in p.parts:
                continue
            src = p.read_text(encoding="utf-8")
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for n in node.names:
                        top = n.name.split(".")[0]
                        if top not in declared and not top.startswith("customer_segmentation"):
                            offenders.append((p, "import", n.name))
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        top = node.module.split(".")[0]
                        if top not in declared and not top.startswith("customer_segmentation"):
                            offenders.append((p, "from", node.module))
        assert offenders == [], f"Undeclared imports: " + "\n".join(
            f"  {p}: {kind} {name}" for p, kind, name in offenders
        )
