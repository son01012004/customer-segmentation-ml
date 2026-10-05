"""Evidence-based feature selection for FE-05.

Hard constraints (Plan V5):
- Evidence-based gates (Interpretability, Data Quality, Leakage, Zero-Variance, Redundancy)
- NO numerical score, ranking, or weights.
- Redundancy Gate = DIAGNOSTIC ONLY.
- Stability Gate = DIAGNOSTIC ONLY.
- Shapiro-Wilk Gate = OPTIONAL DIAGNOSTIC ONLY.
- RETAIN_CANDIDATE = "đủ điều kiện FE-06", KHÔNG phải final.
- KHÔNG gọi feature nào "best", "recommended", "final".
- All unsupported features must be documented.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

__all__ = [
    "FeatureSelectionResult",
    "apply_interpretability_gate",
    "apply_data_quality_gate",
    "apply_leakage_gate",
    "apply_zero_variance_gate",
    "apply_redundancy_gate",
    "apply_stability_gate",
    "apply_shapiro_wilk_gate",
    "make_selection_decisions",
    "build_feature_selection_report",
    "DECISION_RETAIN_CANDIDATE",
    "DECISION_EXCLUDE",
    "DECISION_ADJUST",
    "DECISION_PENDING_REVIEW",
    "GATE_STATUS_PASS",
    "GATE_STATUS_FAIL",
    "GATE_STATUS_WARNING",
    "GATE_STATUS_NOT_APPLICABLE",
    "GATE_STATUS_DIAGNOSTIC",
    "DEFAULT_INTERPRETABLE_FEATURES",
]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


GATE_STATUS_PASS = "PASS"
GATE_STATUS_FAIL = "FAIL"
GATE_STATUS_WARNING = "WARNING"
GATE_STATUS_NOT_APPLICABLE = "N/A"
GATE_STATUS_DIAGNOSTIC = "DIAGNOSTIC_ONLY"


DECISION_RETAIN_CANDIDATE = "RETAIN_CANDIDATE"
DECISION_EXCLUDE = "EXCLUDE"
DECISION_ADJUST = "ADJUST"
DECISION_PENDING_REVIEW = "PENDING_REVIEW"


# Default set of standard interpretable features
DEFAULT_INTERPRETABLE_FEATURES = frozenset(
    {
        "Recency",
        "Frequency",
        "Monetary",
        "TenureDays",
        "ActiveDays",
        "ProductsPerInvoice",
        "CancellationRate",
        "ReturnRate",
        "AverageInvoiceValue",
        "TotalQuantity",
        "AverageQuantity",
        "BasketSize",
        "PurchaseIntervalMean",
        "PurchaseIntervalStd",
    }
)


# ---------------------------------------------------------------------------
# Gate implementations
# ---------------------------------------------------------------------------


@dataclass
class GateResult:
    """Result of a single gate check."""

    feature: str
    gate_name: str
    status: str  # PASS | FAIL | WARNING | N/A | DIAGNOSTIC_ONLY
    rationale: str


def apply_interpretability_gate(
    feature: str,
    *,
    is_interpretable: bool,
) -> GateResult:
    """Apply interpretability gate.

    Parameters
    ----------
    feature : str
        Feature name.
    is_interpretable : bool
        Whether feature has clear business interpretation.

    Returns
    -------
    GateResult
        Gate check result.
    """
    status = GATE_STATUS_PASS if is_interpretable else GATE_STATUS_WARNING
    rationale = (
        f"Feature {feature!r} has standard business interpretation."
        if is_interpretable
        else f"Feature {feature!r} has unclear business interpretation. "
        "Requires domain expert review."
    )
    return GateResult(
        feature=feature,
        gate_name="Interpretability",
        status=status,
        rationale=rationale,
    )


def apply_data_quality_gate(
    feature: str,
    series: pd.Series,
    *,
    max_missing_ratio: float = 0.5,
) -> GateResult:
    """Apply data quality gate.

    PASS if missing_ratio <= max_missing_ratio.
    WARNING if missing_ratio is higher.

    Parameters
    ----------
    feature : str
        Feature name.
    series : pandas.Series
        Feature values.
    max_missing_ratio : float
        Maximum allowed missing ratio.

    Returns
    -------
    GateResult
        Gate check result.
    """
    missing_count = int(series.isna().sum())
    total_count = len(series)
    missing_ratio = missing_count / max(total_count, 1)

    if missing_ratio == 0:
        status = GATE_STATUS_PASS
        rationale = f"Feature {feature!r} has no missing values."
    elif missing_ratio <= max_missing_ratio:
        status = GATE_STATUS_PASS
        rationale = (
            f"Feature {feature!r} has missing ratio {missing_ratio:.2%} "
            f"(<= {max_missing_ratio:.0%} threshold)."
        )
    elif missing_ratio < 0.9:
        status = GATE_STATUS_WARNING
        rationale = (
            f"Feature {feature!r} has high missing ratio {missing_ratio:.2%} "
            f"(> {max_missing_ratio:.0%} threshold). Review imputation strategy."
        )
    else:
        status = GATE_STATUS_FAIL
        rationale = (
            f"Feature {feature!r} has {missing_ratio:.2%} missing values. "
            "Insufficient data for clustering."
        )

    return GateResult(
        feature=feature,
        gate_name="DataQuality",
        status=status,
        rationale=rationale,
    )


def apply_leakage_gate(
    feature: str,
    *,
    is_potential_leakage: bool = False,
) -> GateResult:
    """Apply leakage gate.

    FAIL if feature potentially leaks target information.

    Parameters
    ----------
    feature : str
        Feature name.
    is_potential_leakage : bool
        Whether feature may leak target info.

    Returns
    -------
    GateResult
        Gate check result.
    """
    if is_potential_leakage:
        status = GATE_STATUS_FAIL
        rationale = f"Feature {feature!r} may leak target information. " "Requires investigation."
    else:
        status = GATE_STATUS_PASS
        rationale = f"Feature {feature!r} does not leak target information."

    return GateResult(
        feature=feature,
        gate_name="Leakage",
        status=status,
        rationale=rationale,
    )


def apply_zero_variance_gate(
    feature: str,
    series: pd.Series,
) -> GateResult:
    """Apply zero-variance gate.

    FAIL if feature has zero variance (no discriminative power).

    Parameters
    ----------
    feature : str
        Feature name.
    series : pandas.Series
        Feature values.

    Returns
    -------
    GateResult
        Gate check result.
    """
    valid = series.dropna()
    if len(valid) == 0:
        status = GATE_STATUS_FAIL
        rationale = f"Feature {feature!r} has no valid values."
    elif valid.nunique() <= 1:
        status = GATE_STATUS_FAIL
        rationale = (
            f"Feature {feature!r} has zero variance "
            f"(all values equal: {valid.iloc[0]}). No discriminative power."
        )
    else:
        status = GATE_STATUS_PASS
        rationale = f"Feature {feature!r} has variance > 0."

    return GateResult(
        feature=feature,
        gate_name="ZeroVariance",
        status=status,
        rationale=rationale,
    )


def apply_redundancy_gate(
    feature: str,
    *,
    max_correlation_with_others: float,
    threshold: float = 0.95,
) -> GateResult:
    """Apply redundancy gate (DIAGNOSTIC ONLY).

    This gate does NOT auto-exclude features. It only flags them.

    Parameters
    ----------
    feature : str
        Feature name.
    max_correlation_with_others : float
        Maximum absolute correlation with other features.
    threshold : float
        Correlation threshold.

    Returns
    -------
    GateResult
        Gate check result (DIAGNOSTIC_ONLY status).
    """
    if pd.notna(max_correlation_with_others) and max_correlation_with_others >= threshold:
        status = GATE_STATUS_DIAGNOSTIC
        rationale = (
            f"Feature {feature!r} has |correlation| = {max_correlation_with_others:.3f} "
            f">= threshold {threshold}. Potential redundancy. Diagnostic only - "
            "does not auto-exclude."
        )
    else:
        status = GATE_STATUS_DIAGNOSTIC
        rationale = (
            f"Feature {feature!r} has max |correlation| = "
            f"{max_correlation_with_others if pd.notna(max_correlation_with_others) else 'N/A'}. "
            "Diagnostic only."
        )

    return GateResult(
        feature=feature,
        gate_name="Redundancy",
        status=status,
        rationale=rationale,
    )


def apply_stability_gate(
    feature: str,
    *,
    stability_score: float | None = None,
) -> GateResult:
    """Apply stability gate (DIAGNOSTIC ONLY).

    Parameters
    ----------
    feature : str
        Feature name.
    stability_score : float, optional
        Bootstrap stability score (e.g., 1 - mean(relative_std)).

    Returns
    -------
    GateResult
        Gate check result (DIAGNOSTIC_ONLY status).
    """
    status = GATE_STATUS_DIAGNOSTIC
    if stability_score is None:
        rationale = f"Stability check skipped for {feature!r}. " "Stability is diagnostic only."
    else:
        rationale = (
            f"Feature {feature!r} stability score = {stability_score:.3f}. "
            "Diagnostic only - does not affect KEEP/DROP decision."
        )

    return GateResult(
        feature=feature,
        gate_name="Stability",
        status=status,
        rationale=rationale,
    )


def apply_shapiro_wilk_gate(
    feature: str,
    *,
    is_normal: bool | None = None,
) -> GateResult:
    """Apply Shapiro-Wilk gate (OPTIONAL DIAGNOSTIC ONLY).

    Parameters
    ----------
    feature : str
        Feature name.
    is_normal : bool, optional
        Whether feature passes Shapiro-Wilk normality test.

    Returns
    -------
    GateResult
        Gate check result (DIAGNOSTIC_ONLY status).
    """
    status = GATE_STATUS_DIAGNOSTIC
    if is_normal is None:
        rationale = f"Shapiro-Wilk test skipped for {feature!r}. " "Optional diagnostic only."
    elif is_normal:
        rationale = (
            f"Feature {feature!r} passes Shapiro-Wilk normality test. "
            "Optional diagnostic only - does not affect KEEP/DROP decision."
        )
    else:
        rationale = (
            f"Feature {feature!r} fails Shapiro-Wilk normality test "
            "(non-normal distribution). Optional diagnostic only - "
            "does not affect KEEP/DROP decision."
        )

    return GateResult(
        feature=feature,
        gate_name="ShapiroWilk",
        status=status,
        rationale=rationale,
    )


# ---------------------------------------------------------------------------
# Selection decision
# ---------------------------------------------------------------------------


@dataclass
class FeatureSelectionResult:
    """Feature selection result."""

    selection_df: pd.DataFrame
    feature_count: int
    retain_count: int
    pending_count: int


def make_selection_decisions(
    gate_results: dict[str, list[GateResult]],
    redundancy_pairs: pd.DataFrame | None = None,
) -> FeatureSelectionResult:
    """Make selection decisions for each feature based on gate results.

    Decision logic:
    - If any REQUIRED gate fails (Interpretability FAIL, DataQuality FAIL,
      ZeroVariance FAIL, Leakage FAIL): decision = EXCLUDE
    - If Interpretability WARNING, DataQuality WARNING: decision = ADJUST or PENDING_REVIEW
    - If all required gates pass: decision = RETAIN_CANDIDATE
      (eligible for FE-06, NOT final)
    - Redundancy, Stability, Shapiro-Wilk are diagnostic only.

    Parameters
    ----------
    gate_results : dict[str, list[GateResult]]
        Map of feature name to list of GateResult.
    redundancy_pairs : pandas.DataFrame, optional
        Redundancy pairs from analysis.py.

    Returns
    -------
    FeatureSelectionResult
        Container with selection DataFrame.
    """
    rows = []

    # Build redundancy map: feature -> max correlation with others
    redundancy_map: dict[str, float] = {}
    if redundancy_pairs is not None and not redundancy_pairs.empty:
        for _, row in redundancy_pairs.iterrows():
            f1 = row["Feature1"]
            f2 = row["Feature2"]
            corr = abs(float(row["Correlation"]))
            redundancy_map[f1] = max(redundancy_map.get(f1, 0), corr)
            redundancy_map[f2] = max(redundancy_map.get(f2, 0), corr)

    for feature, results in gate_results.items():
        # Aggregate gate status
        has_fail = any(r.status == GATE_STATUS_FAIL for r in results)
        has_warning = any(r.status == GATE_STATUS_WARNING for r in results)
        has_diagnostic = any(r.status == GATE_STATUS_DIAGNOSTIC for r in results)

        # Determine decision
        if has_fail:
            decision = DECISION_EXCLUDE
        elif has_warning:
            decision = DECISION_PENDING_REVIEW
        elif has_diagnostic and redundancy_map.get(feature, 0) >= 0.95:
            decision = DECISION_PENDING_REVIEW  # Diagnostic only, but flag for review
        else:
            decision = DECISION_RETAIN_CANDIDATE

        # Build gate status summary
        gate_status_dict = {r.gate_name: r.status for r in results}

        row = {
            "Feature": feature,
            "Decision": decision,
            "GateStatus_Interpretability": gate_status_dict.get("Interpretability", "N/A"),
            "GateStatus_DataQuality": gate_status_dict.get("DataQuality", "N/A"),
            "GateStatus_Leakage": gate_status_dict.get("Leakage", "N/A"),
            "GateStatus_ZeroVariance": gate_status_dict.get("ZeroVariance", "N/A"),
            "GateStatus_Redundancy": gate_status_dict.get("Redundancy", "N/A"),
            "GateStatus_Stability": gate_status_dict.get("Stability", "N/A"),
            "GateStatus_ShapiroWilk": gate_status_dict.get("ShapiroWilk", "N/A"),
            "MaxCorrelation": redundancy_map.get(feature, np.nan),
            "Note": (
                "RETAIN_CANDIDATE means eligible for FE-06, NOT final decision."
                if decision == DECISION_RETAIN_CANDIDATE
                else ""
            ),
        }
        rows.append(row)

    selection_df = pd.DataFrame(rows)
    retain_count = int((selection_df["Decision"] == DECISION_RETAIN_CANDIDATE).sum())
    pending_count = int((selection_df["Decision"] == DECISION_PENDING_REVIEW).sum())

    return FeatureSelectionResult(
        selection_df=selection_df,
        feature_count=len(rows),
        retain_count=retain_count,
        pending_count=pending_count,
    )


def build_feature_selection_report(
    selection_result: FeatureSelectionResult,
    unsupported_features: list[str] | None = None,
) -> pd.DataFrame:
    """Build feature selection report CSV with unsupported features.

    Parameters
    ----------
    selection_result : FeatureSelectionResult
        Selection result.
    unsupported_features : list[str], optional
        Names of unsupported features (NOT materialized).

    Returns
    -------
    pandas.DataFrame
        Report DataFrame.
    """
    selection_df = selection_result.selection_df.copy()

    if unsupported_features:
        # Add rows for unsupported features
        unsupported_rows = []
        for feat in unsupported_features:
            unsupported_rows.append(
                {
                    "Feature": feat,
                    "Decision": "UNSUPPORTED",
                    "GateStatus_Interpretability": "N/A",
                    "GateStatus_DataQuality": "N/A",
                    "GateStatus_Leakage": "N/A",
                    "GateStatus_ZeroVariance": "N/A",
                    "GateStatus_Redundancy": "N/A",
                    "GateStatus_Stability": "N/A",
                    "GateStatus_ShapiroWilk": "N/A",
                    "MaxCorrelation": np.nan,
                    "Note": "Not materialized - dataset lacks official taxonomy.",
                }
            )
        unsupported_df = pd.DataFrame(unsupported_rows)
        selection_df = pd.concat([selection_df, unsupported_df], ignore_index=True)

    return selection_df
