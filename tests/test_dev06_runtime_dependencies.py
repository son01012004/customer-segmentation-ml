"""Runtime dependency / forbidden-import runtime tests for DEV-06.

Ensures DEV-06 source code does not import any forbidden third-party
library at runtime (e.g. matplotlib / seaborn / plotly for plotting,
which is out of scope for DEV-06). Uses ``sys.modules`` after import
to detect.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_DIR = _REPO_ROOT / "src" / "customer_segmentation" / "prototype" / "segmentation"


FORBIDDEN_RUNTIME_LIBS = (
    "matplotlib",
    "seaborn",
    "plotly",
    "bokeh",
    "dash",
    "tabulate",
)


@pytest.fixture
def segmentation_modules_snapshot():
    """Snapshot/restore ``sys.modules`` for the segmentation namespace.

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
    # Snapshot only the segmentation namespace + their transitive deps.
    # We snapshot by identity so that downstream tests see exactly the
    # same module objects they would have seen without these tests.
    snapshot: dict[str, object] = {
        name: module
        for name, module in sys.modules.items()
        if name.startswith("customer_segmentation.prototype.segmentation")
    }
    try:
        yield snapshot
    finally:
        current = {
            name: module
            for name, module in sys.modules.items()
            if name.startswith("customer_segmentation.prototype.segmentation")
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
    def test_importing_dev06_does_not_load_matplotlib(self, segmentation_modules_snapshot) -> None:
        """Importing the dev07 package must not pull in matplotlib."""
        # Snapshot the current set of loaded top-level modules.
        before = set(sys.modules.keys())
        # Force a re-import by removing the package and its submodules.
        for name in list(sys.modules.keys()):
            if name.startswith("customer_segmentation.prototype.segmentation"):
                del sys.modules[name]
        import customer_segmentation.prototype.segmentation  # noqa: F401

        after = set(sys.modules.keys())
        new_modules = after - before
        forbidden_loaded = [m for m in new_modules if m.split(".")[0] in FORBIDDEN_RUNTIME_LIBS]
        assert (
            forbidden_loaded == []
        ), f"Importing DEV-06 pulled in forbidden runtime libs: {forbidden_loaded}"

    def test_importing_dev06_does_not_load_research_evaluation(
        self, segmentation_modules_snapshot
    ) -> None:
        """R-DEV-06-15: must not import research-core evaluation package."""
        for name in list(sys.modules.keys()):
            if name.startswith("customer_segmentation.prototype.segmentation"):
                del sys.modules[name]
        before = set(sys.modules.keys())
        import customer_segmentation.prototype.segmentation  # noqa: F401

        after = set(sys.modules.keys())
        new_research_eval = [
            m
            for m in (after - before)
            if m == "customer_segmentation.evaluation"
            or m.startswith("customer_segmentation.evaluation.")
        ]
        assert (
            new_research_eval == []
        ), f"Importing DEV-06 loaded research evaluation modules: {new_research_eval}"

    def test_importing_dev06_does_not_load_research_profiling(
        self, segmentation_modules_snapshot
    ) -> None:
        """R-DEV-06-15: must not import research-core profiling package."""
        for name in list(sys.modules.keys()):
            if name.startswith("customer_segmentation.prototype.segmentation"):
                del sys.modules[name]
        before = set(sys.modules.keys())
        import customer_segmentation.prototype.segmentation  # noqa: F401

        after = set(sys.modules.keys())
        new_profiling = [
            m
            for m in (after - before)
            if m == "customer_segmentation.profiling"
            or m.startswith("customer_segmentation.profiling.")
        ]
        assert (
            new_profiling == []
        ), f"Importing DEV-06 loaded research profiling modules: {new_profiling}"

    def test_importing_dev06_does_not_load_feature_engineering(
        self, segmentation_modules_snapshot
    ) -> None:
        """R-DEV-06-15: must not import research-core feature_engineering."""
        for name in list(sys.modules.keys()):
            if name.startswith("customer_segmentation.prototype.segmentation"):
                del sys.modules[name]
        before = set(sys.modules.keys())
        import customer_segmentation.prototype.segmentation  # noqa: F401

        after = set(sys.modules.keys())
        new_fe = [
            m
            for m in (after - before)
            if m == "customer_segmentation.feature_engineering"
            or m.startswith("customer_segmentation.feature_engineering.")
        ]
        assert new_fe == [], f"Importing DEV-06 loaded research feature_engineering: {new_fe}"


class TestPinnedDependencies:
    def test_only_declared_deps_used(self) -> None:
        """DEV-06 should only import from declared dependencies."""
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
                elif isinstance(node, ast.ImportFrom) and node.module:
                    top = node.module.split(".")[0]
                    if top not in declared and not top.startswith("customer_segmentation"):
                        offenders.append((p, "from", node.module))
        assert offenders == [], "Undeclared imports: " + "\n".join(
            f"  {p}: {kind} {name}" for p, kind, name in offenders
        )
