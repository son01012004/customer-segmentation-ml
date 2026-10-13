"""Tests for the preprocessing storage helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from customer_segmentation.prototype.preprocessing.storage import (
    PREPROCESSED_DIR_SUFFIX,
    PREPROCESSED_ID_HEX_LEN,
    PREPROCESSED_ID_PREFIX,
    Dev03StoragePathError,
    config_hash_yaml,
    derive_preprocessed_id,
    ensure_preprocessed_container,
    preprocessed_dir,
    preprocessed_log_path,
    resolve_storage_root,
)


def test_preprocessed_id_constant_lengths() -> None:
    assert len(PREPROCESSED_ID_PREFIX) > 0
    assert PREPROCESSED_ID_HEX_LEN == 24
    # Total preprocessed_id length: prefix + 24 hex chars.
    assert PREPROCESSED_ID_HEX_LEN % 2 == 0


def test_derive_preprocessed_id_is_deterministic() -> None:
    ppid1 = derive_preprocessed_id("ds_abc", "cfg_xyz", "content_999")
    ppid2 = derive_preprocessed_id("ds_abc", "cfg_xyz", "content_999")
    assert ppid1 == ppid2
    assert ppid1.startswith(PREPROCESSED_ID_PREFIX)
    assert len(ppid1) == len(PREPROCESSED_ID_PREFIX) + PREPROCESSED_ID_HEX_LEN


def test_derive_preprocessed_id_differs_for_different_inputs() -> None:
    base = derive_preprocessed_id("ds_abc", "cfg_xyz", "content_999")
    assert base != derive_preprocessed_id("ds_DEF", "cfg_xyz", "content_999")
    assert base != derive_preprocessed_id("ds_abc", "cfg_DEF", "content_999")
    assert base != derive_preprocessed_id("ds_abc", "cfg_xyz", "content_DEF")


def test_derive_preprocessed_id_rejects_empty_inputs() -> None:
    with pytest.raises(Dev03StoragePathError):
        derive_preprocessed_id("", "cfg_xyz", "content_999")
    with pytest.raises(Dev03StoragePathError):
        derive_preprocessed_id("ds_abc", "", "content_999")
    with pytest.raises(Dev03StoragePathError):
        derive_preprocessed_id("ds_abc", "cfg_xyz", "")


def test_config_hash_yaml_matches_file(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("foo: bar\n")
    h1 = config_hash_yaml(cfg)
    h2 = config_hash_yaml(cfg)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_config_hash_yaml_missing_file(tmp_path: Path) -> None:
    cfg = tmp_path / "nope.yaml"
    with pytest.raises(Dev03StoragePathError):
        config_hash_yaml(cfg)


def test_preprocessed_dir_resolves_inside_storage_root(tmp_path: Path) -> None:
    root = tmp_path / "datasets"
    root.mkdir()
    d = preprocessed_dir(root, "ds_abc123def456")
    assert str(d).endswith(f"/ds_abc123def456/{PREPROCESSED_DIR_SUFFIX}")


def test_preprocessed_dir_rejects_empty_dataset_id(tmp_path: Path) -> None:
    with pytest.raises(Dev03StoragePathError):
        preprocessed_dir(tmp_path, "")


def test_ensure_preprocessed_container_creates_dir(tmp_path: Path) -> None:
    root = tmp_path / "datasets"
    root.mkdir()
    d = ensure_preprocessed_container(root, "ds_abc")
    assert d.exists()
    assert d.is_dir()
    # Idempotent.
    d2 = ensure_preprocessed_container(root, "ds_abc")
    assert d2 == d


def test_preprocessed_log_path_returns_canonical(tmp_path: Path) -> None:
    root = tmp_path / "datasets"
    root.mkdir()
    p = preprocessed_log_path(root, "ds_abc", "pp_abcdef0123456789abcdef01")
    assert p.name == "pp_abcdef0123456789abcdef01.log"
    assert p.parent.exists()


def test_resolve_storage_root_reads_dev02_config(tmp_path: Path, monkeypatch) -> None:
    """resolve_storage_root returns DEV-02's storage_root."""
    import yaml

    cfg_yaml = tmp_path / "dev02.yaml"
    cfg_yaml.parent.mkdir(parents=True, exist_ok=True)
    cfg_inner = {
        "storage_root": str(tmp_path / "fake_storage"),
        "max_file_size_mb": 256,
        "supported_import_formats": ["csv", "parquet"],
        "default_csv_encoding": "utf-8",
        "source_path_policy": {"allow_external_source": False},
        "readonly_research_paths": ["data/raw/primary"],
    }
    cfg_yaml.write_text(yaml.safe_dump({"dataset_management": cfg_inner}))
    root = resolve_storage_root(cfg_yaml)
    assert root == (tmp_path / "fake_storage").resolve()
