"""Summary table builders for the EVA-01 repository.

Three summary tables are produced:

1. **Per-experiment summary** — one row per source experiment with
   counts of total / successful / failed runs and metric min/max/mean.
2. **Per-algorithm summary** — one row per (source_experiment,
   algorithm) with metric statistics across configurations.
3. **Per-K summary** — one row per (source_experiment, algorithm,
   n_clusters) with metric statistics. Used by EVA-02/03 to see the
   K-sweep evidence without re-parsing the raw CSVs.

All summary tables are descriptive only. They do NOT compute any
quality judgement, ranking, or "best" classification.
"""

from __future__ import annotations

import math
from datetime import UTC
from typing import Any

import pandas as pd

from customer_segmentation.evaluation.experiment_results.schema import MISSING
from customer_segmentation.evaluation.experiment_results.validation import (
    ValidationReport,
)

__all__ = [
    "build_experiment_summary",
    "build_algorithm_summary",
    "build_k_summary",
    "summary_tables_to_markdown",
    "summarise_metrics",
]


def _safe_mean(values: list[float]) -> float:
    """Return arithmetic mean; ``None`` if input is empty."""
    if not values:
        return math.nan
    return sum(values) / len(values)


def _safe_min(values: list[float]) -> float:
    """Return minimum; ``NaN`` if input is empty."""
    if not values:
        return math.nan
    return min(values)


def _safe_max(values: list[float]) -> float:
    """Return maximum; ``NaN`` if input is empty."""
    if not values:
        return math.nan
    return max(values)


def summarise_metrics(values: list[Any]) -> dict[str, float]:
    """Compute min/max/mean/n for a list of metric values.

    NaN / None entries are dropped. Returns ``n_valid`` so callers
    can tell apart "all values are NaN" from "no values recorded".
    """
    cleaned: list[float] = []
    n_total = len(values)
    for v in values:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            continue
        try:
            cleaned.append(float(v))
        except (TypeError, ValueError):
            continue
    return {
        "n": len(cleaned),
        "n_total": n_total,
        "mean": _safe_mean(cleaned) if cleaned else math.nan,
        "min": _safe_min(cleaned) if cleaned else math.nan,
        "max": _safe_max(cleaned) if cleaned else math.nan,
    }


def _to_float_or_nan(value: Any) -> float:
    """Convert a metric cell to float; ``NaN`` for missing / sentinel."""
    if value is None or value == MISSING:
        return math.nan
    try:
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return math.nan
        return f
    except (TypeError, ValueError):
        return math.nan


def _to_int_or_nan(value: Any) -> int:
    """Convert a count cell to int; ``-1`` for missing / sentinel."""
    if value is None or value == MISSING:
        return -1
    try:
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return -1
        return int(f)
    except (TypeError, ValueError):
        return -1


def build_experiment_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Per-source-experiment summary table.

    Columns:
    - ``source_experiment``
    - ``n_rows`` (total)
    - ``n_successful`` (run_status == SUCCESS)
    - ``n_failed`` (run_status == FAILED)
    - silhouette / DBI / CH / WCSS min / max / mean (across all rows)
    - ``n_unique_algorithms``
    """
    if df.empty:
        return pd.DataFrame(
            columns=[
                "source_experiment",
                "n_rows",
                "n_successful",
                "n_failed",
                "n_unique_algorithms",
                "silhouette_min",
                "silhouette_max",
                "silhouette_mean",
                "davies_bouldin_min",
                "davies_bouldin_max",
                "davies_bouldin_mean",
                "calinski_harabasz_min",
                "calinski_harabasz_max",
                "calinski_harabasz_mean",
                "wcss_min",
                "wcss_max",
                "wcss_mean",
                "execution_time_seconds_min",
                "execution_time_seconds_max",
                "execution_time_seconds_mean",
            ]
        )

    rows: list[dict[str, Any]] = []
    for source_exp, group in df.groupby("source_experiment", dropna=False):
        n_rows = len(group)
        n_successful = int((group["run_status"] == "SUCCESS").sum())
        n_failed = int((group["run_status"] == "FAILED").sum())
        n_unique_algorithms = int(group["algorithm"].nunique())
        sil = summarise_metrics([_to_float_or_nan(v) for v in group["silhouette"]])
        dbi = summarise_metrics([_to_float_or_nan(v) for v in group["davies_bouldin"]])
        ch = summarise_metrics([_to_float_or_nan(v) for v in group["calinski_harabasz"]])
        wcss = summarise_metrics([_to_float_or_nan(v) for v in group["wcss"]])
        runtime = summarise_metrics([_to_float_or_nan(v) for v in group["execution_time_seconds"]])
        rows.append(
            {
                "source_experiment": source_exp,
                "n_rows": n_rows,
                "n_successful": n_successful,
                "n_failed": n_failed,
                "n_unique_algorithms": n_unique_algorithms,
                "silhouette_min": sil["min"],
                "silhouette_max": sil["max"],
                "silhouette_mean": sil["mean"],
                "davies_bouldin_min": dbi["min"],
                "davies_bouldin_max": dbi["max"],
                "davies_bouldin_mean": dbi["mean"],
                "calinski_harabasz_min": ch["min"],
                "calinski_harabasz_max": ch["max"],
                "calinski_harabasz_mean": ch["mean"],
                "wcss_min": wcss["min"],
                "wcss_max": wcss["max"],
                "wcss_mean": wcss["mean"],
                "execution_time_seconds_min": runtime["min"],
                "execution_time_seconds_max": runtime["max"],
                "execution_time_seconds_mean": runtime["mean"],
            }
        )
    out = pd.DataFrame(rows)
    return out.sort_values("source_experiment").reset_index(drop=True)


def build_algorithm_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Per-(source_experiment, algorithm) summary table."""
    if df.empty:
        return pd.DataFrame(
            columns=[
                "source_experiment",
                "algorithm",
                "n_rows",
                "n_unique_n_clusters",
                "silhouette_min",
                "silhouette_max",
                "silhouette_mean",
                "davies_bouldin_min",
                "davies_bouldin_max",
                "davies_bouldin_mean",
                "calinski_harabasz_min",
                "calinski_harabasz_max",
                "calinski_harabasz_mean",
                "wcss_min",
                "wcss_max",
                "wcss_mean",
                "execution_time_seconds_min",
                "execution_time_seconds_max",
                "execution_time_seconds_mean",
            ]
        )

    rows: list[dict[str, Any]] = []
    grouped = df.groupby(["source_experiment", "algorithm"], dropna=False)
    for (source_exp, algorithm), group in grouped:
        n_rows = len(group)
        unique_k = group["n_clusters"].apply(_to_int_or_nan)
        unique_k = sorted({k for k in unique_k if k >= 0})
        sil = summarise_metrics([_to_float_or_nan(v) for v in group["silhouette"]])
        dbi = summarise_metrics([_to_float_or_nan(v) for v in group["davies_bouldin"]])
        ch = summarise_metrics([_to_float_or_nan(v) for v in group["calinski_harabasz"]])
        wcss = summarise_metrics([_to_float_or_nan(v) for v in group["wcss"]])
        runtime = summarise_metrics([_to_float_or_nan(v) for v in group["execution_time_seconds"]])
        rows.append(
            {
                "source_experiment": source_exp,
                "algorithm": algorithm,
                "n_rows": n_rows,
                "n_unique_n_clusters": len(unique_k),
                "silhouette_min": sil["min"],
                "silhouette_max": sil["max"],
                "silhouette_mean": sil["mean"],
                "davies_bouldin_min": dbi["min"],
                "davies_bouldin_max": dbi["max"],
                "davies_bouldin_mean": dbi["mean"],
                "calinski_harabasz_min": ch["min"],
                "calinski_harabasz_max": ch["max"],
                "calinski_harabasz_mean": ch["mean"],
                "wcss_min": wcss["min"],
                "wcss_max": wcss["max"],
                "wcss_mean": wcss["mean"],
                "execution_time_seconds_min": runtime["min"],
                "execution_time_seconds_max": runtime["max"],
                "execution_time_seconds_mean": runtime["mean"],
            }
        )
    out = pd.DataFrame(rows)
    return out.sort_values(["source_experiment", "algorithm"]).reset_index(drop=True)


def build_k_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Per-(source_experiment, algorithm, n_clusters) summary table."""
    if df.empty:
        return pd.DataFrame(
            columns=[
                "source_experiment",
                "algorithm",
                "n_clusters",
                "n_rows",
                "silhouette_min",
                "silhouette_max",
                "silhouette_mean",
                "davies_bouldin_min",
                "davies_bouldin_max",
                "davies_bouldin_mean",
                "calinski_harabasz_min",
                "calinski_harabasz_max",
                "calinski_harabasz_mean",
                "wcss_min",
                "wcss_max",
                "wcss_mean",
                "execution_time_seconds_min",
                "execution_time_seconds_max",
                "execution_time_seconds_mean",
            ]
        )

    rows: list[dict[str, Any]] = []
    grouped = df.groupby(["source_experiment", "algorithm", "n_clusters"], dropna=False)
    for (source_exp, algorithm, k), group in grouped:
        k_int = _to_int_or_nan(k)
        if k_int < 0:
            continue
        n_rows = len(group)
        sil = summarise_metrics([_to_float_or_nan(v) for v in group["silhouette"]])
        dbi = summarise_metrics([_to_float_or_nan(v) for v in group["davies_bouldin"]])
        ch = summarise_metrics([_to_float_or_nan(v) for v in group["calinski_harabasz"]])
        wcss = summarise_metrics([_to_float_or_nan(v) for v in group["wcss"]])
        runtime = summarise_metrics([_to_float_or_nan(v) for v in group["execution_time_seconds"]])
        rows.append(
            {
                "source_experiment": source_exp,
                "algorithm": algorithm,
                "n_clusters": k_int,
                "n_rows": n_rows,
                "silhouette_min": sil["min"],
                "silhouette_max": sil["max"],
                "silhouette_mean": sil["mean"],
                "davies_bouldin_min": dbi["min"],
                "davies_bouldin_max": dbi["max"],
                "davies_bouldin_mean": dbi["mean"],
                "calinski_harabasz_min": ch["min"],
                "calinski_harabasz_max": ch["max"],
                "calinski_harabasz_mean": ch["mean"],
                "wcss_min": wcss["min"],
                "wcss_max": wcss["max"],
                "wcss_mean": wcss["mean"],
                "execution_time_seconds_min": runtime["min"],
                "execution_time_seconds_max": runtime["max"],
                "execution_time_seconds_mean": runtime["mean"],
            }
        )
    out = pd.DataFrame(rows)
    return out.sort_values(["source_experiment", "algorithm", "n_clusters"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def _format_float(v: Any, digits: int = 4) -> str:
    """Format a float for human-readable Markdown; ``-`` for NaN / missing."""
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return "-"
    return f"{v:.{digits}f}"


def _df_to_md_table(df: pd.DataFrame, *, float_digits: int = 4) -> str:
    """Render a small DataFrame as a Markdown table.

    The function is intentionally simple — it does NOT try to align
    long tables. If ``df`` has more than 40 rows, only the first 40
    are rendered.
    """
    if df.empty:
        return "_(empty)_\n"
    truncated = df.head(40)
    columns = [str(c) for c in truncated.columns]
    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join("---" for _ in columns) + " |"
    lines = [header, sep]
    for _, row in truncated.iterrows():
        cells: list[str] = []
        for c in columns:
            v = row[c]
            if isinstance(v, float):
                cells.append(_format_float(v, digits=float_digits))
            elif isinstance(v, int):
                cells.append(str(v))
            else:
                s = str(v)
                # Escape pipes in cell values
                s = s.replace("|", "\\|")
                # Truncate very long values for readability
                if len(s) > 80:
                    s = s[:77] + "..."
                cells.append(s)
        lines.append("| " + " | ".join(cells) + " |")
    if len(df) > 40:
        lines.append("")
        lines.append(f"_... {len(df) - 40} more rows omitted from this preview._")
    return "\n".join(lines) + "\n"


def summary_tables_to_markdown(
    *,
    dataset: pd.DataFrame,
    tables: dict[str, pd.DataFrame],
    validation_report: ValidationReport,
    generated_at: str | None = None,
) -> str:
    """Build the Markdown summary report for the EVA-01 repository.

    The report contains:

    1. Provenance header (row counts, validation summary).
    2. Per-experiment summary table.
    3. Per-algorithm summary table.
    4. Per-(experiment, algorithm, K) summary table.
    5. Validation report digest (row statuses, anomalies, field coverage).
    """
    from datetime import datetime

    if generated_at is None:
        generated_at = datetime.now(UTC).isoformat()

    lines: list[str] = []
    lines.append("# EVA-01 — Experiment Result Repository Summary")
    lines.append("")
    lines.append(f"_Generated: {generated_at}_")
    lines.append("")

    # Provenance header
    lines.append("## 1. Provenance")
    lines.append("")
    n_by_exp = dataset["source_experiment"].value_counts().to_dict()
    lines.append(f"- Total rows: **{len(dataset)}**")
    lines.append("- Rows per source experiment:")
    for exp in sorted(n_by_exp):
        lines.append(f"  - {exp}: {n_by_exp[exp]}")
    if "feature_set_sha256" in dataset.columns:
        shas = sorted(set(dataset["feature_set_sha256"].dropna().astype(str)))
        shas = [s for s in shas if s and s != MISSING]
        if shas:
            lines.append(f"- Distinct feature-set SHA-256 values: {len(shas)}")
            for s in shas:
                lines.append(f"  - `{s}`")
    lines.append("")
    lines.append("**Note:** EVA-01 does NOT compute any ranking, composite score,")
    lines.append("or 'best/winner/optimal/recommended/final' label. The repository")
    lines.append("is descriptive only.")
    lines.append("")

    # Validation digest
    lines.append("## 2. Validation digest")
    lines.append("")
    lines.append(f"- Total rows: **{validation_report.n_total}**")
    lines.append(f"- OK rows: **{validation_report.n_ok}**")
    lines.append(f"- Rows with missing required fields: **{validation_report.n_missing}**")
    lines.append(f"- Rows with invalid metric values: **{validation_report.n_invalid}**")
    lines.append("")
    lines.append(f"- DUPLICATE_EXACT groups: **{len(validation_report.duplicate_exact)}**")
    lines.append(
        f"- DUPLICATE_BY_INTENT groups (same config, different outputs): "
        f"**{len(validation_report.duplicate_by_intent)}**"
    )
    lines.append(
        f"- INCONSISTENT_CONDITIONS groups (same config, different conditions): "
        f"**{len(validation_report.inconsistent_conditions)}**"
    )
    lines.append("")
    lines.append("### 2.1 Field coverage")
    lines.append("")
    coverage_df = pd.DataFrame.from_records(
        [
            {
                "field": field,
                "present": stats["present"],
                "missing_with_reason": stats["missing_with_reason"],
                "missing_no_reason": stats["missing_no_reason"],
            }
            for field, stats in sorted(validation_report.field_coverage.items())
        ]
    )
    # Highlight only fields with non-trivial missing-with-reason coverage.
    nontrivial = coverage_df[
        (coverage_df["missing_with_reason"] > 0) | (coverage_df["missing_no_reason"] > 0)
    ]
    lines.append(_df_to_md_table(nontrivial, float_digits=0))
    if nontrivial.empty:
        lines.append("_(All fields fully populated.)_\n")

    # Anomaly groups (preview)
    lines.append("### 2.2 Duplicate & inconsistent-conditions groups (preview)")
    lines.append("")
    if validation_report.duplicate_exact:
        lines.append("**DUPLICATE_EXACT** groups:")
        for group in validation_report.duplicate_exact[:10]:
            lines.append(
                f"- identity_key=`{group['identity_key'][:12]}...` " f"({group['n_rows']} rows)"
            )
        if len(validation_report.duplicate_exact) > 10:
            lines.append(f"- ... and {len(validation_report.duplicate_exact) - 10} more")
    else:
        lines.append("- No DUPLICATE_EXACT groups detected.")
    lines.append("")
    if validation_report.duplicate_by_intent:
        lines.append("**DUPLICATE_BY_INTENT** groups (same config, different outputs):")
        for group in validation_report.duplicate_by_intent[:10]:
            differing = ", ".join(group["differing_fields"][:5])
            lines.append(
                f"- intent_key=`{group['intent_key'][:12]}...` "
                f"({group['n_rows']} rows; differing: {differing})"
            )
        if len(validation_report.duplicate_by_intent) > 10:
            lines.append(f"- ... and {len(validation_report.duplicate_by_intent) - 10} more")
    else:
        lines.append("- No DUPLICATE_BY_INTENT groups detected.")
    lines.append("")
    if validation_report.inconsistent_conditions:
        lines.append("**INCONSISTENT_CONDITIONS** groups:")
        for group in validation_report.inconsistent_conditions[:10]:
            differ = ", ".join(group["differing_condition_fields"][:5])
            lines.append(
                f"- inconsistent_key=`{group['inconsistent_key'][:12]}...` "
                f"({group['n_rows']} rows; differing: {differ})"
            )
        if len(validation_report.inconsistent_conditions) > 10:
            lines.append(f"- ... and {len(validation_report.inconsistent_conditions) - 10} more")
    else:
        lines.append("- No INCONSISTENT_CONDITIONS groups detected.")
    lines.append("")

    # Summary tables
    lines.append("## 3. Per-experiment summary")
    lines.append("")
    lines.append(_df_to_md_table(tables["experiment_summary"], float_digits=4))
    lines.append("")

    lines.append("## 4. Per-algorithm summary")
    lines.append("")
    lines.append(_df_to_md_table(tables["algorithm_summary"], float_digits=4))
    lines.append("")

    lines.append("## 5. Per-(experiment, algorithm, K) summary")
    lines.append("")
    lines.append(_df_to_md_table(tables["k_summary"], float_digits=4))
    lines.append("")

    # Provenance rule
    lines.append("## 6. Provenance rule")
    lines.append("")
    lines.append("Every row in the standardized dataset is traceable to its source:")
    lines.append("")
    lines.append("- `source_experiment` — which EPIC-07 experiment produced it")
    lines.append("- `source_run_id` — the run_id / experiment_id from that artifact")
    lines.append("- `source_artifact` — the relative path of the source CSV/JSON")
    lines.append("- `feature_set_sha256`, `config_sha256`, `input_sha256` — SHA chain")
    lines.append("- `library_versions`, `platform` — execution environment")
    lines.append("")
    lines.append("No metric values are invented. Where the source did not record a")
    lines.append("value, the row uses the literal sentinel `MISSING` paired with a")
    lines.append("`missing_reason` annotation describing why.")
    lines.append("")

    return "\n".join(lines)
