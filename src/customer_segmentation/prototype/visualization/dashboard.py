"""Dashboard orchestrator for DEV-08 Prototype Visualization.

The :class:`DashboardGenerator` composes all four chart modules into
one dashboard output for a given segmentation + evaluation pair.

Charts emitted
--------------
1. Cluster Distribution (bar chart)
2. Segment Profile (text table)
4. Feature Comparison (heatmap)
5. Metric Comparison (text table + bar chart)
6. Marketing placeholder (text only; REVIEW_REQUIRED by default)

The Cluster Visualization (2D scatter) is **blocked**: no 2D
projection methodology has been approved (per the DEV-08 implementation
plan §4.2). The dashboard emits a clear BLOCKED note instead of a
chart so the gap is visible but no fake implementation is fabricated.

Hard rules
----------
- Inputs are read from existing manifest schemas only.
- The dashboard never modifies input manifests.
- The dashboard never aggregates metrics or assigns composite scores.
- Banned-word discipline is enforced on all text outputs (the
  mandatory disclaimer phrase is the single allowed occurrence).
- The dashboard never invents "best" / "winner" / "optimal" /
  "recommended" / "ranking" language.
- Output paths are validated to live inside the resolved run_dir.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

import matplotlib

matplotlib.use("Agg")

from customer_segmentation.prototype.evaluation.manifest import (
    EvaluationManifest,
)
from customer_segmentation.prototype.marketing.manifest import (
    MarketingRecommendationManifest,
)
from customer_segmentation.prototype.segmentation.manifest import (
    SegmentationManifest,
)
from customer_segmentation.prototype.visualization.charts.cluster_distribution import (
    format_cluster_distribution_table,
    plot_cluster_distribution,
)
from customer_segmentation.prototype.visualization.charts.feature_comparison import (
    format_feature_comparison_table,
    plot_feature_heatmap,
)
from customer_segmentation.prototype.visualization.charts.marketing_placeholder import (
    format_marketing_placeholder,
)
from customer_segmentation.prototype.visualization.charts.metric_comparison import (
    format_metric_comparison_table,
    plot_metric_comparison,
)
from customer_segmentation.prototype.visualization.charts.segment_profile import (
    format_segment_profile_table,
)
from customer_segmentation.prototype.visualization.config_loader import (
    Dev08Config,
)
from customer_segmentation.prototype.visualization.display import (
    DashboardChartRecord,
    DashboardResult,
)
from customer_segmentation.prototype.visualization.exceptions import (
    VisualizationError,
)

__all__ = [
    "DASHBOARD_CHARTS",
    "DashboardGenerator",
    "CLUSTER_VISUALIZATION_BLOCKED_NOTE",
]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Canonical list of chart names the dashboard can emit.
#: "cluster_visualization_2d" is BLOCKED — no 2D projection methodology
#: is approved (per DEV-08 implementation plan §4.2).
DASHBOARD_CHARTS: Final[tuple[str, ...]] = (
    "cluster_distribution",
    "segment_profile",
    "feature_comparison",
    "metric_comparison",
    "marketing",
    "cluster_visualization_2d",
)

#: Emitted into the cluster_visualization_2d record so the gap is visible
#: in the run report.
CLUSTER_VISUALIZATION_BLOCKED_NOTE: Final[str] = (
    "BLOCKED: 2D projection methodology (PCA / t-SNE / UMAP) is not "
    "approved. No chart is fabricated. See docs/system/DEV-08_*.md "
    "implementation plan §4.2 for context."
)


# ---------------------------------------------------------------------------
# Dashboard generator
# ---------------------------------------------------------------------------


class DashboardGenerator:
    """Compose all four chart modules into one dashboard output.

    The generator is constructed with the validated DEV-08 config and
    the three input manifests (segmentation, evaluation list,
    marketing). Output paths are validated to live inside ``run_dir``.

    Parameters
    ----------
    config : Dev08Config
        Validated DEV-08 config object.
    segmentation_manifest : SegmentationManifest
        DEV-06 segmentation manifest.
    evaluation_manifests : list[EvaluationManifest] or None
        List of DEV-05 evaluation manifests (may be empty for
        segmentation-only dashboards).
    marketing_manifest : MarketingRecommendationManifest or None
        DEV-07 marketing manifest (optional). When ``None``, the
        marketing section defaults to REVIEW_REQUIRED placeholder.
    run_dir : pathlib.Path
        Output directory for the dashboard. Must already exist.
    output_format : str, optional
        File extension to use for chart files (``png`` or ``svg``).
        Defaults to the value in ``config.output_format``.
    """

    def __init__(
        self,
        *,
        config: Dev08Config,
        segmentation_manifest: SegmentationManifest,
        evaluation_manifests: list[EvaluationManifest] | None = None,
        marketing_manifest: MarketingRecommendationManifest | None = None,
        run_dir: Path,
        output_format: str | None = None,
    ) -> None:
        if not isinstance(config, Dev08Config):
            raise VisualizationError(f"config must be a Dev08Config; got {type(config).__name__}.")
        if not isinstance(segmentation_manifest, SegmentationManifest):
            raise VisualizationError(
                f"segmentation_manifest must be a SegmentationManifest; "
                f"got {type(segmentation_manifest).__name__}."
            )
        if evaluation_manifests is None:
            evaluation_manifests = []
        if not isinstance(evaluation_manifests, list):
            raise VisualizationError(
                f"evaluation_manifests must be a list; "
                f"got {type(evaluation_manifests).__name__}."
            )
        for m in evaluation_manifests:
            if not isinstance(m, EvaluationManifest):
                raise VisualizationError(
                    f"evaluation_manifests[] must contain EvaluationManifest; "
                    f"got {type(m).__name__}."
                )
        if marketing_manifest is not None and not isinstance(
            marketing_manifest, MarketingRecommendationManifest
        ):
            raise VisualizationError(
                f"marketing_manifest must be a MarketingRecommendationManifest "
                f"or None; got {type(marketing_manifest).__name__}."
            )
        run_dir = Path(run_dir)
        if not run_dir.exists():
            raise VisualizationError(f"run_dir must already exist; got {run_dir!s}.")
        if not run_dir.is_dir():
            raise VisualizationError(f"run_dir must be a directory; got {run_dir!s}.")

        self.config = config
        self.segmentation_manifest = segmentation_manifest
        self.evaluation_manifests = list(evaluation_manifests)
        self.marketing_manifest = marketing_manifest
        self.run_dir = run_dir
        self.output_format = (
            str(output_format) if output_format is not None else str(config.output_format)
        ).lower()
        if self.output_format not in {"png", "svg"}:
            raise VisualizationError(
                f"output_format {self.output_format!r} is not in the closed set "
                f"{['png', 'svg']}."
            )

    # -- helpers -----------------------------------------------------------

    def _resolve_chart_path(self, chart_basename: str) -> Path:
        """Return the absolute path for a chart under ``run_dir``."""
        if not chart_basename or not isinstance(chart_basename, str):
            raise VisualizationError(
                f"chart_basename must be a non-empty str; got {chart_basename!r}."
            )
        candidate = (self.run_dir / f"{chart_basename}.{self.output_format}").resolve()
        try:
            candidate.relative_to(self.run_dir.resolve())
        except ValueError as exc:
            raise VisualizationError(
                f"Computed chart path {candidate!s} is not inside run_dir "
                f"{self.run_dir.resolve()!s}."
            ) from exc
        return candidate

    def _make_text_path(self, text_basename: str) -> Path:
        """Return the absolute path for a text artefact under ``run_dir``."""
        if not text_basename or not isinstance(text_basename, str):
            raise VisualizationError(
                f"text_basename must be a non-empty str; got {text_basename!r}."
            )
        candidate = (self.run_dir / f"{text_basename}.txt").resolve()
        try:
            candidate.relative_to(self.run_dir.resolve())
        except ValueError as exc:
            raise VisualizationError(
                f"Computed text path {candidate!s} is not inside run_dir "
                f"{self.run_dir.resolve()!s}."
            ) from exc
        return candidate

    # -- chart emitters ----------------------------------------------------

    def _emit_cluster_distribution(self) -> tuple[DashboardChartRecord, Path]:
        chart_path = self._resolve_chart_path("cluster_distribution")
        text_path = self._make_text_path("cluster_distribution")
        plot_cluster_distribution(
            self.segmentation_manifest,
            include_noise=self.config.include_noise_in_charts,
            title="Cluster Size Distribution",
            output_path=chart_path,
        )
        text = format_cluster_distribution_table(
            self.segmentation_manifest,
            include_noise=self.config.include_noise_in_text,
            disclaimer=self.config.display.disclaimer_text,
            missing_value_placeholder=self.config.display.missing_value_placeholder,
            separator_char=self.config.display.separator,
        )
        text_path.write_text(text, encoding="utf-8")
        return (
            DashboardChartRecord(
                name="cluster_distribution",
                output_path=str(chart_path),
                status="EMITTED",
                note="",
            ),
            text_path,
        )

    def _emit_segment_profile(self) -> tuple[DashboardChartRecord, Path]:
        text_path = self._make_text_path("segment_profile")
        text = format_segment_profile_table(
            self.segmentation_manifest,
            include_noise=self.config.include_noise_in_text,
            disclaimer=self.config.display.disclaimer_text,
            missing_value_placeholder=self.config.display.missing_value_placeholder,
        )
        text_path.write_text(text, encoding="utf-8")
        return (
            DashboardChartRecord(
                name="segment_profile",
                output_path=str(text_path),
                status="EMITTED",
                note="(text-only)",
            ),
            text_path,
        )

    def _emit_feature_comparison(self) -> tuple[DashboardChartRecord, Path]:
        """Emit a feature-comparison heatmap.

        If the manifest has no ``profiles`` entries, emit a SKIPPED
        record with a clear note (do not silently produce an empty
        chart).
        """
        profiles = list(self.segmentation_manifest.profiles)
        if not profiles:
            return (
                DashboardChartRecord(
                    name="feature_comparison",
                    output_path="",
                    status="SKIPPED",
                    note="manifest has no FeatureProfile entries",
                ),
                self._make_text_path("feature_comparison"),
            )
        if len(profiles) > self.config.max_features_per_heatmap * 100:
            # Heuristic: each profile row = 1 segment × 1 feature; if
            # the count exceeds max_features_per_heatmap × 100 (a very
            # wide matrix), skip and let the caller decide.
            return (
                DashboardChartRecord(
                    name="feature_comparison",
                    output_path="",
                    status="SKIPPED",
                    note=(
                        f"profile row count {len(profiles)} exceeds "
                        f"max_features_per_heatmap * 100 = "
                        f"{self.config.max_features_per_heatmap * 100}"
                    ),
                ),
                self._make_text_path("feature_comparison"),
            )
        chart_path = self._resolve_chart_path("feature_comparison")
        text_path = self._make_text_path("feature_comparison")
        plot_feature_heatmap(
            self.segmentation_manifest,
            statistic="mean",
            include_noise=self.config.include_noise_in_charts,
            output_path=chart_path,
            missing_value_placeholder=self.config.display.missing_value_placeholder,
        )
        text = format_feature_comparison_table(
            self.segmentation_manifest,
            statistic="mean",
            include_noise=self.config.include_noise_in_text,
            missing_value_placeholder=self.config.display.missing_value_placeholder,
            disclaimer=self.config.display.disclaimer_text,
            separator_char=self.config.display.separator,
        )
        text_path.write_text(text, encoding="utf-8")
        return (
            DashboardChartRecord(
                name="feature_comparison",
                output_path=str(chart_path),
                status="EMITTED",
                note=f"(statistic=mean; profiles={len(profiles)})",
            ),
            text_path,
        )

    def _emit_metric_comparison(self) -> tuple[DashboardChartRecord, Path]:
        if not self.evaluation_manifests:
            return (
                DashboardChartRecord(
                    name="metric_comparison",
                    output_path="",
                    status="SKIPPED",
                    note="no EvaluationManifest provided",
                ),
                self._make_text_path("metric_comparison"),
            )
        if len(self.evaluation_manifests) > self.config.max_runs_per_chart:
            return (
                DashboardChartRecord(
                    name="metric_comparison",
                    output_path="",
                    status="SKIPPED",
                    note=(
                        f"manifest count {len(self.evaluation_manifests)} exceeds "
                        f"max_runs_per_chart={self.config.max_runs_per_chart}"
                    ),
                ),
                self._make_text_path("metric_comparison"),
            )
        chart_path = self._resolve_chart_path("metric_comparison")
        text_path = self._make_text_path("metric_comparison")
        plot_metric_comparison(
            self.evaluation_manifests,
            title="Metric Comparison (per metric, native scale)",
            output_path=chart_path,
            missing_value_placeholder=self.config.display.missing_value_placeholder,
        )
        text = format_metric_comparison_table(
            self.evaluation_manifests,
            disclaimer=self.config.display.disclaimer_text,
            missing_value_placeholder=self.config.display.missing_value_placeholder,
            separator_char=self.config.display.separator,
        )
        text_path.write_text(text, encoding="utf-8")
        return (
            DashboardChartRecord(
                name="metric_comparison",
                output_path=str(chart_path),
                status="EMITTED",
                note=f"(n_evaluations={len(self.evaluation_manifests)})",
            ),
            text_path,
        )

    def _emit_marketing(self) -> tuple[DashboardChartRecord, Path]:
        text_path = self._make_text_path("marketing")
        text = format_marketing_placeholder(
            self.marketing_manifest,
            disclaimer=self.config.display.disclaimer_text,
            marketing_section=self.config.marketing_section,
            separator=self.config.display.separator,
        )
        if self.config.marketing_section == "hidden" or not text:
            # Hidden mode: write nothing, record SKIPPED.
            return (
                DashboardChartRecord(
                    name="marketing",
                    output_path="",
                    status="SKIPPED",
                    note="marketing_section='hidden' (or empty placeholder)",
                ),
                text_path,
            )
        text_path.write_text(text, encoding="utf-8")
        if self.marketing_manifest is None:
            note = "manifest=None; availability=REVIEW_REQUIRED"
        else:
            note = f"availability={self.marketing_manifest.availability}"
        return (
            DashboardChartRecord(
                name="marketing",
                output_path=str(text_path),
                status="EMITTED",
                note=note,
            ),
            text_path,
        )

    def _record_blocked_cluster_visualization_2d(self) -> DashboardChartRecord:
        return DashboardChartRecord(
            name="cluster_visualization_2d",
            output_path="",
            status="BLOCKED",
            note=CLUSTER_VISUALIZATION_BLOCKED_NOTE,
        )

    # -- entry point -------------------------------------------------------

    def generate(self) -> list[DashboardChartRecord]:
        """Run all chart emitters and return the dashboard chart records.

        Returns
        -------
        list[DashboardChartRecord]
            One record per chart in the canonical order
            (:data:`DASHBOARD_CHARTS`).

        Raises
        ------
        VisualizationError
            On any unhandled chart-level failure (a chart-level failure
            is caught and recorded as ``status="ERROR"`` in the record
            so the rest of the dashboard can still render).
        """
        records: list[DashboardChartRecord] = []

        # Cluster distribution.
        try:
            rec, _ = self._emit_cluster_distribution()
            records.append(rec)
        except VisualizationError as exc:
            records.append(
                DashboardChartRecord(
                    name="cluster_distribution",
                    output_path="",
                    status="ERROR",
                    note=str(exc),
                )
            )

        # Segment profile.
        try:
            rec, _ = self._emit_segment_profile()
            records.append(rec)
        except VisualizationError as exc:
            records.append(
                DashboardChartRecord(
                    name="segment_profile",
                    output_path="",
                    status="ERROR",
                    note=str(exc),
                )
            )

        # Feature comparison.
        try:
            rec, _ = self._emit_feature_comparison()
            records.append(rec)
        except VisualizationError as exc:
            records.append(
                DashboardChartRecord(
                    name="feature_comparison",
                    output_path="",
                    status="ERROR",
                    note=str(exc),
                )
            )

        # Metric comparison.
        try:
            rec, _ = self._emit_metric_comparison()
            records.append(rec)
        except VisualizationError as exc:
            records.append(
                DashboardChartRecord(
                    name="metric_comparison",
                    output_path="",
                    status="ERROR",
                    note=str(exc),
                )
            )

        # Marketing placeholder.
        try:
            rec, _ = self._emit_marketing()
            records.append(rec)
        except VisualizationError as exc:
            records.append(
                DashboardChartRecord(
                    name="marketing",
                    output_path="",
                    status="ERROR",
                    note=str(exc),
                )
            )

        # Cluster visualization 2D: BLOCKED. Recorded as a special
        # status so the gap is visible but no chart is fabricated.
        records.append(self._record_blocked_cluster_visualization_2d())

        return records


# ---------------------------------------------------------------------------
# Helpers (module-level)
# ---------------------------------------------------------------------------


def build_dashboard_result(
    *,
    dashboard_id: str,
    segmentation_manifest: SegmentationManifest,
    clustering_id: str,
    preprocessed_id: str,
    dataset_id: str,
    run_dir: Path,
    lifecycle: str,
    validation_passed: bool,
    charts: list[DashboardChartRecord],
    input_segmentation_manifest_path: Path | str | None,
    input_evaluation_manifest_paths: list[Path | str] | None = None,
    input_marketing_manifest_path: Path | str | None = None,
    notes: list[str] | None = None,
) -> DashboardResult:
    """Build a :class:`DashboardResult` from the generator's output.

    This helper exists so the pipeline layer can assemble the result
    without duplicating the field assembly.
    """
    eval_paths = [str(p) for p in (input_evaluation_manifest_paths or [])]
    return DashboardResult(
        dashboard_id=dashboard_id,
        segmentation_id=str(segmentation_manifest.segmentation_id),
        clustering_id=str(clustering_id),
        preprocessed_id=str(preprocessed_id),
        dataset_id=str(dataset_id),
        run_dir=str(run_dir),
        lifecycle=str(lifecycle),
        validation_passed=bool(validation_passed),
        charts=list(charts),
        input_segmentation_manifest_path=(
            str(input_segmentation_manifest_path)
            if input_segmentation_manifest_path is not None
            else None
        ),
        input_evaluation_manifest_paths=eval_paths,
        input_marketing_manifest_path=(
            str(input_marketing_manifest_path)
            if input_marketing_manifest_path is not None
            else None
        ),
        notes=list(notes or []),
    )
