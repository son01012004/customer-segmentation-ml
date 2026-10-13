"""Tests for DEV-08 loaders (wrappers around the existing readers)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from customer_segmentation.prototype.visualization.exceptions import (
    VisualizationError,
)
from customer_segmentation.prototype.visualization.loaders import (
    load_evaluation_manifest,
    load_marketing_manifest,
    load_segmentation_manifest,
)


def _write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def test_load_segmentation_manifest_raises_on_missing(tmp_path: Path) -> None:
    p = tmp_path / "missing.json"
    with pytest.raises(VisualizationError):
        load_segmentation_manifest(p)


def test_load_evaluation_manifest_raises_on_missing(tmp_path: Path) -> None:
    p = tmp_path / "missing.json"
    with pytest.raises(VisualizationError):
        load_evaluation_manifest(p)


def test_load_marketing_manifest_raises_on_missing(tmp_path: Path) -> None:
    p = tmp_path / "missing.json"
    with pytest.raises(VisualizationError):
        load_marketing_manifest(p)


def test_load_segmentation_manifest_raises_on_bad_json(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("not json at all", encoding="utf-8")
    with pytest.raises(VisualizationError):
        load_segmentation_manifest(p)


def test_load_evaluation_manifest_raises_on_bad_json(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("not json", encoding="utf-8")
    with pytest.raises(VisualizationError):
        load_evaluation_manifest(p)


def test_load_marketing_manifest_raises_on_bad_json(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("not json", encoding="utf-8")
    with pytest.raises(VisualizationError):
        load_marketing_manifest(p)


def test_loaders_raise_with_visualization_error(tmp_path: Path) -> None:
    """All three loaders must raise VisualizationError, not the original exception."""
    p = tmp_path / "missing.json"
    try:
        load_segmentation_manifest(p)
    except VisualizationError as exc:
        assert "Failed to load" in str(exc)
        # __cause__ should preserve the underlying error.
        assert exc.__cause__ is not None


def test_loader_accepts_pathlib_path(tmp_path: Path) -> None:
    p = tmp_path / "missing.json"
    # Path object should be accepted, not just str.
    with pytest.raises(VisualizationError):
        load_segmentation_manifest(p)
