"""CP-02 orchestrator.

The orchestrator:

1. Loads RAW customer features from ``customer_candidates.parquet``.
2. Builds CP-02 analysis units (reuses CP-01's analysis-unit construction).
3. Computes per-(unit, cluster, feature) statistics.
4. Computes relative-difference vs OVERALL.
5. Computes behavioural interpretation text per (cluster, feature).
6. Renders boxplots + heatmaps per analysis unit.
7. Writes CSV / JSON / Markdown artifacts.

Hard constraints recorded at the package level
(``src/customer_segmentation/profiling/cp02/__init__.py``).

Read-only against source artifacts:
- EXP-01 cluster_labels_*.parquet (read)
- EXP-03 exp03_selected_configurations.csv (read)
- data/processed/customer_candidates.parquet (read)
- data/processed/customer_metadata.parquet (read)
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from customer_segmentation.profiling.cp01.provenance import (
    ALGORITHMS,
)
from customer_segmentation.profiling.cp02.behavioral_interpretation import (
    compute_behavioral_interpretation_table_from_units,
)
from customer_segmentation.profiling.cp02.feature_profiling import (
    compute_feature_profile_table,
)
from customer_segmentation.profiling.cp02.provenance import (
    RAW_FEATURES_PATH,
    build_cp02_analysis_units,
)
from customer_segmentation.profiling.cp02.relative_comparison import (
    compute_relative_comparison_table,
)
from customer_segmentation.profiling.cp02.report import (
    Cp02ReportContext,
    build_cp02_markdown,
)
from customer_segmentation.profiling.cp02.visualization import (
    BOXPLOT_FEATURE_SUBSET,
    render_all_cp02_charts,
)

DEFAULT_OUTPUT_DIR = Path("reports/profiling/cp02")


def _file_sha256(path: Path) -> str | None:
    """Return the SHA-256 hex digest of a file, or None if missing."""
    if not path.exists():
        return None
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


class Cp02Runner:
    """Configuration for one CP-02 run."""

    def __init__(
        self,
        repo_root: Path,
        output_dir: Path = DEFAULT_OUTPUT_DIR,
        include_exp03: bool = True,
        figure_dpi: int = 120,
        cp01_size_table_path: Path | None = None,
    ) -> None:
        self.repo_root = repo_root
        self.output_dir = output_dir
        self.include_exp03 = include_exp03
        self.figure_dpi = figure_dpi
        # Default CP-01 cluster size table — used for the
        # consistency-with-CP-01 check and as a provenance reference.
        self.cp01_size_table_path = cp01_size_table_path or (
            repo_root / "reports/profiling/cp01/cp01_cluster_size_table.csv"
        )

    def run(self) -> Mapping[str, Any]:
        """Execute CP-02 and return the run-summary as a dict.

        Side effects:
        - writes ``cp02_feature_profile_table.csv``
        - writes ``cp02_relative_comparison.csv``
        - writes ``cp02_behavioral_interpretation.csv``
        - writes ``cp02_unit_provenance.csv``
        - writes ``cp02_cp01_consistency.csv``
        - writes ``cp02_runner_manifest.json``
        - writes ``figures/cp02_*_boxplot.png`` (per cluster subset)
        - writes ``figures/cp02_*_heatmap.png`` (one per unit)
        - writes ``cp02_report.md``
        """
        # 1. Build analysis units (reuses CP-01).
        units = build_cp02_analysis_units(self.repo_root)
        if not self.include_exp03:
            units = [u for u in units if u.source_experiment != "EXP-03"]
        # 2. Compute per-(unit, cluster, feature) statistics.
        feature_rows = compute_feature_profile_table(units)
        # 3. Compute relative comparison vs OVERALL.
        rel_rows = compute_relative_comparison_table(units)
        # 4. Compute behavioural interpretation.
        interp_rows = compute_behavioral_interpretation_table_from_units(units)
        # 5. Render charts.
        self.output_dir.mkdir(parents=True, exist_ok=True)
        figures_dir = self.output_dir / "figures"
        figures_dir.mkdir(parents=True, exist_ok=True)
        chart_paths = render_all_cp02_charts(
            units=units,
            out_dir=figures_dir,
            feature_subset=BOXPLOT_FEATURE_SUBSET,
        )

        # 6. CSVs.
        feat_df = pd.DataFrame(
            [
                {
                    "unit_id": r.unit_id,
                    "algorithm": r.algorithm,
                    "source_experiment": r.source_experiment,
                    "cluster_id": r.cluster_id,
                    "cluster_label": r.cluster_label,
                    "feature": r.feature,
                    "count": r.count,
                    "count_total": r.count_total,
                    "mean": r.mean,
                    "median": r.median,
                    "p25": r.p25,
                    "p75": r.p75,
                    "min": r.min,
                    "max": r.max,
                    "std": r.std,
                    "n_missing": r.n_missing,
                }
                for r in feature_rows
            ]
        )
        if not feat_df.empty:
            feat_df = feat_df.sort_values(["unit_id", "cluster_label", "feature"]).reset_index(
                drop=True
            )
        feat_path = self.output_dir / "cp02_feature_profile_table.csv"
        feat_df.to_csv(feat_path, index=False)

        rel_df = pd.DataFrame(
            [
                {
                    "unit_id": r.unit_id,
                    "algorithm": r.algorithm,
                    "source_experiment": r.source_experiment,
                    "cluster_id": r.cluster_id,
                    "cluster_label": r.cluster_label,
                    "feature": r.feature,
                    "cluster_median": r.cluster_median,
                    "cluster_mean": r.cluster_mean,
                    "overall_median": r.overall_median,
                    "overall_mean": r.overall_mean,
                    "rel_diff_median_pct": r.rel_diff_median_pct,
                    "rel_diff_mean_pct": r.rel_diff_mean_pct,
                    "reference_status": r.reference_status,
                    "reference_count": r.reference_count,
                }
                for r in rel_rows
            ]
        )
        if not rel_df.empty:
            rel_df = rel_df.sort_values(["unit_id", "cluster_label", "feature"]).reset_index(
                drop=True
            )
        rel_path = self.output_dir / "cp02_relative_comparison.csv"
        rel_df.to_csv(rel_path, index=False)

        interp_df = pd.DataFrame(
            [
                {
                    "unit_id": r.unit_id,
                    "algorithm": r.algorithm,
                    "source_experiment": r.source_experiment,
                    "cluster_id": r.cluster_id,
                    "cluster_label": r.cluster_label,
                    "feature": r.feature,
                    "direction": r.direction,
                    "rel_diff_median_pct": r.rel_diff_median_pct,
                    "cluster_median": r.cluster_median,
                    "overall_median": r.overall_median,
                    "interpretation": r.interpretation,
                }
                for r in interp_rows
            ]
        )
        if not interp_df.empty:
            interp_df = interp_df.sort_values(["unit_id", "cluster_label", "feature"]).reset_index(
                drop=True
            )
        interp_path = self.output_dir / "cp02_behavioral_interpretation.csv"
        interp_df.to_csv(interp_path, index=False)

        # 7. Unit provenance (so a reader can map each row to a source).
        prov_df = pd.DataFrame(
            [
                {
                    "unit_id": u.unit_id,
                    "algorithm": u.algorithm,
                    "source_experiment": u.source_experiment,
                    "configuration_id": u.configuration_id,
                    "configuration_status": u.configuration_status,
                    "labels_persisted": u.labels_persisted,
                    "n_customers_eligible": u.n_customers_eligible,
                }
                for u in units
            ]
        )
        prov_path = self.output_dir / "cp02_unit_provenance.csv"
        prov_df.to_csv(prov_path, index=False)

        # 8. CP-01 consistency check (per (unit, cluster) → CP-01 size).
        consistency_df = self._build_consistency_table(units)
        consistency_path = self.output_dir / "cp02_cp01_consistency.csv"
        consistency_df.to_csv(consistency_path, index=False)

        # 9. Build report.
        artifact_paths_for_report: dict[str, list[str]] = defaultdict(list)
        for p in chart_paths:
            stem = p.stem
            for uid in {u.unit_id for u in units if u.labels_persisted}:
                safe_uid = uid.replace("/", "_").replace(" ", "_")
                if stem.startswith(f"cp02_{safe_uid}_"):
                    artifact_paths_for_report[uid].append(str(p.relative_to(self.output_dir)))
                    break
        raw_features_sha = _file_sha256(self.repo_root / RAW_FEATURES_PATH)
        report_ctx = Cp02ReportContext(
            units=units,
            feature_rows=feature_rows,
            rel_rows=rel_rows,
            interp_rows=interp_rows,
            artifacts=dict(artifact_paths_for_report),
            analysis_units_total=len(units),
            units_with_labels=sum(1 for u in units if u.labels_persisted),
            units_without_labels=sum(1 for u in units if not u.labels_persisted),
            raw_features_path=str(RAW_FEATURES_PATH),
            raw_features_sha256=raw_features_sha,
            cluster_size_table_path=str(self.cp01_size_table_path),
        )
        report_path = self.output_dir / "cp02_report.md"
        build_cp02_markdown(report_ctx, report_path)

        # 10. Manifest.
        manifest = {
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "output_dir": str(self.output_dir),
            "include_exp03": bool(self.include_exp03),
            "algorithms": list(ALGORITHMS),
            "analysis_units_total": report_ctx.analysis_units_total,
            "units_with_labels": report_ctx.units_with_labels,
            "units_without_labels": report_ctx.units_without_labels,
            "outputs": {
                "feature_profile_table_csv": str(feat_path),
                "relative_comparison_csv": str(rel_path),
                "behavioral_interpretation_csv": str(interp_path),
                "unit_provenance_csv": str(prov_path),
                "cp01_consistency_csv": str(consistency_path),
                "report_md": str(report_path),
                "figures": [str(p) for p in chart_paths],
            },
            "input_sources": {
                "raw_features_path": str(RAW_FEATURES_PATH),
                "raw_features_sha256": raw_features_sha,
                "cp01_cluster_size_table_path": str(self.cp01_size_table_path),
                "cp01_cluster_size_table_sha256": _file_sha256(self.cp01_size_table_path),
            },
            "feature_set": list(
                __import__(
                    "customer_segmentation.profiling.cp02.provenance",
                    fromlist=["FEATURE_COLUMNS"],
                ).FEATURE_COLUMNS
            ),
            "feature_source": (
                "RAW interpretable values from data/processed/customer_candidates.parquet "
                "(FE-05 output). NOT Yeo-Johnson / RobustScaler values."
            ),
            "methodology_gate": (
                "AGENTS.md §2 — no segment naming, no Marketing recommendation, "
                "no algorithm ranking. DBSCAN noise separated. EXP-03 working-selected "
                "labels reported as NOT_AVAILABLE (per EV03-HP-01)."
            ),
        }
        manifest_path = self.output_dir / "cp02_runner_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return {
            "feature_profile_table_csv": str(feat_path),
            "relative_comparison_csv": str(rel_path),
            "behavioral_interpretation_csv": str(interp_path),
            "unit_provenance_csv": str(prov_path),
            "cp01_consistency_csv": str(consistency_path),
            "report_md": str(report_path),
            "manifest_json": str(manifest_path),
            "figures": [str(p) for p in chart_paths],
            "analysis_units_total": report_ctx.analysis_units_total,
            "units_with_labels": report_ctx.units_with_labels,
            "units_without_labels": report_ctx.units_without_labels,
        }

    def _build_consistency_table(self, units: Sequence) -> pd.DataFrame:
        """Build the CP-01 ↔ CP-02 consistency table.

        For each (unit, cluster) we record:
        - ``cp02_cluster_customer_count`` — count from the joined frame.
        - ``cp01_cluster_customer_count`` — count from CP-01 size table.
        - ``match`` — boolean.
        - ``diff`` — signed difference.

        Only non-noise clusters are checked (CP-01 reports them in the
        size table; noise is reported separately).
        """
        size_csv_path = self.cp01_size_table_path
        if not size_csv_path.exists():
            # CP-01 may not have run yet — emit empty table with a note.
            return pd.DataFrame(
                columns=[
                    "unit_id",
                    "algorithm",
                    "cluster_id",
                    "is_noise",
                    "cp02_cluster_customer_count",
                    "cp01_cluster_customer_count",
                    "match",
                    "diff",
                ]
            )
        cp01_df = pd.read_csv(size_csv_path)
        # Only non-noise rows from CP-01.
        cp01_df = cp01_df.loc[cp01_df["is_noise"] == False].copy()  # noqa: E712
        rows: list[dict[str, Any]] = []
        for unit in units:
            if not unit.labels_persisted:
                continue
            df = unit.cluster_labels_frame
            eligible = df.loc[df["ClusterLabel"] != -1]
            for cl, sub in eligible.groupby("ClusterLabel", sort=True):
                cp02_count = int(sub["CustomerID"].nunique())
                cp01_row = cp01_df.loc[
                    (cp01_df["unit_id"] == unit.unit_id) & (cp01_df["cluster_id"] == int(cl))
                ]
                if cp01_row.empty:
                    cp01_count = None
                    match = False
                    diff = None
                else:
                    cp01_count = int(cp01_row.iloc[0]["customer_count"])
                    match = cp02_count == cp01_count
                    diff = cp02_count - cp01_count
                rows.append(
                    {
                        "unit_id": unit.unit_id,
                        "algorithm": unit.algorithm,
                        "cluster_id": int(cl),
                        "is_noise": False,
                        "cp02_cluster_customer_count": cp02_count,
                        "cp01_cluster_customer_count": cp01_count,
                        "match": match,
                        "diff": diff,
                    }
                )
        return pd.DataFrame(rows)


def run_cp02(
    repo_root: Path | None = None,
    output_dir: Path | None = None,
    include_exp03: bool = True,
) -> Mapping[str, Any]:
    """Convenience entry-point mirroring the package-level API."""
    if repo_root is None:
        repo_root = Path.cwd()
    if output_dir is None:
        output_dir = repo_root / DEFAULT_OUTPUT_DIR
    return Cp02Runner(
        repo_root=repo_root,
        output_dir=output_dir,
        include_exp03=include_exp03,
    ).run()


__all__ = [
    "Cp02Runner",
    "run_cp02",
    "DEFAULT_OUTPUT_DIR",
]
