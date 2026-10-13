"""Tests that DEV-03 does not introduce forbidden runtime dependencies."""

from __future__ import annotations

import re
from pathlib import Path


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


def test_dev03_does_not_introduce_new_dependencies() -> None:
    """Inspect pyproject.toml + requirements.txt + configs for new libs."""
    pyproject = Path("pyproject.toml").read_text()
    req = Path("requirements.txt").read_text()
    cfg = Path("configs/dev03_preprocessing.yaml").read_text()

    new_libs_not_seen_in_research_core = [
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
        "kafka",
        "pydantic",
        "pint",
        "marshmallow",
    ]
    for lib in new_libs_not_seen_in_research_core:
        assert not _lib_present_in(pyproject, lib)
        assert not _lib_present_in(req, lib)
        assert not _lib_present_in(cfg, lib)


def test_sklearn_is_already_present() -> None:
    """scikit-learn is a required research-core dep (used by FE-06 + DEV-03).

    DEV-03 calls ``StandardScaler`` / ``MinMaxScaler`` / ``RobustScaler``
    / ``PowerTransformer`` directly (NOT via
    ``customer_segmentation.transformation.scaling`` — that path is
    C7-bound per AGENTS.md §5.2.3). The dependency must already be
    declared; DEV-03 does not add a new dependency.
    """
    pyproject = Path("pyproject.toml").read_text()
    req = Path("requirements.txt").read_text()
    assert "scikit-learn" in pyproject or "sklearn" in pyproject
    assert "scikit-learn" in req or "sklearn" in req


def test_pandas_pyarrow_numpy_already_present() -> None:
    pyproject = Path("pyproject.toml").read_text()
    req = Path("requirements.txt").read_text()
    for lib in ("pandas", "pyarrow", "numpy", "PyYAML"):
        assert lib in pyproject or lib.lower() in pyproject.lower()
        assert lib in req or lib.lower() in req.lower()
