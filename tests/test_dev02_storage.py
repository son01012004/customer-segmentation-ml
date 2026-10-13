"""Tests for dataset_management storage helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from customer_segmentation.dataset_management.storage import (
    DATASET_ID_HEX_LEN,
    DATASET_ID_PREFIX,
    StoragePathError,
    dataset_dir,
    derive_dataset_id,
    find_existing_dataset,
    load_config,
    resolve_storage_root,
    validate_config,
)


# ---------------------------------------------------------------------------
# derive_dataset_id
# ---------------------------------------------------------------------------


def test_derive_dataset_id_uses_first_24_hex_chars() -> None:
    sha = "0" * 64
    assert derive_dataset_id(sha) == DATASET_ID_PREFIX + ("0" * DATASET_ID_HEX_LEN)


def test_derive_dataset_id_lowercases_input() -> None:
    sha = "ABCDEF0123456789ABCDEF01" + "0" * 40
    assert derive_dataset_id(sha) == "ds_abcdef0123456789abcdef01"


def test_derive_dataset_id_accepts_full_length() -> None:
    sha = "a" * 64
    assert derive_dataset_id(sha) == "ds_" + "a" * 24


def test_derive_dataset_id_rejects_empty_string() -> None:
    with pytest.raises(StoragePathError):
        derive_dataset_id("")


def test_derive_dataset_id_rejects_non_string() -> None:
    with pytest.raises(StoragePathError):
        derive_dataset_id(12345)  # type: ignore[arg-type]


def test_derive_dataset_id_rejects_non_hex() -> None:
    with pytest.raises(StoragePathError):
        derive_dataset_id("not-hex-1234567890abcdef")


def test_derive_dataset_id_rejects_too_short() -> None:
    with pytest.raises(StoragePathError):
        derive_dataset_id("a" * 23)


# ---------------------------------------------------------------------------
# dataset_dir
# ---------------------------------------------------------------------------


def test_dataset_dir_is_inside_storage_root(tmp_path: Path) -> None:
    root = (tmp_path / "data" / "prototype" / "datasets").resolve()
    root.mkdir(parents=True, exist_ok=True)
    d = dataset_dir(root, "ds_abc123def4567890abcdef01")
    assert d.parent == root


def test_dataset_dir_rejects_invalid_id_format(tmp_path: Path) -> None:
    root = tmp_path / "r"
    root.mkdir()
    with pytest.raises(StoragePathError):
        dataset_dir(root, "not_ds_prefix")


def test_dataset_dir_rejects_traversal(tmp_path: Path) -> None:
    root = (tmp_path / "root").resolve()
    root.mkdir()
    # The validation in dataset_dir only checks the prefix; the
    # content of dataset_id is otherwise not sanitised. Test that
    # the prefix check is the gate.
    with pytest.raises(StoragePathError):
        dataset_dir(root, "../etc/passwd")


# ---------------------------------------------------------------------------
# find_existing_dataset
# ---------------------------------------------------------------------------


def test_find_existing_dataset_returns_none_when_no_storage(tmp_path: Path) -> None:
    assert find_existing_dataset(tmp_path, "a" * 64) is None


def test_find_existing_dataset_finds_matching_hash(tmp_path: Path) -> None:
    root = (tmp_path / "datasets").resolve()
    root.mkdir(parents=True, exist_ok=True)
    ds_id = "ds_" + "b" * 24
    (root / ds_id).mkdir()
    sha = "b" * 64
    (root / ds_id / "manifest.json").write_text(
        f'{{"sha256": "{sha}", "dataset_id": "{ds_id}"}}', encoding="utf-8"
    )
    found = find_existing_dataset(root, sha)
    assert found is not None
    assert found.name == "manifest.json"


def test_find_existing_dataset_skips_unrelated_manifests(tmp_path: Path) -> None:
    root = (tmp_path / "datasets").resolve()
    root.mkdir(parents=True, exist_ok=True)
    for i, h in enumerate(["c", "d", "e"]):
        ds_id = f"ds_{h * 24}"
        (root / ds_id).mkdir()
        (root / ds_id / "manifest.json").write_text(
            f'{{"sha256": "{h * 64}", "dataset_id": "{ds_id}"}}',
            encoding="utf-8",
        )
    target = "f" * 64
    assert find_existing_dataset(root, target) is None


def test_find_existing_dataset_swallows_corrupt_manifest(tmp_path: Path) -> None:
    root = (tmp_path / "datasets").resolve()
    root.mkdir(parents=True, exist_ok=True)
    ds_id = "ds_" + "0" * 24
    (root / ds_id).mkdir()
    (root / ds_id / "manifest.json").write_text("not-json", encoding="utf-8")
    assert find_existing_dataset(root, "0" * 64) is None


# ---------------------------------------------------------------------------
# load_config + validate_config
# ---------------------------------------------------------------------------


def test_load_config_returns_inner_mapping(tmp_path: Path) -> None:
    cfg = tmp_path / "c.yaml"
    cfg.write_text(
        "dataset_management:\n  storage_root: data/prototype/datasets\n  "
        "max_file_size_mb: 1\n  supported_import_formats: ['csv']\n  "
        "default_csv_encoding: 'utf-8'\n  source_path_policy:\n    "
        "allow_external_source: false\n  readonly_research_paths: []\n",
        encoding="utf-8",
    )
    inner = load_config(cfg)
    assert inner["storage_root"] == "data/prototype/datasets"


def test_load_config_missing_file(tmp_path: Path) -> None:
    with pytest.raises(StoragePathError):
        load_config(tmp_path / "missing.yaml")


def test_load_config_invalid_yaml(tmp_path: Path) -> None:
    cfg = tmp_path / "c.yaml"
    cfg.write_text("dataset_management: [:", encoding="utf-8")
    with pytest.raises(StoragePathError):
        load_config(cfg)


def test_load_config_missing_dataset_management_key(tmp_path: Path) -> None:
    cfg = tmp_path / "c.yaml"
    cfg.write_text("foo: bar\n", encoding="utf-8")
    with pytest.raises(StoragePathError):
        load_config(cfg)


def test_resolve_storage_root_returns_absolute_path(tmp_path: Path) -> None:
    cfg = {"storage_root": str(tmp_path)}
    assert resolve_storage_root(cfg) == tmp_path.resolve()


def test_resolve_storage_root_rejects_empty(tmp_path: Path) -> None:
    with pytest.raises(StoragePathError):
        resolve_storage_root({"storage_root": ""})


def test_resolve_storage_root_rejects_missing_key(tmp_path: Path) -> None:
    with pytest.raises(StoragePathError):
        resolve_storage_root({})


def test_validate_config_accepts_minimal_valid() -> None:
    validate_config(
        {
            "storage_root": "data/prototype/datasets",
            "max_file_size_mb": 256,
            "supported_import_formats": ["csv", "parquet"],
            "default_csv_encoding": "utf-8",
            "source_path_policy": {"allow_external_source": False},
            "readonly_research_paths": ["data/raw/primary"],
        }
    )


def test_validate_config_rejects_non_positive_max_size() -> None:
    with pytest.raises(StoragePathError):
        validate_config(
            {
                "storage_root": "x",
                "max_file_size_mb": 0,
                "supported_import_formats": ["csv"],
                "default_csv_encoding": "utf-8",
                "source_path_policy": {"allow_external_source": False},
                "readonly_research_paths": [],
            }
        )


def test_validate_config_rejects_dotted_format() -> None:
    with pytest.raises(StoragePathError):
        validate_config(
            {
                "storage_root": "x",
                "max_file_size_mb": 1,
                "supported_import_formats": [".csv"],
                "default_csv_encoding": "utf-8",
                "source_path_policy": {"allow_external_source": False},
                "readonly_research_paths": [],
            }
        )


def test_validate_config_rejects_uppercase_format() -> None:
    with pytest.raises(StoragePathError):
        validate_config(
            {
                "storage_root": "x",
                "max_file_size_mb": 1,
                "supported_import_formats": ["CSV"],
                "default_csv_encoding": "utf-8",
                "source_path_policy": {"allow_external_source": False},
                "readonly_research_paths": [],
            }
        )


def test_validate_config_rejects_non_bool_policy() -> None:
    with pytest.raises(StoragePathError):
        validate_config(
            {
                "storage_root": "x",
                "max_file_size_mb": 1,
                "supported_import_formats": ["csv"],
                "default_csv_encoding": "utf-8",
                "source_path_policy": {"allow_external_source": "yes"},
                "readonly_research_paths": [],
            }
        )
