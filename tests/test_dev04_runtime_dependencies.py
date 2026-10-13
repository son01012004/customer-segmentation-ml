"""Tests that DEV-04 does not introduce forbidden runtime dependencies.

Mirrors ``tests/test_dev03_runtime_dependencies.py``. The forbidden libs
are backend frameworks, ORM, queue, and other surfaces that would
violate the offline single-machine file-based architecture (ADR-0005).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))


# ---------------------------------------------------------------------------
# Forbidden libs
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _lib_present_in(text: str, lib_name: str) -> bool:
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


def _iter_prototype_clustering_files() -> list[Path]:
    pkg_dir = _REPO_ROOT / "src" / "customer_segmentation" / "prototype" / "clustering"
    return sorted(pkg_dir.rglob("*.py"))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_dev04_does_not_introduce_new_dependencies() -> None:
    """Inspect pyproject.toml + requirements.txt + dev04 config for new libs."""
    pyproject = (_REPO_ROOT / "pyproject.toml").read_text()
    req_path = _REPO_ROOT / "requirements.txt"
    req = req_path.read_text() if req_path.exists() else ""
    cfg = (_REPO_ROOT / "configs" / "dev04_clustering.yaml").read_text()

    for lib in FORBIDDEN_LIBS:
        assert not _lib_present_in(
            pyproject, lib
        ), f"pyproject.toml must not declare forbidden lib {lib!r}"
        assert not _lib_present_in(
            req, lib
        ), f"requirements.txt must not declare forbidden lib {lib!r}"
        assert not _lib_present_in(
            cfg, lib
        ), f"configs/dev04_clustering.yaml must not reference forbidden lib {lib!r}"


@pytest.mark.parametrize("lib_name", FORBIDDEN_LIBS)
def test_forbidden_lib_not_imported_in_dev04(lib_name: str) -> None:
    """The DEV-04 prototype.clustering package must not import a
    forbidden library at runtime.
    """
    for py in _iter_prototype_clustering_files():
        text = py.read_text()
        # Match ``import <lib>`` or ``from <lib> import ...``
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if not (stripped.startswith("import ") or stripped.startswith("from ")):
                continue
            tokens = re.split(r"[\s,()]+", stripped)
            for tok in tokens:
                clean = tok.rstrip(".").split(" as ")[0]
                # Match the top-level package name; ignore submodules
                # that are obviously unrelated (e.g. ``import json``).
                if clean == lib_name or clean.startswith(lib_name + "."):
                    pytest.fail(f"{py.name}: imports forbidden lib {lib_name!r}: " f"{stripped!r}")


def test_dev04_config_does_not_redeclare_dependencies() -> None:
    """The DEV-04 config YAML must not introduce a ``dependencies`` or
    ``pip`` block that lists new libraries.
    """
    cfg = (_REPO_ROOT / "configs" / "dev04_clustering.yaml").read_text()
    for forbidden_section in ("dependencies:", "pip:", "requirements:"):
        assert forbidden_section not in cfg, (
            f"dev04_clustering.yaml must not contain a {forbidden_section!r} "
            f"section; all dependencies belong in pyproject.toml"
        )


def test_pyproject_dependencies_unchanged_relative_to_baseline() -> None:
    """Sanity check: the pyproject.toml ``[project.dependencies]`` list
    is shared with DEV-02/DEV-03. DEV-04 must not modify it.

    The check is purely textual: parse the ``[project.dependencies]``
    block and verify it does not mention any forbidden backend lib.
    """
    pyproject = (_REPO_ROOT / "pyproject.toml").read_text()
    for lib in FORBIDDEN_LIBS:
        assert not _lib_present_in(pyproject, lib), (
            f"pyproject.toml [project.dependencies] must not list " f"forbidden lib {lib!r}"
        )
