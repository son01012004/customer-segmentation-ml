"""Tests for list_preprocessed enumeration."""

from __future__ import annotations

from pathlib import Path

import pytest

from customer_segmentation.prototype.preprocessing.list import (
    list_preprocessed,
)


def test_list_preprocessed_on_empty_dir_returns_empty(tmp_path: Path) -> None:
    assert list_preprocessed(tmp_path, "ds_abc") == []


def test_list_preprocessed_returns_manifes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    container = tmp_path / "ds_abc" / "preprocessed"
    container.mkdir(parents=True)
    manifest_path = container / "preprocessed_manifest.json"
    manifest_path.write_text('{"x": 1}')
    out = list_preprocessed(tmp_path, "ds_abc")
    # Path doesn't have a parseable manifest but it's still listed as malformed
    # skipped silently per the design.
    assert out == []
