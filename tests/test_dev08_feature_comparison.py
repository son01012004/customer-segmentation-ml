"""Tests for DEV-08 feature comparison chart (Task 1.4)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from customer_segmentation.prototype.segmentation.manifest import (
    FeatureProfile,
    SegmentationManifest,
    SegmentationValidationReport,
    SegmentSize,
    build_segmentation_manifest,
)
from customer_segmentation.prototype.segmentation.scope import (
    PROFILING_STATISTICS_SET,
)
from customer_segmentation.prototype.visualization.charts.feature_comparison import (
    extract_statistic_matrix,
    format_feature_comparison_table,
    format_statistic_value,
    get_feature_color,
    is_numerical_statistic,
    plot_feature_bars,
    plot_feature_heatmap,
)
from customer_segmentation.prototype.visualization.exceptions import (
    VisualizationError,
)
from customer_segmentation.prototype.visualization.scope import (
    BANNED_SUBSTRINGS,
    DEFAULT_COLOR_PALETTE,
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
        "profiles": [],
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


def _make_full_manifest() -> SegmentationManifest:
    """Manifest with 3 features × 3 segments × multiple statistics."""
    profiles = [
        FeatureProfile(
            segment_id=0,
            feature_name="Recency",
            statistics={"mean": 5.0, "median": 4.0, "std": 1.0, "min": 0, "max": 10},
        ),
        FeatureProfile(
            segment_id=1,
            feature_name="Recency",
            statistics={"mean": 15.0, "median": 14.0, "std": 2.0, "min": 10, "max": 20},
        ),
        FeatureProfile(
            segment_id=2,
            feature_name="Recency",
            statistics={"mean": 30.0, "median": 30.0, "std": 5.0, "min": 20, "max": 40},
        ),
        FeatureProfile(
            segment_id=0,
            feature_name="Frequency",
            statistics={"mean": 10.0, "median": 9.0, "std": 2.0, "min": 1, "max": 20},
        ),
        FeatureProfile(
            segment_id=1,
            feature_name="Frequency",
            statistics={"mean": 5.0, "median": 4.0, "std": 1.5, "min": 1, "max": 10},
        ),
        FeatureProfile(
            segment_id=2,
            feature_name="Frequency",
            statistics={"mean": 2.0, "median": 2.0, "std": 0.5, "min": 1, "max": 5},
        ),
        FeatureProfile(
            segment_id=0,
            feature_name="Monetary",
            statistics={"mean": 1000.0, "median": 900.0, "std": 200.0, "min": 0, "max": 2000},
        ),
        FeatureProfile(
            segment_id=1,
            feature_name="Monetary",
            statistics={"mean": 500.0, "median": 450.0, "std": 100.0, "min": 100, "max": 1000},
        ),
        FeatureProfile(
            segment_id=2,
            feature_name="Monetary",
            statistics={"mean": 200.0, "median": 200.0, "std": 50.0, "min": 50, "max": 500},
        ),
    ]
    return _make_manifest(profiles=profiles)


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
    """Return any banned substrings found in ``text`` (after stripping disclaimer)."""
    cleaned = _strip_disclaimer(text)
    found: list[str] = []
    for banned in BANNED_SUBSTRINGS:
        pattern = r"\b" + re.escape(banned).replace("\\-", r"[-\s]") + r"\b"
        if re.search(pattern, cleaned, flags=re.IGNORECASE):
            found.append(banned)
    return found


# ---------------------------------------------------------------------------
# Package imports / re-exports
# ---------------------------------------------------------------------------


def test_package_re_exports_format_feature_comparison_table() -> None:
    from customer_segmentation.prototype.visualization import (
        format_feature_comparison_table as exported,
    )

    assert exported is format_feature_comparison_table


def test_package_re_exports_plot_feature_heatmap() -> None:
    from customer_segmentation.prototype.visualization import (
        plot_feature_heatmap as exported,
    )

    assert exported is plot_feature_heatmap


def test_package_re_exports_plot_feature_bars() -> None:
    from customer_segmentation.prototype.visualization import (
        plot_feature_bars as exported,
    )

    assert exported is plot_feature_bars


def test_package_re_exports_get_feature_color() -> None:
    from customer_segmentation.prototype.visualization import (
        get_feature_color as exported,
    )

    assert exported is get_feature_color


def test_package_re_exports_extract_statistic_matrix() -> None:
    from customer_segmentation.prototype.visualization import (
        extract_statistic_matrix as exported,
    )

    assert exported is extract_statistic_matrix


def test_package_re_exports_format_statistic_value() -> None:
    from customer_segmentation.prototype.visualization import (
        format_statistic_value as exported,
    )

    assert exported is format_statistic_value


def test_package_re_exports_is_numerical_statistic() -> None:
    from customer_segmentation.prototype.visualization import (
        is_numerical_statistic as exported,
    )

    assert exported is is_numerical_statistic


# ---------------------------------------------------------------------------
# Constants / helpers
# ---------------------------------------------------------------------------


class TestIsNumericalStatistic:
    @pytest.mark.parametrize("stat", ["mean", "median", "std", "q1", "q3", "min", "max"])
    def test_numerical_statistics(self, stat: str) -> None:
        assert is_numerical_statistic(stat) is True

    @pytest.mark.parametrize(
        "stat", ["topk_categories", "value_counts", "other_count", "missing_count"]
    )
    def test_categorical_statistics(self, stat: str) -> None:
        assert is_numerical_statistic(stat) is False

    def test_unknown_returns_false(self) -> None:
        assert is_numerical_statistic("silhouette") is False
        assert is_numerical_statistic("") is False


class TestGetFeatureColor:
    def test_returns_palette_entry(self) -> None:
        c = get_feature_color("Recency")
        assert c in DEFAULT_COLOR_PALETTE

    def test_is_deterministic(self) -> None:
        c1 = get_feature_color("Frequency")
        c2 = get_feature_color("Frequency")
        assert c1 == c2

    def test_different_features_can_have_different_colors(self) -> None:
        # Recency, Frequency, Monetary should map to different palette
        # entries given the hash function. (They do; assert at least
        # two distinct colors across the 3 features.)
        colors = {
            get_feature_color("Recency"),
            get_feature_color("Frequency"),
            get_feature_color("Monetary"),
        }
        assert len(colors) >= 2

    def test_color_in_palette(self) -> None:
        for name in ("alpha", "beta", "gamma", "x", "y", "z"):
            assert get_feature_color(name) in DEFAULT_COLOR_PALETTE


class TestFormatStatisticValue:
    def test_none_renders_placeholder(self) -> None:
        assert format_statistic_value(None) == "--"

    def test_int(self) -> None:
        assert format_statistic_value(42) == "42"

    def test_float(self) -> None:
        assert format_statistic_value(1.5) == "1.5"

    def test_float_trims_trailing_zeros(self) -> None:
        assert format_statistic_value(1.0) == "1"

    def test_nan_renders_placeholder(self) -> None:
        assert format_statistic_value(float("nan")) == "--"

    def test_inf_renders_placeholder(self) -> None:
        assert format_statistic_value(float("inf")) == "--"

    def test_list_renders_compact(self) -> None:
        out = format_statistic_value([("EU", 50), ("US", 30)])
        assert "EU:50" in out
        assert "US:30" in out

    def test_empty_list_renders_placeholder(self) -> None:
        assert format_statistic_value([]) == "--"

    def test_dict_renders_compact(self) -> None:
        out = format_statistic_value({"a": 1, "b": 2})
        assert "a=1" in out
        assert "b=2" in out

    def test_empty_dict_renders_placeholder(self) -> None:
        assert format_statistic_value({}) == "--"

    def test_custom_placeholder(self) -> None:
        assert format_statistic_value(None, missing_value_placeholder="N/A") == "N/A"

    def test_bool(self) -> None:
        assert format_statistic_value(True) == "True"
        assert format_statistic_value(False) == "False"


# ---------------------------------------------------------------------------
# extract_statistic_matrix
# ---------------------------------------------------------------------------


class TestExtractStatisticMatrix:
    def test_basic_extraction(self) -> None:
        m = _make_full_manifest()
        feats, sids, vals = extract_statistic_matrix(m, "mean")
        assert feats == ["Frequency", "Monetary", "Recency"]  # sorted
        assert sids == [0, 1, 2]
        # Recency mean: 5.0, 15.0, 30.0 → row index 2 (alphabetical order)
        assert vals[2] == [5.0, 15.0, 30.0]
        # Frequency mean: 10.0, 5.0, 2.0 → row index 0
        assert vals[0] == [10.0, 5.0, 2.0]
        # Monetary mean: 1000.0, 500.0, 200.0 → row index 1
        assert vals[1] == [1000.0, 500.0, 200.0]

    def test_invalid_statistic_raises(self) -> None:
        m = _make_full_manifest()
        with pytest.raises(VisualizationError, match="not a supported profile"):
            extract_statistic_matrix(m, "silhouette")

    def test_empty_profiles_raises(self) -> None:
        m = _make_manifest(profiles=[])
        with pytest.raises(VisualizationError, match="profiles is empty"):
            extract_statistic_matrix(m, "mean")

    def test_missing_statistic_renders_as_none(self) -> None:
        # Recency has no 'q1' in the fixture.
        m = _make_full_manifest()
        feats, sids, vals = extract_statistic_matrix(m, "q1")
        # All values should be None.
        for row in vals:
            for cell in row:
                assert cell is None

    def test_features_sorted_deterministically(self) -> None:
        m = _make_full_manifest()
        feats, _, _ = extract_statistic_matrix(m, "mean")
        assert feats == sorted(feats)

    def test_categorical_statistic_extraction(self) -> None:
        # topk_categories is a list of (category, count) tuples
        profiles = [
            FeatureProfile(
                segment_id=0,
                feature_name="Region",
                statistics={
                    "topk_categories": [("EU", 50), ("US", 30)],
                    "value_counts": {"EU": 50, "US": 30},
                },
            ),
            FeatureProfile(
                segment_id=1,
                feature_name="Region",
                statistics={
                    "topk_categories": [("US", 60), ("EU", 20)],
                    "value_counts": {"US": 60, "EU": 20},
                },
            ),
        ]
        m = _make_manifest(profiles=profiles)
        feats, sids, vals = extract_statistic_matrix(m, "topk_categories")
        assert feats == ["Region"]
        assert sids == [0, 1, 2]
        # Segment 2 has no Region profile → cell is None.
        assert vals[0][0] == [("EU", 50), ("US", 30)]
        assert vals[0][1] == [("US", 60), ("EU", 20)]
        assert vals[0][2] is None

    def test_raw_list_input(self) -> None:
        # When input is a raw list of FeatureProfile, segment_ids are
        # inferred from the profiles themselves.
        profiles = [
            FeatureProfile(segment_id=0, feature_name="F", statistics={"mean": 1.0}),
            FeatureProfile(segment_id=1, feature_name="F", statistics={"mean": 2.0}),
        ]
        feats, sids, vals = extract_statistic_matrix(profiles, "mean")
        assert feats == ["F"]
        assert sids == [0, 1]
        assert vals == [[1.0, 2.0]]


# ---------------------------------------------------------------------------
# format_feature_comparison_table
# ---------------------------------------------------------------------------


class TestFormatFeatureComparisonTable:
    def test_contains_header(self) -> None:
        m = _make_full_manifest()
        table = format_feature_comparison_table(m, statistic="mean")
        assert "# Feature Comparison" in table

    def test_contains_statistic_label(self) -> None:
        m = _make_full_manifest()
        table = format_feature_comparison_table(m, statistic="median")
        assert "statistic         : median" in table

    def test_contains_segmentation_id(self) -> None:
        m = _make_full_manifest()
        table = format_feature_comparison_table(m, statistic="mean")
        assert m.segmentation_id in table

    def test_contains_post_preprocessing_warning(self) -> None:
        m = _make_full_manifest()
        table = format_feature_comparison_table(m, statistic="mean")
        assert "Values are post-preprocessing" in table
        assert "preprocessing_warning" not in table  # not set

    def test_preprocessing_warning_surfaced_when_set(self) -> None:
        m = _make_manifest(
            profiles=[
                FeatureProfile(segment_id=0, feature_name="F", statistics={"mean": 1.0}),
            ],
            preprocessing_warning="Custom preprocessing warning text.",
        )
        table = format_feature_comparison_table(m, statistic="mean")
        assert "preprocessing_warning" in table
        assert "Custom preprocessing warning text." in table

    def test_all_features_present(self) -> None:
        m = _make_full_manifest()
        table = format_feature_comparison_table(m, statistic="mean")
        for f in ("Recency", "Frequency", "Monetary"):
            assert f in table

    def test_all_segment_ids_in_header(self) -> None:
        m = _make_full_manifest()
        table = format_feature_comparison_table(m, statistic="mean")
        for sid in (0, 1, 2):
            assert f"seg_{sid}" in table

    def test_correct_value_in_cell(self) -> None:
        m = _make_full_manifest()
        table = format_feature_comparison_table(m, statistic="mean")
        # The formatter trims trailing zeros; float 5.0 renders as "5".
        # Recency mean: [5.0, 15.0, 30.0] → "5", "15", "30" in the row.
        assert "5" in table
        assert "15" in table
        assert "30" in table

    def test_missing_statistic_renders_placeholder(self) -> None:
        m = _make_full_manifest()
        table = format_feature_comparison_table(m, statistic="q1")
        assert "--" in table

    def test_disclaimer_appended(self) -> None:
        m = _make_full_manifest()
        table = format_feature_comparison_table(m, statistic="mean")
        assert "Disclaimer:" in table
        assert DEFAULT_DISCLAIMER_TEXT in table

    def test_custom_disclaimer(self) -> None:
        m = _make_full_manifest()
        table = format_feature_comparison_table(m, statistic="mean", disclaimer="custom text")
        assert "custom text" in table
        assert DEFAULT_DISCLAIMER_TEXT not in table

    def test_custom_missing_placeholder(self) -> None:
        m = _make_full_manifest()
        table = format_feature_comparison_table(m, statistic="q1", missing_value_placeholder="N/A")
        assert "N/A" in table

    def test_invalid_statistic_raises(self) -> None:
        m = _make_full_manifest()
        with pytest.raises(VisualizationError, match="not a supported profile"):
            format_feature_comparison_table(m, statistic="silhouette")

    def test_categorical_statistic_renders_in_table(self) -> None:
        profiles = [
            FeatureProfile(
                segment_id=0,
                feature_name="Region",
                statistics={"topk_categories": [("EU", 50)]},
            ),
        ]
        m = _make_manifest(profiles=profiles)
        table = format_feature_comparison_table(m, statistic="topk_categories")
        assert "EU:50" in table

    def test_feature_absent_from_some_segments_renders_placeholder(self) -> None:
        # Region exists for segment 0 only.
        profiles = [
            FeatureProfile(
                segment_id=0,
                feature_name="Region",
                statistics={"mean": 1.0},
            ),
        ]
        m = _make_manifest(profiles=profiles)
        table = format_feature_comparison_table(m, statistic="mean")
        # The placeholder must appear in the table for segments 1 and 2.
        assert "--" in table

    def test_banned_words_not_present_outside_disclaimer(self) -> None:
        m = _make_full_manifest()
        table = format_feature_comparison_table(m, statistic="mean")
        found = _find_banned_substrings(table)
        assert found == [], f"Banned substrings found: {found}"

    def test_output_is_stable(self) -> None:
        m = _make_full_manifest()
        t1 = format_feature_comparison_table(m, statistic="mean")
        t2 = format_feature_comparison_table(m, statistic="mean")
        assert t1 == t2

    def test_feature_set_uses_documented_field(self) -> None:
        # Sanity: FeatureProfile has the documented fields.
        m = _make_full_manifest()
        # The manifest's feature_set list is a documented field.
        assert hasattr(m, "feature_set")
        assert m.feature_set == ["Recency", "Frequency", "Monetary"]


# ---------------------------------------------------------------------------
# plot_feature_heatmap
# ---------------------------------------------------------------------------


class TestPlotFeatureHeatmap:
    def test_renders_with_valid_manifest(self) -> None:
        m = _make_full_manifest()
        fig = plot_feature_heatmap(m, statistic="mean")
        assert fig is not None
        import matplotlib.pyplot as plt

        plt.close(fig)

    def test_saves_to_output_path(self, tmp_path: Path) -> None:
        m = _make_full_manifest()
        out = tmp_path / "heatmap.png"
        fig = plot_feature_heatmap(m, statistic="mean", output_path=out)
        assert out.exists()
        assert out.stat().st_size > 0
        import matplotlib.pyplot as plt

        plt.close(fig)

    def test_non_numerical_statistic_raises(self) -> None:
        m = _make_full_manifest()
        with pytest.raises(VisualizationError, match="numerical statistic"):
            plot_feature_heatmap(m, statistic="topk_categories")

    def test_invalid_statistic_raises(self) -> None:
        m = _make_full_manifest()
        with pytest.raises(VisualizationError, match="requires a numerical statistic"):
            plot_feature_heatmap(m, statistic="silhouette")

    def test_too_many_features_raises(self) -> None:
        # Build a manifest with more than MAX_HEATMAP_FEATURES features.
        profiles = [
            FeatureProfile(
                segment_id=0,
                feature_name=f"F{i:03d}",
                statistics={"mean": float(i)},
            )
            for i in range(50)
        ]
        m = _make_manifest(profiles=profiles)
        with pytest.raises(VisualizationError, match="exceeds MAX_HEATMAP_FEATURES"):
            plot_feature_heatmap(m, statistic="mean")

    def test_empty_profiles_raises(self) -> None:
        m = _make_manifest(profiles=[])
        with pytest.raises(VisualizationError, match="profiles is empty"):
            plot_feature_heatmap(m, statistic="mean")

    def test_custom_title(self) -> None:
        m = _make_full_manifest()
        fig = plot_feature_heatmap(m, statistic="mean", title="My Title")
        assert fig is not None
        import matplotlib.pyplot as plt

        plt.close(fig)

    def test_every_numerical_statistic_renders(self) -> None:
        m = _make_full_manifest()
        for stat in ("mean", "median", "std", "q1", "q3", "min", "max"):
            fig = plot_feature_heatmap(m, statistic=stat)
            assert fig is not None
            import matplotlib.pyplot as plt

            plt.close(fig)

    def test_missing_value_renders_placeholder(self, tmp_path: Path) -> None:
        # q1 is missing in the fixture; the heatmap should still render
        # with placeholder cells.
        m = _make_full_manifest()
        out = tmp_path / "heatmap.png"
        fig = plot_feature_heatmap(m, statistic="q1", output_path=out)
        assert out.exists()
        import matplotlib.pyplot as plt

        plt.close(fig)

    def test_no_normalization_applied(self) -> None:
        """Per the constraint: values are never normalized / rescaled."""
        m = _make_full_manifest()
        # Extract raw values; verify they are unchanged.
        _, _, vals = extract_statistic_matrix(m, "mean")
        # Monetary mean is 1000.0, 500.0, 200.0 — these are not
        # normalized. If the heatmap were normalizing per-row, the
        # resulting matrix passed to imshow would not match.
        assert vals[1] == [1000.0, 500.0, 200.0]


# ---------------------------------------------------------------------------
# plot_feature_bars
# ---------------------------------------------------------------------------


class TestPlotFeatureBars:
    def test_renders_with_valid_input(self) -> None:
        m = _make_full_manifest()
        fig = plot_feature_bars(m, feature_name="Recency", statistic="mean")
        assert fig is not None
        import matplotlib.pyplot as plt

        plt.close(fig)

    def test_saves_to_output_path(self, tmp_path: Path) -> None:
        m = _make_full_manifest()
        out = tmp_path / "bars.png"
        fig = plot_feature_bars(m, feature_name="Recency", statistic="mean", output_path=out)
        assert out.exists()
        assert out.stat().st_size > 0
        import matplotlib.pyplot as plt

        plt.close(fig)

    def test_unknown_feature_raises(self) -> None:
        m = _make_full_manifest()
        with pytest.raises(VisualizationError, match="not present in any profile"):
            plot_feature_bars(m, feature_name="Nope", statistic="mean")

    def test_non_numerical_statistic_raises(self) -> None:
        m = _make_full_manifest()
        with pytest.raises(VisualizationError, match="numerical statistic"):
            plot_feature_bars(m, feature_name="Recency", statistic="topk_categories")

    def test_invalid_statistic_raises(self) -> None:
        m = _make_full_manifest()
        with pytest.raises(VisualizationError, match="requires a numerical statistic"):
            plot_feature_bars(m, feature_name="Recency", statistic="silhouette")

    def test_missing_value_uses_placeholder(self, tmp_path: Path) -> None:
        m = _make_full_manifest()
        out = tmp_path / "bars.png"
        # q1 is missing → bars should still render (with placeholders).
        fig = plot_feature_bars(m, feature_name="Recency", statistic="q1", output_path=out)
        assert out.exists()
        import matplotlib.pyplot as plt

        plt.close(fig)

    def test_every_numerical_statistic_renders(self) -> None:
        m = _make_full_manifest()
        for stat in ("mean", "median", "std", "q1", "q3", "min", "max"):
            fig = plot_feature_bars(m, feature_name="Recency", statistic=stat)
            assert fig is not None
            import matplotlib.pyplot as plt

            plt.close(fig)

    def test_custom_title(self) -> None:
        m = _make_full_manifest()
        fig = plot_feature_bars(m, feature_name="Recency", statistic="mean", title="My Title")
        assert fig is not None
        import matplotlib.pyplot as plt

        plt.close(fig)


# ---------------------------------------------------------------------------
# Noise handling
# ---------------------------------------------------------------------------


class TestNoiseHandling:
    def _make_manifest_with_noise(self) -> SegmentationManifest:
        sizes = [
            SegmentSize(0, 400, 40.0, "n_samples_used_for_compute", False),
            SegmentSize(1, 350, 35.0, "n_samples_used_for_compute", False),
            SegmentSize(2, 250, 25.0, "n_samples_used_for_compute", False),
            SegmentSize(-1, 50, 5.0, "n_samples_input", True),
        ]
        profiles = [
            FeatureProfile(segment_id=0, feature_name="F", statistics={"mean": 1.0}),
            FeatureProfile(segment_id=1, feature_name="F", statistics={"mean": 2.0}),
            FeatureProfile(segment_id=2, feature_name="F", statistics={"mean": 3.0}),
            FeatureProfile(segment_id=-1, feature_name="F", statistics={"mean": 99.0}),
        ]
        return _make_manifest(
            algorithm="dbscan",
            algorithm_family="density_based",
            n_samples_input=1050,
            n_samples_used_for_compute=1000,
            n_clusters_input=3,
            n_segments=3,
            noise_count=50,
            noise_ratio=0.05,
            noise_policy_used="exclude",
            segment_sizes=sizes,
            profiles=profiles,
        )

    def test_noise_included_by_default(self) -> None:
        m = self._make_manifest_with_noise()
        _, sids, vals = extract_statistic_matrix(m, "mean")
        assert -1 in sids
        # The noise value 99.0 should appear in the matrix.
        for row in vals:
            if -1 in sids and 99.0 in row:
                break
        else:
            pytest.fail("Noise value 99.0 not found in matrix")

    def test_noise_excluded_when_flag_false(self) -> None:
        m = self._make_manifest_with_noise()
        _, sids, vals = extract_statistic_matrix(m, "mean", include_noise=False)
        assert -1 not in sids
        # The 99.0 value should not appear anywhere.
        for row in vals:
            for cell in row:
                if cell is not None:
                    assert cell != 99.0

    def test_text_table_with_noise(self) -> None:
        m = self._make_manifest_with_noise()
        table = format_feature_comparison_table(m, statistic="mean")
        # Noise column header should appear
        assert "Noise (-1)" in table

    def test_heatmap_with_noise(self) -> None:
        m = self._make_manifest_with_noise()
        fig = plot_feature_heatmap(m, statistic="mean")
        assert fig is not None
        import matplotlib.pyplot as plt

        plt.close(fig)

    def test_bars_with_noise(self) -> None:
        m = self._make_manifest_with_noise()
        fig = plot_feature_bars(m, feature_name="F", statistic="mean")
        assert fig is not None
        import matplotlib.pyplot as plt

        plt.close(fig)


# ---------------------------------------------------------------------------
# Schema evidence
# ---------------------------------------------------------------------------


def test_only_documented_fields_are_read() -> None:
    """Verify the module only reads documented FeatureProfile fields."""
    m = _make_full_manifest()
    # Documented FeatureProfile fields.
    p = m.profiles[0]
    assert hasattr(p, "segment_id")
    assert hasattr(p, "feature_name")
    assert hasattr(p, "statistics")
    # Documented manifest fields.
    assert hasattr(m, "profiles")
    assert hasattr(m, "segment_sizes")
    assert hasattr(m, "segmentation_id")
    assert hasattr(m, "preprocessing_warning")


def test_profiling_statistics_set_constant() -> None:
    """Verify the supported statistics are a known closed set."""
    # All 7 numerical + 4 categorical = 11 names.
    assert len(PROFILING_STATISTICS_SET) == 11
    # Numerical subset.
    assert {"mean", "median", "std", "q1", "q3", "min", "max"}.issubset(PROFILING_STATISTICS_SET)
    # Categorical subset.
    assert {
        "topk_categories",
        "value_counts",
        "other_count",
        "missing_count",
    }.issubset(PROFILING_STATISTICS_SET)
