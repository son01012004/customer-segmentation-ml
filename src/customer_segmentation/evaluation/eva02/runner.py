"""Top-level orchestration for EVA-02 — Cluster Quality Evaluation.

The runner is the single entry point that ties together the
comparison, quality, visualisation, and report layers. It does
NOT modify any EVA-01 artifact; it only reads them, computes
descriptive summary tables, writes CSV / Markdown / PNG outputs
under ``reports/evaluation/eva02/``, and emits a small JSON
``run_manifest.json`` with provenance information.

Hard constraints (AGENTS.md §2):

- Read-only against EVA-01.
- No ranking / "best/winner/optimal/recommended/final" labels.
- No composite score.
- No commit / push / PR.

Public entry points
-------------------

- :class:`Eva02Runner` — orchestrator class.
- :func:`run_eva02` — convenience wrapper that constructs
  ``Eva02Runner`` and runs the full pipeline.
"""

from __future__ import annotations

import json
import platform
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from customer_segmentation.evaluation.eva02.comparison import (
    compare_by_algorithm,
    compare_by_hyperparameter,
    compare_by_k,
    compare_by_preprocessing,
    metric_ranking_per_metric,
)
from customer_segmentation.evaluation.eva02.load import (
    DEFAULT_EVA01_DIR,
    REPOSITORY_PARQUET_NAME,
    load_repository,
)
from customer_segmentation.evaluation.eva02.quality import (
    cross_metric_conflicts,
    dataset_quality_overview,
    dbscan_noise_summary,
    quality_by_algorithm,
    quality_by_algorithm_and_k,
    quality_by_k,
    quality_by_preprocessing,
)
from customer_segmentation.evaluation.eva02.report import build_report
from customer_segmentation.evaluation.eva02.visualization import (
    plot_metric_by_algorithm,
    plot_metric_by_hyperparameter_family,
    plot_metric_by_preprocessing,
    plot_metric_distributions,
    plot_metric_vs_k,
)

__all__ = [
    "Eva02Config",
    "Eva02Runner",
    "run_eva02",
]


# Default output directory — keeps parity with EVA-01.
DEFAULT_EVA02_DIR: Path = Path("reports/evaluation/eva02")

# Manifest filename.
RUN_MANIFEST_NAME: str = "eva02_run_manifest.json"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Eva02Config:
    """Immutable configuration object for EVA-02."""

    eva01_dir: Path = DEFAULT_EVA01_DIR
    output_dir: Path = DEFAULT_EVA02_DIR
    figures_subdir: str = "figures"
    tables_subdir: str = "tables"
    prefer_parquet: bool = True
    rank_tolerance: int = 1
    # Ranking is reported per metric; it is NEVER promoted to a
    # final algorithm ranking. The flag controls whether the
    # per-metric ranking tables are written to disk.
    write_rankings: bool = True
    # When ``True``, :func:`compare_by_hyperparameter` appends an
    # extra ``non_exp03_aggregate`` row per algorithm that aggregates
    # the non-EXP-03 rows for the same algorithm. The label is *not*
    # a hyperparameter family; the flag is provided so callers can
    # opt-in if they want the aggregate surfaced (default off).
    include_non_exp03_aggregate: bool = False


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


@dataclass
class Eva02Runner:
    """Run the full EVA-02 pipeline.

    Parameters
    ----------
    config : Eva02Config
        Pipeline configuration (paths, tolerances, switches).
    """

    config: Eva02Config = field(default_factory=Eva02Config)

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------

    def _tables_dir(self) -> Path:
        return self.config.output_dir / self.config.tables_subdir

    def _figures_dir(self) -> Path:
        return self.config.output_dir / self.config.figures_subdir

    def _ensure_dirs(self) -> None:
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        self._tables_dir().mkdir(parents=True, exist_ok=True)
        self._figures_dir().mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # I/O helpers
    # ------------------------------------------------------------------

    def _write_csv(self, df: pd.DataFrame, filename: str) -> Path:
        path = self._tables_dir() / filename
        df.to_csv(path, index=False)
        return path

    def _relative_to_repo(self, path: Path) -> str:
        """Return a repo-relative path string when possible."""
        try:
            cwd = Path.cwd().resolve()
            resolved = path.resolve()
            return str(resolved.relative_to(cwd))
        except ValueError:
            return str(path)

    # ------------------------------------------------------------------
    # Pipeline
    # ------------------------------------------------------------------

    def load(self) -> pd.DataFrame:
        """Load the EVA-01 standardised repository."""
        return load_repository(
            self.config.eva01_dir,
            prefer_parquet=self.config.prefer_parquet,
        )

    def run(self) -> Mapping[str, object]:
        """Execute the full EVA-02 pipeline.

        Returns
        -------
        Mapping[str, object]
            A manifest dictionary describing what was produced.
            The manifest is also written to
            ``<output_dir>/eva02_run_manifest.json``.
        """
        self._ensure_dirs()

        # 1) Load
        df = self.load()

        # 2) Tables
        tables: dict[str, pd.DataFrame] = {}
        tables["dataset_overview"] = pd.DataFrame.from_records([dataset_quality_overview_row(df)])
        tables["by_algorithm"] = compare_by_algorithm(df)
        tables["by_k"] = compare_by_k(df)
        tables["by_algorithm_and_k"] = quality_by_algorithm_and_k(df)
        tables["by_preprocessing"] = compare_by_preprocessing(df)
        tables["by_hyperparameter"] = compare_by_hyperparameter(
            df,
            include_non_exp03_aggregate=self.config.include_non_exp03_aggregate,
        )
        tables["quality_by_algorithm"] = quality_by_algorithm(df)
        tables["quality_by_k"] = quality_by_k(df)
        tables["quality_by_preprocessing"] = quality_by_preprocessing(df)
        conflicts = cross_metric_conflicts(df, rank_tolerance=self.config.rank_tolerance)
        tables["cross_metric_conflicts"] = conflicts
        flagged = _filter_flagged_conflicts(conflicts)
        tables["cross_metric_conflicts_flagged"] = flagged
        tables["dbscan_noise"] = dbscan_noise_summary(df)

        # 3) Per-metric ranking tables (rank-by-metric, NOT a final ranking)
        rankings: dict[str, pd.DataFrame] = {}
        if self.config.write_rankings:
            rankings = metric_ranking_per_metric(df)

        # 4) Figures
        figures: list[Path] = []
        figures.extend(plot_metric_vs_k(df, self._figures_dir()))
        figures.extend(plot_metric_by_algorithm(df, self._figures_dir()))
        figures.extend(plot_metric_by_preprocessing(df, self._figures_dir()))
        figures.extend(plot_metric_by_hyperparameter_family(df, self._figures_dir()))
        figures.extend(plot_metric_distributions(df, self._figures_dir()))

        # 5) Persist tables
        table_paths: list[Path] = []
        table_paths.append(
            self._write_csv(tables["dataset_overview"], "eva02_dataset_overview.csv")
        )
        table_paths.append(self._write_csv(tables["by_algorithm"], "eva02_by_algorithm.csv"))
        table_paths.append(self._write_csv(tables["by_k"], "eva02_by_k.csv"))
        table_paths.append(
            self._write_csv(tables["by_algorithm_and_k"], "eva02_by_algorithm_and_k.csv")
        )
        table_paths.append(
            self._write_csv(tables["by_preprocessing"], "eva02_by_preprocessing.csv")
        )
        table_paths.append(
            self._write_csv(tables["by_hyperparameter"], "eva02_by_hyperparameter.csv")
        )
        table_paths.append(
            self._write_csv(tables["quality_by_algorithm"], "eva02_quality_by_algorithm.csv")
        )
        table_paths.append(self._write_csv(tables["quality_by_k"], "eva02_quality_by_k.csv"))
        table_paths.append(
            self._write_csv(
                tables["quality_by_preprocessing"], "eva02_quality_by_preprocessing.csv"
            )
        )
        table_paths.append(
            self._write_csv(tables["cross_metric_conflicts"], "eva02_cross_metric_conflicts.csv")
        )
        if not flagged.empty:
            table_paths.append(self._write_csv(flagged, "eva02_cross_metric_conflicts_flagged.csv"))
        if not tables["dbscan_noise"].empty:
            table_paths.append(self._write_csv(tables["dbscan_noise"], "eva02_dbscan_noise.csv"))

        ranking_paths: list[Path] = []
        for metric, rank_df in rankings.items():
            ranking_paths.append(self._write_csv(rank_df, f"eva02_ranking_{metric}.csv"))

        # 6) Markdown report
        generated_at = datetime.now(UTC).isoformat()
        report_md = build_report(
            df,
            table_paths=[self._relative_to_repo(p) for p in table_paths],
            figure_paths=[self._relative_to_repo(p) for p in figures],
            ranking_paths=[self._relative_to_repo(p) for p in ranking_paths],
            generated_at=generated_at,
        )
        report_path = self.config.output_dir / "eva02_report.md"
        report_path.write_text(report_md, encoding="utf-8")

        # 7) Manifest
        manifest: dict[str, object] = {
            "generated_at": generated_at,
            "eva01_dir": self._relative_to_repo(Path(self.config.eva01_dir)),
            "eva01_repository_file": REPOSITORY_PARQUET_NAME,
            "output_dir": self._relative_to_repo(self.config.output_dir),
            "n_rows": int(len(df)),
            "rank_tolerance": int(self.config.rank_tolerance),
            "tables": [self._relative_to_repo(p) for p in table_paths],
            "rankings": [self._relative_to_repo(p) for p in ranking_paths],
            "figures": [self._relative_to_repo(p) for p in figures],
            "report": self._relative_to_repo(report_path),
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "scope_notes": [
                "EVA-02 is descriptive only. No algorithm is declared 'best'.",
                "Cross-metric rankings are per-metric, per-condition.",
                "Cross-algorithm conclusions require stability + hypothesis "
                "tests (out of scope here).",
                "Hyperparameter-family table is restricted to EXP-03 rows; "
                "non-EXP-03 rows are NOT aggregated as a hyperparameter family.",
                "Conflict-detection ranking groups enforce the EXP-05 R/S/N, "
                "EXP-03 Stage A/B/C and EXP-04 scenario boundaries.",
                "DBSCAN's n_clusters is the *realized* cluster count; K-bearing "
                "algorithms' n_clusters is the *requested* K. The metric-vs-K "
                "plot uses a distinct marker / line for DBSCAN.",
                "rank_tolerance=1 is a WORKING_ANALYTICAL_THRESHOLD; see "
                "customer_segmentation.evaluation.eva02.quality.RANK_TOLERANCE_NOTE.",
            ],
        }
        manifest_path = self.config.output_dir / RUN_MANIFEST_NAME
        manifest_path.write_text(
            json.dumps(manifest, indent=2, default=_json_default),
            encoding="utf-8",
        )
        return manifest


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _json_default(value: object) -> object:
    """Default JSON serialiser for numpy / pandas types."""
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except (ValueError, TypeError):
            return str(value)
    if isinstance(value, Path):
        return str(value)
    return str(value)


def dataset_quality_overview_row(df: pd.DataFrame) -> dict[str, object]:
    """Flatten :func:`dataset_quality_overview` into a single-row dict
    suitable for CSV export."""

    overview = dataset_quality_overview(df)
    row: dict[str, object] = {
        "n_rows": overview["n_rows"],
        "n_rows_with_all_metrics": overview["n_rows_with_all_metrics"],
        "n_unique_algorithms": overview["n_unique_algorithms"],
        "dbscan_total_noise_count": overview["dbscan_total_noise_count"],
    }
    for metric, cov in overview["metric_coverage"].items():
        row[f"{metric}_n_present"] = cov["n_present"]
        row[f"{metric}_fraction"] = cov["fraction"]
    for algo, frac in overview["algorithm_metric_coverage"].items():
        row[f"algo_{algo}_fraction"] = frac
    return row


def _filter_flagged_conflicts(conflicts: pd.DataFrame) -> pd.DataFrame:
    """Return only the rows whose Silhouette rank disagrees with at
    least one of the secondary metrics beyond the configured
    tolerance. The table is intended for human review only.
    """
    if conflicts.empty:
        return conflicts
    if "conflict_with_secondary" not in conflicts.columns:
        return conflicts.iloc[0:0]
    mask = conflicts["conflict_with_secondary"] | conflicts["conflict_with_tertiary"]
    return conflicts.loc[mask].reset_index(drop=True)


def run_eva02(
    *,
    eva01_dir: Path | str = DEFAULT_EVA01_DIR,
    output_dir: Path | str = DEFAULT_EVA02_DIR,
    rank_tolerance: int = 1,
    prefer_parquet: bool = True,
    include_non_exp03_aggregate: bool = False,
    write_rankings: bool = True,
) -> Mapping[str, object]:
    """Convenience wrapper around :class:`Eva02Runner`.

    Parameters
    ----------
    eva01_dir : path-like
        Directory containing the EVA-01 outputs.
    output_dir : path-like
        Directory where EVA-02 will write its outputs.
    rank_tolerance : int
        Maximum allowed rank difference before a row is flagged as
        a cross-metric conflict. Working analytical threshold.
    prefer_parquet : bool
        Whether to prefer parquet over CSV when loading EVA-01.
    include_non_exp03_aggregate : bool
        When ``True``, the hyperparameter-family table appends one
        ``non_exp03_aggregate`` row per algorithm that aggregates
        the non-EXP-03 rows.
    write_rankings : bool
        When ``False``, skip writing per-metric ranking CSVs.

    Returns
    -------
    Mapping[str, object]
        The manifest dictionary.
    """
    config = Eva02Config(
        eva01_dir=Path(eva01_dir),
        output_dir=Path(output_dir),
        rank_tolerance=rank_tolerance,
        prefer_parquet=prefer_parquet,
        include_non_exp03_aggregate=include_non_exp03_aggregate,
        write_rankings=write_rankings,
    )
    runner = Eva02Runner(config=config)
    return runner.run()
