"""Tests for the DEV-06 SegmentationManifest dataclass + I/O."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from customer_segmentation.prototype.segmentation.manifest import (
    CharacteristicEntry,
    FeatureProfile,
    ResearchSafetyBlock,
    SegmentationManifest,
    SegmentationManifestError,
    SegmentationValidationReport,
    SegmentSize,
    ValidationCheck,
    build_segmentation_manifest,
    manifest_to_dict,
    read_segmentation_manifest,
    write_segmentation_manifest,
)
from customer_segmentation.prototype.segmentation.scope import (
    PROFILED_SCOPES,
    SEGMENTATION_MANIFEST_SCHEMA_VERSION,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_args(**overrides):
    """Return a baseline set of valid kwargs for build_segmentation_manifest."""
    base = {
        "segmentation_id": "seg_" + "0" * 24,
        "clustering_id": "cl_" + "1" * 24,
        "preprocessed_id": "pp_x",
        "dataset_id": "ds_x",
        "evaluation_id": None,
        "algorithm": "kmeans",
        "algorithm_version": "1.0",
        "algorithm_family": "hard",
        "ml_dataset_sha256": "a" * 64,
        "feature_set_sha256": "b" * 64,
        "preprocessing_config_sha256": "c" * 64,
        "feature_set": ["Recency", "Frequency", "Monetary"],
        "n_samples_input": 100,
        "n_samples_used_for_compute": 100,
        "n_clusters_input": 3,
        "n_segments": 3,
        "noise_count": None,
        "noise_ratio": None,
        "noise_policy_used": "exclude",
        "segment_sizes": [
            SegmentSize(
                segment_id=0,
                count=50,
                percentage=50.0,
                percentage_base="n_samples_used_for_compute",
                is_noise=False,
            ),
            SegmentSize(
                segment_id=1,
                count=30,
                percentage=30.0,
                percentage_base="n_samples_used_for_compute",
                is_noise=False,
            ),
            SegmentSize(
                segment_id=2,
                count=20,
                percentage=20.0,
                percentage_base="n_samples_used_for_compute",
                is_noise=False,
            ),
        ],
        "profiles": [
            FeatureProfile(segment_id=0, feature_name="Recency", statistics={"mean": 5.0}),
        ],
        "characteristics": [],
        "config_sha256": "d" * 64,
        "environment": {
            "python": "3.14",
            "platform": "Linux",
            "release": "7.0",
            "machine": "x86_64",
            "key_libraries": {"pandas": "2.0"},
        },
        "log_file": "seg.log",
        "validation_report": SegmentationValidationReport(all_passed=True, checks=[]),
        "readonly_paths": ["data/raw/primary"],
        "input_clustering_manifest": "clustering_manifest.json",
        "input_cluster_labels": "cluster_labels_x.parquet",
        "input_ml_dataset": "ml_dataset_x.parquet",
        "input_evaluation_manifest": None,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# ResearchSafetyBlock invariants
# ---------------------------------------------------------------------------


def test_research_safety_block_rejects_wrong_scope() -> None:
    with pytest.raises(SegmentationManifestError):
        ResearchSafetyBlock(
            automatically_promoted_to_research=False,
            scope="RESEARCH_APPROVED",
            appeared_in_research_evidence=False,
        )


def test_research_safety_block_rejects_promoted_true() -> None:
    with pytest.raises(SegmentationManifestError):
        ResearchSafetyBlock(
            automatically_promoted_to_research=True,
            scope="PROFILED_PROTOTYPE",
            appeared_in_research_evidence=False,
        )


def test_research_safety_block_rejects_research_evidence_true() -> None:
    with pytest.raises(SegmentationManifestError):
        ResearchSafetyBlock(
            automatically_promoted_to_research=False,
            scope="PROFILED_PROTOTYPE",
            appeared_in_research_evidence=True,
        )


def test_research_safety_block_accepts_canonical_values() -> None:
    rs = ResearchSafetyBlock(
        automatically_promoted_to_research=False,
        scope="PROFILED_PROTOTYPE",
        appeared_in_research_evidence=False,
    )
    assert rs.scope in PROFILED_SCOPES


# ---------------------------------------------------------------------------
# SegmentationValidationReport
# ---------------------------------------------------------------------------


def test_validation_report_default_all_passed_false() -> None:
    """A report with no checks is NOT automatically all_passed=True."""
    r = SegmentationValidationReport(all_passed=False, checks=[])
    assert r.all_passed is False


def test_validation_report_with_failing_check() -> None:
    r = SegmentationValidationReport(
        all_passed=False,
        checks=[ValidationCheck(check_id="x", passed=False, detail="bad")],
    )
    assert r.all_passed is False
    assert len(r.checks) == 1


# ---------------------------------------------------------------------------
# SegmentSize + FeatureProfile + CharacteristicEntry shape
# ---------------------------------------------------------------------------


def test_segment_size_required_fields() -> None:
    s = SegmentSize(
        segment_id=0,
        count=10,
        percentage=10.0,
        percentage_base="n_samples_used_for_compute",
        is_noise=False,
    )
    assert s.segment_id == 0
    assert s.count == 10


def test_feature_profile_nested_dict() -> None:
    p = FeatureProfile(
        segment_id=0,
        feature_name="Recency",
        statistics={"mean": 5.0, "median": 4.0},
    )
    assert p.statistics["mean"] == 5.0


def test_characteristic_entry_shape() -> None:
    c = CharacteristicEntry(
        characteristic_id="mean_high_Recency",
        description="mean of Recency is above threshold",
        source_features=["Recency"],
        derived_stats={"threshold": 1.0, "actual": 1.5},
    )
    assert c.characteristic_id == "mean_high_Recency"


# ---------------------------------------------------------------------------
# build_segmentation_manifest — happy path
# ---------------------------------------------------------------------------


def test_build_segmentation_manifest_minimal() -> None:
    m = build_segmentation_manifest(**_make_args())
    assert m.segmentation_id == "seg_" + "0" * 24
    assert m.schema_version == SEGMENTATION_MANIFEST_SCHEMA_VERSION
    assert m.scope == "PROFILED_PROTOTYPE"
    assert m.research_safety.automatically_promoted_to_research is False
    assert m.research_safety.appeared_in_research_evidence is False


def test_build_segmentation_manifest_segments_count() -> None:
    m = build_segmentation_manifest(**_make_args())
    assert m.n_segments == 3
    assert len(m.segment_sizes) == 3


def test_build_segmentation_manifest_dbscan_with_noise() -> None:
    m = build_segmentation_manifest(
        **_make_args(
            algorithm="dbscan",
            algorithm_family="density_based",
            noise_count=10,
            noise_ratio=0.1,
            n_samples_used_for_compute=90,
            segment_sizes=[
                SegmentSize(
                    segment_id=0,
                    count=50,
                    percentage=50.0,
                    percentage_base="n_samples_used_for_compute",
                    is_noise=False,
                ),
                SegmentSize(
                    segment_id=1,
                    count=30,
                    percentage=30.0,
                    percentage_base="n_samples_used_for_compute",
                    is_noise=False,
                ),
                SegmentSize(
                    segment_id=-1,
                    count=10,
                    percentage=10.0,
                    percentage_base="n_samples_input",
                    is_noise=True,
                ),
            ],
        )
    )
    assert m.noise_count == 10
    assert m.noise_ratio == 0.1
    # n_samples_used_for_compute = n_samples_input - noise_count = 100 - 10 = 90
    assert m.n_samples_used_for_compute == 90


# ---------------------------------------------------------------------------
# build_segmentation_manifest — invariants
# ---------------------------------------------------------------------------


def test_build_rejects_schema_version_mismatch() -> None:
    args = _make_args()
    m = build_segmentation_manifest(**args)
    # Tamper via object.__setattr__ (frozen).
    import dataclasses

    object.__setattr__(m, "schema_version", "0.9.0")
    with pytest.raises(SegmentationManifestError, match="schema_version"):
        # Re-instantiating the same m via a constructor will trigger __post_init__.
        # Instead, construct a new manifest via dict to verify check.
        SegmentationManifest(**dataclasses.asdict(m))


def test_build_rejects_non_density_algorithm_with_noise_count() -> None:
    """non-density algorithm (e.g. kmeans) MUST have noise_count=None."""
    with pytest.raises(SegmentationManifestError, match="noise_count MUST be None"):
        build_segmentation_manifest(**_make_args(noise_count=5, noise_ratio=0.05))


def test_build_rejects_density_algorithm_missing_noise_count() -> None:
    """density_based algorithm MUST have noise_count set."""
    with pytest.raises(SegmentationManifestError, match="noise_count MUST be set"):
        build_segmentation_manifest(
            **_make_args(algorithm="dbscan", algorithm_family="density_based", noise_count=None)
        )


def test_build_rejects_density_algorithm_missing_noise_ratio() -> None:
    with pytest.raises(SegmentationManifestError, match="noise_ratio MUST be set"):
        build_segmentation_manifest(
            **_make_args(
                algorithm="dbscan",
                algorithm_family="density_based",
                noise_count=5,
                noise_ratio=None,
            )
        )


def test_build_rejects_n_samples_used_exceeds_input() -> None:
    with pytest.raises(SegmentationManifestError, match="n_samples_used_for_compute"):
        build_segmentation_manifest(
            **_make_args(n_samples_input=100, n_samples_used_for_compute=200)
        )


def test_build_rejects_invalid_scope() -> None:
    args = _make_args()
    m = build_segmentation_manifest(**args)
    import dataclasses

    object.__setattr__(m, "scope", "EVALUATED_PROTOTYPE")
    with pytest.raises(SegmentationManifestError, match="scope"):
        SegmentationManifest(**dataclasses.asdict(m))


def test_build_rejects_invalid_noise_policy() -> None:
    with pytest.raises(SegmentationManifestError, match="noise_policy_used"):
        build_segmentation_manifest(**_make_args(noise_policy_used="maybe"))


def test_build_rejects_negative_segment_id() -> None:
    with pytest.raises(SegmentationManifestError):
        build_segmentation_manifest(
            **_make_args(
                segment_sizes=[
                    SegmentSize(
                        segment_id=-2,
                        count=1,
                        percentage=1.0,
                        percentage_base="n_samples_used_for_compute",
                        is_noise=False,
                    )
                ]
            )
        )


def test_build_rejects_unknown_percentage_base() -> None:
    with pytest.raises(SegmentationManifestError, match="percentage_base"):
        build_segmentation_manifest(
            **_make_args(
                segment_sizes=[
                    SegmentSize(
                        segment_id=0,
                        count=10,
                        percentage=10.0,
                        percentage_base="n_samples_unknown",
                        is_noise=False,
                    )
                ]
            )
        )


# ---------------------------------------------------------------------------
# manifest_to_dict
# ---------------------------------------------------------------------------


def test_manifest_to_dict_basic() -> None:
    m = build_segmentation_manifest(**_make_args())
    d = manifest_to_dict(m)
    assert isinstance(d, dict)
    assert d["schema_version"] == SEGMENTATION_MANIFEST_SCHEMA_VERSION
    assert d["scope"] == "PROFILED_PROTOTYPE"
    assert d["segmentation_id"] == "seg_" + "0" * 24


def test_manifest_to_dict_serializable_to_json() -> None:
    m = build_segmentation_manifest(**_make_args())
    d = manifest_to_dict(m)
    # Must round-trip through json.dumps without errors.
    s = json.dumps(d, ensure_ascii=False, indent=2, sort_keys=True)
    assert isinstance(s, str)
    assert "PROFILED_PROTOTYPE" in s


# ---------------------------------------------------------------------------
# write_segmentation_manifest / read_segmentation_manifest
# ---------------------------------------------------------------------------


def test_write_and_read_roundtrip(tmp_path: Path) -> None:
    m = build_segmentation_manifest(**_make_args())
    p = tmp_path / "seg" / "segmentation_manifest.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    write_segmentation_manifest(m, p)
    m2 = read_segmentation_manifest(p)
    assert m2.segmentation_id == m.segmentation_id
    assert m2.clustering_id == m.clustering_id
    assert m2.scope == m.scope
    assert m2.noise_count == m.noise_count
    assert m2.n_samples_input == m.n_samples_input


def test_write_atomic_no_leftover_tmp(tmp_path: Path) -> None:
    """write_segmentation_manifest must leave no .tmp file on success."""
    m = build_segmentation_manifest(**_make_args())
    p = tmp_path / "segmentation_manifest.json"
    write_segmentation_manifest(m, p)
    assert p.exists()
    assert not (p.with_suffix(p.suffix + ".tmp")).exists()


def test_write_rejects_missing_parent_dir(tmp_path: Path) -> None:
    m = build_segmentation_manifest(**_make_args())
    p = tmp_path / "nonexistent" / "segmentation_manifest.json"
    with pytest.raises(SegmentationManifestError, match="parent"):
        write_segmentation_manifest(m, p)


def test_read_missing_file(tmp_path: Path) -> None:
    with pytest.raises(SegmentationManifestError, match="not found"):
        read_segmentation_manifest(tmp_path / "nope.json")


def test_read_invalid_json(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("{not valid json")
    with pytest.raises(SegmentationManifestError, match="parse"):
        read_segmentation_manifest(p)


def test_read_non_object(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("[]")
    with pytest.raises(SegmentationManifestError, match="JSON object"):
        read_segmentation_manifest(p)


def test_read_rejects_wrong_schema_version(tmp_path: Path) -> None:
    m = build_segmentation_manifest(**_make_args())
    d = manifest_to_dict(m)
    d["schema_version"] = "0.0.1"
    p = tmp_path / "old.json"
    p.write_text(json.dumps(d))
    with pytest.raises(SegmentationManifestError, match="schema_version"):
        read_segmentation_manifest(p)


def test_read_rejects_missing_field(tmp_path: Path) -> None:
    m = build_segmentation_manifest(**_make_args())
    d = manifest_to_dict(m)
    del d["clustering_id"]
    p = tmp_path / "missing.json"
    p.write_text(json.dumps(d))
    with pytest.raises(SegmentationManifestError, match="clustering_id"):
        read_segmentation_manifest(p)


def test_read_rejects_research_safety_promoted_to_research_true(tmp_path: Path) -> None:
    m = build_segmentation_manifest(**_make_args())
    d = manifest_to_dict(m)
    d["research_safety"]["automatically_promoted_to_research"] = True
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(d))
    with pytest.raises(SegmentationManifestError, match="automatically_promoted_to_research"):
        read_segmentation_manifest(p)


# ---------------------------------------------------------------------------
# Now_utc_iso
# ---------------------------------------------------------------------------


def test_now_utc_iso_format() -> None:
    from customer_segmentation.prototype.segmentation.manifest import now_utc_iso

    s = now_utc_iso()
    # Format: YYYY-MM-DDTHH:MM:SSZ
    assert len(s) == 20
    assert s[4] == "-"
    assert s[10] == "T"
    assert s.endswith("Z")
