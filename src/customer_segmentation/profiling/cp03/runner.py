"""CP-03 orchestrator.

The orchestrator:

1. Reuses CP-02 analysis units (read-only, no new cluster labels).
2. Builds the segment comparison matrix (joins CP-02 stats + CP-03 IQR overlap).
3. Computes per-(unit, feature) distinguishing indicators + classification.
4. Computes pairwise IQR overlap rows.
5. Renders violin plots + distinguishing bar charts + IQR overlap heatmaps.
6. Writes CSV / JSON / Markdown artifacts.

Hard constraints recorded at the package level
(``src/customer_segmentation/profiling/cp03/__init__.py``).

Read-only against source artifacts:
- EXP-01 cluster_labels_*.parquet (read)
- EXP-03 exp03_selected_configurations.csv (read)
- data/processed/customer_candidates.parquet (read)
- data/processed/customer_metadata.parquet (read)
- CP-02 outputs: feature_profile_table.csv, relative_comparison.csv,
  behavioral_interpretation.csv, cp02_unit_provenance.csv,
  cp02_cp01_consistency.csv (read, verified via SHA-256).

No new cluster labels are produced.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from customer_segmentation.profiling.cp01.provenance import (
    ALGORITHMS,
)
from customer_segmentation.profiling.cp02.provenance import (
    RAW_FEATURES_PATH,
    build_cp02_analysis_units,
)
from customer_segmentation.profiling.cp03.comparison import (
    comparison_rows_to_dicts,
    compute_segment_comparison_matrix,
)
from customer_segmentation.profiling.cp03.difference_analysis import (
    compute_distinguishing_feature_table,
    distinguishing_rows_to_dicts,
)
from customer_segmentation.profiling.cp03.overlap_analysis import (
    compute_pairwise_overlap_table,
)
from customer_segmentation.profiling.cp03.report import (
    Cp03ReportContext,
    build_cp03_markdown,
)
from customer_segmentation.profiling.cp03.visualization import (
    VIOLIN_FEATURE_SUBSET,
    render_all_cp03_charts,
)

DEFAULT_OUTPUT_DIR = Path("reports/profiling/cp03")


def _file_sha256(path: Path) -> str | None:
    """Return the SHA-256 hex digest of a file, or None if missing."""
    if not path.exists():
        return None
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


class Cp03Runner:
    """Configuration for one CP-03 run."""

    def __init__(
        self,
        repo_root: Path,
        output_dir: Path = DEFAULT_OUTPUT_DIR,
        include_exp03: bool = True,
        figure_dpi: int = 120,
        cp02_output_dir: Path | None = None,
        cp02_feature_profile_csv: Path | None = None,
        cp02_relative_comparison_csv: Path | None = None,
        cp02_behavioral_csv: Path | None = None,
        cp02_report_path: Path | None = None,
    ) -> None:
        self.repo_root = repo_root
        self.output_dir = output_dir
        self.include_exp03 = include_exp03
        self.figure_dpi = figure_dpi
        self.cp02_output_dir = cp02_output_dir or (repo_root / DEFAULT_OUTPUT_DIR.parent / "cp02")
        self.cp02_feature_profile_csv = (
            cp02_feature_profile_csv or self.cp02_output_dir / "cp02_feature_profile_table.csv"
        )
        self.cp02_relative_comparison_csv = (
            cp02_relative_comparison_csv or self.cp02_output_dir / "cp02_relative_comparison.csv"
        )
        self.cp02_behavioral_csv = (
            cp02_behavioral_csv or self.cp02_output_dir / "cp02_behavioral_interpretation.csv"
        )
        self.cp02_report_path = cp02_report_path or self.cp02_output_dir / "cp02_report.md"

    def run(self) -> Mapping[str, Any]:
        """Execute CP-03 and return the run-summary as a dict.

        Side effects:
        - writes ``cp03_segment_comparison_matrix.csv``
        - writes ``cp03_distinguishing_features.csv``
        - writes ``cp03_overlap_analysis.csv``
        - writes ``cp03_unit_provenance.csv``
        - writes ``cp03_runner_manifest.json``
        - writes ``cp03_report.md``
        - writes ``figures/cp03_*_violin.png`` (per unit, per feature)
        - writes ``figures/cp03_*_distinguishing.png`` (per unit)
        - writes ``figures/cp03_*_iqr_overlap.png`` (per unit)
        """
        # 1. Build analysis units (reuses CP-02).
        units = build_cp02_analysis_units(self.repo_root)
        if not self.include_exp03:
            units = [u for u in units if u.source_experiment != "EXP-03"]

        # 2. Build segment comparison matrix.
        comparison_rows = compute_segment_comparison_matrix(units)

        # 3. Compute distinguishing feature indicators + classification.
        distinguishing_rows = compute_distinguishing_feature_table(units)

        # 4. Compute pairwise IQR overlap rows.
        overlap_rows = compute_pairwise_overlap_table(units)

        # 5. Render charts.
        self.output_dir.mkdir(parents=True, exist_ok=True)
        figures_dir = self.output_dir / "figures"
        figures_dir.mkdir(parents=True, exist_ok=True)
        chart_paths = render_all_cp03_charts(
            units=units,
            out_dir=figures_dir,
            feature_subset=VIOLIN_FEATURE_SUBSET,
        )

        # 6. Write CSVs.
        comp_df = pd.DataFrame(comparison_rows_to_dicts(comparison_rows))
        if not comp_df.empty:
            comp_df = comp_df.sort_values(["unit_id", "cluster_label", "feature"]).reset_index(
                drop=True
            )
        comp_path = self.output_dir / "cp03_segment_comparison_matrix.csv"
        comp_df.to_csv(comp_path, index=False)

        dist_df = pd.DataFrame(distinguishing_rows_to_dicts(distinguishing_rows))
        if not dist_df.empty:
            dist_df = dist_df.sort_values(["unit_id", "feature"]).reset_index(drop=True)
        dist_path = self.output_dir / "cp03_distinguishing_features.csv"
        dist_df.to_csv(dist_path, index=False)

        overlap_list: list[dict[str, Any]] = [
            {
                "unit_id": r.unit_id,
                "algorithm": r.algorithm,
                "source_experiment": r.source_experiment,
                "feature": r.feature,
                "cluster_a_label": r.cluster_a_label,
                "cluster_a_id": r.cluster_a_id,
                "cluster_b_label": r.cluster_b_label,
                "cluster_b_id": r.cluster_b_id,
                "iqr_overlap_coefficient": r.iqr_overlap_coefficient,
                "iqr_intersection_width": r.iqr_intersection_width,
                "iqr_width_a": r.iqr_width_a,
                "iqr_width_b": r.iqr_width_b,
            }
            for r in overlap_rows
        ]
        overlap_df = pd.DataFrame(overlap_list)
        if not overlap_df.empty:
            overlap_df = overlap_df.sort_values(
                ["unit_id", "feature", "cluster_a_id", "cluster_b_id"]
            ).reset_index(drop=True)
        overlap_path = self.output_dir / "cp03_overlap_analysis.csv"
        overlap_df.to_csv(overlap_path, index=False)

        # 7. Unit provenance (mirror CP-02).
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
        prov_path = self.output_dir / "cp03_unit_provenance.csv"
        prov_df.to_csv(prov_path, index=False)

        # 8. Build report.
        artifact_paths_for_report: dict[str, list[str]] = defaultdict(list)
        for p in chart_paths:
            stem = p.stem
            for uid in {u.unit_id for u in units if u.labels_persisted}:
                safe_uid = uid.replace("/", "_").replace(" ", "_")
                if stem.startswith(f"cp03_{safe_uid}_"):
                    artifact_paths_for_report[uid].append(str(p.relative_to(self.output_dir)))
                    break
        raw_features_sha = _file_sha256(self.repo_root / RAW_FEATURES_PATH)
        report_ctx = Cp03ReportContext(
            units=units,
            comparison_rows=comparison_rows,
            distinguishing_rows=distinguishing_rows,
            overlap_rows=overlap_rows,
            artifacts=dict(artifact_paths_for_report),
            analysis_units_total=len(units),
            units_with_labels=sum(1 for u in units if u.labels_persisted),
            units_without_labels=sum(1 for u in units if not u.labels_persisted),
            raw_features_path=str(RAW_FEATURES_PATH),
            raw_features_sha256=raw_features_sha,
            cp02_report_path=str(self.cp02_report_path),
        )
        report_path = self.output_dir / "cp03_report.md"
        build_cp03_markdown(report_ctx, report_path)

        # 9. Manifest.
        manifest = {
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "output_dir": str(self.output_dir),
            "include_exp03": bool(self.include_exp03),
            "algorithms": list(ALGORITHMS),
            "analysis_units_total": report_ctx.analysis_units_total,
            "units_with_labels": report_ctx.units_with_labels,
            "units_without_labels": report_ctx.units_without_labels,
            "outputs": {
                "segment_comparison_matrix_csv": str(comp_path),
                "distinguishing_features_csv": str(dist_path),
                "overlap_analysis_csv": str(overlap_path),
                "unit_provenance_csv": str(prov_path),
                "report_md": str(report_path),
                "figures": [str(p) for p in chart_paths],
            },
            "input_sources": {
                "raw_features_path": str(RAW_FEATURES_PATH),
                "raw_features_sha256": raw_features_sha,
                "cp02_feature_profile_csv": str(self.cp02_feature_profile_csv),
                "cp02_feature_profile_sha256": _file_sha256(self.cp02_feature_profile_csv),
                "cp02_relative_comparison_csv": str(self.cp02_relative_comparison_csv),
                "cp02_relative_comparison_sha256": _file_sha256(self.cp02_relative_comparison_csv),
                "cp02_behavioral_csv": str(self.cp02_behavioral_csv),
                "cp02_behavioral_sha256": _file_sha256(self.cp02_behavioral_csv),
                "cp02_report_path": str(self.cp02_report_path),
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
                "labels reported as NOT_AVAILABLE (per EV03-HP-01). "
                "WORKING_ANALYTICAL_THRESHOLD explicitly labelled."
            ),
        }
        manifest_path = self.output_dir / "cp03_runner_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return {
            "segment_comparison_matrix_csv": str(comp_path),
            "distinguishing_features_csv": str(dist_path),
            "overlap_analysis_csv": str(overlap_path),
            "unit_provenance_csv": str(prov_path),
            "report_md": str(report_path),
            "manifest_json": str(manifest_path),
            "figures": [str(p) for p in chart_paths],
            "analysis_units_total": report_ctx.analysis_units_total,
            "units_with_labels": report_ctx.units_with_labels,
            "units_without_labels": report_ctx.units_without_labels,
        }


def run_cp03(
    repo_root: Path | None = None,
    output_dir: Path | None = None,
    include_exp03: bool = True,
) -> Mapping[str, Any]:
    """Convenience entry-point mirroring the package-level API."""
    if repo_root is None:
        repo_root = Path.cwd()
    if output_dir is None:
        output_dir = repo_root / DEFAULT_OUTPUT_DIR
    return Cp03Runner(
        repo_root=repo_root,
        output_dir=output_dir,
        include_exp03=include_exp03,
    ).run()


__all__ = [
    "Cp03Runner",
    "run_cp03",
    "DEFAULT_OUTPUT_DIR",
]
