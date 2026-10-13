"""Tests for DEV-08 cluster distribution chart (Task 1.2)."""

from __future__ import annotations

from pathlib import Path

import matplotlib
import pytest

from customer_segmentation.prototype.segmentation.manifest import (
    FeatureProfile,
    SegmentationManifest,
    SegmentationValidationReport,
    SegmentSize,
    build_segmentation_manifest,
)
from customer_segmentation.prototype.visualization.charts.cluster_distribution import (
    format_cluster_distribution_table,
    get_segment_color,
    plot_cluster_distribution,
)
from customer_segmentation.prototype.visualization.exceptions import (
    VisualizationError,
)
from customer_segmentation.prototype.visualization.scope import (
    DEFAULT_COLOR_PALETTE,
    DEFAULT_DISCLAIMER_TEXT,
    NOISE_COLOR,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_args(**overrides):
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


def _make_manifest(**overrides):
    return build_segmentation_manifest(**_make_args(**overrides))


# ---------------------------------------------------------------------------
# Package imports
# ---------------------------------------------------------------------------


def test_package_re_exports_get_segment_color() -> None:
    from customer_segmentation.prototype.visualization import get_segment_color

    assert get_segment_color is get_segment_color


def test_package_re_exports_format_cluster_distribution_table() -> None:
    from customer_segmentation.prototype.visualization import (
        format_cluster_distribution_table,
    )

    assert format_cluster_distribution_table is format_cluster_distribution_table


def test_package_re_exports_plot_cluster_distribution() -> None:
    from customer_segmentation.prototype.visualization import plot_cluster_distribution

    assert plot_cluster_distribution is plot_cluster_distribution


# ---------------------------------------------------------------------------
# get_segment_color
# ---------------------------------------------------------------------------


def test_segment_color_within_palette_range() -> None:
    """Segment IDs within palette length map to their index."""
    for seg_id in range(len(DEFAULT_COLOR_PALETTE)):
        color = get_segment_color(seg_id)
        assert color in DEFAULT_COLOR_PALETTE


def test_segment_color_modulo_wraps() -> None:
    """Segment IDs beyond palette length wrap via modulo."""
    palette_len = len(DEFAULT_COLOR_PALETTE)
    for seg_id in range(palette_len, palette_len * 3):
        expected = DEFAULT_COLOR_PALETTE[seg_id % palette_len]
        assert get_segment_color(seg_id) == expected


def test_segment_color_deterministic() -> None:
    """The same segment_id always returns the same colour."""
    for seg_id in [0, 1, 7, 42, -1]:
        assert get_segment_color(seg_id) == get_segment_color(seg_id)


def test_segment_color_noise_negative_id() -> None:
    """Noise segment ID -1 gets a colour (modulo wraps)."""
    color = get_segment_color(-1)
    assert color in DEFAULT_COLOR_PALETTE


def test_segment_color_distinct_entries() -> None:
    """Different segment IDs produce distinct colours (within palette size)."""
    palette_len = len(DEFAULT_COLOR_PALETTE)
    seen: set[str] = set()
    for seg_id in range(palette_len):
        color = get_segment_color(seg_id)
        assert color not in seen, f"Colour collision for segment_id={seg_id}"
        seen.add(color)


# ---------------------------------------------------------------------------
# format_cluster_distribution_table — happy path
# ---------------------------------------------------------------------------


class TestFormatTableManifestInput:
    def test_header_present(self) -> None:
        m = _make_manifest()
        table = format_cluster_distribution_table(m)
        assert "segment_id" in table
        assert "count" in table
        assert "pct" in table

    def test_all_segments_present(self) -> None:
        m = _make_manifest()
        table = format_cluster_distribution_table(m)
        for s in m.segment_sizes:
            assert str(s.segment_id) in table

    def test_counts_correct(self) -> None:
        m = _make_manifest()
        table = format_cluster_distribution_table(m)
        for s in m.segment_sizes:
            assert str(s.count) in table

    def test_percentages_correct(self) -> None:
        m = _make_manifest()
        table = format_cluster_distribution_table(m)
        for s in m.segment_sizes:
            assert f"{s.percentage:.1f}" in table

    def test_n_samples_input_footer(self) -> None:
        m = _make_manifest()
        table = format_cluster_distribution_table(m)
        assert f"n_samples_input={m.n_samples_input}" in table

    def test_disclaimer_appended(self) -> None:
        m = _make_manifest()
        table = format_cluster_distribution_table(m)
        assert "Disclaimer:" in table
        assert DEFAULT_DISCLAIMER_TEXT in table

    def test_noise_excluded_by_default_in_manifest(self) -> None:
        """Manifest with no noise row: noise exclusion is a no-op."""
        m = _make_manifest()
        table = format_cluster_distribution_table(m)
        # No is_noise column in table when no noise row exists.
        # Just ensure no crash.
        assert "segment_id" in table

    def test_is_noise_column_shows_false(self) -> None:
        m = _make_manifest()
        table = format_cluster_distribution_table(m)
        # All segments are non-noise.
        assert "False" in table


class TestFormatTableRawListInput:
    def test_accepts_raw_list(self) -> None:
        sizes = [
            SegmentSize(0, 10, 50.0, "n_samples_input", False),
            SegmentSize(1, 10, 50.0, "n_samples_input", False),
        ]
        table = format_cluster_distribution_table(sizes, n_samples_input=20)
        assert "0" in table
        assert "1" in table

    def test_rejects_missing_n_samples_input(self) -> None:
        sizes = [
            SegmentSize(0, 10, 50.0, "n_samples_input", False),
        ]
        with pytest.raises(VisualizationError, match="n_samples_input"):
            format_cluster_distribution_table(sizes)


# ---------------------------------------------------------------------------
# format_cluster_distribution_table — noise handling
# ---------------------------------------------------------------------------


class TestFormatTableNoiseHandling:
    def _make_dbscan_manifest(self, include_noise: bool = True) -> SegmentationManifest:
        sizes = [
            SegmentSize(0, 400, 40.0, "n_samples_used_for_compute", False),
            SegmentSize(1, 350, 35.0, "n_samples_used_for_compute", False),
            SegmentSize(2, 250, 25.0, "n_samples_used_for_compute", False),
        ]
        if include_noise:
            sizes.append(
                SegmentSize(
                    -1,
                    100,
                    10.0,
                    "n_samples_input",  # base = n_samples_input
                    True,
                )
            )
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

    def test_noise_included_when_flag_true(self) -> None:
        m = self._make_dbscan_manifest(include_noise=True)
        table = format_cluster_distribution_table(m, include_noise=True)
        # Noise segment should appear.
        assert "-1" in table
        assert "True" in table  # is_noise=True

    def test_noise_excluded_when_flag_false(self) -> None:
        m = self._make_dbscan_manifest(include_noise=True)
        table = format_cluster_distribution_table(m, include_noise=False)
        # Noise segment should NOT appear.
        assert "-1" not in table

    def test_noise_pct_placeholder_when_base_excludes_noise(self) -> None:
        # When percentage_base = n_samples_used_for_compute (excludes noise),
        # the noise percentage field is not meaningful → placeholder shown.
        sizes = [
            SegmentSize(0, 400, 40.0, "n_samples_used_for_compute", False),
            SegmentSize(
                -1,
                100,
                0.0,  # meaningless under this base
                "n_samples_used_for_compute",  # base excludes noise
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
        table = format_cluster_distribution_table(m, include_noise=True)
        # Noise row must show placeholder for percentage.
        assert "--" in table


# ---------------------------------------------------------------------------
# format_cluster_distribution_table — error / edge cases
# ---------------------------------------------------------------------------


def test_empty_segment_sizes_raises() -> None:
    with pytest.raises(VisualizationError, match="empty"):
        format_cluster_distribution_table([])


def test_empty_with_n_samples_input_still_raises() -> None:
    """Even with n_samples_input provided, empty list is an error."""
    with pytest.raises(VisualizationError, match="empty"):
        format_cluster_distribution_table([], n_samples_input=100)


def test_custom_disclaimer_overrides_default() -> None:
    m = _make_manifest()
    custom = "custom disclaimer text"
    table = format_cluster_distribution_table(m, disclaimer=custom)
    assert custom in table


def test_custom_separator() -> None:
    m = _make_manifest()
    table = format_cluster_distribution_table(m, separator_char=" | ")
    assert " | " in table


def test_segment_ids_non_consecutive() -> None:
    """Non-consecutive segment IDs (e.g., DBSCAN) render correctly."""
    sizes = [
        SegmentSize(0, 10, 50.0, "n_samples_input", False),
        SegmentSize(2, 5, 25.0, "n_samples_input", False),
        SegmentSize(5, 5, 25.0, "n_samples_input", False),
    ]
    m = _make_manifest(
        n_clusters_input=3,
        n_segments=3,
        segment_sizes=sizes,
    )
    table = format_cluster_distribution_table(m)
    for s in sizes:
        assert str(s.segment_id) in table


# ---------------------------------------------------------------------------
# plot_cluster_distribution — happy path
# ---------------------------------------------------------------------------


class TestPlotManifestInput:
    def test_returns_figure(self) -> None:
        m = _make_manifest()
        fig = plot_cluster_distribution(m)
        import matplotlib.figure

        assert isinstance(fig, matplotlib.figure.Figure)

    def test_figure_has_one_axes(self) -> None:
        m = _make_manifest()
        fig = plot_cluster_distribution(m)
        assert len(fig.axes) == 1

    def test_contains_bars(self) -> None:
        m = _make_manifest()
        fig = plot_cluster_distribution(m)
        ax = fig.axes[0]
        assert len(ax.containers) >= 1
        bars = ax.containers[0]
        assert len(bars) == 3  # 3 segments

    def test_bar_heights_match_counts(self) -> None:
        m = _make_manifest()
        fig = plot_cluster_distribution(m)
        ax = fig.axes[0]
        bars = ax.containers[0]
        expected_counts = [s.count for s in m.segment_sizes]
        bar_heights = [bar.get_height() for bar in bars]
        assert bar_heights == expected_counts

    def test_tick_labels_are_segment_ids(self) -> None:
        m = _make_manifest()
        fig = plot_cluster_distribution(m)
        ax = fig.axes[0]
        ticks = [t.get_text() for t in ax.get_xticklabels()]
        seg_ids = [str(s.segment_id) for s in m.segment_sizes]
        assert ticks == seg_ids

    def test_title_set(self) -> None:
        m = _make_manifest()
        fig = plot_cluster_distribution(m, title="My chart")
        assert fig.axes[0].get_title() == "My chart"

    def test_ylabel_set(self) -> None:
        m = _make_manifest()
        fig = plot_cluster_distribution(m, y_label="My ylabel")
        assert fig.axes[0].get_ylabel() == "My ylabel"

    def test_saves_to_file(self, tmp_path: Path) -> None:
        m = _make_manifest()
        out = tmp_path / "chart.png"
        plot_cluster_distribution(m, output_path=out)
        assert out.exists()
        assert out.stat().st_size > 0


class TestPlotRawListInput:
    def test_accepts_raw_list(self) -> None:
        sizes = [
            SegmentSize(0, 10, 50.0, "n_samples_input", False),
            SegmentSize(1, 10, 50.0, "n_samples_input", False),
        ]
        fig = plot_cluster_distribution(sizes, n_samples_input=20)
        assert len(fig.axes[0].containers[0]) == 2

    def test_rejects_missing_n_samples_input(self) -> None:
        sizes = [
            SegmentSize(0, 10, 50.0, "n_samples_input", False),
        ]
        with pytest.raises(VisualizationError, match="n_samples_input"):
            plot_cluster_distribution(sizes)


# ---------------------------------------------------------------------------
# plot_cluster_distribution — noise handling
# ---------------------------------------------------------------------------


class TestPlotNoiseHandling:
    def _make_dbscan_manifest(self, include_noise: bool = True) -> SegmentationManifest:
        sizes = [
            SegmentSize(0, 400, 40.0, "n_samples_used_for_compute", False),
            SegmentSize(1, 350, 35.0, "n_samples_used_for_compute", False),
            SegmentSize(2, 250, 25.0, "n_samples_used_for_compute", False),
        ]
        if include_noise:
            sizes.append(
                SegmentSize(-1, 100, 9.09, "n_samples_input", True),
            )
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

    def test_noise_excluded_by_default(self) -> None:
        m = self._make_dbscan_manifest(include_noise=True)
        fig = plot_cluster_distribution(m)  # include_noise=False by default
        bars = fig.axes[0].containers[0]
        assert len(bars) == 3  # noise excluded

    def test_noise_included_when_flag_true(self) -> None:
        m = self._make_dbscan_manifest(include_noise=True)
        fig = plot_cluster_distribution(m, include_noise=True)
        bars = fig.axes[0].containers[0]
        assert len(bars) == 4  # 3 clusters + noise

    def test_noise_bar_uses_noise_color(self) -> None:
        m = self._make_dbscan_manifest(include_noise=True)
        fig = plot_cluster_distribution(m, include_noise=True)
        bars = fig.axes[0].containers[0]
        noise_bar = bars[-1]
        assert noise_bar.get_facecolor()[:3] == matplotlib.colors.to_rgb(NOISE_COLOR)[:3]

    def test_non_noise_bars_use_palette_colors(self) -> None:
        m = self._make_dbscan_manifest(include_noise=True)
        fig = plot_cluster_distribution(m, include_noise=True)
        bars = fig.axes[0].containers[0]
        # First 3 bars (non-noise) should use palette colors.
        for i, bar in enumerate(bars[:3]):
            expected = DEFAULT_COLOR_PALETTE[i % len(DEFAULT_COLOR_PALETTE)]
            assert bar.get_facecolor()[:3] == matplotlib.colors.to_rgb(expected)[:3]


# ---------------------------------------------------------------------------
# plot_cluster_distribution — error / edge cases
# ---------------------------------------------------------------------------


def test_empty_raises_visualization_error() -> None:
    with pytest.raises(VisualizationError, match="empty"):
        plot_cluster_distribution([])


def test_plot_empty_with_n_samples_input_still_raises() -> None:
    with pytest.raises(VisualizationError, match="empty"):
        plot_cluster_distribution([], n_samples_input=100)


def test_segment_size_rejects_negative_count() -> None:
    """The manifest layer rejects SegmentSize with negative count."""
    from customer_segmentation.prototype.segmentation.manifest import SegmentationManifestError

    with pytest.raises(SegmentationManifestError, match="MUST be >= 0"):
        SegmentSize(0, -5, -10.0, "n_samples_input", False)


def test_segment_size_rejects_negative_percentage() -> None:
    """The manifest layer rejects SegmentSize with negative percentage."""
    from customer_segmentation.prototype.segmentation.manifest import SegmentationManifestError

    with pytest.raises(SegmentationManifestError, match="percentage"):
        SegmentSize(0, 5, -10.0, "n_samples_input", False)


def test_count_exceeds_n_samples_input_raises() -> None:
    sizes = [
        SegmentSize(0, 9999, 99.9, "n_samples_input", False),
    ]
    with pytest.raises(VisualizationError, match="exceeds n_samples_input"):
        plot_cluster_distribution(sizes, n_samples_input=100)


# ---------------------------------------------------------------------------
# Color assignment — deterministic, no semantic ranking
# ---------------------------------------------------------------------------


def test_color_assignment_is_deterministic() -> None:
    """Same segment always gets same colour across calls."""
    for seg_id in [0, 1, 5, 42]:
        color1 = get_segment_color(seg_id)
        color2 = get_segment_color(seg_id)
        assert color1 == color2


def test_colors_use_only_palette() -> None:
    """No colour outside the palette is used."""
    for seg_id in range(-5, 50):
        color = get_segment_color(seg_id)
        assert color in DEFAULT_COLOR_PALETTE


def test_noise_color_not_in_palette() -> None:
    """NOISE_COLOR is distinct from the cluster palette."""
    assert NOISE_COLOR not in DEFAULT_COLOR_PALETTE
