"""Tests for DEV-08 storage layer (storage.py)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from customer_segmentation.prototype.visualization.exceptions import (
    VisualizationStoragePathError,
)
from customer_segmentation.prototype.visualization.storage import (
    CANONICAL_PAYLOAD_KEYS,
    DASHBOARD_ID_HEX_LEN,
    DASHBOARD_ID_PREFIX,
    compute_config_sha256,
    derive_dashboard_id,
    prototype_visualization_base_dir,
    prototype_visualization_run_dir,
)

# ---------------------------------------------------------------------------
# compute_config_sha256
# ---------------------------------------------------------------------------


def test_compute_config_sha256_deterministic() -> None:
    h1 = compute_config_sha256("dev08_visualization: {x: 1}")
    h2 = compute_config_sha256("dev08_visualization: {x: 1}")
    assert h1 == h2


def test_compute_config_sha256_is_64_hex() -> None:
    h = compute_config_sha256("anything")
    assert re.match(r"^[0-9a-f]{64}$", h)


def test_compute_config_sha256_different_content_different_hash() -> None:
    h1 = compute_config_sha256("aaa")
    h2 = compute_config_sha256("bbb")
    assert h1 != h2


def test_compute_config_sha256_non_string_raises() -> None:
    with pytest.raises(VisualizationStoragePathError, match="must be a str"):
        compute_config_sha256(123)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# derive_dashboard_id
# ---------------------------------------------------------------------------


def test_derive_dashboard_id_prefix_and_length() -> None:
    did = derive_dashboard_id(
        segmentation_id="seg_" + "0" * 24,
        clustering_id="cl_" + "1" * 24,
        preprocessed_id="pp_x",
        dataset_id="ds_x",
        config_sha256="a" * 64,
    )
    assert did.startswith(DASHBOARD_ID_PREFIX)
    assert len(did) == len(DASHBOARD_ID_PREFIX) + DASHBOARD_ID_HEX_LEN


def test_derive_dashboard_id_deterministic() -> None:
    kwargs = {
        "segmentation_id": "seg_" + "0" * 24,
        "clustering_id": "cl_" + "1" * 24,
        "preprocessed_id": "pp_x",
        "dataset_id": "ds_x",
        "config_sha256": "a" * 64,
    }
    assert derive_dashboard_id(**kwargs) == derive_dashboard_id(**kwargs)


def test_derive_dashboard_id_invalid_segmentation_id() -> None:
    with pytest.raises(VisualizationStoragePathError, match="segmentation_id"):
        derive_dashboard_id(
            segmentation_id="bad",
            clustering_id="cl_" + "1" * 24,
            preprocessed_id="pp_x",
            dataset_id="ds_x",
            config_sha256="a" * 64,
        )


def test_derive_dashboard_id_invalid_clustering_id() -> None:
    with pytest.raises(VisualizationStoragePathError, match="clustering_id"):
        derive_dashboard_id(
            segmentation_id="seg_" + "0" * 24,
            clustering_id="bad",
            preprocessed_id="pp_x",
            dataset_id="ds_x",
            config_sha256="a" * 64,
        )


def test_derive_dashboard_id_empty_preprocessed_id() -> None:
    with pytest.raises(VisualizationStoragePathError, match="preprocessed_id"):
        derive_dashboard_id(
            segmentation_id="seg_" + "0" * 24,
            clustering_id="cl_" + "1" * 24,
            preprocessed_id="",
            dataset_id="ds_x",
            config_sha256="a" * 64,
        )


def test_derive_dashboard_id_empty_dataset_id() -> None:
    with pytest.raises(VisualizationStoragePathError, match="dataset_id"):
        derive_dashboard_id(
            segmentation_id="seg_" + "0" * 24,
            clustering_id="cl_" + "1" * 24,
            preprocessed_id="pp_x",
            dataset_id="",
            config_sha256="a" * 64,
        )


def test_derive_dashboard_id_empty_config_sha() -> None:
    with pytest.raises(VisualizationStoragePathError, match="config_sha256"):
        derive_dashboard_id(
            segmentation_id="seg_" + "0" * 24,
            clustering_id="cl_" + "1" * 24,
            preprocessed_id="pp_x",
            dataset_id="ds_x",
            config_sha256="",
        )


def test_derive_dashboard_id_changes_with_inputs() -> None:
    base = {
        "segmentation_id": "seg_" + "0" * 24,
        "clustering_id": "cl_" + "1" * 24,
        "preprocessed_id": "pp_x",
        "dataset_id": "ds_x",
        "config_sha256": "a" * 64,
    }
    a = derive_dashboard_id(**base)
    b = derive_dashboard_id(**{**base, "config_sha256": "b" * 64})
    assert a != b


def test_canonical_payload_keys_locked() -> None:
    assert CANONICAL_PAYLOAD_KEYS == (
        "segmentation_id",
        "clustering_id",
        "preprocessed_id",
        "dataset_id",
        "schema_version",
        "config_sha256",
    )


# ---------------------------------------------------------------------------
# prototype_visualization_base_dir / prototype_visualization_run_dir
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_storage_root(tmp_path: Path) -> Path:
    return (tmp_path / "datasets").resolve()


def test_base_dir_layout(sample_storage_root: Path) -> None:
    base = prototype_visualization_base_dir(
        sample_storage_root,
        dataset_id="ds_x",
        preprocessed_id="pp_x",
        clustering_id="cl_" + "1" * 24,
        segmentation_id="seg_" + "0" * 24,
    )
    assert base.name == "visualization"
    assert "datasets" in base.parts
    assert "seg_" + "0" * 24 in base.parts


def test_base_dir_invalid_segmentation_id(sample_storage_root: Path) -> None:
    with pytest.raises(VisualizationStoragePathError, match="segmentation_id"):
        prototype_visualization_base_dir(
            sample_storage_root,
            dataset_id="ds_x",
            preprocessed_id="pp_x",
            clustering_id="cl_" + "1" * 24,
            segmentation_id="bad",
        )


def test_base_dir_invalid_clustering_id(sample_storage_root: Path) -> None:
    with pytest.raises(VisualizationStoragePathError, match="clustering_id"):
        prototype_visualization_base_dir(
            sample_storage_root,
            dataset_id="ds_x",
            preprocessed_id="pp_x",
            clustering_id="bad",
            segmentation_id="seg_" + "0" * 24,
        )


def test_base_dir_empty_dataset_id(sample_storage_root: Path) -> None:
    with pytest.raises(VisualizationStoragePathError, match="dataset_id"):
        prototype_visualization_base_dir(
            sample_storage_root,
            dataset_id="",
            preprocessed_id="pp_x",
            clustering_id="cl_" + "1" * 24,
            segmentation_id="seg_" + "0" * 24,
        )


def test_base_dir_empty_preprocessed_id(sample_storage_root: Path) -> None:
    with pytest.raises(VisualizationStoragePathError, match="preprocessed_id"):
        prototype_visualization_base_dir(
            sample_storage_root,
            dataset_id="ds_x",
            preprocessed_id="",
            clustering_id="cl_" + "1" * 24,
            segmentation_id="seg_" + "0" * 24,
        )


def test_run_dir_layout(sample_storage_root: Path) -> None:
    did = derive_dashboard_id(
        segmentation_id="seg_" + "0" * 24,
        clustering_id="cl_" + "1" * 24,
        preprocessed_id="pp_x",
        dataset_id="ds_x",
        config_sha256="a" * 64,
    )
    run_dir = prototype_visualization_run_dir(
        sample_storage_root,
        dataset_id="ds_x",
        preprocessed_id="pp_x",
        clustering_id="cl_" + "1" * 24,
        segmentation_id="seg_" + "0" * 24,
        dashboard_id=did,
    )
    assert run_dir.name == did


def test_run_dir_invalid_dashboard_id(sample_storage_root: Path) -> None:
    with pytest.raises(VisualizationStoragePathError, match="dashboard_id"):
        prototype_visualization_run_dir(
            sample_storage_root,
            dataset_id="ds_x",
            preprocessed_id="pp_x",
            clustering_id="cl_" + "1" * 24,
            segmentation_id="seg_" + "0" * 24,
            dashboard_id="bad",
        )


# ---------------------------------------------------------------------------
# resolve_storage_root — integration with DEV-02 config
# ---------------------------------------------------------------------------


def test_resolve_storage_root_uses_dev02_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """resolve_storage_root reads configs/dev02_dataset_management.yaml."""
    from customer_segmentation.prototype.visualization import storage as s

    # Patch the underlying loader to return a known root.
    sentinel = Path("/tmp/dev08_test_storage").resolve()
    called = {"v": False}

    def fake_load(path):
        called["v"] = True
        return {"storage_root": str(sentinel)}

    monkeypatch.setattr("customer_segmentation.dataset_management.storage.load_config", fake_load)
    root = s.resolve_storage_root()
    assert root == sentinel
    assert called["v"] is True
