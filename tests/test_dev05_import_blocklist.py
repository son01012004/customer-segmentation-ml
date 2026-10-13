"""Import blocklist tests for DEV-05.

Forbids DEV-05 source code from importing:

- ``customer_segmentation.evaluation.*`` (research core; R-EVAL-15).
- ``customer_segmentation.clustering.{baseline, cluster_number,
  hyperparameter_search, metrics, stability,
  preprocessing_feature_sensitivity}`` (EPIC-07/08 owned; mirror
  DEV-04 R-15 import blocklist).
- Forbidden third-party libs (matplotlib at runtime; etc.).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_DIR = _REPO_ROOT / "src" / "customer_segmentation" / "prototype" / "evaluation"
_SCRIPTS_DIR = _REPO_ROOT / "scripts"


# Forbidden subpackage patterns.
FORBIDDEN_RESEARCH_SUBPACKAGES = (
    "customer_segmentation.evaluation",
)


# Forbidden submodules inside research core (per plan §6.2).
FORBIDDEN_RESEARCH_SUBMODULES = (
    "customer_segmentation.clustering.baseline",
    "customer_segmentation.clustering.cluster_number",
    "customer_segmentation.clustering.hyperparameter_search",
    "customer_segmentation.clustering.metrics",
    "customer_segmentation.clustering.stability",
    "customer_segmentation.clustering.preprocessing_feature_sensitivity",
)


# Forbidden third-party libs at runtime.
FORBIDDEN_LIBS = (
    "matplotlib",
    "seaborn",
    "plotly",
    "bokeh",
    "dash",
)


def _iter_python_files() -> list[Path]:
    files: list[Path] = []
    for p in _SRC_DIR.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        files.append(p)
    p = _SCRIPTS_DIR / "dev05_evaluate_clustering.py"
    if p.exists():
        files.append(p)
    return files


def _imports_in_file(path: Path) -> list[tuple[str, str]]:
    """Return list of (kind, name) for every import in ``path``."""
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    found: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                found.append(("import", n.name))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                found.append(("from", node.module))
    return found


class TestForbiddenResearchImports:
    def test_no_evaluation_research_imports(self) -> None:
        """Forbid import of research core ``evaluation.*`` package."""
        offenders: list[tuple[Path, str, str]] = []
        for p in _iter_python_files():
            for kind, name in _imports_in_file(p):
                for forbidden in FORBIDDEN_RESEARCH_SUBPACKAGES:
                    if name == forbidden or name.startswith(forbidden + "."):
                        offenders.append((p, kind, name))
        assert offenders == [], (
            "Forbidden research evaluation imports found: "
            + "\n".join(f"  {p}: {kind} {name}" for p, kind, name in offenders)
        )

    def test_no_evaluation_clustering_submodule_imports(self) -> None:
        offenders: list[tuple[Path, str, str]] = []
        for p in _iter_python_files():
            for kind, name in _imports_in_file(p):
                for forbidden in FORBIDDEN_RESEARCH_SUBMODULES:
                    if name == forbidden or name.startswith(forbidden + "."):
                        offenders.append((p, kind, name))
        assert offenders == [], (
            "Forbidden research clustering submodule imports found: "
            + "\n".join(f"  {p}: {kind} {name}" for p, kind, name in offenders)
        )


class TestForbiddenThirdPartyLibs:
    def test_no_forbidden_lib_imports(self) -> None:
        offenders: list[tuple[Path, str, str]] = []
        for p in _iter_python_files():
            for kind, name in _imports_in_file(p):
                top = name.split(".")[0]
                if top in FORBIDDEN_LIBS:
                    offenders.append((p, kind, name))
        assert offenders == [], (
            "Forbidden third-party lib imports found: "
            + "\n".join(f"  {p}: {kind} {name}" for p, kind, name in offenders)
        )


class TestSourceStructure:
    def test_all_documented_modules_exist(self) -> None:
        """All Phase 2 module files must exist."""
        expected = {
            "__init__.py",
            "scope.py",
            "config_loader.py",
            "storage.py",
            "manifest.py",
            "metrics.py",
            "logging_config.py",
            "pipeline.py",
            "display.py",
            "compare.py",
        }
        actual = {p.name for p in _SRC_DIR.iterdir() if p.is_file()}
        missing = expected - actual
        assert missing == set(), f"Missing modules: {missing}"

    def test_cli_script_exists(self) -> None:
        assert (_SCRIPTS_DIR / "dev05_evaluate_clustering.py").exists()
