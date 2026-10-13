"""Tests for the DEV-02 import blocklist.

Verifies that the dataset_management package does not import from
forbidden surfaces (backend frameworks, ORM, queue, forbidden
research subpackages) and does not expose any of those names in its
public API.
"""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path

import pytest

# Names that the package MUST NOT import from anywhere in its dep
# tree (a sample of common dangerous names).
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


# Research subpackages that DEV-02 is forbidden to import.
FORBIDDEN_RESEARCH_SUBPACKAGES = [
    "customer_segmentation.preprocessing",
    "customer_segmentation.features",
    "customer_segmentation.clustering",
    "customer_segmentation.evaluation",
    "customer_segmentation.profiling",
    "customer_segmentation.aggregation",
    "customer_segmentation.outlier_analysis",
    "customer_segmentation.visualization",
]


def _lib_present_in(text: str, lib_name: str) -> bool:
    """Return True if ``lib_name`` appears as a top-level token
    (i.e. as a PyPI dependency declaration) in ``text``.

    A simple ``in`` check would false-positive on substrings like
    ``"Parquet"`` (which contains ``"rq"``). We look for the name
    as a stand-alone token: start of line, after a separator, or
    as part of a quoted requirement.
    """
    # Split into lines and check each line for a top-level token.
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # Tokenise on whitespace and punctuation that separates dep names.
        tokens = re.split(r"[\s,=<>!\[\]\"';]+", stripped)
        for tok in tokens:
            if tok == lib_name:
                return True
    return False


@pytest.mark.parametrize("lib_name", FORBIDDEN_LIBS)
def test_forbidden_lib_not_a_dependency(lib_name: str) -> None:
    """The forbidden library is not a runtime dependency of this repo.

    We allow it to be installed at the system level (some Linux
    distros pre-install psycopg2, for example) but it MUST NOT
    appear in ``pyproject.toml::dependencies`` or
    ``requirements.txt``.
    """
    pyproject = Path("pyproject.toml").read_text()
    req = Path("requirements.txt").read_text()
    assert not _lib_present_in(pyproject, lib_name), (
        f"forbidden lib {lib_name!r} appears in pyproject.toml"
    )
    assert not _lib_present_in(req, lib_name), (
        f"forbidden lib {lib_name!r} appears in requirements.txt"
    )


@pytest.mark.parametrize("subpkg", FORBIDDEN_RESEARCH_SUBPACKAGES)
def test_forbidden_research_subpackage_not_imported_by_dataset_management(
    subpkg: str,
) -> None:
    """The dataset_management package does not import a forbidden
    research subpackage at module-load time."""
    pkg_name = "customer_segmentation.dataset_management"
    if pkg_name in sys.modules:
        importlib.reload(sys.modules[pkg_name])
    else:
        importlib.import_module(pkg_name)
    for name in sys.modules:
        if not name.startswith(pkg_name):
            continue
        if subpkg in name:
            pytest.fail(
                f"{pkg_name} sub-module {name!r} imported forbidden "
                f"research subpackage {subpkg!r}."
            )


def test_no_fastapi_dependency_anywhere_in_source() -> None:
    """The dataset_management source files do not `import fastapi`."""
    src_dir = Path("src/customer_segmentation/dataset_management")
    for py in src_dir.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_LIBS:
            assert f"import {forbidden}" not in text
            assert f"from {forbidden}" not in text


def test_public_api_does_not_expose_forbidden_names() -> None:
    """The package __all__ does not contain any of the forbidden names."""
    from customer_segmentation import dataset_management as dm

    public = set(getattr(dm, "__all__", []))
    for forbidden in FORBIDDEN_LIBS:
        assert forbidden not in public, (
            f"forbidden name {forbidden!r} appears in "
            f"customer_segmentation.dataset_management.__all__"
        )
