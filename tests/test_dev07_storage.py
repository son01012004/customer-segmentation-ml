"""Tests for DEV-07 storage, content-addressed identity, and idempotency."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from customer_segmentation.prototype.marketing.exceptions import (
    MarketingCollisionError,
    MarketingManifestCorrupt,
    MarketingStoragePathError,
)
from customer_segmentation.prototype.marketing.storage import (
    CANONICAL_PAYLOAD_KEYS,
    MARKETING_ID_HEX_LEN,
    MARKETING_ID_PREFIX,
    compute_config_sha256,
    derive_marketing_id,
    find_existing_marketing,
    prototype_marketing_base_dir,
    prototype_marketing_run_dir,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_marketing_id_prefix() -> None:
    assert MARKETING_ID_PREFIX == "mkt_"


def test_marketing_id_hex_len() -> None:
    assert MARKETING_ID_HEX_LEN == 24


def test_canonical_payload_keys_count() -> None:
    assert len(CANONICAL_PAYLOAD_KEYS) == 9
    assert "segmentation_id" in CANONICAL_PAYLOAD_KEYS
    assert "mkt_framework_version" in CANONICAL_PAYLOAD_KEYS
    assert "mkt_framework_found" in CANONICAL_PAYLOAD_KEYS
    assert "schema_version" in CANONICAL_PAYLOAD_KEYS


# ---------------------------------------------------------------------------
# compute_config_sha256
# ---------------------------------------------------------------------------


def test_compute_config_sha256_deterministic() -> None:
    h1 = compute_config_sha256("hello world")
    h2 = compute_config_sha256("hello world")
    assert h1 == h2


def test_compute_config_sha256_changes_with_text() -> None:
    assert compute_config_sha256("a") != compute_config_sha256("b")


def test_compute_config_sha256_returns_64_hex() -> None:
    h = compute_config_sha256("test")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


# ---------------------------------------------------------------------------
# derive_marketing_id — happy path
# ---------------------------------------------------------------------------


def _valid_canonical_kwargs() -> dict:
    return {
        "segmentation_id": "seg_" + "a" * 24,
        "clustering_id": "cl_" + "b" * 24,
        "preprocessed_id": "pp_test",
        "dataset_id": "ds_test",
        "segmentation_manifest_sha256": "c" * 64,
        "mkt_framework_version": None,
        "mkt_framework_found": False,
        "noise_policy_used": "exclude",
    }


def test_derive_marketing_id_happy_path() -> None:
    mid = derive_marketing_id(**_valid_canonical_kwargs())
    assert mid.startswith(MARKETING_ID_PREFIX)
    assert len(mid) == len(MARKETING_ID_PREFIX) + MARKETING_ID_HEX_LEN
    assert all(c in "0123456789abcdef" for c in mid[len(MARKETING_ID_PREFIX) :])


def test_derive_marketing_id_deterministic() -> None:
    kw = _valid_canonical_kwargs()
    assert derive_marketing_id(**kw) == derive_marketing_id(**kw)


def test_derive_marketing_id_changes_with_input() -> None:
    kw1 = _valid_canonical_kwargs()
    kw2 = _valid_canonical_kwargs()
    kw2["dataset_id"] = "ds_other"
    assert derive_marketing_id(**kw1) != derive_marketing_id(**kw2)


def test_derive_marketing_id_changes_with_mkt_framework() -> None:
    kw1 = _valid_canonical_kwargs()
    kw2 = _valid_canonical_kwargs()
    kw2["mkt_framework_version"] = "MKT-01..05__v1"
    kw2["mkt_framework_found"] = True
    assert derive_marketing_id(**kw1) != derive_marketing_id(**kw2)


def test_derive_marketing_id_changes_with_schema_version() -> None:
    kw1 = _valid_canonical_kwargs()
    kw2 = _valid_canonical_kwargs()
    kw2["schema_version"] = "0.9.0"
    assert derive_marketing_id(**kw1) != derive_marketing_id(**kw2)


# ---------------------------------------------------------------------------
# derive_marketing_id — validation
# ---------------------------------------------------------------------------


def test_derive_marketing_id_rejects_bad_segmentation_id() -> None:
    kw = _valid_canonical_kwargs()
    kw["segmentation_id"] = "seg_BAD"
    with pytest.raises(MarketingStoragePathError, match="segmentation_id"):
        derive_marketing_id(**kw)


def test_derive_marketing_id_rejects_bad_clustering_id() -> None:
    kw = _valid_canonical_kwargs()
    kw["clustering_id"] = "cl_BAD"
    with pytest.raises(MarketingStoragePathError, match="clustering_id"):
        derive_marketing_id(**kw)


def test_derive_marketing_id_rejects_bad_noise_policy() -> None:
    kw = _valid_canonical_kwargs()
    kw["noise_policy_used"] = "maybe"
    with pytest.raises(MarketingStoragePathError, match="noise_policy_used"):
        derive_marketing_id(**kw)


def test_derive_marketing_id_rejects_non_bool_mkt_found() -> None:
    kw = _valid_canonical_kwargs()
    kw["mkt_framework_found"] = "yes"  # type: ignore[arg-type]
    with pytest.raises(MarketingStoragePathError, match="mkt_framework_found"):
        derive_marketing_id(**kw)


def test_derive_marketing_id_rejects_empty_strings() -> None:
    kw = _valid_canonical_kwargs()
    kw["dataset_id"] = ""
    with pytest.raises(MarketingStoragePathError, match="dataset_id"):
        derive_marketing_id(**kw)


# ---------------------------------------------------------------------------
# prototype_marketing_base_dir
# ---------------------------------------------------------------------------


def test_prototype_marketing_base_dir_layout(tmp_path: Path) -> None:
    base = prototype_marketing_base_dir(
        storage_root=tmp_path,
        dataset_id="ds",
        preprocessed_id="pp",
        clustering_id="cl_" + "1" * 24,
        segmentation_id="seg_" + "0" * 24,
    )
    assert base.is_absolute()
    assert "marketing" in str(base)
    assert str(base).endswith("/marketing") or str(base).endswith("\\marketing")


def test_prototype_marketing_base_dir_rejects_bad_clustering() -> None:
    with pytest.raises(MarketingStoragePathError):
        prototype_marketing_base_dir(
            storage_root=Path("/tmp"),
            dataset_id="ds",
            preprocessed_id="pp",
            clustering_id="bad",
            segmentation_id="seg_" + "0" * 24,
        )


def test_prototype_marketing_base_dir_rejects_bad_segmentation() -> None:
    with pytest.raises(MarketingStoragePathError):
        prototype_marketing_base_dir(
            storage_root=Path("/tmp"),
            dataset_id="ds",
            preprocessed_id="pp",
            clustering_id="cl_" + "1" * 24,
            segmentation_id="bad",
        )


# ---------------------------------------------------------------------------
# prototype_marketing_run_dir
# ---------------------------------------------------------------------------


def test_prototype_marketing_run_dir_layout(tmp_path: Path) -> None:
    rd = prototype_marketing_run_dir(
        storage_root=tmp_path,
        dataset_id="ds",
        preprocessed_id="pp",
        clustering_id="cl_" + "1" * 24,
        segmentation_id="seg_" + "0" * 24,
        marketing_id="mkt_" + "0" * 24,
    )
    assert rd.is_absolute()
    assert str(rd).endswith("/mkt_" + "0" * 24) or str(rd).endswith("\\mkt_" + "0" * 24)


def test_prototype_marketing_run_dir_rejects_bad_marketing_id() -> None:
    with pytest.raises(MarketingStoragePathError):
        prototype_marketing_run_dir(
            storage_root=Path("/tmp"),
            dataset_id="ds",
            preprocessed_id="pp",
            clustering_id="cl_" + "1" * 24,
            segmentation_id="seg_" + "0" * 24,
            marketing_id="bad",
        )


# ---------------------------------------------------------------------------
# find_existing_marketing — idempotency
# ---------------------------------------------------------------------------


def test_find_existing_marketing_missing(tmp_path: Path) -> None:
    base = tmp_path / "mkt_base"
    found, path = find_existing_marketing(
        base_dir=base,
        marketing_id="mkt_" + "0" * 24,
        expected_canonical={
            "segmentation_id": "seg_" + "0" * 24,
            "clustering_id": "cl_" + "0" * 24,
            "preprocessed_id": "pp",
            "dataset_id": "ds",
            "segmentation_manifest_sha256": "a" * 64,
            "mkt_framework_version": None,
            "mkt_framework_found": False,
            "noise_policy_used": "exclude",
            "schema_version": "1.0.0",
        },
    )
    assert found is False
    assert path is None


def test_find_existing_marketing_match(tmp_path: Path) -> None:
    base = tmp_path / "mkt_base"
    run_dir = base / ("mkt_" + "0" * 24)
    run_dir.mkdir(parents=True)
    manifest = {
        "schema_version": "1.0.0",
        "segmentation_id": "seg_" + "0" * 24,
        "clustering_id": "cl_" + "0" * 24,
        "preprocessed_id": "pp",
        "dataset_id": "ds",
        "segmentation_manifest_sha256": "a" * 64,
        "mkt_framework_version": None,
        "mkt_framework_found": False,
        "noise_policy_used": "exclude",
        "source_framework_version": None,
    }
    (run_dir / "marketing_manifest.json").write_text(json.dumps(manifest))
    found, path = find_existing_marketing(
        base_dir=base,
        marketing_id="mkt_" + "0" * 24,
        expected_canonical={
            "segmentation_id": "seg_" + "0" * 24,
            "clustering_id": "cl_" + "0" * 24,
            "preprocessed_id": "pp",
            "dataset_id": "ds",
            "segmentation_manifest_sha256": "a" * 64,
            "mkt_framework_version": None,
            "mkt_framework_found": False,
            "noise_policy_used": "exclude",
            "schema_version": "1.0.0",
        },
    )
    assert found is True
    assert path is not None
    assert path.name == "marketing_manifest.json"


def test_find_existing_marketing_collision(tmp_path: Path) -> None:
    """Different canonical payload → MarketingCollisionError."""
    base = tmp_path / "mkt_base"
    run_dir = base / ("mkt_" + "0" * 24)
    run_dir.mkdir(parents=True)
    manifest = {
        "schema_version": "1.0.0",
        "segmentation_id": "seg_" + "0" * 24,
        "clustering_id": "cl_" + "0" * 24,
        "preprocessed_id": "pp",
        "dataset_id": "ds_OTHER",  # differs
        "segmentation_manifest_sha256": "a" * 64,
        "mkt_framework_version": None,
        "mkt_framework_found": False,
        "noise_policy_used": "exclude",
        "source_framework_version": None,
    }
    (run_dir / "marketing_manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(MarketingCollisionError, match="dataset_id"):
        find_existing_marketing(
            base_dir=base,
            marketing_id="mkt_" + "0" * 24,
            expected_canonical={
                "segmentation_id": "seg_" + "0" * 24,
                "clustering_id": "cl_" + "0" * 24,
                "preprocessed_id": "pp",
                "dataset_id": "ds",
                "segmentation_manifest_sha256": "a" * 64,
                "mkt_framework_version": None,
                "mkt_framework_found": False,
                "noise_policy_used": "exclude",
                "schema_version": "1.0.0",
            },
        )


def test_find_existing_marketing_corrupt(tmp_path: Path) -> None:
    base = tmp_path / "mkt_base"
    run_dir = base / ("mkt_" + "0" * 24)
    run_dir.mkdir(parents=True)
    (run_dir / "marketing_manifest.json").write_text("{not json")
    with pytest.raises(MarketingManifestCorrupt):
        find_existing_marketing(
            base_dir=base,
            marketing_id="mkt_" + "0" * 24,
            expected_canonical={
                "segmentation_id": "seg_" + "0" * 24,
                "clustering_id": "cl_" + "0" * 24,
                "preprocessed_id": "pp",
                "dataset_id": "ds",
                "segmentation_manifest_sha256": "a" * 64,
                "mkt_framework_version": None,
                "mkt_framework_found": False,
                "noise_policy_used": "exclude",
                "schema_version": "1.0.0",
            },
        )
