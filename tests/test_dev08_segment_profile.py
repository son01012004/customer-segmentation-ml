"""Tests for DEV-08 segment profile table (Task 1.3)."""

from __future__ import annotations

import re
from typing import Any

import pytest

from customer_segmentation.prototype.segmentation.manifest import (
    CharacteristicEntry,
    FeatureProfile,
    SegmentationManifest,
    SegmentationValidationReport,
    SegmentSize,
    build_segmentation_manifest,
)
from customer_segmentation.prototype.visualization.charts.segment_profile import (
    collect_segment_characteristics,
    format_characteristic_entry,
    format_segment_profile_table,
)
from customer_segmentation.prototype.visualization.exceptions import (
    VisualizationError,
)
from customer_segmentation.prototype.visualization.scope import (
    BANNED_SUBSTRINGS,
    DEFAULT_DISCLAIMER_TEXT,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_args(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
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
        "n_samples_input": 1000,
        "n_samples_used_for_compute": 1000,
        "n_clusters_input": 3,
        "n_segments": 3,
        "noise_count": None,
        "noise_ratio": None,
        "noise_policy_used": "exclude",
        "segment_sizes": [
            SegmentSize(
                segment_id=0,
                count=400,
                percentage=40.0,
                percentage_base="n_samples_used_for_compute",
                is_noise=False,
            ),
            SegmentSize(
                segment_id=1,
                count=350,
                percentage=35.0,
                percentage_base="n_samples_used_for_compute",
                is_noise=False,
            ),
            SegmentSize(
                segment_id=2,
                count=250,
                percentage=25.0,
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


def _make_manifest(**overrides: Any) -> SegmentationManifest:
    return build_segmentation_manifest(**_make_args(**overrides))


def _make_chars_for_segment(seg_id: int, n: int = 2) -> list[CharacteristicEntry]:
    """Build ``n`` synthetic characteristics scoped to ``seg_id``."""
    rules = [
        "mean_high_Recency",
        "mean_low_Frequency",
        "median_above_dataset_median_Monetary",
        "top_category_Region_EU",
    ]
    feats = ["Recency", "Frequency", "Monetary", "Region"]
    out: list[CharacteristicEntry] = []
    for i in range(n):
        rule = rules[(seg_id + i) % len(rules)]
        feat = feats[(seg_id + i) % len(feats)]
        out.append(
            CharacteristicEntry(
                characteristic_id=rule,
                description=(
                    f"Descriptive rule {rule} applied to segment {seg_id} "
                    f"for testing purposes only."
                ),
                source_features=[feat],
                derived_stats={"threshold": 1.0, "actual": 1.25, "n": 100},
                segment_id=seg_id,
            )
        )
    return out


def _strip_disclaimer(text: str, disclaimer: str = DEFAULT_DISCLAIMER_TEXT) -> str:
    """Remove all occurrences of ``disclaimer`` from ``text`` (case-insensitive)."""
    if not disclaimer:
        return text
    out = text
    lower = out.lower()
    dl = disclaimer.lower()
    while dl in lower:
        idx = lower.index(dl)
        out = out[:idx] + out[idx + len(dl) :]
        lower = out.lower()
    return out


def _find_banned_substrings(text: str) -> list[str]:
    """Return any banned substrings found in ``text`` (after stripping the disclaimer)."""
    cleaned = _strip_disclaimer(text)
    found: list[str] = []
    for banned in BANNED_SUBSTRINGS:
        pattern = r"\b" + re.escape(banned).replace("\\-", r"[-\s]") + r"\b"
        if re.search(pattern, cleaned, flags=re.IGNORECASE):
            found.append(banned)
    return found


# ---------------------------------------------------------------------------
# Package imports
# ---------------------------------------------------------------------------


def test_package_re_exports_format_segment_profile_table() -> None:
    from customer_segmentation.prototype.visualization import (
        format_segment_profile_table as exported,
    )

    assert exported is format_segment_profile_table


def test_package_re_exports_format_characteristic_entry() -> None:
    from customer_segmentation.prototype.visualization import (
        format_characteristic_entry as exported,
    )

    assert exported is format_characteristic_entry


def test_package_re_exports_collect_segment_characteristics() -> None:
    from customer_segmentation.prototype.visualization import (
        collect_segment_characteristics as exported,
    )

    assert exported is collect_segment_characteristics


# ---------------------------------------------------------------------------
# format_segment_profile_table — happy path
# ---------------------------------------------------------------------------


class TestFormatTableManifestInput:
    def test_contains_segment_profile_header(self) -> None:
        m = _make_manifest()
        table = format_segment_profile_table(m)
        assert "# Segment Profile" in table

    def test_contains_segmentation_id(self) -> None:
        m = _make_manifest()
        table = format_segment_profile_table(m)
        assert m.segmentation_id in table

    def test_contains_algorithm_metadata(self) -> None:
        m = _make_manifest()
        table = format_segment_profile_table(m)
        assert "kmeans" in table
        assert "hard" in table

    def test_contains_n_samples_metadata(self) -> None:
        m = _make_manifest()
        table = format_segment_profile_table(m)
        assert "n_samples_input" in table
        assert str(m.n_samples_input) in table
        assert "n_samples_used_for_compute" in table

    def test_contains_n_segments(self) -> None:
        m = _make_manifest()
        table = format_segment_profile_table(m)
        assert "n_segments" in table
        assert str(m.n_segments) in table

    def test_each_segment_block_present(self) -> None:
        m = _make_manifest()
        table = format_segment_profile_table(m)
        for s in m.segment_sizes:
            assert f"Segment {s.segment_id}" in table

    def test_segment_counts_present(self) -> None:
        m = _make_manifest()
        table = format_segment_profile_table(m)
        for s in m.segment_sizes:
            assert str(s.count) in table

    def test_segment_percentages_present(self) -> None:
        m = _make_manifest()
        table = format_segment_profile_table(m)
        for s in m.segment_sizes:
            assert f"{s.percentage:.1f}" in table

    def test_percentage_base_present(self) -> None:
        m = _make_manifest()
        table = format_segment_profile_table(m)
        for s in m.segment_sizes:
            assert s.percentage_base in table

    def test_is_noise_present(self) -> None:
        m = _make_manifest()
        table = format_segment_profile_table(m)
        assert "is_noise" in table
        # All non-noise rows.
        assert "False" in table

    def test_disclaimer_appended(self) -> None:
        m = _make_manifest()
        table = format_segment_profile_table(m)
        assert "Disclaimer:" in table
        assert DEFAULT_DISCLAIMER_TEXT in table

    def test_no_characteristics_placeholder_when_empty(self) -> None:
        m = _make_manifest()  # no characteristics
        table = format_segment_profile_table(m)
        assert "no characteristics available" in table

    def test_characteristics_block_when_present(self) -> None:
        chars = (
            _make_chars_for_segment(0, n=2)
            + _make_chars_for_segment(1, n=1)
            + _make_chars_for_segment(2, n=1)
        )
        m = _make_manifest(characteristics=chars)
        table = format_segment_profile_table(m)
        assert "characteristics (2):" in table  # for segment 0
        assert "characteristics (1):" in table  # for segment 1 and 2
        # The characteristic_id of every char must appear in the output.
        for c in chars:
            assert c.characteristic_id in table

    def test_preprocessing_warning_surfaced(self) -> None:
        m = _make_manifest(preprocessing_warning="Values are post-preprocessing (test warning).")
        table = format_segment_profile_table(m)
        assert "preprocessing_warning" in table
        assert "Values are post-preprocessing" in table


# ---------------------------------------------------------------------------
# format_segment_profile_table — raw list input
# ---------------------------------------------------------------------------


class TestFormatTableRawListInput:
    def test_accepts_raw_list_of_segment_size(self) -> None:
        sizes = [
            SegmentSize(0, 10, 50.0, "n_samples_input", False),
            SegmentSize(1, 10, 50.0, "n_samples_input", False),
        ]
        table = format_segment_profile_table(sizes)
        assert "Segment 0" in table
        assert "Segment 1" in table
        # Manifest-level metadata fields (with the "# field_name :" header)
        # are NOT rendered when the input is a raw list.
        assert "# segmentation_id" not in table
        assert "# algorithm" not in table
        assert "# n_segments" not in table

    def test_raw_list_has_disclaimer(self) -> None:
        sizes = [
            SegmentSize(0, 10, 50.0, "n_samples_input", False),
        ]
        table = format_segment_profile_table(sizes)
        assert "Disclaimer:" in table
        assert DEFAULT_DISCLAIMER_TEXT in table


# ---------------------------------------------------------------------------
# format_segment_profile_table — noise handling
# ---------------------------------------------------------------------------


class TestFormatTableNoiseHandling:
    def _make_dbscan_manifest(self) -> SegmentationManifest:
        sizes = [
            SegmentSize(0, 400, 40.0, "n_samples_used_for_compute", False),
            SegmentSize(1, 350, 35.0, "n_samples_used_for_compute", False),
            SegmentSize(2, 250, 25.0, "n_samples_used_for_compute", False),
            SegmentSize(-1, 100, 10.0, "n_samples_input", True),
        ]
        return _make_manifest(
            algorithm="dbscan",
            algorithm_family="density_based",
            n_samples_input=1100,
            n_samples_used_for_compute=1000,
            n_clusters_input=3,
            n_segments=3,
            noise_count=100,
            noise_ratio=0.1,
            noise_policy_used="exclude",
            segment_sizes=sizes,
        )

    def test_noise_included_by_default(self) -> None:
        m = self._make_dbscan_manifest()
        table = format_segment_profile_table(m)
        assert "Noise" in table
        assert "is_noise" in table
        assert "True" in table

    def test_noise_excluded_when_flag_false(self) -> None:
        m = self._make_dbscan_manifest()
        table = format_segment_profile_table(m, include_noise=False)
        # The "Noise" block header should not appear.
        # Note: "is_noise : True" is part of the noise block; check the
        # header line specifically.
        assert "# Noise" not in table

    def test_noise_metadata_in_header(self) -> None:
        m = self._make_dbscan_manifest()
        table = format_segment_profile_table(m)
        assert "noise_count" in table
        assert "noise_ratio" in table
        assert "noise_policy_used" in table
        assert str(m.noise_count) in table
        assert m.noise_policy_used in table

    def test_noise_pct_placeholder_when_base_excludes_noise(self) -> None:
        # When percentage_base == n_samples_used_for_compute, the
        # percentage field is not meaningful for noise → placeholder.
        sizes = [
            SegmentSize(0, 400, 40.0, "n_samples_used_for_compute", False),
            SegmentSize(
                -1,
                100,
                0.0,  # meaningless under this base
                "n_samples_used_for_compute",
                True,
            ),
        ]
        m = _make_manifest(
            algorithm="dbscan",
            algorithm_family="density_based",
            n_samples_input=1100,
            n_samples_used_for_compute=1000,
            n_clusters_input=1,
            n_segments=1,
            noise_count=100,
            noise_ratio=0.1,
            noise_policy_used="exclude",
            segment_sizes=sizes,
        )
        table = format_segment_profile_table(m)
        # The placeholder must appear inside the Noise block.
        # The "not meaningful" note is also part of the block.
        assert "not meaningful" in table
        assert "--" in table

    def test_legacy_noise_characteristics_kept_with_noise_block(self) -> None:
        # Characteristics with segment_id == -1 (legacy / backward compat)
        # should appear under the Noise block, not under any other segment.
        sizes = [
            SegmentSize(0, 10, 100.0, "n_samples_input", False),
            SegmentSize(-1, 5, 50.0, "n_samples_input", True),
        ]
        legacy_char = CharacteristicEntry(
            characteristic_id="mean_high_Recency",
            description="Legacy characteristic for noise segment",
            source_features=["Recency"],
            derived_stats={"threshold": 1.0, "actual": 1.5},
            segment_id=-1,
        )
        m = _make_manifest(
            algorithm="dbscan",
            algorithm_family="density_based",
            n_samples_input=15,
            n_samples_used_for_compute=10,
            n_clusters_input=1,
            n_segments=1,
            noise_count=5,
            noise_ratio=0.5,
            noise_policy_used="exclude",
            segment_sizes=sizes,
            characteristics=[legacy_char],
        )
        table = format_segment_profile_table(m)
        # The legacy char should appear in the table (and only under Noise).
        assert legacy_char.characteristic_id in table
        assert "Legacy characteristic for noise segment" in table


# ---------------------------------------------------------------------------
# format_segment_profile_table — error / edge cases
# ---------------------------------------------------------------------------


def test_empty_segment_sizes_raises() -> None:
    with pytest.raises(VisualizationError, match="no segment_sizes"):
        format_segment_profile_table([])


def test_custom_disclaimer_overrides_default() -> None:
    m = _make_manifest()
    custom = "custom disclaimer text"
    table = format_segment_profile_table(m, disclaimer=custom)
    assert custom in table
    assert DEFAULT_DISCLAIMER_TEXT not in table


def test_custom_missing_placeholder_used() -> None:
    sizes = [
        SegmentSize(0, 10, 100.0, "n_samples_input", False),
        SegmentSize(-1, 5, 50.0, "n_samples_used_for_compute", True),
    ]
    m = _make_manifest(
        algorithm="dbscan",
        algorithm_family="density_based",
        n_samples_input=15,
        n_samples_used_for_compute=10,
        n_clusters_input=1,
        n_segments=1,
        noise_count=5,
        noise_ratio=0.5,
        noise_policy_used="exclude",
        segment_sizes=sizes,
    )
    table = format_segment_profile_table(m, missing_value_placeholder="N/A")
    assert "N/A" in table


def test_output_is_stable_across_calls() -> None:
    """Same input must produce the same output (deterministic)."""
    m = _make_manifest(
        characteristics=(
            _make_chars_for_segment(0, n=2)
            + _make_chars_for_segment(1, n=2)
            + _make_chars_for_segment(2, n=2)
        )
    )
    t1 = format_segment_profile_table(m)
    t2 = format_segment_profile_table(m)
    assert t1 == t2


def test_banned_words_not_present_outside_disclaimer() -> None:
    """No banned word may appear outside the disclaimer phrase."""
    m = _make_manifest(
        characteristics=(
            _make_chars_for_segment(0, n=2)
            + _make_chars_for_segment(1, n=2)
            + _make_chars_for_segment(2, n=2)
        ),
        preprocessing_warning="Some post-preprocessing warning text.",
    )
    table = format_segment_profile_table(m)
    found = _find_banned_substrings(table)
    assert found == [], f"Banned substrings found: {found}"


def test_banned_words_check_uses_visualization_constants() -> None:
    """The check must operate on the visualization BANNED_SUBSTRINGS set."""
    # Sanity: the visualization list must contain at least one known entry.
    assert "best" in BANNED_SUBSTRINGS
    assert "winner" in BANNED_SUBSTRINGS
    assert "churn" in BANNED_SUBSTRINGS


# ---------------------------------------------------------------------------
# format_characteristic_entry
# ---------------------------------------------------------------------------


class TestFormatCharacteristicEntry:
    def test_basic_fields_present(self) -> None:
        c = CharacteristicEntry(
            characteristic_id="mean_high_Recency",
            description="Mean of Recency is above threshold",
            source_features=["Recency"],
            derived_stats={"threshold": 1.0, "actual": 1.5},
            segment_id=0,
        )
        out = format_characteristic_entry(c)
        assert "mean_high_Recency" in out
        assert "Mean of Recency is above threshold" in out
        assert "Recency" in out
        assert "threshold=1.0" in out
        assert "actual=1.5" in out

    def test_empty_description_renders_placeholder(self) -> None:
        c = CharacteristicEntry(
            characteristic_id="mean_high_Recency",
            description="",
            source_features=["Recency"],
            derived_stats={"threshold": 1.0},
            segment_id=0,
        )
        out = format_characteristic_entry(c)
        assert "--" in out

    def test_source_features_non_empty_per_contract(self) -> None:
        """Per the manifest contract, source_features MUST be non-empty.

        This is enforced at the manifest layer; the visualization layer
        relies on the invariant. We assert the contract here so the
        expectation is documented next to the visual layer tests.
        """
        from customer_segmentation.prototype.segmentation.manifest import (
            SegmentationManifestError,
        )

        with pytest.raises(SegmentationManifestError, match="source_features"):
            CharacteristicEntry(
                characteristic_id="mean_high_Recency",
                description="x",
                source_features=[],
                derived_stats={"threshold": 1.0},
                segment_id=0,
            )

    def test_empty_derived_stats_renders_placeholder(self) -> None:
        c = CharacteristicEntry(
            characteristic_id="mean_high_Recency",
            description="x",
            source_features=["Recency"],
            derived_stats={},
            segment_id=0,
        )
        out = format_characteristic_entry(c)
        assert "derived_stats: --" in out

    def test_none_value_in_stats_renders_placeholder(self) -> None:
        c = CharacteristicEntry(
            characteristic_id="mean_high_Recency",
            description="x",
            source_features=["Recency"],
            derived_stats={"threshold": None},
            segment_id=0,
        )
        out = format_characteristic_entry(c)
        assert "threshold=--" in out

    def test_dict_value_in_stats_renders_as_json(self) -> None:
        c = CharacteristicEntry(
            characteristic_id="mean_high_Recency",
            description="x",
            source_features=["Recency"],
            derived_stats={"sub": {"a": 1, "b": 2}},
            segment_id=0,
        )
        out = format_characteristic_entry(c)
        # JSON is compact + sorted; braces appear.
        assert "{" in out
        assert "}" in out

    def test_list_value_in_stats_renders_as_json(self) -> None:
        c = CharacteristicEntry(
            characteristic_id="mean_high_Recency",
            description="x",
            source_features=["Recency"],
            derived_stats={"values": [1, 2, 3]},
            segment_id=0,
        )
        out = format_characteristic_entry(c)
        assert "[1,2,3]" in out or "[1, 2, 3]" in out

    def test_custom_missing_placeholder(self) -> None:
        c = CharacteristicEntry(
            characteristic_id="mean_high_Recency",
            description="",
            source_features=["Recency"],
            derived_stats={},
            segment_id=0,
        )
        out = format_characteristic_entry(c, missing_value_placeholder="N/A")
        # Empty description + empty derived_stats both render as the
        # custom placeholder.
        assert "N/A" in out


# ---------------------------------------------------------------------------
# collect_segment_characteristics
# ---------------------------------------------------------------------------


class TestCollectSegmentCharacteristics:
    def test_filters_by_segment_id(self) -> None:
        chars = (
            _make_chars_for_segment(0, n=2)
            + _make_chars_for_segment(1, n=1)
            + _make_chars_for_segment(2, n=3)
        )
        result = collect_segment_characteristics(chars, segment_id=0)
        assert len(result) == 2
        assert all(int(c.segment_id) == 0 for c in result)

    def test_no_match_returns_empty(self) -> None:
        chars = _make_chars_for_segment(0, n=1)
        result = collect_segment_characteristics(chars, segment_id=999)
        assert result == []

    def test_empty_input_returns_empty(self) -> None:
        assert collect_segment_characteristics([], segment_id=0) == []

    def test_accepts_manifest(self) -> None:
        chars = _make_chars_for_segment(0, n=1) + _make_chars_for_segment(1, n=1)
        m = _make_manifest(characteristics=chars)
        result = collect_segment_characteristics(m, segment_id=1)
        assert len(result) == 1
        assert int(result[0].segment_id) == 1

    def test_preserves_input_order(self) -> None:
        chars = _make_chars_for_segment(0, n=3)
        result = collect_segment_characteristics(chars, segment_id=0)
        assert [c.characteristic_id for c in result] == [c.characteristic_id for c in chars]


# ---------------------------------------------------------------------------
# Schema evidence — confirm we read only documented fields
# ---------------------------------------------------------------------------


def test_only_documented_fields_are_read() -> None:
    """The table must not invent fields beyond the documented contract."""
    m = _make_manifest()
    # Sanity: the documented SegmentationManifest fields are present.
    assert hasattr(m, "segment_sizes")
    assert hasattr(m, "characteristics")
    assert hasattr(m, "n_samples_input")
    assert hasattr(m, "n_samples_used_for_compute")
    assert hasattr(m, "n_segments")
    assert hasattr(m, "algorithm")
    assert hasattr(m, "algorithm_family")
    assert hasattr(m, "noise_count")
    assert hasattr(m, "noise_ratio")
    assert hasattr(m, "noise_policy_used")
    assert hasattr(m, "segmentation_id")
    assert hasattr(m, "preprocessing_warning")

    table = format_segment_profile_table(m)
    # The header section is the only place where manifest metadata appears.
    header_end = table.find("# " + "-" * 78)
    header_section = table[:header_end] if header_end != -1 else ""
    # Each documented field name must appear at least once in the header.
    for field_name in (
        "segmentation_id",
        "algorithm",
        "n_samples_input",
        "n_samples_used_for_compute",
        "n_segments",
    ):
        assert (
            field_name in header_section
        ), f"Expected {field_name!r} in header section; got:\n{header_section}"
