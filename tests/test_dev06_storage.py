"""Tests for the DEV-06 storage, content-addressed identity, and idempotency."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from customer_segmentation.prototype.segmentation.scope import (
    NOISE_POLICIES,
    SEGMENTATION_MANIFEST_SCHEMA_VERSION,
)
from customer_segmentation.prototype.segmentation.storage import (
    _CLUSTERING_ID_RE,
    _SEGMENTATION_ID_RE,
    CANONICAL_PAYLOAD_KEYS,
    SEGMENTATION_ID_HEX_LEN,
    SEGMENTATION_ID_PREFIX,
    Dev06CollisionError,
    Dev06ManifestCorrupt,
    Dev06StoragePathError,
    compute_config_sha256,
    compute_feature_set_sha256,
    derive_segmentation_id,
    find_existing_segmentation,
    prototype_segmentation_base_dir,
    prototype_segmentation_run_dir,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _valid_kwargs() -> dict:
    """Return a baseline valid canonical kwarg set for tests."""
    return {
        "clustering_id": "cl_" + "0" * 24,
        "preprocessed_id": "pp_synthetic01",
        "dataset_id": "ds_synthetic01",
        "ml_dataset_sha256": "a" * 64,
        "feature_set_sha256": "b" * 64,
        "preprocessing_config_sha256": "c" * 64,
        "noise_policy": "exclude",
    }


# ---------------------------------------------------------------------------
# Id format / constants
# ---------------------------------------------------------------------------


def test_segmentation_id_prefix_constant() -> None:
    assert SEGMENTATION_ID_PREFIX == "seg_"


def test_segmentation_id_hex_length_constant() -> None:
    assert SEGMENTATION_ID_HEX_LEN == 24


def test_segmentation_id_regex_matches_24_hex() -> None:
    s = SEGMENTATION_ID_PREFIX + "0" * 24
    assert _SEGMENTATION_ID_RE.match(s) is not None
    assert _SEGMENTATION_ID_RE.match(SEGMENTATION_ID_PREFIX + "0" * 23) is None
    assert _SEGMENTATION_ID_RE.match(SEGMENTATION_ID_PREFIX + "Z" * 24) is None


def test_clustering_id_regex_unchanged_from_dev05() -> None:
    """Mirror DEV-05 cluster ID format (defence against cross-module drift)."""
    assert _CLUSTERING_ID_RE.match("cl_" + "0" * 24) is not None
    assert _CLUSTERING_ID_RE.match("cl_" + "0" * 23) is None
    assert _CLUSTERING_ID_RE.match("ev_" + "0" * 24) is None


def test_canonical_payload_keys_count_is_eight() -> None:
    """Per §4.3, segmentation_id is derived from exactly 8 canonical fields."""
    assert len(CANONICAL_PAYLOAD_KEYS) == 8


def test_canonical_payload_keys_order() -> None:
    """Canonical key order must match §4.3 enumeration."""
    assert CANONICAL_PAYLOAD_KEYS == (
        "clustering_id",
        "preprocessed_id",
        "dataset_id",
        "ml_dataset_sha256",
        "feature_set_sha256",
        "preprocessing_config_sha256",
        "noise_policy",
        "schema_version",
    )


def test_canonical_payload_keys_no_metric_set() -> None:
    """DEV-06 CompatibilityKey has NO metric_set (no metrics in DEV-06)."""
    assert "metric_set" not in CANONICAL_PAYLOAD_KEYS
    assert "metric_set_hash" not in CANONICAL_PAYLOAD_KEYS


def test_canonical_payload_keys_no_evaluation_id() -> None:
    """DEV-06 segmentation_id is derived from clustering + preprocessed only;
    evaluation_id (DEV-05) is optional provenance (not canonical key)."""
    assert "evaluation_id" not in CANONICAL_PAYLOAD_KEYS


def test_canonical_payload_types_match_keys() -> None:
    """``_CANONICAL_PAYLOAD_TYPES`` keys MUST equal ``CANONICAL_PAYLOAD_KEYS``.

    P2-4 fix: the dead ``"config_sha256"`` key was previously present in
    ``_CANONICAL_PAYLOAD_TYPES`` but absent from ``CANONICAL_PAYLOAD_KEYS``,
    so it was never validated and never used. This test pins the contract
    that the two sets are identical.
    """
    from customer_segmentation.prototype.segmentation.storage import (
        _CANONICAL_PAYLOAD_TYPES,
    )

    assert set(_CANONICAL_PAYLOAD_TYPES.keys()) == set(CANONICAL_PAYLOAD_KEYS)


def test_canonical_payload_types_does_not_contain_config_sha256() -> None:
    """``config_sha256`` is provenance-only, NOT a canonical key (plan §4.3)."""
    from customer_segmentation.prototype.segmentation.storage import (
        _CANONICAL_PAYLOAD_TYPES,
    )

    assert "config_sha256" not in _CANONICAL_PAYLOAD_TYPES
    assert "config_sha256" not in CANONICAL_PAYLOAD_KEYS


# ---------------------------------------------------------------------------
# compute_config_sha256
# ---------------------------------------------------------------------------


def test_compute_config_sha256_deterministic() -> None:
    h1 = compute_config_sha256("hello world")
    h2 = compute_config_sha256("hello world")
    assert h1 == h2


def test_compute_config_sha256_changes_with_input() -> None:
    h1 = compute_config_sha256("hello world")
    h2 = compute_config_sha256("hello WORLD")
    assert h1 != h2


def test_compute_config_sha256_64_hex_chars() -> None:
    h = compute_config_sha256("anything")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_compute_config_sha256_matches_hashlib() -> None:
    text = "abc: 1\n"
    assert compute_config_sha256(text) == hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# compute_feature_set_sha256
# ---------------------------------------------------------------------------


def test_compute_feature_set_sha256_list() -> None:
    h = compute_feature_set_sha256(["Recency", "Frequency", "Monetary"])
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_compute_feature_set_sha256_tuple() -> None:
    h1 = compute_feature_set_sha256(("Recency", "Frequency", "Monetary"))
    h2 = compute_feature_set_sha256(["Recency", "Frequency", "Monetary"])
    assert h1 == h2


def test_compute_feature_set_sha256_order_independent() -> None:
    """Hash must be order-independent (sorted before joining)."""
    h1 = compute_feature_set_sha256(["Recency", "Frequency", "Monetary"])
    h2 = compute_feature_set_sha256(["Monetary", "Recency", "Frequency"])
    assert h1 == h2


def test_compute_feature_set_sha256_set_input() -> None:
    h_set = compute_feature_set_sha256({"Recency", "Frequency"})
    h_list = compute_feature_set_sha256(["Recency", "Frequency"])
    assert h_set == h_list


def test_compute_feature_set_sha256_empty_raises() -> None:
    with pytest.raises(Dev06StoragePathError, match="non-empty"):
        compute_feature_set_sha256([])


def test_compute_feature_set_sha256_single_element() -> None:
    h = compute_feature_set_sha256(["Recency"])
    assert len(h) == 64


def test_compute_feature_set_sha256_uses_pipe_delimiter() -> None:
    """Verify the join delimiter (for stability across reorderings)."""
    h1 = compute_feature_set_sha256(["A", "B"])
    h2 = compute_feature_set_sha256(["AB"])
    assert h1 != h2  # delimiter ensures 'A|B' != 'AB'


# ---------------------------------------------------------------------------
# derive_segmentation_id
# ---------------------------------------------------------------------------


def test_derive_segmentation_id_basic() -> None:
    kwargs = _valid_kwargs()
    sid = derive_segmentation_id(**kwargs)
    assert sid.startswith(SEGMENTATION_ID_PREFIX)
    assert len(sid) == len(SEGMENTATION_ID_PREFIX) + SEGMENTATION_ID_HEX_LEN


def test_derive_segmentation_id_deterministic() -> None:
    kwargs = _valid_kwargs()
    s1 = derive_segmentation_id(**kwargs)
    s2 = derive_segmentation_id(**kwargs)
    assert s1 == s2


def test_derive_segmentation_id_changes_with_clustering() -> None:
    kwargs = _valid_kwargs()
    s1 = derive_segmentation_id(**kwargs)
    kwargs2 = _valid_kwargs()
    kwargs2["clustering_id"] = "cl_" + "1" * 24
    s2 = derive_segmentation_id(**kwargs2)
    assert s1 != s2


def test_derive_segmentation_id_changes_with_feature_set() -> None:
    kwargs = _valid_kwargs()
    s1 = derive_segmentation_id(**kwargs)
    kwargs2 = _valid_kwargs()
    kwargs2["feature_set_sha256"] = "f" * 64
    s2 = derive_segmentation_id(**kwargs2)
    assert s1 != s2


def test_derive_segmentation_id_changes_with_noise_policy() -> None:
    """Same clustering + same feature_set but different noise policy ⇒
    different segmentation_id."""
    kwargs = _valid_kwargs()
    s1 = derive_segmentation_id(**kwargs)
    kwargs2 = _valid_kwargs()
    kwargs2["noise_policy"] = "include"
    s2 = derive_segmentation_id(**kwargs2)
    assert s1 != s2


def test_derive_segmentation_id_changes_with_schema_version() -> None:
    """Schema bump must invalidate old segmentation_ids."""
    kwargs = _valid_kwargs()
    s1 = derive_segmentation_id(**kwargs)
    s2 = derive_segmentation_id(**kwargs, schema_version="1.0.1")
    assert s1 != s2


def test_derive_segmentation_id_rejects_invalid_clustering_id() -> None:
    kwargs = _valid_kwargs()
    kwargs["clustering_id"] = "cl_BADHEX"
    with pytest.raises(Dev06StoragePathError):
        derive_segmentation_id(**kwargs)


def test_derive_segmentation_id_rejects_invalid_noise_policy() -> None:
    kwargs = _valid_kwargs()
    kwargs["noise_policy"] = "maybe"
    with pytest.raises(Dev06StoragePathError):
        derive_segmentation_id(**kwargs)


def test_derive_segmentation_id_rejects_empty_feature_set_sha256() -> None:
    kwargs = _valid_kwargs()
    kwargs["feature_set_sha256"] = ""
    with pytest.raises(Dev06StoragePathError):
        derive_segmentation_id(**kwargs)


def test_derive_segmentation_id_accepts_both_noise_policies() -> None:
    for p in NOISE_POLICIES:
        kwargs = _valid_kwargs()
        kwargs["noise_policy"] = p
        sid = derive_segmentation_id(**kwargs)
        assert sid.startswith(SEGMENTATION_ID_PREFIX)


def test_derive_segmentation_id_default_schema_version_pinned() -> None:
    """The default schema_version must be the pinned constant."""
    kwargs = _valid_kwargs()
    s_default = derive_segmentation_id(**kwargs)
    s_pinned = derive_segmentation_id(**kwargs, schema_version=SEGMENTATION_MANIFEST_SCHEMA_VERSION)
    assert s_default == s_pinned


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def test_prototype_segmentation_base_dir(tmp_path: Path) -> None:
    base = prototype_segmentation_base_dir(
        tmp_path,
        dataset_id="ds_x",
        preprocessed_id="pp_x",
        clustering_id="cl_" + "0" * 24,
    )
    expected = (
        tmp_path
        / "ds_x"
        / "preprocessed"
        / "pp_x"
        / "clustering"
        / ("cl_" + "0" * 24)
        / "segmentation"
    )
    assert base == expected.resolve()


def test_prototype_segmentation_run_dir(tmp_path: Path) -> None:
    run = prototype_segmentation_run_dir(
        tmp_path,
        dataset_id="ds_x",
        preprocessed_id="pp_x",
        clustering_id="cl_" + "0" * 24,
        segmentation_id=SEGMENTATION_ID_PREFIX + "1" * 24,
    )
    assert run.name == SEGMENTATION_ID_PREFIX + "1" * 24
    assert run.parent.name == "segmentation"


def test_prototype_segmentation_base_dir_rejects_bad_clustering_id(tmp_path: Path) -> None:
    with pytest.raises(Dev06StoragePathError):
        prototype_segmentation_base_dir(
            tmp_path, dataset_id="ds", preprocessed_id="pp", clustering_id="bad"
        )


def test_prototype_segmentation_run_dir_rejects_bad_segmentation_id(tmp_path: Path) -> None:
    with pytest.raises(Dev06StoragePathError):
        prototype_segmentation_run_dir(
            tmp_path,
            dataset_id="ds",
            preprocessed_id="pp",
            clustering_id="cl_" + "0" * 24,
            segmentation_id="not-a-seg-id",
        )


def test_prototype_segmentation_base_dir_rejects_empty_dataset_id(tmp_path: Path) -> None:
    with pytest.raises(Dev06StoragePathError):
        prototype_segmentation_base_dir(
            tmp_path, dataset_id="", preprocessed_id="pp", clustering_id="cl_" + "0" * 24
        )


# ---------------------------------------------------------------------------
# Idempotency lookup
# ---------------------------------------------------------------------------


def _write_segmentation_manifest(
    run_dir: Path,
    *,
    clustering_id: str = "cl_" + "0" * 24,
    preprocessed_id: str = "pp_synthetic01",
    dataset_id: str = "ds_synthetic01",
    ml_dataset_sha256: str = "a" * 64,
    feature_set_sha256: str = "b" * 64,
    preprocessing_config_sha256: str = "c" * 64,
    config_sha256: str = "d" * 64,
    noise_policy: str = "exclude",
    schema_version: str = SEGMENTATION_MANIFEST_SCHEMA_VERSION,
) -> Path:
    """Write a minimal valid segmentation manifest JSON in run_dir."""
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": schema_version,
        "clustering_id": clustering_id,
        "preprocessed_id": preprocessed_id,
        "dataset_id": dataset_id,
        "ml_dataset_sha256": ml_dataset_sha256,
        "feature_set_sha256": feature_set_sha256,
        "preprocessing_config_sha256": preprocessing_config_sha256,
        "config_sha256": config_sha256,
        "noise_policy": noise_policy,
    }
    p = run_dir / "segmentation_manifest.json"
    with p.open("w", encoding="utf-8") as fh:
        json.dump(manifest, fh)
    return p


def test_find_existing_segmentation_missing(tmp_path: Path) -> None:
    base = tmp_path / "seg-base"
    expected = _build_expected_canonical()
    found, path = find_existing_segmentation(
        base_dir=base, segmentation_id="seg_" + "0" * 24, expected_canonical=expected
    )
    assert found is False
    assert path is None


def test_find_existing_segmentation_match(tmp_path: Path) -> None:
    sid = "seg_" + "0" * 24
    base = tmp_path / "seg-base"
    run_dir = base / sid
    _write_segmentation_manifest(run_dir)
    expected = _build_expected_canonical()
    found, path = find_existing_segmentation(
        base_dir=base, segmentation_id=sid, expected_canonical=expected
    )
    assert found is True
    assert path == (run_dir / "segmentation_manifest.json")


def test_find_existing_segmentation_collision_raises(tmp_path: Path) -> None:
    """Same segmentation_id but different canonical ⇒ collision error."""
    sid = "seg_" + "0" * 24
    base = tmp_path / "seg-base"
    run_dir = base / sid
    _write_segmentation_manifest(run_dir, ml_dataset_sha256="z" * 64)  # different
    expected = _build_expected_canonical()
    with pytest.raises(Dev06CollisionError):
        find_existing_segmentation(base_dir=base, segmentation_id=sid, expected_canonical=expected)


def test_find_existing_segmentation_corrupt_json(tmp_path: Path) -> None:
    sid = "seg_" + "0" * 24
    base = tmp_path / "seg-base"
    run_dir = base / sid
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "segmentation_manifest.json").write_text("{invalid json")
    expected = _build_expected_canonical()
    with pytest.raises(Dev06ManifestCorrupt):
        find_existing_segmentation(base_dir=base, segmentation_id=sid, expected_canonical=expected)


def test_find_existing_segmentation_corrupt_missing_key(tmp_path: Path) -> None:
    """Missing canonical key in stored manifest ⇒ manifest-corrupt error."""
    sid = "seg_" + "0" * 24
    base = tmp_path / "seg-base"
    run_dir = base / sid
    run_dir.mkdir(parents=True, exist_ok=True)
    # Omit preprocessing_config_sha256
    incomplete = {
        "schema_version": SEGMENTATION_MANIFEST_SCHEMA_VERSION,
        "clustering_id": "cl_" + "0" * 24,
        "preprocessed_id": "pp_synthetic01",
        "dataset_id": "ds_synthetic01",
        "ml_dataset_sha256": "a" * 64,
        "feature_set_sha256": "b" * 64,
        "config_sha256": "d" * 64,
        "noise_policy": "exclude",
    }
    with (run_dir / "segmentation_manifest.json").open("w", encoding="utf-8") as fh:
        json.dump(incomplete, fh)
    expected = _build_expected_canonical()
    with pytest.raises(Dev06ManifestCorrupt):
        find_existing_segmentation(base_dir=base, segmentation_id=sid, expected_canonical=expected)


def test_find_existing_segmentation_invalid_segmentation_id(tmp_path: Path) -> None:
    base = tmp_path / "seg-base"
    expected = _build_expected_canonical()
    with pytest.raises(Dev06StoragePathError):
        find_existing_segmentation(
            base_dir=base, segmentation_id="bad-id", expected_canonical=expected
        )


def test_find_existing_segmentation_schema_version_mismatch(tmp_path: Path) -> None:
    """Old schema_version in stored manifest ⇒ manifest-corrupt error."""
    sid = "seg_" + "0" * 24
    base = tmp_path / "seg-base"
    run_dir = base / sid
    _write_segmentation_manifest(run_dir, schema_version="0.9.0")
    expected = _build_expected_canonical()
    with pytest.raises(Dev06ManifestCorrupt) as exc_info:
        find_existing_segmentation(base_dir=base, segmentation_id=sid, expected_canonical=expected)
    # P2-5: the error message MUST mention --force-rerun as the recovery
    # path (per plan §14.2.6 / §9.2 schema-version recovery contract).
    assert "--force-rerun" in str(exc_info.value)


def test_find_existing_segmentation_schema_version_mismatch_mentions_expected_version(
    tmp_path: Path,
) -> None:
    """P2-5: schema-version error message names BOTH the stored and the
    expected schema version, so an operator can decide whether to
    ``--force-rerun`` (migration) or treat as corruption."""
    sid = "seg_" + "0" * 24
    base = tmp_path / "seg-base"
    run_dir = base / sid
    _write_segmentation_manifest(run_dir, schema_version="0.7.5")
    expected = _build_expected_canonical()
    with pytest.raises(Dev06ManifestCorrupt) as exc_info:
        find_existing_segmentation(base_dir=base, segmentation_id=sid, expected_canonical=expected)
    msg = str(exc_info.value)
    assert "0.7.5" in msg, "stored schema version 0.7.5 must be in error message"
    assert (
        SEGMENTATION_MANIFEST_SCHEMA_VERSION in msg
    ), "current schema version must be in error message"


def test_find_existing_segmentation_json_corrupt_does_NOT_suggest_force_rerun(
    tmp_path: Path,
) -> None:
    """P2-5: schema-version mismatch and JSON corruption are
    semantically different and produce distinguishable error messages.

    A JSON corruption suggests investigation (not a migration); the
    error message MUST NOT suggest ``--force-rerun`` as the recovery
    because that would silently overwrite a potentially-salvageable
    artefact with a fresh re-compute.
    """
    sid = "seg_" + "0" * 24
    base = tmp_path / "seg-base"
    run_dir = base / sid
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "segmentation_manifest.json").write_text("{invalid json")
    expected = _build_expected_canonical()
    with pytest.raises(Dev06ManifestCorrupt) as exc_info:
        find_existing_segmentation(base_dir=base, segmentation_id=sid, expected_canonical=expected)
    msg = str(exc_info.value)
    # JSON corruption message MUST NOT propose --force-rerun (different
    # recovery path: investigate, restore from backup, etc.).
    assert "--force-rerun" not in msg, (
        "JSON corruption must not suggest --force-rerun; the two cases "
        "are semantically different (see plan §14.2.6 recovery contract)."
    )


# ---------------------------------------------------------------------------
# Helpers for find_existing_segmentation tests
# ---------------------------------------------------------------------------


def _build_expected_canonical() -> dict:
    """Return a canonical 8-field payload matching _write_segmentation_manifest defaults."""
    return {
        "clustering_id": "cl_" + "0" * 24,
        "preprocessed_id": "pp_synthetic01",
        "dataset_id": "ds_synthetic01",
        "ml_dataset_sha256": "a" * 64,
        "feature_set_sha256": "b" * 64,
        "preprocessing_config_sha256": "c" * 64,
        "config_sha256": "d" * 64,
        "noise_policy": "exclude",
        "schema_version": SEGMENTATION_MANIFEST_SCHEMA_VERSION,
    }
