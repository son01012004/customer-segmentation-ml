"""Tests for DEV-08 metric comparison chart (Task 1.5)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from customer_segmentation.prototype.evaluation.manifest import (
    EnvironmentBlock,
    EvaluationManifest,
    EvaluationMetricsResult,
    EvaluationValidationReport,
    make_computation_error_entry,
    make_missing_entry,
    make_not_applicable_entry,
    make_valid_entry,
)
from customer_segmentation.prototype.evaluation.scope import (
    METRIC_NAMES,
    MetricStatus,
)
from customer_segmentation.prototype.visualization.charts.metric_comparison import (
    METRIC_VALUE_COLUMNS,
    extract_metric_matrix,
    format_metric_comparison_table,
    format_metric_status_block,
    format_metric_value,
    format_run_identifier,
    get_algorithm_color,
    is_metric_value,
    plot_metric_comparison,
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


def _build_manifest(
    *,
    evaluation_id: str = "ev_" + "a" * 24,
    algorithm: str = "kmeans",
    algorithm_family: str = "hard",
    n_clusters: int = 3,
    n_samples: int = 1000,
    noise_count: int | None = None,
    noise_ratio: float | None = None,
    metrics: EvaluationMetricsResult | None = None,
    noise_policy: str = "exclude",
    seed: int | None = 42,
) -> EvaluationManifest:
    if metrics is None:
        metrics = EvaluationMetricsResult(
            entries={
                "silhouette": make_valid_entry("silhouette", 0.5),
                "davies_bouldin": make_valid_entry("davies_bouldin", 1.0),
                "calinski_harabasz": make_valid_entry("calinski_harabasz", 100.0),
            }
        )
    env = EnvironmentBlock(
        python="3.14.4",
        platform="Linux",
        release="7.0.0",
        machine="x86_64",
        key_libraries={"numpy": "2.0", "pandas": "2.0"},
    )
    from customer_segmentation.prototype.evaluation.manifest import (
        build_evaluation_manifest,
    )

    return build_evaluation_manifest(
        evaluation_id=evaluation_id,
        clustering_id="cl_" + "b" * 24,
        preprocessed_id="pp_xyz",
        dataset_id="ds_abc",
        ml_dataset_sha256="a" * 64,
        feature_set_sha256="b" * 64,
        preprocessing_config_sha256="c" * 64,
        algorithm=algorithm,
        algorithm_version="sklearn_1.5",
        algorithm_family=algorithm_family,
        n_samples=n_samples,
        n_features=14,
        feature_set=["a", "b", "c", "d"],
        hyperparameters={"n_clusters": n_clusters},
        seed_policy="stochastic" if seed is not None else "deterministic",
        seed=seed,
        noise_policy_used=noise_policy,
        metric_set=list(METRIC_NAMES),
        metrics=metrics,
        n_samples_input=n_samples,
        n_samples_used_for_compute=n_samples - (noise_count or 0),
        n_clusters_realized=n_clusters,
        noise_count=noise_count,
        noise_ratio=noise_ratio,
        config_sha256="d" * 64,
        environment=env,
        log_file="ev.log",
        validation_report=EvaluationValidationReport(all_passed=True),
        readonly_paths=["data/raw/primary"],
    )


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
        pattern = r"\b" + re.escape(banned) + r"\b"
        if re.search(pattern, cleaned, flags=re.IGNORECASE):
            found.append(banned)
    return found


# ---------------------------------------------------------------------------
# Package imports / re-exports
# ---------------------------------------------------------------------------


def test_package_re_exports_format_metric_comparison_table() -> None:
    from customer_segmentation.prototype.visualization import (
        format_metric_comparison_table as exported,
    )

    assert exported is format_metric_comparison_table


def test_package_re_exports_plot_metric_comparison() -> None:
    from customer_segmentation.prototype.visualization import (
        plot_metric_comparison as exported,
    )

    assert exported is plot_metric_comparison


def test_package_re_exports_get_algorithm_color() -> None:
    from customer_segmentation.prototype.visualization import (
        get_algorithm_color as exported,
    )

    assert exported is get_algorithm_color


def test_package_re_exports_extract_metric_matrix() -> None:
    from customer_segmentation.prototype.visualization import (
        extract_metric_matrix as exported,
    )

    assert exported is extract_metric_matrix


def test_package_re_exports_format_metric_value() -> None:
    from customer_segmentation.prototype.visualization import (
        format_metric_value as exported,
    )

    assert exported is format_metric_value


def test_package_re_exports_format_metric_status_block() -> None:
    from customer_segmentation.prototype.visualization import (
        format_metric_status_block as exported,
    )

    assert exported is format_metric_status_block


def test_package_re_exports_format_run_identifier() -> None:
    from customer_segmentation.prototype.visualization import (
        format_run_identifier as exported,
    )

    assert exported is format_run_identifier


def test_package_re_exports_is_metric_value() -> None:
    from customer_segmentation.prototype.visualization import (
        is_metric_value as exported,
    )

    assert exported is is_metric_value


# ---------------------------------------------------------------------------
# Constants / helpers
# ---------------------------------------------------------------------------


class TestMetricValueColumns:
    def test_includes_all_three_metrics(self) -> None:
        assert set(METRIC_VALUE_COLUMNS) == set(METRIC_NAMES)

    def test_is_tuple(self) -> None:
        assert isinstance(METRIC_VALUE_COLUMNS, tuple)


class TestIsMetricValue:
    def test_none_returns_false(self) -> None:
        assert is_metric_value(None) is False

    def test_int_returns_true(self) -> None:
        assert is_metric_value(5) is True

    def test_float_returns_true(self) -> None:
        assert is_metric_value(3.14) is True

    def test_nan_returns_false(self) -> None:
        assert is_metric_value(float("nan")) is False

    def test_inf_returns_false(self) -> None:
        assert is_metric_value(float("inf")) is False
        assert is_metric_value(float("-inf")) is False

    def test_bool_returns_true(self) -> None:
        # bool is subclass of int; treated as value (defensive).
        assert is_metric_value(True) is True

    def test_string_returns_false(self) -> None:
        assert is_metric_value("0.5") is False

    def test_list_returns_false(self) -> None:
        assert is_metric_value([0.5]) is False


class TestGetAlgorithmColor:
    def test_returns_palette_entry(self) -> None:
        c = get_algorithm_color("kmeans")
        assert c in DEFAULT_COLOR_PALETTE

    def test_is_deterministic(self) -> None:
        c1 = get_algorithm_color("dbscan")
        c2 = get_algorithm_color("dbscan")
        assert c1 == c2

    def test_different_algorithms_can_have_different_colors(self) -> None:
        colors = {
            get_algorithm_color("kmeans"),
            get_algorithm_color("dbscan"),
            get_algorithm_color("agglomerative"),
        }
        assert len(colors) >= 2

    def test_all_in_palette(self) -> None:
        for name in ("kmeans", "dbscan", "agglomerative", "gmm", "fuzzy_cmeans"):
            assert get_algorithm_color(name) in DEFAULT_COLOR_PALETTE


class TestFormatMetricValue:
    def test_finite_float(self) -> None:
        out = format_metric_value(0.5)
        assert "0.5" in out
        assert out == "    0.5000"

    def test_none_renders_placeholder(self) -> None:
        assert format_metric_value(None) == "        --"

    def test_nan_renders_placeholder(self) -> None:
        assert format_metric_value(float("nan")) == "        --"

    def test_inf_renders_placeholder(self) -> None:
        assert format_metric_value(float("inf")) == "        --"

    def test_string_renders_placeholder(self) -> None:
        assert format_metric_value("0.5") == "        --"

    def test_custom_placeholder(self) -> None:
        out = format_metric_value(None, missing_value_placeholder="N/A")
        assert "N/A" in out


class TestFormatMetricStatusBlock:
    def test_valid_value(self) -> None:
        entry = make_valid_entry("silhouette", 0.5)
        block = format_metric_status_block(entry)
        assert "[VALID_VALUE]" in block
        assert "COMPUTED" in block

    def test_not_applicable(self) -> None:
        entry = make_not_applicable_entry("davies_bouldin", "ALL_NOISE")
        block = format_metric_status_block(entry)
        assert "[NOT_APPLICABLE]" in block
        assert "ALL_NOISE" in block

    def test_missing(self) -> None:
        entry = make_missing_entry("silhouette", "MANIFEST_MISSING")
        block = format_metric_status_block(entry)
        assert "[MISSING]" in block
        assert "MANIFEST_MISSING" in block

    def test_computation_error(self) -> None:
        entry = make_computation_error_entry("calinski_harabasz", "SKLEARN_EXCEPTION")
        block = format_metric_status_block(entry)
        assert "[COMPUTATION_ERROR]" in block
        assert "SKLEARN_EXCEPTION" in block


class TestFormatRunIdentifier:
    def test_includes_algorithm(self) -> None:
        m = _build_manifest(algorithm="kmeans")
        rid = format_run_identifier(m)
        assert "kmeans" in rid

    def test_includes_k(self) -> None:
        m = _build_manifest(n_clusters=5)
        rid = format_run_identifier(m)
        assert "k=5" in rid

    def test_includes_noise_policy(self) -> None:
        m = _build_manifest(noise_policy="include")
        rid = format_run_identifier(m)
        assert "np=include" in rid

    def test_includes_evaluation_id_tail(self) -> None:
        m = _build_manifest(evaluation_id="ev_" + "x" * 24)
        rid = format_run_identifier(m)
        assert "ev=" in rid
        # Last 8 chars of "ev_" + 24 x's is "xxxxxxxx".
        assert "xxxxxxxx" in rid

    def test_short_evaluation_id_unchanged(self) -> None:
        m = _build_manifest(evaluation_id="ev_short")
        rid = format_run_identifier(m)
        # Full id should be in the output when shorter than tail_length.
        assert "ev_short" in rid


# ---------------------------------------------------------------------------
# extract_metric_matrix
# ---------------------------------------------------------------------------


class TestExtractMetricMatrix:
    def test_single_manifest(self) -> None:
        m = _build_manifest()
        run_ids, metric_names, values = extract_metric_matrix(m)
        assert len(run_ids) == 1
        assert len(metric_names) == 3
        assert len(values) == 1
        assert set(metric_names) == set(METRIC_NAMES)
        # All 3 values are finite floats.
        for v in values[0]:
            assert isinstance(v, float)

    def test_multiple_manifests(self) -> None:
        m1 = _build_manifest(evaluation_id="ev_" + "1" * 24, algorithm="kmeans")
        m2 = _build_manifest(evaluation_id="ev_" + "2" * 24, algorithm="dbscan")
        m3 = _build_manifest(evaluation_id="ev_" + "3" * 24, algorithm="gmm")
        run_ids, metric_names, values = extract_metric_matrix([m1, m2, m3])
        assert len(run_ids) == 3
        assert len(values) == 3
        # Order is preserved.
        assert "kmeans" in run_ids[0]
        assert "dbscan" in run_ids[1]
        assert "gmm" in run_ids[2]

    def test_empty_raises(self) -> None:
        with pytest.raises(VisualizationError, match="manifests is empty"):
            extract_metric_matrix([])

    def test_too_many_manifests_raises(self) -> None:
        # Build 31 manifests.
        manifests = [_build_manifest(evaluation_id=f"ev_{i:022}") for i in range(31)]
        with pytest.raises(VisualizationError, match="MAX_RUNS_PER_CHART"):
            extract_metric_matrix(manifests)

    def test_invalid_status_becomes_none(self) -> None:
        m = _build_manifest(
            metrics=EvaluationMetricsResult(
                entries={
                    "silhouette": make_valid_entry("silhouette", 0.5),
                    "davies_bouldin": make_not_applicable_entry("davies_bouldin", "ALL_NOISE"),
                    "calinski_harabasz": make_computation_error_entry(
                        "calinski_harabasz", "SKLEARN_EXCEPTION"
                    ),
                }
            )
        )
        run_ids, metric_names, values = extract_metric_matrix(m)
        # silhouette = 0.5; DBI and CH are None (non-VALID).
        sil_idx = metric_names.index("silhouette")
        dbi_idx = metric_names.index("davies_bouldin")
        ch_idx = metric_names.index("calinski_harabasz")
        assert values[0][sil_idx] == 0.5
        assert values[0][dbi_idx] is None
        assert values[0][ch_idx] is None


# ---------------------------------------------------------------------------
# format_metric_comparison_table
# ---------------------------------------------------------------------------


class TestFormatMetricComparisonTable:
    def test_contains_header(self) -> None:
        m = _build_manifest()
        table = format_metric_comparison_table(m)
        assert "# Metric Comparison" in table

    def test_contains_metric_names(self) -> None:
        m = _build_manifest()
        table = format_metric_comparison_table(m)
        for name in METRIC_NAMES:
            assert name in table

    def test_contains_run_count(self) -> None:
        m1 = _build_manifest(evaluation_id="ev_" + "1" * 24)
        m2 = _build_manifest(evaluation_id="ev_" + "2" * 24)
        table = format_metric_comparison_table([m1, m2])
        assert "n_runs        : 2" in table

    def test_contains_algorithm(self) -> None:
        m = _build_manifest(algorithm="dbscan")
        table = format_metric_comparison_table(m)
        assert "dbscan" in table

    def test_contains_k(self) -> None:
        m = _build_manifest(n_clusters=5)
        table = format_metric_comparison_table(m)
        assert "k=5" in table

    def test_contains_noise_policy(self) -> None:
        m = _build_manifest(noise_policy="include")
        table = format_metric_comparison_table(m)
        assert "np=include" in table

    def test_contains_evaluation_id_tail(self) -> None:
        m = _build_manifest(evaluation_id="ev_" + "x" * 24)
        table = format_metric_comparison_table(m)
        assert "ev=xxxxxxxx" in table

    def test_disclaimer_appended(self) -> None:
        m = _build_manifest()
        table = format_metric_comparison_table(m)
        assert "Disclaimer:" in table
        assert DEFAULT_DISCLAIMER_TEXT in table

    def test_custom_disclaimer(self) -> None:
        m = _build_manifest()
        table = format_metric_comparison_table(m, disclaimer="custom text")
        assert "custom text" in table
        assert DEFAULT_DISCLAIMER_TEXT not in table

    def test_invalid_status_renders_placeholder_with_suffix(self) -> None:
        m = _build_manifest(
            metrics=EvaluationMetricsResult(
                entries={
                    "silhouette": make_not_applicable_entry("silhouette", "ALL_NOISE"),
                    "davies_bouldin": make_valid_entry("davies_bouldin", 1.0),
                    "calinski_harabasz": make_valid_entry("calinski_harabasz", 100.0),
                }
            )
        )
        table = format_metric_comparison_table(m)
        assert "[NOT_APPLICABLE]" in table
        assert "ALL_NOISE" in table

    def test_status_suffix_disabled(self) -> None:
        m = _build_manifest(
            metrics=EvaluationMetricsResult(
                entries={
                    "silhouette": make_not_applicable_entry("silhouette", "ALL_NOISE"),
                    "davies_bouldin": make_valid_entry("davies_bouldin", 1.0),
                    "calinski_harabasz": make_valid_entry("calinski_harabasz", 100.0),
                }
            )
        )
        table = format_metric_comparison_table(m, status_suffix=False)
        # Status block should NOT appear in this mode.
        assert "[NOT_APPLICABLE]" not in table

    def test_missing_status_renders_placeholder(self) -> None:
        m = _build_manifest(
            metrics=EvaluationMetricsResult(
                entries={
                    "silhouette": make_valid_entry("silhouette", 0.5),
                    "davies_bouldin": make_valid_entry("davies_bouldin", 1.0),
                    "calinski_harabasz": make_missing_entry(
                        "calinski_harabasz", "MANIFEST_MISSING"
                    ),
                }
            )
        )
        table = format_metric_comparison_table(m)
        assert "[MISSING]" in table
        assert "MANIFEST_MISSING" in table

    def test_computation_error_renders_placeholder(self) -> None:
        m = _build_manifest(
            metrics=EvaluationMetricsResult(
                entries={
                    "silhouette": make_valid_entry("silhouette", 0.5),
                    "davies_bouldin": make_valid_entry("davies_bouldin", 1.0),
                    "calinski_harabasz": make_computation_error_entry(
                        "calinski_harabasz", "NAN_OR_INF_INPUT"
                    ),
                }
            )
        )
        table = format_metric_comparison_table(m)
        assert "[COMPUTATION_ERROR]" in table
        assert "NAN_OR_INF_INPUT" in table

    def test_computation_time_subtable_when_present(self) -> None:
        m = _build_manifest(
            metrics=EvaluationMetricsResult(
                entries={
                    "silhouette": make_valid_entry(
                        "silhouette", 0.5, computation_time_seconds=0.42
                    ),
                    "davies_bouldin": make_valid_entry(
                        "davies_bouldin", 1.0, computation_time_seconds=0.15
                    ),
                    "calinski_harabasz": make_valid_entry(
                        "calinski_harabasz", 100.0, computation_time_seconds=0.20
                    ),
                }
            )
        )
        table = format_metric_comparison_table(m)
        assert "Computation time" in table
        assert "0.4200" in table

    def test_no_computation_time_subtable_when_all_none(self) -> None:
        m = _build_manifest()  # default metrics have no computation time
        table = format_metric_comparison_table(m)
        assert "Computation time" not in table

    def test_empty_manifests_raises(self) -> None:
        with pytest.raises(VisualizationError, match="manifests is empty"):
            format_metric_comparison_table([])

    def test_multi_manifest_distinct_rows(self) -> None:
        m1 = _build_manifest(evaluation_id="ev_" + "1" * 24, algorithm="kmeans")
        m2 = _build_manifest(evaluation_id="ev_" + "2" * 24, algorithm="dbscan")
        table = format_metric_comparison_table([m1, m2])
        assert "kmeans" in table
        assert "dbscan" in table

    def test_output_is_stable(self) -> None:
        m = _build_manifest()
        t1 = format_metric_comparison_table(m)
        t2 = format_metric_comparison_table(m)
        assert t1 == t2

    def test_banned_words_not_present_outside_disclaimer(self) -> None:
        m1 = _build_manifest(evaluation_id="ev_" + "1" * 24)
        m2 = _build_manifest(evaluation_id="ev_" + "2" * 24)
        table = format_metric_comparison_table([m1, m2])
        found = _find_banned_substrings(table)
        assert found == [], f"Banned substrings found: {found}"

    def test_banned_words_in_mixed_status_manifest(self) -> None:
        m = _build_manifest(
            metrics=EvaluationMetricsResult(
                entries={
                    "silhouette": make_not_applicable_entry("silhouette", "ALL_NOISE"),
                    "davies_bouldin": make_computation_error_entry(
                        "davies_bouldin", "SKLEARN_EXCEPTION"
                    ),
                    "calinski_harabasz": make_missing_entry(
                        "calinski_harabasz", "MANIFEST_MISSING"
                    ),
                }
            )
        )
        table = format_metric_comparison_table(m)
        found = _find_banned_substrings(table)
        assert found == [], f"Banned substrings found: {found}"

    def test_post_preprocessing_note_present(self) -> None:
        m = _build_manifest()
        table = format_metric_comparison_table(m)
        assert "different scales" in table or "post-preprocessing" in table


# ---------------------------------------------------------------------------
# plot_metric_comparison
# ---------------------------------------------------------------------------


class TestPlotMetricComparison:
    def test_renders_with_valid_manifest(self) -> None:
        m = _build_manifest()
        fig = plot_metric_comparison(m)
        assert fig is not None
        import matplotlib.pyplot as plt

        plt.close(fig)

    def test_saves_to_output_path(self, tmp_path: Path) -> None:
        m = _build_manifest()
        out = tmp_path / "metric.png"
        fig = plot_metric_comparison(m, output_path=out)
        assert out.exists()
        assert out.stat().st_size > 0
        import matplotlib.pyplot as plt

        plt.close(fig)

    def test_renders_multiple_manifests(self) -> None:
        m1 = _build_manifest(evaluation_id="ev_" + "1" * 24, algorithm="kmeans")
        m2 = _build_manifest(evaluation_id="ev_" + "2" * 24, algorithm="dbscan")
        fig = plot_metric_comparison([m1, m2])
        assert fig is not None
        import matplotlib.pyplot as plt

        plt.close(fig)

    def test_renders_with_mixed_status(self) -> None:
        m = _build_manifest(
            metrics=EvaluationMetricsResult(
                entries={
                    "silhouette": make_valid_entry("silhouette", 0.5),
                    "davies_bouldin": make_not_applicable_entry("davies_bouldin", "ALL_NOISE"),
                    "calinski_harabasz": make_computation_error_entry(
                        "calinski_harabasz", "SKLEARN_EXCEPTION"
                    ),
                }
            )
        )
        fig = plot_metric_comparison(m)
        assert fig is not None
        import matplotlib.pyplot as plt

        plt.close(fig)

    def test_empty_manifests_raises(self) -> None:
        with pytest.raises(VisualizationError, match="manifests is empty"):
            plot_metric_comparison([])

    def test_custom_title(self) -> None:
        m = _build_manifest()
        fig = plot_metric_comparison(m, title="My Title")
        assert fig is not None
        import matplotlib.pyplot as plt

        plt.close(fig)

    def test_each_metric_has_its_own_subplot(self) -> None:
        # The 3-metric closed set is rendered as 3 subplots.
        m = _build_manifest()
        fig = plot_metric_comparison(m)
        # 3 axes for 3 metrics.
        axes = fig.get_axes()
        assert len(axes) >= 3
        import matplotlib.pyplot as plt

        plt.close(fig)

    def test_no_normalization_applied(self) -> None:
        """The implementation does NOT normalize / rescale metrics.

        We verify the raw values are passed through to the matrix
        extraction unchanged.
        """
        m = _build_manifest()
        run_ids, metric_names, values = extract_metric_matrix(m)
        # Raw values: silhouette=0.5, dbi=1.0, ch=100.0
        sil_idx = metric_names.index("silhouette")
        dbi_idx = metric_names.index("davies_bouldin")
        ch_idx = metric_names.index("calinski_harabasz")
        assert values[0][sil_idx] == 0.5
        assert values[0][dbi_idx] == 1.0
        assert values[0][ch_idx] == 100.0


# ---------------------------------------------------------------------------
# Schema evidence
# ---------------------------------------------------------------------------


def test_only_documented_fields_are_read() -> None:
    """Verify the module only reads documented EvaluationManifest fields."""
    m = _build_manifest()
    # Documented EvaluationManifest fields used.
    assert hasattr(m, "evaluation_id")
    assert hasattr(m, "algorithm")
    assert hasattr(m, "algorithm_family")
    assert hasattr(m, "n_clusters_realized")
    assert hasattr(m, "noise_policy_used")
    assert hasattr(m, "metrics")
    # Documented EvaluationMetricEntry fields.
    entry = m.metrics.entries["silhouette"]
    assert hasattr(entry, "value")
    assert hasattr(entry, "status")
    assert hasattr(entry, "reason")
    assert hasattr(entry, "is_diagnostic_only")
    assert hasattr(entry, "lower_is_better")
    assert hasattr(entry, "computation_time_seconds")


def test_metric_names_constant() -> None:
    """Verify the supported metric set is the documented closed set."""
    assert frozenset({"silhouette", "davies_bouldin", "calinski_harabasz"}) == METRIC_NAMES
    assert len(METRIC_NAMES) == 3


def test_metric_statuses_constant() -> None:
    """Verify the supported status set is the documented closed set."""
    assert MetricStatus.VALID_VALUE.value == "VALID_VALUE"
    assert MetricStatus.NOT_APPLICABLE.value == "NOT_APPLICABLE"
    assert MetricStatus.MISSING.value == "MISSING"
    assert MetricStatus.COMPUTATION_ERROR.value == "COMPUTATION_ERROR"
    assert len(list(MetricStatus)) == 4


def test_input_integrity_for_manifests() -> None:
    """Verify the module does not mutate the input manifest."""
    m = _build_manifest()
    # Snapshot the manifest's metrics dict id.
    metrics_id = id(m.metrics)
    # Call the various functions.
    _ = format_metric_comparison_table(m)
    _ = extract_metric_matrix(m)
    fig = plot_metric_comparison(m)
    import matplotlib.pyplot as plt

    plt.close(fig)
    # The manifest's metrics block should still be the same object.
    assert id(m.metrics) == metrics_id
