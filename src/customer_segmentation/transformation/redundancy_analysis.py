"""Redundancy analysis with 3-category classification for FE-06.

Distinguishes three empirical categories based on data evidence:

1. **DUPLICATE_INFORMATION**: Features are mathematically or empirically
   identical (equality rate = 1.0 across all rows, max |diff| = 0).

2. **HIGH_CORRELATION**: Features have |Pearson| >= threshold and are
   semantically related but NOT identical (equality rate < 1.0).

3. **DISTINCT_BUT_RELATED**: Features have lower correlation but share a
   semantic relationship (e.g. defined on the same underlying data).

Hard constraints (FE-06):
- Detection + quantification + classification only.
- NO auto-drop, NO scoring, NO ranking.
- Each pair is reported with full evidence (Pearson, Spearman, equality
  rate, max |diff|, definitions).
- PENDING_REVIEW if evidence is insufficient to classify.

This module operates on **pre-transformation data** (i.e. the imputed
working matrix). Yeo-Johnson and RobustScaler are monotone / linear
operations on correlation structure (with caveats for Yeo-Johnson sign
changes at zero), so pre/post correlations are reported separately by
the pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

__all__ = [
    "RedundancyCategory",
    "REDUNDANCY_DUPLICATE",
    "REDUNDANCY_HIGH_CORRELATION",
    "REDUNDANCY_DISTINCT_BUT_RELATED",
    "REDUNDANCY_PENDING_REVIEW",
    "RedundancyPair",
    "RedundancyAnalysisResult",
    "analyze_redundancy_pair",
    "analyze_redundancy_pairs",
    "FEATURE_DEFINITIONS",
]


# ---------------------------------------------------------------------------
# Category constants
# ---------------------------------------------------------------------------

REDUNDANCY_DUPLICATE = "DUPLICATE_INFORMATION"
"""Features are mathematically or empirically identical across all rows."""

REDUNDANCY_HIGH_CORRELATION = "HIGH_CORRELATION"
"""Features have |Pearson| >= threshold but are NOT identical (equality rate < 1.0)."""

REDUNDANCY_DISTINCT_BUT_RELATED = "DISTINCT_BUT_RELATED"
"""Features share semantic lineage but correlation < threshold."""

REDUNDANCY_PENDING_REVIEW = "PENDING_REVIEW"
"""Insufficient evidence to classify (kept conservative)."""


class RedundancyCategory:
    """Redundancy category constants."""

    DUPLICATE_INFORMATION = REDUNDANCY_DUPLICATE
    HIGH_CORRELATION = REDUNDANCY_HIGH_CORRELATION
    DISTINCT_BUT_RELATED = REDUNDANCY_DISTINCT_BUT_RELATED
    PENDING_REVIEW = REDUNDANCY_PENDING_REVIEW


# ---------------------------------------------------------------------------
# Feature definitions (FE-05 source of truth, documented here for FE-06
# traceability)
# ---------------------------------------------------------------------------

FEATURE_DEFINITIONS: dict[str, str] = {
    "AverageQuantity": (
        "sum(Quantity) / nunique(InvoiceNo) per CustomerID " "(signed; includes cancellations)"
    ),
    "BasketSize": "alias for AverageQuantity per CustomerID (signed)",
    "CancellationRate": "CancellationInvoiceCount / Frequency",
    "ReturnRate": "ReturnInvoiceCount / Frequency",
    "Frequency": "nunique(InvoiceNo) per CustomerID",
    "ActiveDays": "nunique(date(InvoiceDate)) per CustomerID",
    "PurchaseIntervalMean": (
        "mean(diff(consecutive InvoiceDate per customer)) in days; " "NaN if < 2 invoices"
    ),
    "PurchaseIntervalStd": (
        "std(diff(consecutive InvoiceDate per customer), ddof=1) in days; "
        "NaN if < 2 invoices (ddof=1 with n=1 returns NaN)"
    ),
}
"""Human-readable feature definitions used for redundancy documentation.

These are the canonical definitions from FE-05
(`customer_segmentation.features.transaction_behavior`,
`customer_segmentation.features.cancellation`). They are documented here so
FE-06 can produce self-contained redundancy reports without importing FE-05.
"""


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass
class RedundancyPair:
    """A single redundancy pair with full evidence."""

    feature1: str
    feature2: str
    pearson: float
    spearman: float
    equality_rate: float
    max_abs_diff: float
    category: str  # one of RedundancyCategory.*
    definition_feature1: str
    definition_feature2: str
    note: str

    def to_dict(self) -> dict:
        """Convert to dict for CSV writing."""
        return {
            "Feature1": self.feature1,
            "Feature2": self.feature2,
            "Pearson": self.pearson,
            "Spearman": self.spearman,
            "EqualityRate": self.equality_rate,
            "MaxAbsDiff": self.max_abs_diff,
            "Category": self.category,
            "Definition_Feature1": self.definition_feature1,
            "Definition_Feature2": self.definition_feature2,
            "Note": self.note,
        }


@dataclass
class RedundancyAnalysisResult:
    """Container for all redundancy pair analyses."""

    pairs: list[RedundancyPair]

    def to_dataframe(self) -> pd.DataFrame:
        """Convert pairs to a DataFrame."""
        if not self.pairs:
            return pd.DataFrame(
                columns=[
                    "Feature1",
                    "Feature2",
                    "Pearson",
                    "Spearman",
                    "EqualityRate",
                    "MaxAbsDiff",
                    "Category",
                    "Definition_Feature1",
                    "Definition_Feature2",
                    "Note",
                ]
            )
        return pd.DataFrame([p.to_dict() for p in self.pairs])


# ---------------------------------------------------------------------------
# Pairwise analysis
# ---------------------------------------------------------------------------


def analyze_redundancy_pair(
    df: pd.DataFrame,
    feature1: str,
    feature2: str,
    *,
    threshold: float = 0.95,
    duplicate_tolerance: float = 1e-12,
) -> RedundancyPair:
    """Analyze a single feature pair for redundancy.

    Parameters
    ----------
    df : pandas.DataFrame
        Customer-level DataFrame (after imputation, before transformation).
    feature1, feature2 : str
        Feature column names to compare.
    threshold : float
        |Pearson| threshold above which a pair is flagged HIGH_CORRELATION
        (only if not DUPLICATE_INFORMATION). Default 0.95.
    duplicate_tolerance : float
        Absolute tolerance for declaring two features "equal" element-wise.
        Default 1e-12 (float64 precision).

    Returns
    -------
    RedundancyPair
        Full evidence and classification.

    Notes
    -----
    Classification rules (in order of precedence):

    1. DUPLICATE_INFORMATION if equality_rate == 1.0 (all rows identical
       within tolerance). This takes precedence even if formulas differ,
       because the empirical data shows the same values.
    2. HIGH_CORRELATION if |Pearson| >= threshold and equality_rate < 1.0.
    3. DISTINCT_BUT_RELATED if 0 < |Pearson| < threshold and at least one
       of the features has a known semantic relationship.
    4. PENDING_REVIEW otherwise.
    """
    if feature1 not in df.columns:
        raise ValueError(f"Feature {feature1!r} not in DataFrame.")
    if feature2 not in df.columns:
        raise ValueError(f"Feature {feature2!r} not in DataFrame.")

    s1 = df[feature1].astype(float)
    s2 = df[feature2].astype(float)

    # Handle NaN: drop rows where either is NaN before computing stats.
    mask = s1.notna() & s2.notna()
    s1v = s1.loc[mask]
    s2v = s2.loc[mask]

    n = int(len(s1v))
    if n < 2:
        # Not enough data to classify.
        return RedundancyPair(
            feature1=feature1,
            feature2=feature2,
            pearson=float("nan"),
            spearman=float("nan"),
            equality_rate=float("nan"),
            max_abs_diff=float("nan"),
            category=RedundancyCategory.PENDING_REVIEW,
            definition_feature1=FEATURE_DEFINITIONS.get(feature1, "(not documented)"),
            definition_feature2=FEATURE_DEFINITIONS.get(feature2, "(not documented)"),
            note=f"Insufficient non-NaN rows ({n}) to classify.",
        )

    # Pearson correlation (guard against zero variance).
    if float(s1v.std(ddof=1)) == 0 or float(s2v.std(ddof=1)) == 0:
        pearson = float("nan")
        spearman = float("nan")
    else:
        pearson = float(s1v.corr(s2v))
        spearman = float(s1v.corr(s2v, method="spearman"))

    # Element-wise equality and difference distribution.
    abs_diff = (s1v - s2v).abs()
    max_abs_diff = float(abs_diff.max())
    equality_count = int((abs_diff <= duplicate_tolerance).sum())
    equality_rate = float(equality_count / n)

    # Classification.
    if equality_rate >= 1.0:
        category = RedundancyCategory.DUPLICATE_INFORMATION
        note = (
            "Empirical equality for all customers. Whether by construction "
            "(same formula) or by data coincidence, the two columns carry "
            "the same information and one of them is redundant for FE-06 "
            "purposes. Auto-drop not applied (PENDING_REVIEW per FE-06 plan)."
        )
    elif not np.isnan(pearson) and abs(pearson) >= threshold and equality_rate < 1.0:
        category = RedundancyCategory.HIGH_CORRELATION
        note = (
            f"|Pearson|={abs(pearson):.4f} >= threshold {threshold}. "
            "Not identical (equality_rate < 1.0); features carry overlapping "
            "but distinct information. Auto-drop not applied."
        )
    elif (feature1 in FEATURE_DEFINITIONS) and (feature2 in FEATURE_DEFINITIONS):
        # Both features are documented but correlation is below threshold.
        category = RedundancyCategory.DISTINCT_BUT_RELATED
        note = (
            "Both features documented in FE-05; correlation below redundancy "
            "threshold. They are semantically related but empirically distinct."
        )
    else:
        category = RedundancyCategory.PENDING_REVIEW
        note = (
            "Insufficient evidence to classify. No FE-05 definition for one "
            "or both features, and correlation below threshold."
        )

    return RedundancyPair(
        feature1=feature1,
        feature2=feature2,
        pearson=pearson,
        spearman=spearman,
        equality_rate=equality_rate,
        max_abs_diff=max_abs_diff,
        category=category,
        definition_feature1=FEATURE_DEFINITIONS.get(feature1, "(not documented)"),
        definition_feature2=FEATURE_DEFINITIONS.get(feature2, "(not documented)"),
        note=note,
    )


def analyze_redundancy_pairs(
    df: pd.DataFrame,
    pairs: list[tuple[str, str]],
    *,
    threshold: float = 0.95,
) -> RedundancyAnalysisResult:
    """Analyze a list of feature pairs for redundancy.

    Parameters
    ----------
    df : pandas.DataFrame
        Customer-level DataFrame (after imputation, before transformation).
    pairs : list[tuple[str, str]]
        List of (feature1, feature2) tuples to analyze.
    threshold : float
        |Pearson| threshold for HIGH_CORRELATION classification.

    Returns
    -------
    RedundancyAnalysisResult
        Container with all pair analyses.
    """
    results = [analyze_redundancy_pair(df, f1, f2, threshold=threshold) for f1, f2 in pairs]
    return RedundancyAnalysisResult(pairs=results)
