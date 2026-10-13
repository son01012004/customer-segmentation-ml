"""DEV-03 import-blocklist tests.

Verifies that the prototype.preprocessing and prototype.feature_generation
packages do not import from forbidden surfaces (backend frameworks,
ORM, queue, forbidden research subpackages).
"""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path

import pytest

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


# DEV-03 may wrap a larger set of research-core modules than DEV-02 did
# (specifically: preprocessing.*, aggregation.*, features.*). That is
# expected; sub-packages that are OUT OF DEV-03's scope must remain
# forbidden (clustering, evaluation, profiling, visualization,
# transformation.{scaling,pipeline}).
FORBIDDEN_RESEARCH_SUBPACKAGES = [
    "customer_segmentation.clustering",
    "customer_segmentation.evaluation",
    "customer_segmentation.profiling",
    "customer_segmentation.visualization",
    "customer_segmentation.outlier_analysis",
    "customer_segmentation.transformation.scaling",
    "customer_segmentation.transformation.pipeline",
]


ALLOWED_RESEARCH_SUBPACKAGES = [
    "customer_segmentation.preprocessing",
    "customer_segmentation.aggregation",
    "customer_segmentation.features",
    "customer_segmentation.data",
    "customer_segmentation.config",
    "customer_segmentation.transformation.versioning",
    "customer_segmentation.dataset_management",
]


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


@pytest.mark.parametrize("lib_name", FORBIDDEN_LIBS)
def test_forbidden_lib_not_a_dependency(lib_name: str) -> None:
    pyproject = Path("pyproject.toml").read_text()
    req = Path("requirements.txt").read_text()
    assert not _lib_present(pyproject, lib_name)
    assert not _lib_present(req, lib_name)


@pytest.mark.parametrize("subpkg", FORBIDDEN_RESEARCH_SUBPACKAGES)
def test_forbidden_research_subpackage_not_imported(subpkg: str) -> None:
    pkg_names = (
        "customer_segmentation.prototype.preprocessing",
        "customer_segmentation.prototype.feature_generation",
    )
    for pkg_name in pkg_names:
        if pkg_name in sys.modules:
            importlib.reload(sys.modules[pkg_name])
        else:
            importlib.import_module(pkg_name)
    for name in list(sys.modules):
        if not any(name.startswith(pn) for pn in pkg_names):
            continue
        # Allow feature_generation to import preprocessing; allow preprocessing
        # to import feature_generation. Otherwise, check that the imported
        # sub-module doesn't depend on a forbidden subpackage.
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
                    f"{pkg_name} indirectly imports forbidden {subpkg!r} via {name!r}.{attr_name}."
                )


def test_no_fastapi_in_source() -> None:
    """The prototype.source files do not `import fastapi` (or any forbidden lib)."""
    src_dirs = [
        Path("src/customer_segmentation/prototype/preprocessing"),
        Path("src/customer_segmentation/prototype/feature_generation"),
    ]
    for src_dir in src_dirs:
        for py in src_dir.rglob("*.py"):
            text = py.read_text(encoding="utf-8")
            for forbidden in FORBIDDEN_LIBS:
                assert f"import {forbidden}" not in text
                assert f"from {forbidden}" not in text


def test_public_api_does_not_expose_forbidden_names() -> None:
    """Public __all__ does not contain any forbidden name."""
    from customer_segmentation.prototype import preprocessing as _pre_mod

    public_pre = set(getattr(_pre_mod, "__all__", []))
    from customer_segmentation.prototype import feature_generation as _fg

    public_fg = set(getattr(_fg, "__all__", []))
    for forbidden in FORBIDDEN_LIBS:
        assert forbidden not in public_pre
        assert forbidden not in public_fg
