"""DEV-04 import-blocklist tests.

Verifies that the ``customer_segmentation.prototype.clustering`` package
does not import from forbidden surfaces (backend frameworks, ORM,
queue, forbidden research subpackages). Mirrors the DEV-03 pattern in
``tests/test_dev03_import_blocklist.py`` — both a static scan over the
package's source and a runtime import-graph walk.
"""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))


# ---------------------------------------------------------------------------
# Forbidden surfaces
# ---------------------------------------------------------------------------

FORBIDDEN_LIBS = [
    "fastapi",
    "flask",
    "django",
    "uvicorn",
    "sqlalchemy",
    "psycopg2",
    "redis",
    "celery",
    "rq",
    "pymongo",
    "aiosqlite",
    "starlette",
    "boto3",
]


# DEV-04 may wrap a small set of research-core modules (clustering
# framework, config, dataset_management) and a few prototype modules
# (preprocessing.storage for path resolution; preprocessing.manifest
# for the preprocessed manifest schema; feature_generation.manifest_block).
# That is expected; everything else (evaluation, profiling,
# visualization, transformation.{scaling,pipeline}, ...) must remain
# forbidden.
FORBIDDEN_RESEARCH_SUBPACKAGES = [
    "customer_segmentation.evaluation",
    "customer_segmentation.profiling",
    "customer_segmentation.visualization",
    "customer_segmentation.outlier_analysis",
    "customer_segmentation.transformation.scaling",
    "customer_segmentation.transformation.pipeline",
    "customer_segmentation.preprocessing",
    "customer_segmentation.features",
    "customer_segmentation.aggregation",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _lib_present(text: str, lib_name: str) -> bool:
    """Return True if ``lib_name`` appears as a top-level token in text."""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        tokens = re.split(r"[\s,=<>!\[\]\"';]+", stripped)
        for tok in tokens:
            if tok == lib_name:
                return True
    return False


# ---------------------------------------------------------------------------
# Static tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lib_name", FORBIDDEN_LIBS)
def test_forbidden_lib_not_a_dependency(lib_name: str) -> None:
    """pyproject.toml + requirements.txt must not declare a forbidden lib."""
    pyproject = Path("pyproject.toml").read_text()
    req_file = _REPO_ROOT / "requirements.txt"
    req = req_file.read_text() if req_file.exists() else ""
    assert not _lib_present(
        pyproject, lib_name
    ), f"pyproject.toml must not depend on forbidden lib {lib_name!r}"
    assert not _lib_present(
        req, lib_name
    ), f"requirements.txt must not depend on forbidden lib {lib_name!r}"


@pytest.mark.parametrize("subpkg", FORBIDDEN_RESEARCH_SUBPACKAGES)
def test_forbidden_research_subpackage_not_imported_at_module_level(
    subpkg: str,
) -> None:
    """The DEV-04 prototype.clustering package must not have a direct
    import of a forbidden subpackage.
    """
    pkg_dir = _REPO_ROOT / "src" / "customer_segmentation" / "prototype" / "clustering"
    for py in sorted(pkg_dir.rglob("*.py")):
        text = py.read_text()
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if not (stripped.startswith("import ") or stripped.startswith("from ")):
                continue
            tokens = re.split(r"[\s,()]+", stripped)
            for tok in tokens:
                clean = tok.rstrip(".").split(" as ")[0]
                if clean == subpkg or clean.startswith(subpkg + "."):
                    pytest.fail(
                        f"{py.name}: imports forbidden subpackage " f"{subpkg!r}: {stripped!r}"
                    )


# ---------------------------------------------------------------------------
# Runtime import-graph tests
# ---------------------------------------------------------------------------


def _import_dev04_packages() -> None:
    """Force-import the DEV-04 prototype.clustering package.

    This populates ``sys.modules`` with the package's transitive
    dependencies so we can audit the actual import graph.
    """
    for name in list(sys.modules):
        if name.startswith("customer_segmentation.prototype.clustering"):
            del sys.modules[name]
    for sub in (
        "customer_segmentation.prototype.clustering",
        "customer_segmentation.prototype.clustering.pipeline",
        "customer_segmentation.prototype.clustering.storage",
        "customer_segmentation.prototype.clustering.config_loader",
        "customer_segmentation.prototype.clustering.manifest",
        "customer_segmentation.prototype.clustering.logging_config",
        "customer_segmentation.prototype.clustering.scope",
    ):
        importlib.import_module(sub)


@pytest.mark.parametrize("subpkg", FORBIDDEN_RESEARCH_SUBPACKAGES)
def test_forbidden_research_subpackage_not_loaded_via_dev04(
    subpkg: str,
) -> None:
    """At runtime, importing ``customer_segmentation.prototype.clustering``
    must not pull in any forbidden research subpackage.
    """
    _import_dev04_packages()
    for name in list(sys.modules):
        if not name.startswith("customer_segmentation.prototype.clustering"):
            continue
        mod = sys.modules.get(name)
        if mod is None:
            continue
        for attr_name in dir(mod):
            if attr_name.startswith("__"):
                continue
            attr = getattr(mod, attr_name, None)
            mod_path = getattr(attr, "__module__", "") if attr else ""
            if subpkg in mod_path:
                pytest.fail(
                    f"{name!r} transitively depends on forbidden "
                    f"{subpkg!r} via {attr_name!r} (mod={mod_path!r})."
                )


def test_forbidden_lib_not_loaded_via_dev04() -> None:
    """At runtime, importing DEV-04 must not pull in any forbidden lib."""
    _import_dev04_packages()
    # Inspect each loaded module's __module__ chain for forbidden libs.
    for name, mod in list(sys.modules.items()):
        if not name.startswith("customer_segmentation.prototype.clustering"):
            continue
        for attr_name in dir(mod):
            if attr_name.startswith("__"):
                continue
            attr = getattr(mod, attr_name, None)
            mod_path = getattr(attr, "__module__", "") if attr else ""
            for lib in FORBIDDEN_LIBS:
                if mod_path == lib or mod_path.startswith(lib + "."):
                    pytest.fail(
                        f"{name!r} depends on forbidden lib {lib!r} via "
                        f"{attr_name!r} (mod={mod_path!r})."
                    )
