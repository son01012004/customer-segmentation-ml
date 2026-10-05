"""CP-01 orchestrator.

The orchestrator:

1. Resolves analysis units (EXP-01 baselines + EXP-03 metadata-only).
2. Computes the per-(unit, cluster) size table.
3. Computes per-(unit) distribution indicators.
4. Renders one bar-chart pair per unit (count + percent).
5. Writes the size table + indicators + charts + Markdown report.

Hard constraints are recorded at the package level
(``src/customer_segmentation/profiling/cp01/__init__.py``).

Read-only against source artifacts:
- EXP-01 cluster_labels_*.parquet
- EXP-03 exp03_selected_configurations.csv
- data/processed/customer_metadata.parquet
"""

from __future__ import annotations

import dataclasses
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from customer_segmentation.profiling.cp01.distribution import (
    compute_distribution_indicators,
)
from customer_segmentation.profiling.cp01.provenance import (
    ALGORITHMS,
    AnalysisUnit,
    build_analysis_units,
)
from customer_segmentation.profiling.cp01.report import (
    ReportContext,
    build_markdown,
)
from customer_segmentation.profiling.cp01.size_analysis import (
    ClusterSizeRow,
    NoiseRow,
    compute_cluster_size_table,
    compute_noise_summary,
)
from customer_segmentation.profiling.cp01.visualization import (
    render_all_charts,
)


DEFAULT_OUTPUT_DIR = Path("reports/profiling/cp01")


@dataclasses.dataclass
class Cp01Runner:
    """Configuration for one CP-01 run."""

    repo_root: Path
    output_dir: Path = DEFAULT_OUTPUT_DIR
    include_exp03: bool = True  # Include EXP-03 working-selected metadata.
    figure_dpi: int = 120

    def run(self) -> Mapping[str, Any]:
        """Execute CP-01 and return the run-summary as a dict.

        Side effects:
        - writes ``cp01_cluster_size_table.csv``
        - writes ``cp01_noise_summary.csv``
        - writes ``cp01_distribution_indicators.csv``
        - writes ``cp01_unit_provenance.csv``
        - writes ``cp01_runner_manifest.json``
        - writes ``figures/cp01_*_size.png`` and ``*_pct.png``
        - writes ``cp01_report.md``
        """
        # Resolve units
        units = build_analysis_units(self.repo_root)
        if not self.include_exp03:
            units = [u for u in units if u.source_experiment != "EXP-03"]

        # Per-unit cluster size table + noise summary
        cluster_rows = compute_cluster_size_table(units)
        noise_rows = compute_noise_summary(units)
        # Distribution indicators from cluster rows
        indicators = compute_distribution_indicators(cluster_rows)

        # Group cluster rows + noise by unit for chart rendering
        rows_by_unit: dict[str, list[ClusterSizeRow]] = defaultdict(list)
        for r in cluster_rows:
            rows_by_unit[r.unit_id].append(r)
        noise_by_unit = {n.unit_id: n for n in noise_rows}
        units_with_rows = {
            uid: (rows_by_unit.get(uid, []), noise_by_unit.get(uid))
            for uid in rows_by_unit
        }

        # Create output directories and write artifacts.
        self.output_dir.mkdir(parents=True, exist_ok=True)
        figures_dir = self.output_dir / "figures"
        figures_dir.mkdir(parents=True, exist_ok=True)

        # Cluster-size long-form CSV
        size_df = pd.DataFrame([
            {
                "unit_id": r.unit_id,
                "algorithm": r.algorithm,
                "algorithm_family": r.algorithm_family,
                "source_experiment": r.source_experiment,
                "configuration_id": r.configuration_id,
                "configuration_status": r.configuration_status,
                "cluster_id": r.cluster_id,
                "is_noise": r.is_noise,
                "customer_count": r.customer_count,
                "pct_of_assigned": r.pct_of_assigned,
                "pct_of_total": r.pct_of_total,
                "relative_size_ratio": r.relative_size_ratio,
            }
            for r in cluster_rows
        ])
        if not size_df.empty:
            size_df = size_df.sort_values(["unit_id", "cluster_id"]).reset_index(drop=True)
        size_path = self.output_dir / "cp01_cluster_size_table.csv"
        size_df.to_csv(size_path, index=False)

        # Noise summary CSV
        noise_df = pd.DataFrame([
            {
                "unit_id": n.unit_id,
                "algorithm": n.algorithm,
                "noise_count": n.noise_count,
                "pct_of_total": n.pct_of_total,
            }
            for n in noise_rows
        ])
        noise_path = self.output_dir / "cp01_noise_summary.csv"
        noise_df.to_csv(noise_path, index=False)

        # Distribution indicators CSV
        ind_df = pd.DataFrame([
            {
                "unit_id": i.unit_id,
                "algorithm": i.algorithm,
                "source_experiment": i.source_experiment,
                "n_clusters": i.n_clusters,
                "n_total_customers": i.n_total_customers,
                "largest_cluster_count": i.largest_cluster_count,
                "smallest_cluster_count": i.smallest_cluster_count,
                "largest_pct_of_total": i.largest_pct_of_total,
                "largest_to_smallest_ratio": i.largest_to_smallest_ratio,
                "size_range": i.size_range,
                "deviation_from_equal_size": i.deviation_from_equal_size,
                "median_cluster_size": i.median_cluster_size,
            }
            for i in indicators
        ])
        ind_path = self.output_dir / "cp01_distribution_indicators.csv"
        ind_df.to_csv(ind_path, index=False)

        # Unit provenance CSV (so a reader can trace each row of the
        # size table to a single source artifact).
        prov_df = pd.DataFrame([
            {
                "unit_id": u.unit_id,
                "algorithm": u.algorithm,
                "algorithm_family": u.algorithm_family,
                "source_experiment": u.source_experiment,
                "configuration_id": u.configuration_id,
                "configuration_status": u.configuration_status,
                "random_seed": u.random_seed,
                "n_clusters_requested": u.n_clusters_requested,
                "labels_persisted": u.labels_persisted,
                "n_customers_eligible": u.n_customers_eligible,
                "source_path": str(u.source_path),
            }
            for u in units
        ])
        prov_path = self.output_dir / "cp01_unit_provenance.csv"
        prov_df.to_csv(prov_path, index=False)

        # Charts
        chart_paths = render_all_charts(units_with_rows, figures_dir)
        artifact_paths_for_report: dict[str, list[str]] = defaultdict(list)
        for p in chart_paths:
            # Group by unit_id (filename encodes unit_id)
            stem = p.stem
            for uid in {r.unit_id for r in cluster_rows}:
                if uid.replace("/", "_").replace(" ", "_") in stem:
                    artifact_paths_for_report[uid].append(str(p.relative_to(self.output_dir)))
                    break

        # Report
        ctx = ReportContext(
            cluster_rows=cluster_rows,
            noise_rows=noise_rows,
            indicators=indicators,
            units_metadata=[{
                "unit_id": u.unit_id,
                "algorithm": u.algorithm,
                "source_experiment": u.source_experiment,
                "configuration_id": u.configuration_id,
                "configuration_status": u.configuration_status,
            } for u in units],
            artifacts=dict(artifact_paths_for_report),
            analysis_units_total=len(units),
            units_with_labels=sum(1 for u in units if u.labels_persisted),
            units_without_labels=sum(1 for u in units if not u.labels_persisted),
        )
        report_path = self.output_dir / "cp01_report.md"
        build_markdown(ctx, report_path)

        # Run manifest
        manifest = {
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "output_dir": str(self.output_dir),
            "include_exp03": bool(self.include_exp03),
            "algorithms": list(ALGORITHMS),
            "analysis_units_total": ctx.analysis_units_total,
            "units_with_labels": ctx.units_with_labels,
            "units_without_labels": ctx.units_without_labels,
            "outputs": {
                "cluster_size_table_csv": str(size_path),
                "noise_summary_csv": str(noise_path),
                "distribution_indicators_csv": str(ind_path),
                "unit_provenance_csv": str(prov_path),
                "report_md": str(report_path),
                "figures": [str(p) for p in chart_paths],
            },
            "decision_status_taxonomy": {
                "EXP-01": "WORKING_DEFAULT",
                "EXP-03": "WORKING_SELECTED / TIED_WORKING_SELECTED (verbatim from exp03_selected_configurations.csv)",
            },
            "methodology_gate": "AGENTS.md §2.5 — no algorithm ranking, no composite score.",
        }
        manifest_path = self.output_dir / "cp01_runner_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return {
            "cluster_size_table_csv": str(size_path),
            "noise_summary_csv": str(noise_path),
            "distribution_indicators_csv": str(ind_path),
            "unit_provenance_csv": str(prov_path),
            "report_md": str(report_path),
            "manifest_json": str(manifest_path),
            "figures": [str(p) for p in chart_paths],
            "analysis_units_total": ctx.analysis_units_total,
            "units_with_labels": ctx.units_with_labels,
            "units_without_labels": ctx.units_without_labels,
        }


def run_cp01(
    repo_root: Path | None = None,
    output_dir: Path | None = None,
    include_exp03: bool = True,
) -> Mapping[str, Any]:
    """Convenience entry-point mirroring the package-level API."""
    if repo_root is None:
        repo_root = Path.cwd()
    if output_dir is None:
        output_dir = repo_root / DEFAULT_OUTPUT_DIR
    return Cp01Runner(
        repo_root=repo_root,
        output_dir=output_dir,
        include_exp03=include_exp03,
    ).run()


__all__ = ["Cp01Runner", "run_cp01"]
