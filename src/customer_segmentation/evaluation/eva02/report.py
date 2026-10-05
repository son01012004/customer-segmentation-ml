"""Markdown narrative report builder for EVA-02.

The report contains:

- A provenance / scope header.
- A descriptive metric overview.
- A ranking-boundary / DBSCAN-semantics section (added after the
  post-implementation review).
- Per-experiment metric distributions.
- Per-algorithm / per-K / per-preprocessing comparison summaries.
- Hyperparameter-family summary (EXP-03 only; non-EXP-03 rows are
  explicitly excluded).
- Cross-metric conflict observations (with EXP-05 R/S/N and
  EXP-03 Stage A/B/C boundary columns).
- DBSCAN noise characteristics.
- A list of artefacts produced (figures + tables).
- A explicit "interpretation boundary" section that reminds the
  reader that no algorithm is declared "best".

Hard constraints (AGENTS.md §2):

- No ranking / "best/winner/optimal/recommended/final" labels.
- No composite scores.
- Read-only against EVA-01.
- No promotion of ``WORKING_SELECTED`` to ``RESEARCH_APPROVED``.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Mapping

import pandas as pd

from customer_segmentation.evaluation.eva02.comparison import (
    compare_by_algorithm,
    compare_by_hyperparameter,
    compare_by_k,
    compare_by_preprocessing,
    DEFAULT_RANK_WITHIN_BY_EXPERIMENT,
    metric_ranking_per_metric,
)
from customer_segmentation.evaluation.eva02.quality import (
    RANK_TOLERANCE_NOTE,
    cross_metric_conflicts,
    dbscan_noise_summary,
    dataset_quality_overview,
    default_conflict_group_cols,
    quality_by_algorithm,
    quality_by_algorithm_and_k,
    quality_by_k,
    quality_by_preprocessing,
)
from customer_segmentation.evaluation.eva02.metrics import (
    METRIC_COLUMNS,
    METRIC_DIRECTIONS,
    RUNTIME_COLUMN,
    extract_metric_vector,
    summarise_metric,
)
from customer_segmentation.evaluation.experiment_results.schema import MISSING

__all__ = [
    "build_report",
    "report_to_markdown",
]


# ---------------------------------------------------------------------------
# Markdown helpers
# ---------------------------------------------------------------------------


def _fmt_float(value: object, digits: int = 4) -> str:
    """Format a float for Markdown; ``-`` for NaN / missing."""
    if value is None:
        return "-"
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return "-"
        return f"{value:.{digits}f}"
    if isinstance(value, str) and value == MISSING:
        return "-"
    return str(value)


def _df_to_md(df: pd.DataFrame, *, max_rows: int = 40, digits: int = 4) -> str:
    """Render a DataFrame to a Markdown table."""
    if df.empty:
        return "_(empty)_\n"
    truncated = df.head(max_rows)
    columns = [str(c) for c in truncated.columns]
    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join("---" for _ in columns) + " |"
    lines = [header, sep]
    for _, row in truncated.iterrows():
        cells: list[str] = []
        for c in columns:
            v = row[c]
            if isinstance(v, float):
                cells.append(_fmt_float(v, digits=digits))
            elif isinstance(v, int):
                cells.append(str(v))
            elif isinstance(v, (list, tuple)):
                cells.append(", ".join(str(x) for x in v))
            else:
                s = str(v)
                s = s.replace("|", "\\|")
                if len(s) > 80:
                    s = s[:77] + "..."
                cells.append(s)
        lines.append("| " + " | ".join(cells) + " |")
    if len(df) > max_rows:
        lines.append("")
        lines.append(f"_... {len(df) - max_rows} more rows omitted._")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Per-section builders
# ---------------------------------------------------------------------------


def _section_provenance(overview: Mapping[str, object]) -> str:
    parts: list[str] = []
    parts.append("## 1. Provenance & Scope")
    parts.append("")
    parts.append(
        "EVA-02 consumes the standardised EVA-01 repository and produces "
        "**descriptive** cluster-quality comparisons across the five "
        "EPIC-06 algorithms (K-Means, Agglomerative, DBSCAN, GMM, "
        "Fuzzy C-Means). No algorithm is declared 'best'. No composite "
        "score is computed."
    )
    parts.append("")
    parts.append(f"- Repository rows: **{overview['n_rows']}**")
    parts.append(
        "- Rows with all four primary metrics populated (Silhouette, "
        f"DBI, CH, WCSS): **{overview['n_rows_with_all_metrics']}**"
    )
    parts.append(
        f"- Distinct algorithms: **{overview['n_unique_algorithms']}**"
    )
    parts.append(
        f"- DBSCAN total noise customers (sum across rows): "
        f"**{overview['dbscan_total_noise_count']}**"
    )
    parts.append("")
    parts.append("### Metric coverage")
    parts.append("")
    coverage_rows: list[dict[str, object]] = []
    for m in METRIC_COLUMNS:
        cov = overview["metric_coverage"][m]
        coverage_rows.append(
            {
                "metric": m,
                "n_present": cov["n_present"],
                "fraction": cov["fraction"],
                "direction": METRIC_DIRECTIONS.get(m, ""),
            }
        )
    coverage_df = pd.DataFrame(coverage_rows)
    parts.append(_df_to_md(coverage_df, max_rows=20, digits=3))
    parts.append("")
    parts.append("### Per-algorithm metric completeness")
    parts.append("")
    algo_coverage = pd.DataFrame.from_records(
        [
            {
                "algorithm": algo,
                "fraction_rows_with_all_metrics": frac,
            }
            for algo, frac in overview["algorithm_metric_coverage"].items()
        ]
    )
    parts.append(_df_to_md(algo_coverage, max_rows=20, digits=3))
    parts.append("")
    return "\n".join(parts)


def _section_metric_distributions(df: pd.DataFrame) -> str:
    parts: list[str] = []
    parts.append("## 2. Metric distributions (descriptive)")
    parts.append("")
    parts.append(
        "Per-metric distribution statistics across all 185 EVA-01 rows. "
        "These numbers are descriptive — they do not imply any algorithm "
        "is better than another."
    )
    parts.append("")
    rows: list[dict[str, object]] = []
    for metric in METRIC_COLUMNS:
        vec = extract_metric_vector(df, metric)
        stats = summarise_metric(vec)
        rows.append(
            {
                "metric": metric,
                "direction": METRIC_DIRECTIONS.get(metric, ""),
                "n": stats["n"],
                "min": stats["min"],
                "max": stats["max"],
                "mean": stats["mean"],
                "std": stats["std"],
            }
        )
    parts.append(_df_to_md(pd.DataFrame(rows), max_rows=20, digits=4))
    parts.append("")
    return "\n".join(parts)


def _section_ranking_boundaries() -> str:
    """Document the ranking / conflict boundaries.

    Added after the EVA-02 post-implementation review so a human
    reviewer can verify the grouping logic without re-reading the
    code. The section is intentionally short and references the
    source-of-truth constants in :mod:`quality` and :mod:`comparison`.
    """
    parts: list[str] = []
    parts.append("## 3. Ranking boundaries and DBSCAN semantics")
    parts.append("")
    parts.append(
        "EVA-02 groups rows by *experimental condition*, not just by "
        "algorithm and K. The boundary columns are documented below "
        "and enforced in :data:`quality.DEFAULT_CONFLICT_GROUP_COLS` "
        "and :data:`comparison.DEFAULT_RANK_WITHIN_BY_EXPERIMENT`."
    )
    parts.append("")
    parts.append("### Conflict / per-metric ranking group")
    parts.append("")
    parts.append(
        "Default conflict-detection group: "
        f"`{'`, `'.join(default_conflict_group_cols())}`."
    )
    parts.append("")
    parts.append("Boundary rules:")
    parts.append("")
    parts.append(
        "* **EXP-05** — Block R (Reproducibility), Block S (Stability) "
        "and Block N (Noise perturbation) are NEVER merged into a "
        "single clustering-quality comparison condition. Each block "
        "is carried as ``_exp05_block`` (R / S / N)."
    )
    parts.append(
        "* **EXP-03** — Stage A (baseline at fixed K), Stage B (single-"
        "axis hyperparameter sweep at fixed K) and Stage C (K sweep "
        "combined with one hyperparameter value) are NEVER merged. "
        "Each stage is carried as ``_exp03_stage`` (A / B / C)."
    )
    parts.append(
        "* **EXP-04** — The five repeats of the same "
        "transformation × scaling × imputation scenario remain in the "
        "same group (``_exp04_scenario``); they are NOT independent "
        "configurations."
    )
    parts.append("")
    parts.append("### Per-experiment per-metric ranking boundary")
    parts.append("")
    rows: list[dict[str, object]] = []
    for exp, boundary in DEFAULT_RANK_WITHIN_BY_EXPERIMENT.items():
        rows.append(
            {
                "source_experiment": exp,
                "rank_within_columns": ", ".join(boundary),
            }
        )
    parts.append(_df_to_md(pd.DataFrame(rows), max_rows=20, digits=4))
    parts.append("")
    parts.append("### DBSCAN K semantics")
    parts.append("")
    parts.append(
        "K-bearing algorithms (K-Means, Agglomerative, GMM, "
        "Fuzzy C-Means) report ``n_clusters`` as the *requested* K. "
        "DBSCAN is density-based: ``n_clusters`` is the *realized* "
        "cluster count after fitting. The metric-vs-K plots use a "
        "distinct marker (``x``) and dashed line for DBSCAN and "
        "annotate the legend with `(realized K)` versus "
        "`(requested K)` so a reader cannot infer that DBSCAN was "
        "fitted with a particular K value."
    )
    parts.append("")
    parts.append("### Hyperparameter-family table scope")
    parts.append("")
    parts.append(
        "The hyperparameter-family table is restricted to **EXP-03** "
        "rows; rows from EXP-01 (baseline), EXP-02 (K sweep), EXP-04 "
        "(preprocessing) and EXP-05 (stability) carry different "
        "independent variables and MUST NOT be merged into the "
        "hyperparameter sensitivity comparison. Reviewers can opt in "
        "to a separate `non_exp03_aggregate` row per algorithm via "
        "`compare_by_hyperparameter(..., include_non_exp03_aggregate=True)`."
    )
    parts.append("")
    parts.append("### `rank_tolerance`")
    parts.append("")
    parts.append(RANK_TOLERANCE_NOTE)
    parts.append("")
    return "\n".join(parts)


def _section_per_algorithm(df: pd.DataFrame) -> str:
    parts: list[str] = []
    parts.append("## 4. Per-algorithm comparison")
    parts.append("")
    parts.append(
        "Comparison of metric distributions aggregated per algorithm. "
        "WCSS is reported for completeness (diagnostic only) and is "
        "**not** part of any quality judgement."
    )
    parts.append("")
    table = quality_by_algorithm(df)
    parts.append(_df_to_md(table, max_rows=40, digits=4))
    parts.append("")
    return "\n".join(parts)


def _section_per_k(df: pd.DataFrame) -> str:
    parts: list[str] = []
    parts.append("## 5. Per-K comparison (across algorithms)")
    parts.append("")
    parts.append(
        "Quality statistics aggregated by ``n_clusters`` regardless of "
        "algorithm. Different algorithms may contribute different K "
        "values to the same row (e.g. DBSCAN's realized n_clusters). "
        "This table is descriptive only — see section 3 for the "
        "DBSCAN K semantics caveat."
    )
    parts.append("")
    table = quality_by_k(df)
    parts.append(_df_to_md(table, max_rows=40, digits=4))
    parts.append("")
    parts.append("### Per-(algorithm, K) detail")
    parts.append("")
    table_ak = quality_by_algorithm_and_k(df)
    parts.append(_df_to_md(table_ak, max_rows=60, digits=4))
    parts.append("")
    return "\n".join(parts)


def _section_per_preprocessing(df: pd.DataFrame) -> str:
    parts: list[str] = []
    parts.append("## 6. Per-preprocessing comparison (EXP-04 only)")
    parts.append("")
    parts.append(
        "EXP-04 records six preprocessing scenarios × 5 repeats on "
        "K-Means (K=4). The table below summarises metric statistics "
        "per scenario; the five repeats of each scenario remain in "
        "the same ranking group (they are not independent "
        "configurations)."
    )
    parts.append("")
    table = quality_by_preprocessing(df)
    if table.empty:
        parts.append("_No EXP-04 rows available._\n")
    else:
        parts.append(_df_to_md(table, max_rows=40, digits=4))
    parts.append("")
    return "\n".join(parts)


def _section_per_hyperparameter(df: pd.DataFrame) -> str:
    parts: list[str] = []
    parts.append("## 7. Per-hyperparameter-family comparison (EXP-03 only)")
    parts.append("")
    parts.append(
        "Per-(algorithm, hyperparameter_family) metric summary drawn "
        "exclusively from EXP-03 rows. Rows from EXP-01 / EXP-02 / "
        "EXP-04 / EXP-05 are excluded; they carry different "
        "independent variables and MUST NOT be aggregated as a "
        "hyperparameter sensitivity family. Rows whose EXP-03 "
        "experiment_id does not match a known family token are also "
        "excluded (no synthetic `OTHER` bucket)."
    )
    parts.append("")
    table = compare_by_hyperparameter(df)
    if table.empty:
        parts.append("_No EXP-03 hyperparameter rows available._\n")
    else:
        parts.append(_df_to_md(table, max_rows=40, digits=4))
    parts.append("")
    return "\n".join(parts)


def _section_cross_metric(df: pd.DataFrame) -> str:
    parts: list[str] = []
    parts.append("## 8. Cross-metric conflicts")
    parts.append("")
    parts.append(
        "Rows whose Silhouette rank disagrees with DBI / CH rank by more "
        "than 1 position within the same ranking group "
        "(see :data:`quality.DEFAULT_CONFLICT_GROUP_COLS` for the "
        "EXP-05 R/S/N, EXP-03 Stage A/B/C and EXP-04 scenario "
        "boundaries). These rows are reported for review only — they "
        "do **not** imply an algorithm is bad or good. The rank "
        "difference is computed on signed integers to avoid the "
        "``UInt64`` underflow documented in the post-implementation "
        "review."
    )
    parts.append("")
    conflicts = cross_metric_conflicts(df, rank_tolerance=1)
    if conflicts.empty:
        parts.append("_No rows available._\n")
    else:
        flagged = conflicts.loc[
            conflicts["conflict_with_secondary"]
            | conflicts["conflict_with_tertiary"]
        ]
        n_total = len(conflicts)
        n_flagged = len(flagged)
        n_secondary = int(flagged["conflict_with_secondary"].sum())
        n_tertiary = int(flagged["conflict_with_tertiary"].sum())
        parts.append(
            f"- Rows in ranking groups: **{n_total}**\n"
            f"- Rows flagged: **{n_flagged}** "
            f"(conflict_with_secondary={n_secondary}, "
            f"conflict_with_tertiary={n_tertiary})\n"
        )
        if flagged.empty:
            parts.append("_No rows exhibit rank disagreements larger than the tolerance._\n")
        else:
            keep = [
                "source_experiment",
                "algorithm",
                "n_clusters",
                "experiment_id",
                "silhouette",
                "davies_bouldin",
                "calinski_harabasz",
                "rank_silhouette",
                "rank_davies_bouldin",
                "rank_calinski_harabasz",
                "conflict_with_secondary",
                "conflict_with_tertiary",
            ]
            # Optional boundary columns (only present if the auxiliary
            # columns exist on the conflicts frame).
            for c in ("_exp05_block", "_exp03_stage", "_exp04_scenario"):
                if c in flagged.columns and c not in keep:
                    keep.append(c)
            parts.append(_df_to_md(flagged.loc[:, keep], max_rows=40, digits=4))
    parts.append("")
    return "\n".join(parts)


def _section_dbscan(df: pd.DataFrame) -> str:
    parts: list[str] = []
    parts.append("## 9. DBSCAN noise characteristics")
    parts.append("")
    parts.append(
        "DBSCAN's internal metrics are computed on non-noise points; "
        "noise customers are summarised below per source experiment. "
        "DBSCAN's ``n_clusters`` is the **realized** cluster count, "
        "not a requested K (see section 3)."
    )
    parts.append("")
    table = dbscan_noise_summary(df)
    if table.empty:
        parts.append("_No DBSCAN rows available._\n")
    else:
        parts.append(_df_to_md(table, max_rows=20, digits=4))
    parts.append("")
    return "\n".join(parts)


def _section_artifacts(
    table_paths: list[str],
    figure_paths: list[str],
    ranking_paths: list[str] | None = None,
) -> str:
    parts: list[str] = []
    parts.append("## 10. Generated artefacts")
    parts.append("")
    parts.append("### Tables (CSV)")
    parts.append("")
    if table_paths:
        for p in table_paths:
            parts.append(f"- `{p}`")
    else:
        parts.append("_(none)_")
    parts.append("")
    parts.append("### Per-metric ranking tables (CSV)")
    parts.append("")
    if ranking_paths:
        for p in ranking_paths:
            parts.append(f"- `{p}`")
    else:
        parts.append("_(none — `write_rankings=False` or empty repository)_")
    parts.append("")
    parts.append("### Figures (PNG)")
    parts.append("")
    if figure_paths:
        for p in figure_paths:
            parts.append(f"- `{p}`")
    else:
        parts.append("_(none)_")
    parts.append("")
    return "\n".join(parts)


def _section_interpretation_boundary() -> str:
    return (
        "## 11. Interpretation boundary\n"
        "\n"
        "EVA-02 is a **descriptive** evaluation. It MUST NOT be used to "
        "claim:\n"
        "\n"
        "- A 'best algorithm' across EPIC-06.\n"
        "- A 'best K' value.\n"
        "- A 'recommended' preprocessing scenario.\n"
        "- A composite or weighted ranking.\n"
        "- An overall ranking across experiments.\n"
        "- A promotion of `WORKING_SELECTED` configurations to "
        "`RESEARCH_APPROVED`.\n"
        "\n"
        "Cross-algorithm conclusions require:\n"
        "\n"
        "1. Stability analysis (EPIC-08 / ARI / AMI).\n"
        "2. Statistical hypothesis testing (paired t-test / Wilcoxon, "
        "with multiple-comparison correction).\n"
        "3. Bootstrap confidence intervals.\n"
        "4. External validation against ground truth — not available "
        "in this unsupervised setting.\n"
        "\n"
        "Until those analyses exist, the table values above are "
        "evidence, not recommendations.\n"
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def build_report(
    df: pd.DataFrame,
    *,
    table_paths: list[str] | None = None,
    figure_paths: list[str] | None = None,
    ranking_paths: list[str] | None = None,
    generated_at: str | None = None,
) -> str:
    """Build the EVA-02 Markdown narrative report."""
    if generated_at is None:
        generated_at = datetime.now(UTC).isoformat()
    overview = dataset_quality_overview(df)

    sections: list[str] = []
    sections.append("# EVA-02 — Cluster Quality Evaluation Report")
    sections.append("")
    sections.append(f"_Generated: {generated_at}_")
    sections.append("")
    sections.append(
        "_This report consumes the EVA-01 standardised repository "
        "(`reports/evaluation/eva01/eva01_experiment_repository.parquet`) "
        "and produces descriptive comparisons only. No algorithm is "
        "claimed to be 'best'._"
    )
    sections.append("")
    sections.append(_section_provenance(overview))
    sections.append(_section_metric_distributions(df))
    sections.append(_section_ranking_boundaries())
    sections.append(_section_per_algorithm(df))
    sections.append(_section_per_k(df))
    sections.append(_section_per_preprocessing(df))
    sections.append(_section_per_hyperparameter(df))
    sections.append(_section_cross_metric(df))
    sections.append(_section_dbscan(df))
    sections.append(
        _section_artifacts(
            table_paths=table_paths or [],
            figure_paths=figure_paths or [],
            ranking_paths=ranking_paths,
        )
    )
    sections.append(_section_interpretation_boundary())
    return "\n".join(sections)


def report_to_markdown(report: str) -> str:
    """Pass-through helper to keep imports uniform with other modules."""
    return report
