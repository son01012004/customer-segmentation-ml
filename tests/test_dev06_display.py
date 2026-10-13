"""Tests for the DEV-06 display module (Phase 2E)."""

from __future__ import annotations

from customer_segmentation.prototype.segmentation.display import (
    BANNED_SUBSTRINGS,
    BANNED_SUBSTRINGS_OUTSIDE_DISCLAIMER,
    DEFAULT_DISCLAIMER_TEXT,
    check_no_banned_substrings,
    format_characteristics_table,
    format_comparison_table,
    format_manifest_path,
    format_profiles_table,
    format_segments_table,
    format_sizes_table,
)
from customer_segmentation.prototype.segmentation.manifest import (
    CharacteristicEntry,
    EnvironmentBlock,
    FeatureProfile,
    SegmentationManifest,
    SegmentationValidationReport,
    SegmentSize,
    build_segmentation_manifest,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_manifest(
    *,
    n_segments: int = 3,
    n_samples_input: int = 100,
    noise_count: int | None = 30,
    noise_ratio: float | None = 0.30,
    algorithm_family: str = "density_based",
) -> SegmentationManifest:
    # For non-density algorithms, force noise fields to None.
    if algorithm_family != "density_based":
        noise_count = None
        noise_ratio = None
    sizes: list[SegmentSize] = []
    for i in range(n_segments):
        sizes.append(
            SegmentSize(
                segment_id=i,
                count=20 + i,
                percentage=round((20 + i) / n_samples_input * 100.0, 2),
                percentage_base="n_samples_input",
                is_noise=False,
            )
        )
    if noise_count is not None:
        sizes.append(
            SegmentSize(
                segment_id=-1,
                count=noise_count,
                percentage=round(noise_count / n_samples_input * 100.0, 2),
                percentage_base="n_samples_input",
                is_noise=True,
            )
        )
    profiles = [
        FeatureProfile(
            segment_id=i,
            feature_name="Recency",
            statistics={
                "mean": 0.1 * i,
                "median": 0.2 * i,
                "std": 0.5,
                "min": -1.0,
                "max": 1.0,
            },
        )
        for i in range(n_segments)
    ]
    characteristics = [
        CharacteristicEntry(
            characteristic_id="mean_high_Recency",
            description="Mean of Recency above dataset mean by 1 std.",
            source_features=["Recency"],
            derived_stats={"rule": "mean_high"},
        )
    ]
    return build_segmentation_manifest(
        segmentation_id="seg_" + "a" * 24,
        clustering_id="cl_" + "a" * 24,
        preprocessed_id="pp_xyz",
        dataset_id="ds_abc",
        evaluation_id=None,
        algorithm="dbscan" if algorithm_family == "density_based" else "kmeans",
        algorithm_version="sklearn_1.5",
        algorithm_family=algorithm_family,
        ml_dataset_sha256="b" * 64,
        feature_set_sha256="c" * 64,
        preprocessing_config_sha256="d" * 64,
        feature_set=["Recency"],
        n_samples_input=n_samples_input,
        n_samples_used_for_compute=n_samples_input - (noise_count or 0),
        n_clusters_input=n_segments + (1 if noise_count else 0),
        n_segments=n_segments,
        noise_count=noise_count,
        noise_ratio=noise_ratio,
        noise_policy_used="exclude" if algorithm_family == "density_based" else "n/a",
        segment_sizes=sizes,
        profiles=profiles,
        characteristics=characteristics,
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


# ---------------------------------------------------------------------------
# check_no_banned_substrings (R-DEV-06-08)
# ---------------------------------------------------------------------------


class TestCheckNoBannedSubstrings:
    def test_clean_text_passes(self) -> None:
        text = "Segments: id=0 count=25 percentage=25.00"
        assert check_no_banned_substrings(text) == []

    def test_banned_words_detected(self) -> None:
        text = "This is the best segment with high ranking"
        found = check_no_banned_substrings(text)
        assert "best" in found
        assert "ranking" in found

    def test_disclaimer_excluded(self) -> None:
        text = DEFAULT_DISCLAIMER_TEXT
        # The disclaimer itself mentions "ranking", "recommendation",
        # "winner" — but the check must EXCLUDE it.
        assert check_no_banned_substrings(text) == []

    def test_partial_disclaimer_still_excluded(self) -> None:
        # Even a partial disclaimer substring is excluded.
        text = "header line\n" + DEFAULT_DISCLAIMER_TEXT + "\nfooter line"
        assert check_no_banned_substrings(text) == []

    def test_business_terms_detected(self) -> None:
        text = "This is a champion segment with loyal customers"
        found = check_no_banned_substrings(text)
        assert "champion" in found
        assert "loyal" in found

    def test_all_banned_substrings_listed(self) -> None:
        assert "best" in BANNED_SUBSTRINGS
        assert "winner" in BANNED_SUBSTRINGS
        assert "optimal" in BANNED_SUBSTRINGS
        assert "recommended" in BANNED_SUBSTRINGS
        assert "ranking" in BANNED_SUBSTRINGS
        assert "composite_score" in BANNED_SUBSTRINGS
        assert "champion" in BANNED_SUBSTRINGS
        assert "loyal" in BANNED_SUBSTRINGS
        assert "high-value" in BANNED_SUBSTRINGS
        assert "at-risk" in BANNED_SUBSTRINGS
        assert "vip" in BANNED_SUBSTRINGS
        assert "churn" in BANNED_SUBSTRINGS
        assert "marketing" in BANNED_SUBSTRINGS

    def test_alias_matches(self) -> None:
        assert BANNED_SUBSTRINGS_OUTSIDE_DISCLAIMER == BANNED_SUBSTRINGS

    def test_default_disclaimer_text_contains_negation(self) -> None:
        assert "no" in DEFAULT_DISCLAIMER_TEXT.lower()
        assert "ranking" in DEFAULT_DISCLAIMER_TEXT
        assert "winner" in DEFAULT_DISCLAIMER_TEXT


# ---------------------------------------------------------------------------
# format_segments_table (AC-1)
# ---------------------------------------------------------------------------


class TestFormatSegmentsTable:
    def test_basic_table(self) -> None:
        m = _make_manifest(n_segments=2, noise_count=10)
        table = format_segments_table(m)
        assert "segment_id" in table
        assert "0" in table
        assert "1" in table
        assert "-1" in table  # noise row
        assert "n_samples_input" in table
        assert "noise_count" in table

    def test_non_dbscan_no_noise_row(self) -> None:
        m = _make_manifest(n_segments=2, noise_count=None, algorithm_family="hard")
        table = format_segments_table(m)
        # Non-DBSCAN: noise_count is None → no noise row, no "noise_count=" in output.
        assert "noise_count=" not in table


# ---------------------------------------------------------------------------
# format_sizes_table (AC-2)
# ---------------------------------------------------------------------------


class TestFormatSizesTable:
    def test_basic_sizes(self) -> None:
        m = _make_manifest(n_segments=2, noise_count=10)
        table = format_sizes_table(m.segment_sizes)
        assert "0" in table
        assert "1" in table
        # Noise segment (-1) MUST NOT appear in sizes table.
        assert "-1" not in table

    def test_all_noise_placeholder(self) -> None:
        sizes = [
            SegmentSize(
                segment_id=-1,
                count=100,
                percentage=100.0,
                percentage_base="n_samples_input",
                is_noise=True,
            )
        ]
        table = format_sizes_table(sizes)
        assert "--" in table


# ---------------------------------------------------------------------------
# format_profiles_table (AC-4)
# ---------------------------------------------------------------------------


class TestFormatProfilesTable:
    def test_all_profiles(self) -> None:
        m = _make_manifest(n_segments=2, noise_count=10)
        table = format_profiles_table(m.profiles)
        assert "Recency" in table
        assert "mean" in table

    def test_filter_by_segment_id(self) -> None:
        m = _make_manifest(n_segments=2, noise_count=10)
        table = format_profiles_table(m.profiles, segment_id=0)
        # The table should contain row(s) for segment 0.
        lines_with_zero = [line for line in table.splitlines() if line.startswith("0 ")]
        # 1 feature × 5 statistics = 5 rows for segment 0.
        assert len(lines_with_zero) >= 5


# ---------------------------------------------------------------------------
# format_characteristics_table (AC-3)
# ---------------------------------------------------------------------------


class TestFormatCharacteristicsTable:
    def test_basic(self) -> None:
        m = _make_manifest()
        table = format_characteristics_table(m.characteristics)
        assert "mean_high_Recency" in table

    def test_empty_shows_placeholder(self) -> None:
        table = format_characteristics_table([])
        assert "--" in table


# ---------------------------------------------------------------------------
# format_comparison_table (AC-5)
# ---------------------------------------------------------------------------


class TestFormatComparisonTable:
    def test_basic(self) -> None:
        from customer_segmentation.prototype.segmentation.compare import (
            ComparisonGroup,
            ComparisonReport,
            CompatibilityKey,
        )

        m = _make_manifest()
        report = ComparisonReport(
            schema_version="1.0.0",
            compared_at_utc="2026-10-10T00:00:00Z",
            groups=[
                ComparisonGroup(
                    compatibility_key=CompatibilityKey(
                        dataset_id="ds_abc",
                        preprocessed_id="pp_xyz",
                        ml_dataset_sha256="b" * 64,
                        feature_set_sha256="c" * 64,
                    ),
                    segmentations=[m],
                    per_row_provenance=[],
                    size_distribution=[],
                    note="singleton",
                )
            ],
            incompatibility_reasons=[],
            exclusion_reasons=[],
            total_input_count=1,
            total_compared_count=1,
            total_excluded_count=0,
            disclaimer="no ranking, recommendation, or winner annotation is emitted",
        )
        table = format_comparison_table(report)
        assert "Comparison report" in table
        assert "Group 1" in table
        assert "singleton" in table
        assert "ds_abc" in table


# ---------------------------------------------------------------------------
# format_manifest_path
# ---------------------------------------------------------------------------


class TestFormatManifestPath:
    def test_basic(self) -> None:
        m = _make_manifest()
        line = format_manifest_path(m)
        assert "segmentation_id=seg_" in line
        assert "algorithm=" in line
        assert "n_segments=" in line
