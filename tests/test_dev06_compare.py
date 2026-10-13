"""Tests for the DEV-06 compare module.

Per P1-3 resolution (2026-10-10), this suite pins the new compare
contract: CompatibilityKey is 4-field; ``ComparisonGroup`` represents
at least two manifests (or a single-manifest call singleton);
manifests excluded for lacking a sharing partner are reported through
``exclusion_reasons`` (not via per-row ``incompatibility_reasons``);
summary counts are exact and follow
``total_input_count == total_compared_count + total_excluded_count``.
"""

from __future__ import annotations

import json
from pathlib import Path

from customer_segmentation.prototype.segmentation.compare import (
    COMPATIBILITY_KEY_FIELDS,
    DEFAULT_COMPARISON_DISCLAIMER,
    EXCLUSION_REASON_CODE_NO_SHARED_KEY,
    PER_ROW_PROVENANCE_FIELDS,
    ComparisonReport,
    CompatibilityKey,
    ExclusionReason,
    IncompatibilityReason,
    PerRowProvenance,
    SizeDistributionEntry,
    compare_segmentations,
)
from customer_segmentation.prototype.segmentation.display import (
    check_no_banned_substrings,
)
from customer_segmentation.prototype.segmentation.manifest import (
    CharacteristicEntry,
    EnvironmentBlock,
    FeatureProfile,
    SegmentationManifest,
    SegmentationValidationReport,
    SegmentSize,
    build_segmentation_manifest,
    write_segmentation_manifest,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_manifest(
    *,
    segmentation_id: str = "seg_" + "a" * 24,
    clustering_id: str = "cl_" + "a" * 24,
    preprocessed_id: str = "pp_xyz",
    dataset_id: str = "ds_abc",
    ml_dataset_sha256: str = "b" * 64,
    feature_set_sha256: str = "c" * 64,
    preprocessing_config_sha256: str = "d" * 64,
    algorithm: str = "kmeans",
    algorithm_family: str = "hard",
    algorithm_version: str = "sklearn_1.5",
    noise_count: int | None = None,
    noise_ratio: float | None = None,
    noise_policy_used: str = "n/a",
    n_segments: int = 4,
    feature_set: list[str] | None = None,
) -> SegmentationManifest:
    if feature_set is None:
        feature_set = ["a", "b", "c", "d"]
    return build_segmentation_manifest(
        segmentation_id=segmentation_id,
        clustering_id=clustering_id,
        preprocessed_id=preprocessed_id,
        dataset_id=dataset_id,
        evaluation_id=None,
        algorithm=algorithm,
        algorithm_version=algorithm_version,
        algorithm_family=algorithm_family,
        ml_dataset_sha256=ml_dataset_sha256,
        feature_set_sha256=feature_set_sha256,
        preprocessing_config_sha256=preprocessing_config_sha256,
        feature_set=feature_set,
        n_samples_input=100,
        n_samples_used_for_compute=100,
        n_clusters_input=n_segments,
        n_segments=n_segments,
        noise_count=noise_count,
        noise_ratio=noise_ratio,
        noise_policy_used=noise_policy_used,
        segment_sizes=[
            SegmentSize(
                segment_id=i,
                count=20 + i,
                percentage=25.0 + i,
                percentage_base="n_samples_input",
                is_noise=False,
            )
            for i in range(n_segments)
        ],
        profiles=[
            FeatureProfile(
                segment_id=i,
                feature_name="a",
                statistics={"mean": 0.1 * i, "std": 1.0},
            )
            for i in range(n_segments)
        ],
        characteristics=[
            CharacteristicEntry(
                characteristic_id="mean_high_a",
                description="test",
                source_features=["a"],
                derived_stats={"rule": "mean_high"},
            )
        ],
        config_sha256="e" * 64,
        environment=EnvironmentBlock(
            python="3.11",
            platform="Linux",
            release="7.0",
            machine="x86_64",
            key_libraries={},
        ),
        log_file="x.log",
        validation_report=SegmentationValidationReport(all_passed=True),
        readonly_paths=["data/raw/primary"],
        input_clustering_manifest="cm.json",
        input_cluster_labels="cl.parquet",
        input_ml_dataset="ml.parquet",
        input_evaluation_manifest=None,
    )


def _write(manifest: SegmentationManifest, path: Path) -> None:
    write_segmentation_manifest(manifest, path)


# ---------------------------------------------------------------------------
# CompatibilityKey (4-field invariant — R-DEV-06-24)
# ---------------------------------------------------------------------------


class TestCompatibilityKey:
    def test_key_has_4_fields(self) -> None:
        assert (
            frozenset({"dataset_id", "preprocessed_id", "ml_dataset_sha256", "feature_set_sha256"})
            == COMPATIBILITY_KEY_FIELDS
        )

    def test_key_excludes_preprocessing_config_sha256(self) -> None:
        """R-DEV-06-24: must NOT include preprocessing_config_sha256."""
        assert "preprocessing_config_sha256" not in COMPATIBILITY_KEY_FIELDS

    def test_key_as_tuple(self) -> None:
        k = CompatibilityKey(
            dataset_id="d1",
            preprocessed_id="p1",
            ml_dataset_sha256="m1",
            feature_set_sha256="f1",
        )
        assert k.as_tuple() == ("d1", "p1", "m1", "f1")

    def test_key_hashable(self) -> None:
        k1 = CompatibilityKey("d", "p", "m", "f")
        k2 = CompatibilityKey("d", "p", "m", "f")
        k3 = CompatibilityKey("d", "p", "m", "F")
        assert hash(k1) == hash(k2)
        assert k1 == k2
        assert k1 != k3

    def test_key_to_dict(self) -> None:
        k = CompatibilityKey("d", "p", "m", "f")
        d = k.to_dict()
        assert set(d.keys()) == {
            "dataset_id",
            "preprocessed_id",
            "ml_dataset_sha256",
            "feature_set_sha256",
        }


# ---------------------------------------------------------------------------
# Per-row provenance
# ---------------------------------------------------------------------------


class TestPerRowProvenance:
    def test_fields_match_expected(self) -> None:
        assert (
            frozenset(
                {
                    "algorithm",
                    "algorithm_family",
                    "noise_policy_used",
                    "n_segments",
                    "noise_count",
                    "noise_ratio",
                }
            )
            == PER_ROW_PROVENANCE_FIELDS
        )

    def test_provenance_round_trip(self) -> None:
        p = PerRowProvenance(
            segmentation_id="seg_aaa",
            algorithm="kmeans",
            algorithm_family="hard",
            noise_policy_used="n/a",
            n_segments=4,
            noise_count=None,
            noise_ratio=None,
        )
        d = p.to_dict()
        assert d["segmentation_id"] == "seg_aaa"
        assert d["algorithm"] == "kmeans"


# ---------------------------------------------------------------------------
# ExclusionReason (R-DEV-06-26)
# ---------------------------------------------------------------------------


class TestExclusionReason:
    def test_to_dict_carries_all_fields(self) -> None:
        r = ExclusionReason(
            excluded_segmentation_id="seg_x",
            excluded_key={
                "dataset_id": "d",
                "preprocessed_id": "p",
                "ml_dataset_sha256": "m",
                "feature_set_sha256": "f",
            },
            reason_code=EXCLUSION_REASON_CODE_NO_SHARED_KEY,
            differing_key_field_names=("dataset_id",),
            no_retained_group=False,
        )
        d = r.to_dict()
        assert d["excluded_segmentation_id"] == "seg_x"
        assert d["excluded_key"] == {
            "dataset_id": "d",
            "preprocessed_id": "p",
            "ml_dataset_sha256": "m",
            "feature_set_sha256": "f",
        }
        assert d["reason_code"] == "excluded_no_shared_key"
        assert d["differing_key_field_names"] == ["dataset_id"]
        assert d["no_retained_group"] is False

    def test_reason_code_is_stable_constant(self) -> None:
        assert EXCLUSION_REASON_CODE_NO_SHARED_KEY == "excluded_no_shared_key"


# ---------------------------------------------------------------------------
# Required: single-manifest call (Test #1)
# ---------------------------------------------------------------------------


class TestSingleManifest:
    def test_single_manifest_emits_one_singleton_group(self, tmp_path: Path) -> None:
        """Required test #1: single manifest → 1 singleton group with note."""
        m1 = _make_manifest()
        p1 = tmp_path / "m1.json"
        _write(m1, p1)
        report = compare_segmentations([p1])
        assert isinstance(report, ComparisonReport)
        assert len(report.groups) == 1
        assert report.groups[0].is_singleton is True
        assert "singleton" in report.groups[0].note
        assert "no comparison possible" in report.groups[0].note
        assert len(report.exclusion_reasons) == 0
        assert len(report.incompatibility_reasons) == 0
        assert report.total_input_count == 1
        assert report.total_compared_count == 1
        assert report.total_excluded_count == 0


# ---------------------------------------------------------------------------
# Required: 2 manifests sharing a key (Test #2)
# ---------------------------------------------------------------------------


class TestTwoCompatibleManifests:
    def test_two_compatible_manifests_one_group(self, tmp_path: Path) -> None:
        """Required test #2: 2 manifests sharing key → 1 two-member group."""
        m1 = _make_manifest(segmentation_id="seg_" + "1" * 24)
        m2 = _make_manifest(segmentation_id="seg_" + "2" * 24)
        p1 = tmp_path / "m1.json"
        p2 = tmp_path / "m2.json"
        _write(m1, p1)
        _write(m2, p2)
        report = compare_segmentations([p1, p2])
        assert len(report.groups) == 1
        assert report.groups[0].is_singleton is False
        assert len(report.groups[0].segmentations) == 2
        assert len(report.exclusion_reasons) == 0
        assert len(report.incompatibility_reasons) == 0
        assert report.total_input_count == 2
        assert report.total_compared_count == 2
        assert report.total_excluded_count == 0


# ---------------------------------------------------------------------------
# Required: 2 manifests with different keys (Test #3)
# ---------------------------------------------------------------------------


class TestTwoIncompatibleManifests:
    def test_two_incompatible_manifests_zero_groups_two_exclusions(self, tmp_path: Path) -> None:
        """Required test #3: 2 manifests with different keys → 0 groups + 2 exclusions."""
        m1 = _make_manifest(segmentation_id="seg_" + "1" * 24, dataset_id="ds_a")
        m2 = _make_manifest(segmentation_id="seg_" + "2" * 24, dataset_id="ds_b")
        p1 = tmp_path / "m1.json"
        p2 = tmp_path / "m2.json"
        _write(m1, p1)
        _write(m2, p2)
        report = compare_segmentations([p1, p2])
        # 0 groups (P1-3 resolution: all-incompatible → no groups).
        assert len(report.groups) == 0
        # 2 exclusion reasons — one per manifest.
        assert len(report.exclusion_reasons) == 2
        excluded_ids = {r.excluded_segmentation_id for r in report.exclusion_reasons}
        assert excluded_ids == {m1.segmentation_id, m2.segmentation_id}
        # 0 per-row incompatibility reasons (kept distinct per R-DEV-06-26).
        assert len(report.incompatibility_reasons) == 0
        # All-incompatible: no_retained_group=True.
        assert all(r.no_retained_group is True for r in report.exclusion_reasons)
        # differing_key_field_names includes dataset_id (the only differing field).
        for r in report.exclusion_reasons:
            assert "dataset_id" in r.differing_key_field_names
        # Summary counts.
        assert report.total_input_count == 2
        assert report.total_compared_count == 0
        assert report.total_excluded_count == 2


# ---------------------------------------------------------------------------
# Required: mixed case — 2 share K1, third has K2 (Test #4)
# ---------------------------------------------------------------------------


class TestMixedOneGroupOneExcluded:
    def test_mixed_keeps_group_excludes_singleton_with_reason(self, tmp_path: Path) -> None:
        """Required test #4: 2 share K1, 1 has K2 → keep K1 group, exclude third."""
        m1 = _make_manifest(segmentation_id="seg_" + "1" * 24, dataset_id="ds_shared")
        m2 = _make_manifest(segmentation_id="seg_" + "2" * 24, dataset_id="ds_shared")
        m3 = _make_manifest(segmentation_id="seg_" + "3" * 24, dataset_id="ds_other")
        p1 = tmp_path / "m1.json"
        p2 = tmp_path / "m2.json"
        p3 = tmp_path / "m3.json"
        _write(m1, p1)
        _write(m2, p2)
        _write(m3, p3)
        report = compare_segmentations([p1, p2, p3])
        # The K1 group is retained with both manifests.
        assert len(report.groups) == 1
        assert report.groups[0].compatibility_key.dataset_id == "ds_shared"
        assert len(report.groups[0].segmentations) == 2
        # m3 is excluded.
        assert len(report.exclusion_reasons) == 1
        assert report.exclusion_reasons[0].excluded_segmentation_id == m3.segmentation_id
        assert report.exclusion_reasons[0].no_retained_group is False
        # dataset_id is the differing key field.
        assert "dataset_id" in report.exclusion_reasons[0].differing_key_field_names
        # Summary counts.
        assert report.total_input_count == 3
        assert report.total_compared_count == 2
        assert report.total_excluded_count == 1


# ---------------------------------------------------------------------------
# Required: mixed case — 2 retained groups + ≥1 excluded, no anchor (Test #5)
# ---------------------------------------------------------------------------


class TestMixedTwoRetainedGroupsOneExcluded:
    def test_mixed_two_retained_groups_excludes_singleton_no_anchor(self, tmp_path: Path) -> None:
        """Required test #5: 2 retained groups + 1 excluded; no arbitrary anchor."""
        # Group A: m1, m2 share (ds_a, pp_x, m1, f1).
        m1 = _make_manifest(segmentation_id="seg_" + "1" * 24, dataset_id="ds_a")
        m2 = _make_manifest(segmentation_id="seg_" + "2" * 24, dataset_id="ds_a")
        # Group B: m3, m4 share (ds_b, pp_x, m1, f1).
        m3 = _make_manifest(segmentation_id="seg_" + "3" * 24, dataset_id="ds_b")
        m4 = _make_manifest(segmentation_id="seg_" + "4" * 24, dataset_id="ds_b")
        # Excluded: m5 has unique dataset_id ds_c.
        m5 = _make_manifest(segmentation_id="seg_" + "5" * 24, dataset_id="ds_c")
        paths = []
        for i, m in enumerate([m1, m2, m3, m4, m5], start=1):
            p = tmp_path / f"m{i}.json"
            _write(m, p)
            paths.append(p)
        report = compare_segmentations(paths)
        # Two retained groups, both multi-member.
        assert len(report.groups) == 2
        retained_dataset_ids = {g.compatibility_key.dataset_id for g in report.groups}
        assert retained_dataset_ids == {"ds_a", "ds_b"}
        # m5 is the only excluded manifest.
        assert len(report.exclusion_reasons) == 1
        r = report.exclusion_reasons[0]
        assert r.excluded_segmentation_id == m5.segmentation_id
        assert r.no_retained_group is False
        # dataset_id is the only field that uniquely excludes m5 (other fields
        # like preprocessed_id/ml_dataset_sha256/feature_set_sha256 match at
        # least one retained group).
        assert r.differing_key_field_names == ("dataset_id",)
        # Summary counts.
        assert report.total_input_count == 5
        assert report.total_compared_count == 4
        assert report.total_excluded_count == 1


# ---------------------------------------------------------------------------
# Required: same key, differing per-row → existing incompatibility_reasons (Test #6)
# ---------------------------------------------------------------------------


class TestPerRowIncompatibilityReasons:
    def test_same_key_different_algorithm_emits_per_row_reason(self, tmp_path: Path) -> None:
        """Required test #6: same key, different algorithm → per-row reason."""
        m1 = _make_manifest(segmentation_id="seg_" + "1" * 24, algorithm="kmeans")
        m2 = _make_manifest(segmentation_id="seg_" + "2" * 24, algorithm="dbscan")
        p1 = tmp_path / "m1.json"
        p2 = tmp_path / "m2.json"
        _write(m1, p1)
        _write(m2, p2)
        report = compare_segmentations([p1, p2])
        # Same key → 1 multi-member group; no exclusion.
        assert len(report.groups) == 1
        assert len(report.exclusion_reasons) == 0
        # Per-row incompatibility reason for `algorithm`.
        algorithm_reasons = [
            r for r in report.incompatibility_reasons if r.field_name == "algorithm"
        ]
        assert len(algorithm_reasons) == 1
        # The reason identifies the differing manifest.
        assert algorithm_reasons[0].segmentation_id == m2.segmentation_id
        assert algorithm_reasons[0].stored_value == "dbscan"
        assert algorithm_reasons[0].compared_value == "kmeans"


# ---------------------------------------------------------------------------
# Required: exclusion reasons vs per-row incompatibility reasons are distinct (Test #7)
# ---------------------------------------------------------------------------


class TestReasonConceptsAreDistinct:
    def test_exclusion_and_per_row_reasons_are_separate_fields(self, tmp_path: Path) -> None:
        """Required test #7: the two reason concepts are separate in serialized output."""
        # Build 4 manifests:
        #  - m1, m2 share key (ds_a) but differ on algorithm → multi-member group
        #    with per-row incompatibility_reasons.
        #  - m3, m4 share key (ds_b) → multi-member group.
        #  - m5 has unique key (ds_c) → excluded.
        m1 = _make_manifest(
            segmentation_id="seg_" + "1" * 24, dataset_id="ds_a", algorithm="kmeans"
        )
        m2 = _make_manifest(
            segmentation_id="seg_" + "2" * 24, dataset_id="ds_a", algorithm="dbscan"
        )
        m3 = _make_manifest(segmentation_id="seg_" + "3" * 24, dataset_id="ds_b")
        m4 = _make_manifest(segmentation_id="seg_" + "4" * 24, dataset_id="ds_b")
        m5 = _make_manifest(segmentation_id="seg_" + "5" * 24, dataset_id="ds_c")
        paths = []
        for i, m in enumerate([m1, m2, m3, m4, m5], start=1):
            p = tmp_path / f"m{i}.json"
            _write(m, p)
            paths.append(p)
        report = compare_segmentations(paths)
        # Serialize and round-trip via JSON.
        d = report.to_dict()
        # 2 groups retained.
        assert len(d["groups"]) == 2
        # per-row reasons: at least the algorithm diff.
        per_row_field_names = {r["field_name"] for r in d["incompatibility_reasons"]}
        assert "algorithm" in per_row_field_names
        # exclusion reasons: 1 (for m5).
        assert len(d["exclusion_reasons"]) == 1
        assert d["exclusion_reasons"][0]["excluded_segmentation_id"] == m5.segmentation_id
        assert d["exclusion_reasons"][0]["reason_code"] == "excluded_no_shared_key"
        # The two lists do not overlap: per-row reasons never reference
        # excluded_segmentation_id; exclusion reasons never use
        # "field_name".
        for r in d["incompatibility_reasons"]:
            assert "excluded_segmentation_id" not in r
        for r in d["exclusion_reasons"]:
            assert "field_name" not in r

    def test_reason_field_names_are_distinct_in_dict(self) -> None:
        """Defensive: dataclass shapes never collide."""
        incompat_keys = set(
            IncompatibilityReason(
                segmentation_id="x",
                field_name="algorithm",
                stored_value="a",
                compared_value="b",
            )
            .to_dict()
            .keys()
        )
        exclusion_keys = set(
            ExclusionReason(
                excluded_segmentation_id="x",
                excluded_key={"a": "b"},
                reason_code=EXCLUSION_REASON_CODE_NO_SHARED_KEY,
                differing_key_field_names=("a",),
                no_retained_group=False,
            )
            .to_dict()
            .keys()
        )
        assert "field_name" in incompat_keys
        assert "excluded_segmentation_id" not in incompat_keys
        assert "excluded_segmentation_id" in exclusion_keys
        assert "field_name" not in exclusion_keys


# ---------------------------------------------------------------------------
# Required: summary counts exact for all 4 cases (Test #8)
# ---------------------------------------------------------------------------


class TestSummaryCounts:
    def test_summary_counts_single_manifest(self, tmp_path: Path) -> None:
        m1 = _make_manifest()
        p1 = tmp_path / "m1.json"
        _write(m1, p1)
        report = compare_segmentations([p1])
        assert (
            report.total_input_count,
            report.total_compared_count,
            report.total_excluded_count,
        ) == (1, 1, 0)

    def test_summary_counts_all_compatible(self, tmp_path: Path) -> None:
        m1 = _make_manifest(segmentation_id="seg_" + "1" * 24)
        m2 = _make_manifest(segmentation_id="seg_" + "2" * 24)
        m3 = _make_manifest(segmentation_id="seg_" + "3" * 24)
        paths = []
        for i, m in enumerate([m1, m2, m3], start=1):
            p = tmp_path / f"m{i}.json"
            _write(m, p)
            paths.append(p)
        report = compare_segmentations(paths)
        assert (
            report.total_input_count,
            report.total_compared_count,
            report.total_excluded_count,
        ) == (3, 3, 0)

    def test_summary_counts_all_incompatible(self, tmp_path: Path) -> None:
        m1 = _make_manifest(segmentation_id="seg_" + "1" * 24, dataset_id="ds_a")
        m2 = _make_manifest(segmentation_id="seg_" + "2" * 24, dataset_id="ds_b")
        m3 = _make_manifest(segmentation_id="seg_" + "3" * 24, dataset_id="ds_c")
        paths = []
        for i, m in enumerate([m1, m2, m3], start=1):
            p = tmp_path / f"m{i}.json"
            _write(m, p)
            paths.append(p)
        report = compare_segmentations(paths)
        assert (
            report.total_input_count,
            report.total_compared_count,
            report.total_excluded_count,
        ) == (3, 0, 3)

    def test_summary_counts_mixed(self, tmp_path: Path) -> None:
        m1 = _make_manifest(segmentation_id="seg_" + "1" * 24, dataset_id="ds_a")
        m2 = _make_manifest(segmentation_id="seg_" + "2" * 24, dataset_id="ds_a")
        m3 = _make_manifest(segmentation_id="seg_" + "3" * 24, dataset_id="ds_b")
        m4 = _make_manifest(segmentation_id="seg_" + "4" * 24, dataset_id="ds_c")
        paths = []
        for i, m in enumerate([m1, m2, m3, m4], start=1):
            p = tmp_path / f"m{i}.json"
            _write(m, p)
            paths.append(p)
        report = compare_segmentations(paths)
        # 4 input, 3 in groups (m1, m2 share K_a; m3 alone has K_b → group is a
        # multi-member call with one key? No: m3 is alone in its key with
        # a multi-manifest call → excluded). 1 excluded (m4).
        assert (
            report.total_input_count,
            report.total_compared_count,
            report.total_excluded_count,
        ) == (4, 2, 2)

    def test_invariant_total_input_equals_compared_plus_excluded(self, tmp_path: Path) -> None:
        """R-DEV-06-27: total_input == total_compared + total_excluded."""
        ms = [
            _make_manifest(segmentation_id="seg_" + str(i) * 24, dataset_id=f"ds_{i}")
            for i in range(1, 6)
        ]
        # Plus a duplicate of m1.
        ms.append(_make_manifest(segmentation_id="seg_" + "1" * 24, dataset_id="ds_1"))
        paths = []
        for i, m in enumerate(ms, start=1):
            p = tmp_path / f"m{i}.json"
            _write(m, p)
            paths.append(p)
        report = compare_segmentations(paths)
        assert report.total_input_count == report.total_compared_count + report.total_excluded_count


# ---------------------------------------------------------------------------
# Required: duplicate-input behavior (Test #9)
# ---------------------------------------------------------------------------


class TestDuplicateInput:
    def test_duplicate_paths_dedup_by_segmentation_id(self, tmp_path: Path) -> None:
        """Required test #9: same path twice → counted once; no double-counting."""
        m1 = _make_manifest(segmentation_id="seg_" + "1" * 24)
        p1 = tmp_path / "m1.json"
        _write(m1, p1)
        report = compare_segmentations([p1, p1])
        # Single manifest call after dedup → 1 singleton group.
        assert len(report.groups) == 1
        assert report.groups[0].is_singleton is True
        assert report.total_input_count == 1
        assert report.total_compared_count == 1
        assert report.total_excluded_count == 0

    def test_duplicate_segmentation_id_distinct_paths_dedup(self, tmp_path: Path) -> None:
        """Same ``segmentation_id`` but two paths → deduped (first wins)."""
        m1 = _make_manifest(segmentation_id="seg_" + "1" * 24, dataset_id="ds_a")
        m1_dup = _make_manifest(segmentation_id="seg_" + "1" * 24, dataset_id="ds_a")
        p1 = tmp_path / "m1.json"
        p2 = tmp_path / "m2.json"
        _write(m1, p1)
        _write(m1_dup, p2)
        report = compare_segmentations([p1, p2])
        assert len(report.groups) == 1
        assert report.groups[0].is_singleton is True
        assert report.total_input_count == 1
        assert report.total_compared_count == 1
        assert report.total_excluded_count == 0


# ---------------------------------------------------------------------------
# Required: output order deterministic (Test #10)
# ---------------------------------------------------------------------------


class TestOutputOrder:
    def test_groups_and_exclusions_preserve_input_order(self, tmp_path: Path) -> None:
        """Required test #10: group and exclusion order follow input order."""
        # Build 5 manifests with distinct dataset_ids.
        ms = [
            _make_manifest(segmentation_id="seg_" + str(i) * 24, dataset_id=f"ds_{i}")
            for i in range(1, 6)
        ]
        # First two share a key (need to rewrite m2 to share m1's dataset_id).
        ms[1] = _make_manifest(segmentation_id="seg_" + "2" * 24, dataset_id="ds_1")
        paths = []
        for i, m in enumerate(ms, start=1):
            p = tmp_path / f"m{i}.json"
            _write(m, p)
            paths.append(p)
        report = compare_segmentations(paths)
        # Group 1: m1, m2 share ds_1 (input order: 1, 2).
        assert len(report.groups) == 1
        ids_in_group = [s.segmentation_id for s in report.groups[0].segmentations]
        assert ids_in_group == [ms[0].segmentation_id, ms[1].segmentation_id]
        # Exclusions follow input order: m3, m4, m5.
        excluded_ids = [r.excluded_segmentation_id for r in report.exclusion_reasons]
        assert excluded_ids == [ms[2].segmentation_id, ms[3].segmentation_id, ms[4].segmentation_id]


# ---------------------------------------------------------------------------
# Required: round-trip via existing serializer/parser (Test #11)
# ---------------------------------------------------------------------------


class TestReportSerialization:
    def test_to_dict_has_all_required_keys(self, tmp_path: Path) -> None:
        """Required test #11: ``to_dict()`` produces a well-formed report."""
        m1 = _make_manifest()
        p1 = tmp_path / "m1.json"
        _write(m1, p1)
        report = compare_segmentations([p1])
        d = report.to_dict()
        # Top-level keys.
        assert set(d.keys()) == {
            "schema_version",
            "compared_at_utc",
            "groups",
            "incompatibility_reasons",
            "exclusion_reasons",
            "total_input_count",
            "total_compared_count",
            "total_excluded_count",
            "disclaimer",
        }
        assert d["schema_version"] == "1.0.0"
        assert d["disclaimer"] == DEFAULT_COMPARISON_DISCLAIMER
        assert isinstance(d["groups"], list)
        assert isinstance(d["incompatibility_reasons"], list)
        assert isinstance(d["exclusion_reasons"], list)
        assert isinstance(d["total_input_count"], int)
        assert isinstance(d["total_compared_count"], int)
        assert isinstance(d["total_excluded_count"], int)

    def test_json_round_trip_preserves_values(self, tmp_path: Path) -> None:
        """JSON dump → load preserves every top-level field."""
        m1 = _make_manifest(segmentation_id="seg_" + "1" * 24, dataset_id="ds_a")
        m2 = _make_manifest(segmentation_id="seg_" + "2" * 24, dataset_id="ds_b")
        p1 = tmp_path / "m1.json"
        p2 = tmp_path / "m2.json"
        _write(m1, p1)
        _write(m2, p2)
        report = compare_segmentations([p1, p2])
        d = report.to_dict()
        # JSON round-trip.
        text = json.dumps(d, sort_keys=True)
        d2 = json.loads(text)
        assert d2 == d
        # Top-level values are preserved.
        assert d2["total_input_count"] == 2
        assert d2["total_compared_count"] == 0
        assert d2["total_excluded_count"] == 2
        assert len(d2["exclusion_reasons"]) == 2


# ---------------------------------------------------------------------------
# Required: no algorithm ranking, no banned substrings (Test #13)
# ---------------------------------------------------------------------------


class TestNoRanking:
    def test_no_banned_substring_in_serialized_report(self, tmp_path: Path) -> None:
        """Required test #13: no 'best' / 'winner' / 'ranking' / etc. outside disclaimer."""
        m1 = _make_manifest(
            segmentation_id="seg_" + "1" * 24, dataset_id="ds_a", algorithm="kmeans"
        )
        m2 = _make_manifest(
            segmentation_id="seg_" + "2" * 24, dataset_id="ds_a", algorithm="dbscan"
        )
        p1 = tmp_path / "m1.json"
        p2 = tmp_path / "m2.json"
        _write(m1, p1)
        _write(m2, p2)
        report = compare_segmentations([p1, p2])
        out = json.dumps(report.to_dict(), default=str, sort_keys=True)
        found = check_no_banned_substrings(out, disclaimer=DEFAULT_COMPARISON_DISCLAIMER)
        assert found == [], f"banned words found: {found}"


# ---------------------------------------------------------------------------
# Pre-existing regression tests preserved (singleton + size + round-trip)
# ---------------------------------------------------------------------------


class TestSingletonLegacy:
    def test_singleton_group_with_one_manifest(self, tmp_path: Path) -> None:
        m1 = _make_manifest()
        p1 = tmp_path / "m1.json"
        _write(m1, p1)
        report = compare_segmentations([p1])
        assert len(report.groups) == 1
        assert report.groups[0].is_singleton is True
        assert "singleton" in report.groups[0].note

    def test_size_distribution_included(self, tmp_path: Path) -> None:
        m1 = _make_manifest(segmentation_id="seg_" + "1" * 24, n_segments=3)
        p1 = tmp_path / "m1.json"
        _write(m1, p1)
        report = compare_segmentations([p1])
        g = report.groups[0]
        assert len(g.size_distribution) == 3
        for entry in g.size_distribution:
            assert isinstance(entry, SizeDistributionEntry)
            assert entry.segmentation_id == "seg_" + "1" * 24
