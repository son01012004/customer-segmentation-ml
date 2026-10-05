"""Imputation semantics analysis for FE-06.

Distinguishes two kinds of NaN values in the FE-05 candidate dataset:

1. **GENUINE_DATA_QUALITY_MISSING** — value should exist but is missing
   due to upstream data-quality issues (e.g. join failure, bad row).

2. **STRUCTURALLY_UNDEFINED** — value is mathematically undefined for the
   customer given their transaction history. The most common cases:
   - PurchaseIntervalMean / PurchaseIntervalStd: undefined when the
     customer has < 2 invoices (no consecutive-interval set).
   - PurchaseIntervalStd: ddof=1 with a single observation also returns
     NaN (sample std of a 1-element vector is undefined).

FE-06 treats both kinds with the same working strategy (median imputation),
but reports them separately so the semantics are traceable.

Hard constraints (FE-06):
- Do NOT fill with 0 (would mislead "no interval" as "zero interval").
- Do NOT create sentinel values.
- Report per-feature: NaN count before, semantics classification, median
  used, NaN count after.
- Verify no NaN remains in eligible features after imputation.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

__all__ = [
    "SEMANTICS_STRUCTURAL",
    "SEMANTICS_DATA_QUALITY",
    "SEMANTICS_UNKNOWN",
    "ImputationSemanticsResult",
    "analyze_imputation_semantics",
]


# ---------------------------------------------------------------------------
# Semantics constants
# ---------------------------------------------------------------------------

SEMANTICS_STRUCTURAL = "STRUCTURALLY_UNDEFINED"
"""NaN because value is mathematically undefined for the customer."""

SEMANTICS_DATA_QUALITY = "GENUINE_DATA_QUALITY_MISSING"
"""NaN because value should exist but is missing for data-quality reasons."""

SEMANTICS_UNKNOWN = "UNKNOWN"
"""Cannot be classified from FE-06 context; kept conservative."""

# Feature-level semantics mapping (FE-05 source of truth).
FEATURE_IMPUTATION_SEMANTICS: dict[str, str] = {
    "PurchaseIntervalMean": (
        "STRUCTURALLY_UNDEFINED for customers with < 2 invoices. "
        "diff() over a 1-element series has no defined value, so "
        "FE-05 reports NaN. Median imputation is a working default "
        "(WORKING_ASSUMPTION / MENTOR_REVIEW_PENDING)."
    ),
    "PurchaseIntervalStd": (
        "STRUCTURALLY_UNDEFINED for customers with < 2 invoices. "
        "Additionally, with ddof=1 and only 1 interval (2 invoices), "
        "the sample std is mathematically undefined (NaN). "
        "Median imputation is a working default "
        "(WORKING_ASSUMPTION / MENTOR_REVIEW_PENDING)."
    ),
}


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass
class FeatureImputationSemantics:
    """Semantics result for a single feature."""

    feature: str
    nan_before: int
    nan_after: int
    median_used: float
    semantics: str
    semantics_detail: str
    note: str

    def to_dict(self) -> dict:
        """Convert to dict for CSV writing."""
        return {
            "Feature": self.feature,
            "NaN_Before": self.nan_before,
            "NaN_After": self.nan_after,
            "Median_Used": self.median_used,
            "Semantics": self.semantics,
            "Semantics_Detail": self.semantics_detail,
            "Note": self.note,
        }


@dataclass
class ImputationSemanticsResult:
    """Container for all feature imputation semantics."""

    features: list[FeatureImputationSemantics]

    def to_dataframe(self) -> pd.DataFrame:
        """Convert to a DataFrame."""
        if not self.features:
            return pd.DataFrame(
                columns=[
                    "Feature",
                    "NaN_Before",
                    "NaN_After",
                    "Median_Used",
                    "Semantics",
                    "Semantics_Detail",
                    "Note",
                ]
            )
        return pd.DataFrame([f.to_dict() for f in self.features])


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------


def analyze_imputation_semantics(
    df_before: pd.DataFrame,
    df_after: pd.DataFrame,
    features_to_impute: list[str],
    median_values: dict[str, float],
    total_rows: int,
) -> ImputationSemanticsResult:
    """Build imputation semantics report.

    Parameters
    ----------
    df_before : pandas.DataFrame
        Working DataFrame BEFORE imputation (raw FE-05 candidates).
    df_after : pandas.DataFrame
        Working DataFrame AFTER imputation (no NaN in imputed features).
    features_to_impute : list[str]
        Features that were targeted by imputation.
    median_values : dict[str, float]
        Median values used per feature.
    total_rows : int
        Total customer rows (for context).

    Returns
    -------
    ImputationSemanticsResult
        Per-feature imputation semantics evidence.
    """
    results: list[FeatureImputationSemantics] = []

    for feat in features_to_impute:
        if feat not in df_before.columns:
            # Feature not in input — skip.
            continue

        nan_before = int(df_before[feat].isna().sum())
        nan_after = int(df_after[feat].isna().sum()) if feat in df_after.columns else nan_before
        median_used = median_values.get(feat, float("nan"))

        # Semantics classification.
        if feat in FEATURE_IMPUTATION_SEMANTICS:
            semantics = SEMANTICS_STRUCTURAL
            semantics_detail = FEATURE_IMPUTATION_SEMANTICS[feat]
        else:
            semantics = SEMANTICS_UNKNOWN
            semantics_detail = (
                "Feature not in the FE-06 semantics map. "
                "If this feature appears here, review FE-05 source."
            )

        # Compose a note summarizing the evidence.
        if nan_before == 0:
            note = (
                f"No NaN observed in {feat}; median recorded for reproducibility only. "
                f"{nan_after} NaN remain (== 0)."
            )
        else:
            pct = (nan_before / max(total_rows, 1)) * 100
            note = (
                f"{nan_before} customers ({pct:.1f}%) had NaN in {feat} before imputation; "
                f"{nan_after} remain after median imputation. "
                "Working default; not auto-promoted to final."
            )

        results.append(
            FeatureImputationSemantics(
                feature=feat,
                nan_before=nan_before,
                nan_after=nan_after,
                median_used=median_used,
                semantics=semantics,
                semantics_detail=semantics_detail,
                note=note,
            )
        )

    return ImputationSemanticsResult(features=results)
