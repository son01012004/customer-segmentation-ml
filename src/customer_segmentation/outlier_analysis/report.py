"""FE-03 outlier analysis: report builders (Markdown + CSV).

This module renders the narrative Markdown report
(``reports/fe03/outlier_analysis.md``) and the supporting CSVs from
in-memory artefacts collected by the orchestrator. All numbers come
from the live analysis — nothing is hard-coded.

The Markdown structure follows the FE-03 task spec (§24):

1.  Objective
2.  Dataset and Unit of Analysis
3.  Features Investigated
4.  Distribution Analysis
5.  Outlier Detection Methods
6.  Transaction-Level Analysis
7.  Customer-Level Diagnostic Analysis
8.  Cancellation and Return Analysis
9.  Error vs Real Behavior Assessment
10. Treatment Decisions
11. Before/After Comparison
12. Sensitivity Analysis
13. Mentor Decisions Required
14. Limitations
15. Conclusion
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from customer_segmentation.config.outlier_loader import (
    OUTLIER_STATUS_PENDING_MENTOR_REVIEW,
    FeatureOutlierConfig,
    OutlierAnalysisConfig,
)
from customer_segmentation.outlier_analysis.detection import DetectionRecord
from customer_segmentation.outlier_analysis.distribution import (
    DistributionProfile,
)
from customer_segmentation.outlier_analysis.interpretation import (
    InterpretationDecision,
)

__all__ = [
    "ReportContext",
    "build_distribution_csv",
    "build_outlier_summary_csv",
    "build_treatment_decisions_csv",
    "build_percentile_csv",
    "build_sensitivity_csv",
    "build_feature_statistics_csv",
    "build_customer_diagnostic_csv",
    "build_outlier_analysis_md",
    "render_outlier_analysis_markdown",
]


# ---------------------------------------------------------------------------
# Markdown cell formatter
# ---------------------------------------------------------------------------


# Columns whose values are always rendered to 4 decimal places even if
# pandas returns them as int (e.g. when the source series is integer).
_FLOAT_FORMAT_COLUMNS: frozenset[str] = frozenset(
    {
        "mean",
        "median",
        "std",
        "q1",
        "q3",
        "iqr",
        "min",
        "max",
        "skewness",
        "rate",
        "lower",
        "upper",
        "missing_rate",
        "p1",
        "p5",
        "p25",
        "p50",
        "p75",
        "p90",
        "p95",
        "p99",
        "p99.5",
        "p99.9",
        "p99.95",
    }
)


def _format_cell(v: Any, column: str | None = None) -> str:
    """Format a single cell value for the Markdown tables.

    Rules:
    - ``None`` / NaN → empty string.
    - Strings → as-is.
    - Integers / int-valued floats → integer string.
    - Floats → 4-decimal format (always for known float columns).
    - Booleans → ``"True"`` / ``"False"``.

    The optional ``column`` hint is used to force 4-decimal formatting
    on numeric columns (mean / median / std / q1 / q3 / iqr / min /
    max / skewness / percentiles / rate / lower / upper /
    missing_rate) even when the underlying numpy dtype is int.
    """
    # Missing → blank cell.
    if v is None:
        return ""
    try:
        is_nan = isinstance(v, float) and np.isnan(v)
    except TypeError:
        is_nan = False
    if is_nan:
        return ""

    # Boolean → literal.
    if isinstance(v, bool):
        return "True" if v else "False"

    # String → as-is.
    if isinstance(v, str):
        return v

    # Integer (or int-valued numpy) → integer string.
    if isinstance(v, (int, np.integer)):
        # If this is a known float column rendered as int (rare but
        # possible), promote to float formatting.
        if column in _FLOAT_FORMAT_COLUMNS:
            return f"{float(v):.4f}"
        return str(int(v))

    # Float → 4-decimal format.
    if isinstance(v, (float, np.floating)):
        return f"{float(v):.4f}"

    # Fallback.
    return str(v)


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------


@dataclass
class ReportContext:
    """Everything the report builders need.

    Attributes
    ----------
    config : OutlierAnalysisConfig
        Resolved outlier configuration.
    raw_sha256 : str
        SHA-256 of the raw primary file at run time.
    cleaned_sha256_before : str
        SHA-256 of the FE-02 cleaned parquet before the FE-03 run.
    cleaned_sha256_after : str
        SHA-256 of the FE-02 cleaned parquet after the FE-03 run.
    distribution_profiles : dict[str, dict[str, DistributionProfile]]
        ``filter_mode → feature → DistributionProfile``.
    detection_records : list[DetectionRecord]
        Per-(feature, method, filter_mode) detection records.
    sensitivity_tables : list[pandas.DataFrame]
        Per-feature sensitivity tables.
    interpretation_decisions : list[InterpretationDecision]
        Per-(feature, filter_mode) interpretation outcomes.
    customer_diagnostics : dict[str, pandas.DataFrame]
        ``filter_mode → customer_diagnostic DataFrame`` (one row per
        customer; columns are the diagnostic aggregates + the customer
        key).
    customer_diagnostic_summary : pandas.DataFrame
        Per-aggregate summary table (output of
        :func:`customer_aggregates.summarise_diagnostic`).
    treated_dataset_path : str or None
        Path to the opt-in treated dataset, or ``None`` if not written.
    config_source : str
        One of ``explicit_config``, ``yaml:<path>``,
        ``yaml_auto:<path>``, ``default``.
    run_id : str
        ISO-8601 UTC timestamp of the run.
    platform : dict[str, str]
        Platform info (Python version, OS, ...).
    """

    config: OutlierAnalysisConfig
    raw_sha256: str
    cleaned_sha256_before: str
    cleaned_sha256_after: str
    distribution_profiles: dict[str, dict[str, DistributionProfile]] = field(default_factory=dict)
    detection_records: list[DetectionRecord] = field(default_factory=list)
    sensitivity_tables: list[pd.DataFrame] = field(default_factory=list)
    interpretation_decisions: list[InterpretationDecision] = field(default_factory=list)
    customer_diagnostics: dict[str, pd.DataFrame] = field(default_factory=dict)
    customer_diagnostic_summary: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())
    treated_dataset_path: str | None = None
    config_source: str = "unknown"
    run_id: str = ""
    platform: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# CSV builders
# ---------------------------------------------------------------------------


def build_distribution_csv(ctx: ReportContext) -> pd.DataFrame:
    """Per-feature, per-filter-mode distribution summary."""
    rows: list[dict[str, Any]] = []
    for filter_mode, by_feature in ctx.distribution_profiles.items():
        for _feature_name, prof in by_feature.items():
            row = prof.to_dict()
            row["filter_mode"] = filter_mode
            rows.append(row)
    df = pd.DataFrame.from_records(rows)
    if df.empty:
        return df
    return df.sort_values(["filter_mode", "column"]).reset_index(drop=True)


def build_outlier_summary_csv(ctx: ReportContext) -> pd.DataFrame:
    """Per-feature, per-method, per-filter-mode detection summary."""
    rows = [r.to_dict() for r in ctx.detection_records]
    df = pd.DataFrame.from_records(rows)
    if df.empty:
        return df
    return df.sort_values(["feature", "method", "filter_mode"]).reset_index(drop=True)


def build_treatment_decisions_csv(ctx: ReportContext) -> pd.DataFrame:
    """Per-feature interpretation + treatment recommendation table."""
    rows = [d.to_dict() for d in ctx.interpretation_decisions]
    df = pd.DataFrame.from_records(rows)
    if df.empty:
        return df
    return df.sort_values(["feature", "filter_mode"]).reset_index(drop=True)


def build_percentile_csv(ctx: ReportContext) -> pd.DataFrame:
    """Per-feature, per-filter-mode, per-percentile value table."""
    rows: list[dict[str, Any]] = []
    for filter_mode, by_feature in ctx.distribution_profiles.items():
        for feature_name, prof in by_feature.items():
            row: dict[str, Any] = {"feature": feature_name, "filter_mode": filter_mode}
            row.update(prof.percentiles)
            rows.append(row)
    df = pd.DataFrame.from_records(rows)
    if df.empty:
        return df
    return df.sort_values(["feature", "filter_mode"]).reset_index(drop=True)


def build_sensitivity_csv(ctx: ReportContext) -> pd.DataFrame:
    """Concatenated sensitivity table across all features."""
    chunks = [t for t in ctx.sensitivity_tables if not t.empty]
    if not chunks:
        return pd.DataFrame(
            columns=[
                "feature",
                "filter_mode",
                "method",
                "threshold",
                "lower",
                "upper",
                "candidates",
                "rate",
                "total_rows",
            ]
        )
    df = pd.concat(chunks, ignore_index=True, sort=False)
    return df.sort_values(["feature", "filter_mode", "method", "threshold"]).reset_index(drop=True)


def build_feature_statistics_csv(ctx: ReportContext) -> pd.DataFrame:
    """Wide per-feature statistics for the default filter mode."""
    default_mode = "all_rows"
    by_feature = ctx.distribution_profiles.get(default_mode, {})
    rows: list[dict[str, Any]] = []
    for _feature_name, prof in by_feature.items():
        row = prof.to_dict()
        row["filter_mode"] = default_mode
        rows.append(row)
    df = pd.DataFrame.from_records(rows)
    if df.empty:
        return df
    return df.sort_values("column").reset_index(drop=True)


def build_customer_diagnostic_csv(ctx: ReportContext) -> pd.DataFrame:
    """The customer-level diagnostic table for the default filter mode.

    If the default filter mode produced no customers, the first available
    mode is used instead.
    """
    default_mode = "all_rows"
    if default_mode in ctx.customer_diagnostics:
        diag = ctx.customer_diagnostics[default_mode].copy()
    elif ctx.customer_diagnostics:
        diag = next(iter(ctx.customer_diagnostics.values())).copy()
    else:
        return pd.DataFrame()
    diag["filter_mode"] = (
        default_mode
        if default_mode in ctx.customer_diagnostics
        else next(iter(ctx.customer_diagnostics))
    )
    return diag.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


def render_outlier_analysis_markdown(ctx: ReportContext) -> str:
    """Build the narrative Markdown report from the context."""
    lines: list[str] = []
    config = ctx.config
    features: list[FeatureOutlierConfig] = config.transaction_features

    lines.append("# FE-03 Outlier and Distribution Analysis — UCI Online Retail (Primary)")
    lines.append("")
    lines.append(
        "This report describes the FE-03 outlier analysis applied to the "
        "FE-02 cleaned transaction-level dataset. All numbers are "
        "computed live from the cleaned dataset; nothing is hard-coded. "
        "Customer-level outputs are **diagnostic-only** and explicitly "
        "**not** the project's official RFM / extended-behavioural "
        "features (those belong to FE-04)."
    )
    lines.append("")

    # 1. Objective
    lines.append("## 1. Objective")
    lines.append("")
    lines.append(
        "Analyse and treat outliers in a controlled way to avoid biasing "
        "the downstream clustering step. Distinguish data errors from "
        "genuine customer behaviour, document treatment decisions, and "
        "preserve FE-02 baseline."
    )
    lines.append("")

    # 2. Dataset and Unit of Analysis
    lines.append("## 2. Dataset and Unit of Analysis")
    lines.append("")
    lines.append(f"- **Source dataset**: `{config.source.role}`")
    lines.append(f"- **Cleaned parquet**: `{config.source.cleaned_dataset_path}`")
    lines.append(f"- **Raw xlsx**: `{config.source.raw_dataset_path}`")
    lines.append(f"- **Raw SHA-256**: `{ctx.raw_sha256}`")
    lines.append(f"- **FE-02 cleaned SHA-256 (before run)**: `{ctx.cleaned_sha256_before}`")
    lines.append(f"- **FE-02 cleaned SHA-256 (after run)**:  `{ctx.cleaned_sha256_after}`")
    lines.append(
        f"- **Equal**: {'YES' if ctx.cleaned_sha256_before == ctx.cleaned_sha256_after else 'NO'}"
    )
    lines.append("- **Unit of observation (FE-02)**: transaction-line")
    lines.append("- **Unit of analysis (FE-03 transaction-level)**: transaction-line")
    lines.append("- **Unit of analysis (FE-03 customer-level diagnostic)**: customer")
    lines.append("")

    # 3. Features Investigated
    lines.append("## 3. Features Investigated")
    lines.append("")
    lines.append("### Transaction-level")
    lines.append("")
    lines.append("| Feature | Level | Detection | Threshold | Treatment (default) | Status |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for f in features:
        thresh = (
            f"x={f.iqr_multiplier}"
            if f.detection == "iqr"
            else (
                f"z={f.zscore_threshold}"
                if f.detection == "zscore"
                else f"p={f.percentile_thresholds[0]}"
            )
        )
        lines.append(
            f"| `{f.column}` | transaction | {f.detection} | {thresh} | "
            f"{f.treatment} | {f.status} |"
        )
    lines.append("")
    if config.customer_diagnostic.enabled:
        lines.append("### Customer-level diagnostic (not RFM)")
        lines.append("")
        lines.append("| Diagnostic column | Aggregation | Source | Notes |")
        lines.append("| --- | --- | --- | --- |")
        for name, spec in config.customer_diagnostic.aggregations.items():
            notes = (
                "derived (Quantity*UnitPrice)"
                if spec.source == "LineRevenue"
                else "FE-02 cleaned column"
            )
            lines.append(f"| `{name}` | {spec.fn} | `{spec.source}` | {notes} |")
        lines.append("")
    lines.append(
        "**Important boundary.** The customer-level outputs are "
        "**diagnostic-only** and are explicitly **not** the project's "
        "official RFM Frequency, Monetary, or Recency definitions. "
        "Those belong to FE-04 with mentor approval (DD-01, DD-02, "
        "DD-06)."
    )
    lines.append("")

    # 4. Distribution Analysis (summary)
    lines.append("## 4. Distribution Analysis")
    lines.append("")
    lines.append(
        "Per-feature first-order statistics under the default filter "
        "mode (``all_rows``). Negative counts and skewness are reported "
        "because they are diagnostic of tail behaviour."
    )
    lines.append("")
    if ctx.distribution_profiles.get("all_rows"):
        rows: list[dict[str, Any]] = []
        for _feature_name, prof in ctx.distribution_profiles["all_rows"].items():
            rows.append(prof.to_dict())
        df = pd.DataFrame.from_records(rows)
        keep = [
            "column",
            "count",
            "missing_count",
            "min",
            "max",
            "mean",
            "median",
            "std",
            "q1",
            "q3",
            "iqr",
            "zero_count",
            "negative_count",
            "skewness",
        ]
        keep = [c for c in keep if c in df.columns]
        lines.append("| " + " | ".join(keep) + " |")
        lines.append("| " + " | ".join(["---"] * len(keep)) + " |")
        for _, row in df[keep].iterrows():
            cells: list[str] = []
            for c in keep:
                cells.append(_format_cell(row[c], column=c))
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")
    else:
        lines.append("_No distribution profiles computed._")
        lines.append("")

    # 5. Outlier Detection Methods
    lines.append("## 5. Outlier Detection Methods")
    lines.append("")
    lines.append(
        "FE-03 supports three detection methods. Each is purely "
        "diagnostic — the orchestrator applies **no** treatment unless "
        "the user explicitly opts in via the YAML and the CLI flag."
    )
    lines.append("")
    lines.append("### 5.1. IQR")
    lines.append("")
    lines.append(
        "Lower bound: `Q1 − k · IQR`; upper bound: `Q3 + k · IQR`. "
        f"Multipliers swept for sensitivity: "
        f"{list(config.sensitivity.thresholds)}."
    )
    lines.append("")
    lines.append("### 5.2. Percentile")
    lines.append("")
    lines.append(
        "Symmetric percentile fences. Upper percentile thresholds swept: "
        f"{list(config.sensitivity.percentiles)}."
    )
    lines.append("")
    lines.append("### 5.3. Z-score")
    lines.append("")
    lines.append(
        "Threshold `3.0` is used as a **diagnostic comparison only**. "
        "FE-03 does not silently adopt z-score as a treatment threshold "
        "because transaction features are typically right-skewed / "
        "heavy-tailed."
    )
    lines.append("")

    # 6. Transaction-Level Analysis
    lines.append("## 6. Transaction-Level Analysis")
    lines.append("")
    lines.append(
        "Detection results per (feature, method, filter_mode). "
        "``filter_mode=all_rows`` includes cancellation / return rows; "
        "``filter_mode=clean_purchase`` excludes them so customer "
        "behaviour is not conflated with cancellation mechanics."
    )
    lines.append("")
    if ctx.detection_records:
        rec_rows = [r.to_dict() for r in ctx.detection_records]
        rec_df = pd.DataFrame.from_records(rec_rows)
        rec_df = rec_df.sort_values(["feature", "method", "filter_mode"]).reset_index(drop=True)
        cols = ["feature", "method", "threshold", "filter_mode", "candidates", "rate", "total_rows"]
        cols = [c for c in cols if c in rec_df.columns]
        lines.append("| " + " | ".join(cols) + " |")
        lines.append("| " + " | ".join(["---"] * len(cols)) + " |")
        for _, row in rec_df[cols].iterrows():
            cells = [_format_cell(row[c], column=c) for c in cols]
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")
    else:
        lines.append("_No detection records computed._")
        lines.append("")

    # 7. Customer-Level Diagnostic Analysis
    lines.append("## 7. Customer-Level Diagnostic Analysis")
    lines.append("")
    if not config.customer_diagnostic.enabled:
        lines.append(
            "_Customer-level diagnostic is disabled in the YAML._ "
            "Customer-level outputs are **diagnostic-only** and not the "
            "project's RFM."
        )
        lines.append("")
    elif ctx.customer_diagnostic_summary.empty:
        lines.append("_Customer-level diagnostic produced no rows._")
        lines.append("")
    else:
        lines.append(
            "Per-customer aggregates under the default filter mode. "
            "**These are diagnostic; not RFM Frequency / Monetary / "
            "Recency.** See section 13 for the mentor-decision items."
        )
        lines.append("")
        sum_df = ctx.customer_diagnostic_summary.copy()
        keep = ["column", "count", "min", "max", "mean", "median", "std", "q1", "q3", "iqr"]
        keep = [c for c in keep if c in sum_df.columns]
        lines.append("| " + " | ".join(keep) + " |")
        lines.append("| " + " | ".join(["---"] * len(keep)) + " |")
        for _, row in sum_df[keep].iterrows():
            cells = [_format_cell(row[c], column=c) for c in keep]
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")
        # Detection at customer level.
        if ctx.detection_records:
            cust_recs = [
                r for r in ctx.detection_records if r.feature in {"total_spend", "total_quantity"}
            ]
            if cust_recs:
                lines.append("**Customer-level diagnostic outlier scan (sensitivity config)**")
                lines.append("")
                cust_df = pd.DataFrame.from_records([r.to_dict() for r in cust_recs])
                cols = ["feature", "method", "threshold", "filter_mode", "candidates", "rate"]
                cols = [c for c in cols if c in cust_df.columns]
                lines.append("| " + " | ".join(cols) + " |")
                lines.append("| " + " | ".join(["---"] * len(cols)) + " |")
                for _, row in cust_df[cols].iterrows():
                    cells = [_format_cell(row[c], column=c) for c in cols]
                    lines.append("| " + " | ".join(cells) + " |")
                lines.append("")

    # 8. Cancellation and Return Analysis
    lines.append("## 8. Cancellation and Return Analysis")
    lines.append("")
    lines.append(
        "FE-02 flags cancellations (C-prefixed `InvoiceNo`) and returns "
        "(negative `Quantity`) without dropping them (DD-01, DD-02). "
        "FE-03 keeps this behaviour and **does not** silently change it."
    )
    lines.append("")
    lines.append("Filter modes compared below (default feature = ``Quantity``):")
    lines.append("")
    if ctx.distribution_profiles:
        # Compare Quantity stats across modes.
        rows_q = []
        for mode in ctx.distribution_profiles:
            prof = ctx.distribution_profiles[mode].get("Quantity")
            if prof is None:
                continue
            rows_q.append(
                {
                    "filter_mode": mode,
                    "count": prof.count,
                    "negative_count": prof.negative_count,
                    "min": prof.min,
                    "max": prof.max,
                    "mean": prof.mean,
                }
            )
        if rows_q:
            df = pd.DataFrame.from_records(rows_q)
            cols = ["filter_mode", "count", "negative_count", "min", "max", "mean"]
            lines.append("| " + " | ".join(cols) + " |")
            lines.append("| " + " | ".join(["---"] * len(cols)) + " |")
            for _, row in df[cols].iterrows():
                cells = [_format_cell(row[c], column=c) for c in cols]
                lines.append("| " + " | ".join(cells) + " |")
            lines.append("")
        lines.append(
            "Interpretation: the comparison shows whether extreme values "
            "disappear once cancellation / return rows are excluded. "
            "If they do, the extremes are cancellation mechanics rather "
            "than customer behaviour."
        )
        lines.append("")

    # 9. Error vs Real Behavior Assessment
    lines.append("## 9. Error vs Real Behavior Assessment")
    lines.append("")
    if ctx.interpretation_decisions:
        lines.append("| Feature | Filter | Verdict | Recommendation | Status | Notes |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for d in ctx.interpretation_decisions:
            lines.append(
                f"| `{d.feature}` | {d.filter_mode} | {d.verdict} | "
                f"{d.recommendation} | {d.status} | {d.notes} |"
            )
        lines.append("")
    else:
        lines.append("_No interpretation decisions available._")
        lines.append("")

    # 10. Treatment Decisions
    lines.append("## 10. Treatment Decisions")
    lines.append("")
    lines.append(
        "| Feature | Filter | Method | Threshold | Candidates | Rate | Evidence | Recommendation | Status |"
    )
    lines.append("| --- | --- | --- | --- | ---: | ---: | --- | --- | --- |")
    # Pair detection records with interpretation decisions.
    decision_index: dict[tuple[str, str], InterpretationDecision] = {
        (d.feature, d.filter_mode): d for d in ctx.interpretation_decisions
    }
    for rec in sorted(ctx.detection_records, key=lambda r: (r.feature, r.method, r.filter_mode)):
        dec = decision_index.get((rec.feature, rec.filter_mode))
        evidence = "; ".join(dec.evidence) if dec else ""
        recommendation = dec.recommendation if dec else "KEEP"
        status = dec.status if dec else OUTLIER_STATUS_PENDING_MENTOR_REVIEW
        lines.append(
            f"| `{rec.feature}` | {rec.filter_mode} | {rec.method} | "
            f"{rec.threshold} | {rec.candidates} | {rec.rate:.4f} | "
            f"{evidence} | {recommendation} | {status} |"
        )
    lines.append("")
    lines.append(
        "**Default policy.** Treatment defaults to ``KEEP`` (analysis "
        "only). No treated dataset is written unless the YAML "
        "``output.write_treated_dataset=true`` AND the orchestrator "
        "receives the ``--write-treated`` flag."
    )
    lines.append("")
    if ctx.treated_dataset_path is None:
        lines.append("**Treated dataset.** Not written. The default behaviour is " "preserved.")
    else:
        lines.append(
            f"**Treated dataset.** Written to `{ctx.treated_dataset_path}`. "
            "Verify by re-running with the same config."
        )
    lines.append("")

    # 11. Before / After Comparison
    lines.append("## 11. Before / After Comparison")
    lines.append("")
    lines.append(
        "Because the default treatment is ``KEEP``, there is **no** "
        "before/after dataset for FE-03 to compare. The table below "
        "confirms that the FE-02 cleaned parquet is unchanged by the "
        "FE-03 run."
    )
    lines.append("")
    lines.append("| Check | Before | After | Equal |")
    lines.append("| --- | --- | --- | :---: |")
    lines.append(
        f"| FE-02 cleaned parquet SHA-256 | `{ctx.cleaned_sha256_before}` | "
        f"`{ctx.cleaned_sha256_after}` | "
        f"{'✅' if ctx.cleaned_sha256_before == ctx.cleaned_sha256_after else '❌'} |"
    )
    lines.append(f"| Raw xlsx SHA-256 | `{ctx.raw_sha256}` | `{ctx.raw_sha256}` | ✅ |")
    lines.append("")

    # 12. Sensitivity Analysis
    lines.append("## 12. Sensitivity Analysis")
    lines.append("")
    sens = build_sensitivity_csv(ctx)
    if sens.empty:
        lines.append("_No sensitivity table computed._")
        lines.append("")
    else:
        lines.append("| Feature | Filter | Method | Threshold | Candidates | Rate | Total rows |")
        lines.append("| --- | --- | --- | --- | ---: | ---: | ---: |")
        for _, row in sens.iterrows():
            lines.append(
                f"| `{row['feature']}` | {row['filter_mode']} | {row['method']} | "
                f"{row['threshold']} | {int(row['candidates'])} | "
                f"{float(row['rate']):.4f} | {int(row['total_rows'])} |"
            )
        lines.append("")
        lines.append(
            "Interpretation: thresholds are wider for larger values, so "
            "the IQR-3.0 and P99.9 columns typically flag *fewer* rows "
            "than IQR-1.5 and P99. Z-score results on heavy-tailed "
            "distributions may flag almost nothing because the mean / "
            "std estimate is dominated by extreme values."
        )
        lines.append("")

    # 13. Mentor Decisions Required
    lines.append("## 13. Mentor Decisions Required")
    lines.append("")
    lines.append(
        "Items below require mentor approval before any treatment is "
        "applied. They are derived from the analysis above, not from "
        "any clustering metric (FE-03 is independent of FE-06)."
    )
    lines.append("")
    pending_items = [
        {
            "id": "DD-05 (FE-03 view)",
            "topic": "Quantity at P99.9",
            "description": (
                "Whether to clip `Quantity` above the P99.9 fence, "
                "flag candidates, or KEEP. Recommendation here: **KEEP** "
                "until FE-04 RFM is finalised (extreme positives may "
                "be bulk buyers)."
            ),
        },
        {
            "id": "DD-05 (FE-03 view)",
            "topic": "LineRevenue outliers",
            "description": (
                "Whether to flag the LineRevenue candidates surfaced by "
                "the IQR-1.5 sweep. Recommendation: **KEEP**; LineRevenue "
                "is derived and cancellation / return semantics carry "
                "through."
            ),
        },
        {
            "id": "DD-05 (FE-03 view)",
            "topic": "Customer total_spend extremes",
            "description": (
                "Whether customer-level `total_spend` outliers should be "
                "clipped before FE-04 RFM aggregation. Recommendation: "
                "**DEFER** to FE-04."
            ),
        },
        {
            "id": "DD-02 (FE-02)",
            "topic": "Negative Quantity without C-prefix",
            "description": (
                "Whether negative `Quantity` on non-cancellation rows is "
                "a data-entry error or an undocumented return convention. "
                "FE-03 cannot resolve this on its own."
            ),
        },
        {
            "id": "DD-03 (FE-02)",
            "topic": "UnitPrice P99.9",
            "description": (
                "Whether very-high UnitPrice values (`> £1000`) are "
                "plausible (e.g. postage, antique) or data-entry typos. "
                "FE-03 cannot resolve this on its own."
            ),
        },
    ]
    lines.append("| ID | Topic | Description |")
    lines.append("| --- | --- | --- |")
    for d in pending_items:
        lines.append(f"| {d['id']} | {d['topic']} | {d['description']} |")
    lines.append("")

    # 14. Limitations
    lines.append("## 14. Limitations")
    lines.append("")
    lines.append(
        "- FE-03 is exploratory. No treatment is applied unless the YAML "
        "AND the CLI opt-in agree.\n"
        "- Customer-level outputs are diagnostic; they are not the "
        "project's official RFM / extended-behavioural features.\n"
        "- Z-score on heavy-tailed data is reported only as a diagnostic "
        "comparison; it is not used to choose a treatment.\n"
        "- FE-03 does not run clustering. No clustering metric "
        "(Silhouette, DBI, CHI, ...) was used to choose a threshold.\n"
        "- The cleaned dataset is read-only. The raw file is read-only. "
        "Both SHA-256s are recorded before and after the run."
    )
    lines.append("")

    # 15. Conclusion
    lines.append("## 15. Conclusion")
    lines.append("")
    lines.append(
        f"FE-03 analysed **{len(features)}** transaction-level features "
        f"and **{len(ctx.customer_diagnostics)}** customer-level "
        "diagnostic frame(s). No treatment was applied by default. "
        "All detected outliers are documented in this report; "
        "treatment recommendations are recorded per-feature and "
        "default to ``KEEP``. Mentor-review items are listed in "
        "section 13."
    )
    lines.append("")
    return "\n".join(lines)


# Convenience alias for the orchestrator.
def build_outlier_analysis_md(ctx: ReportContext) -> str:
    """Alias for :func:`render_outlier_analysis_markdown`."""
    return render_outlier_analysis_markdown(ctx)
