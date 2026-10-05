"""Analysis utilities for FE-05 candidate features.

Computes:
- Distribution statistics (numeric Tầng 2 CANDIDATE features only)
- Variance statistics (CV = N/A when mean ≈ 0 or negative)
- Correlation matrices (Pearson + Spearman)
- Redundancy detection (high correlation pairs)
- Outlier detection (IQR-based)
- Interpretability assessment
- Shapiro-Wilk normality test (optional diagnostic only)

Hard constraints:
- Only numeric Tầng 2 CANDIDATE features (no date features).
- Shapiro-Wilk = optional diagnostic, no auto KEEP/DROP.
- CV = N/A when mean ≈ 0 or negative.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats  # type: ignore[import-untyped]

__all__ = [
    "compute_distribution_stats",
    "compute_variance_stats",
    "compute_correlation_matrices",
    "detect_redundancy",
    "detect_outliers",
    "assess_interpretability",
    "shapiro_wilk_diagnostic",
    "DistributionResult",
    "VarianceResult",
    "CorrelationResult",
    "RedundancyResult",
    "OutlierResult",
]


# ---------------------------------------------------------------------------
# Helper: select numeric Tầng 2 CANDIDATE features
# ---------------------------------------------------------------------------


def select_numeric_candidate_columns(
    df: pd.DataFrame,
    candidate_columns: Sequence[str],
    *,
    include_date_features: bool = False,
) -> list[str]:
    """Select only numeric Tầng 2 CANDIDATE columns.

    Parameters
    ----------
    df : pandas.DataFrame
        Candidate DataFrame.
    candidate_columns : Sequence[str]
        Names of candidate columns.
    include_date_features : bool
        If False, exclude date/datetime columns.

    Returns
    -------
    list[str]
        Numeric candidate column names.
    """
    selected = []
    for col in candidate_columns:
        if col not in df.columns:
            continue
        # Check if column is numeric
        if (
            pd.api.types.is_numeric_dtype(df[col])
            or include_date_features
            and pd.api.types.is_datetime64_any_dtype(df[col])
        ):
            selected.append(col)
    return selected


# ---------------------------------------------------------------------------
# Distribution statistics
# ---------------------------------------------------------------------------


@dataclass
class DistributionResult:
    """Distribution statistics container."""

    stats_df: pd.DataFrame
    feature_count: int


def compute_distribution_stats(
    df: pd.DataFrame,
    feature_columns: Sequence[str],
) -> DistributionResult:
    """Compute distribution statistics for numeric features.

    Computes: count, mean, std, min, q25, q50, q75, max, skewness, kurtosis.

    Parameters
    ----------
    df : pandas.DataFrame
        Candidate DataFrame.
    feature_columns : Sequence[str]
        Numeric feature columns to analyze.

    Returns
    -------
    DistributionResult
        Container with stats DataFrame and feature count.
    """
    rows = []
    for col in feature_columns:
        series = df[col]
        valid = series.dropna()
        if len(valid) == 0:
            rows.append(
                {
                    "Feature": col,
                    "Count": 0,
                    "Mean": np.nan,
                    "Std": np.nan,
                    "Min": np.nan,
                    "Q25": np.nan,
                    "Q50": np.nan,
                    "Q75": np.nan,
                    "Max": np.nan,
                    "Skewness": np.nan,
                    "Kurtosis": np.nan,
                    "Missing": int(series.isna().sum()),
                    "MissingRatio": float(series.isna().sum() / max(len(series), 1)),
                }
            )
            continue

        rows.append(
            {
                "Feature": col,
                "Count": int(len(valid)),
                "Mean": float(valid.mean()),
                "Std": float(valid.std(ddof=1)) if len(valid) > 1 else 0.0,
                "Min": float(valid.min()),
                "Q25": float(valid.quantile(0.25)),
                "Q50": float(valid.quantile(0.50)),
                "Q75": float(valid.quantile(0.75)),
                "Max": float(valid.max()),
                "Skewness": float(valid.skew()) if len(valid) > 2 else np.nan,
                "Kurtosis": float(valid.kurtosis()) if len(valid) > 3 else np.nan,
                "Missing": int(series.isna().sum()),
                "MissingRatio": float(series.isna().sum() / max(len(series), 1)),
            }
        )

    stats_df = pd.DataFrame(rows)
    return DistributionResult(stats_df=stats_df, feature_count=len(feature_columns))


# ---------------------------------------------------------------------------
# Variance statistics
# ---------------------------------------------------------------------------


@dataclass
class VarianceResult:
    """Variance statistics container."""

    stats_df: pd.DataFrame
    feature_count: int


def compute_variance_stats(
    df: pd.DataFrame,
    feature_columns: Sequence[str],
) -> VarianceResult:
    """Compute variance statistics.

    CV (Coefficient of Variation) = std / mean.
    CV = N/A when mean ≈ 0 or negative.

    No CV selection rule applied here; this is descriptive only.

    Parameters
    ----------
    df : pandas.DataFrame
        Candidate DataFrame.
    feature_columns : Sequence[str]
        Numeric feature columns.

    Returns
    -------
    VarianceResult
        Container with stats DataFrame.
    """
    rows = []
    for col in feature_columns:
        series = df[col].dropna()
        if len(series) == 0:
            rows.append(
                {
                    "Feature": col,
                    "Count": 0,
                    "Mean": np.nan,
                    "Std": np.nan,
                    "Variance": np.nan,
                    "CV": "N/A",
                    "CV_Status": "N/A",
                }
            )
            continue

        mean = float(series.mean())
        std = float(series.std(ddof=1)) if len(series) > 1 else 0.0
        variance = std**2

        # CV = N/A if mean is near zero or negative
        if mean == 0 or abs(mean) < 1e-9:
            cv_str = "N/A"
            cv_status = "N/A"
        elif mean < 0:
            cv_str = "N/A"
            cv_status = "N/A_negative_mean"
        else:
            cv = std / mean
            cv_str = f"{cv:.4f}"
            cv_status = "valid"

        rows.append(
            {
                "Feature": col,
                "Count": int(len(series)),
                "Mean": mean,
                "Std": std,
                "Variance": variance,
                "CV": cv_str,
                "CV_Status": cv_status,
            }
        )

    stats_df = pd.DataFrame(rows)
    return VarianceResult(stats_df=stats_df, feature_count=len(feature_columns))


# ---------------------------------------------------------------------------
# Correlation matrices
# ---------------------------------------------------------------------------


@dataclass
class CorrelationResult:
    """Correlation matrices container."""

    pearson: pd.DataFrame
    spearman: pd.DataFrame
    feature_count: int


def compute_correlation_matrices(
    df: pd.DataFrame,
    feature_columns: Sequence[str],
) -> CorrelationResult:
    """Compute Pearson and Spearman correlation matrices.

    Only numeric features are included.

    Parameters
    ----------
    df : pandas.DataFrame
        Candidate DataFrame.
    feature_columns : Sequence[str]
        Numeric feature columns.

    Returns
    -------
    CorrelationResult
        Container with Pearson and Spearman matrices.
    """
    # Select only numeric columns
    numeric_cols = [
        col
        for col in feature_columns
        if col in df.columns and pd.api.types.is_numeric_dtype(df[col])
    ]

    if len(numeric_cols) == 0:
        empty_df = pd.DataFrame()
        return CorrelationResult(pearson=empty_df, spearman=empty_df, feature_count=0)

    # Subset to numeric columns
    sub_df = df[numeric_cols]

    # Compute correlation
    pearson = sub_df.corr(method="pearson", numeric_only=True)
    spearman = sub_df.corr(method="spearman", numeric_only=True)

    return CorrelationResult(pearson=pearson, spearman=spearman, feature_count=len(numeric_cols))


# ---------------------------------------------------------------------------
# Redundancy detection
# ---------------------------------------------------------------------------


@dataclass
class RedundancyResult:
    """Redundancy detection result."""

    pairs_df: pd.DataFrame
    high_correlation_count: int


def detect_redundancy(
    correlation_matrix: pd.DataFrame,
    *,
    threshold: float = 0.95,
) -> RedundancyResult:
    """Detect high-correlation feature pairs (redundancy candidates).

    Returns pairs with |correlation| >= threshold.

    Parameters
    ----------
    correlation_matrix : pandas.DataFrame
        Correlation matrix (Pearson or Spearman).
    threshold : float
        Correlation threshold (default 0.95).

    Returns
    -------
    RedundancyResult
        Container with pairs DataFrame and count.
    """
    if correlation_matrix.empty:
        return RedundancyResult(
            pairs_df=pd.DataFrame(columns=["Feature1", "Feature2", "Correlation"]),
            high_correlation_count=0,
        )

    features = list(correlation_matrix.columns)
    pairs = []

    for i in range(len(features)):
        for j in range(i + 1, len(features)):
            corr = correlation_matrix.iloc[i, j]
            if pd.notna(corr) and abs(corr) >= threshold:
                pairs.append(
                    {
                        "Feature1": features[i],
                        "Feature2": features[j],
                        "Correlation": float(corr),
                        "AbsCorrelation": abs(float(corr)),
                    }
                )

    pairs_df = pd.DataFrame(pairs)
    if not pairs_df.empty:
        pairs_df = pairs_df.sort_values("AbsCorrelation", ascending=False).reset_index(drop=True)

    return RedundancyResult(pairs_df=pairs_df, high_correlation_count=len(pairs_df))


# ---------------------------------------------------------------------------
# Outlier detection (IQR-based)
# ---------------------------------------------------------------------------


@dataclass
class OutlierResult:
    """Outlier detection result."""

    outlier_counts: pd.DataFrame  # Per feature outlier count
    outliers_per_feature: dict[str, pd.Series] = field(default_factory=dict)


def detect_outliers(
    df: pd.DataFrame,
    feature_columns: Sequence[str],
    *,
    iqr_multiplier: float = 1.5,
) -> OutlierResult:
    """Detect outliers using IQR method.

    Outlier if value < Q1 - iqr_multiplier * IQR or value > Q3 + iqr_multiplier * IQR.

    Parameters
    ----------
    df : pandas.DataFrame
        Candidate DataFrame.
    feature_columns : Sequence[str]
        Numeric feature columns.
    iqr_multiplier : float
        IQR multiplier (default 1.5).

    Returns
    -------
    OutlierResult
        Container with outlier counts and per-feature boolean Series.
    """
    rows = []
    outliers_per_feature = {}

    for col in feature_columns:
        series = df[col]
        valid = series.dropna()
        if len(valid) < 4:
            rows.append(
                {
                    "Feature": col,
                    "Count": len(series),
                    "Q1": np.nan,
                    "Q3": np.nan,
                    "IQR": np.nan,
                    "LowerBound": np.nan,
                    "UpperBound": np.nan,
                    "OutlierCount": 0,
                    "OutlierRatio": 0.0,
                }
            )
            continue

        q1 = float(valid.quantile(0.25))
        q3 = float(valid.quantile(0.75))
        iqr = q3 - q1
        lower = q1 - iqr_multiplier * iqr
        upper = q3 + iqr_multiplier * iqr

        # Mark outliers
        is_outlier = (series < lower) | (series > upper)
        outlier_count = int(is_outlier.sum())

        outliers_per_feature[col] = is_outlier

        rows.append(
            {
                "Feature": col,
                "Count": len(series),
                "Q1": q1,
                "Q3": q3,
                "IQR": iqr,
                "LowerBound": lower,
                "UpperBound": upper,
                "OutlierCount": outlier_count,
                "OutlierRatio": outlier_count / max(len(series), 1),
            }
        )

    outlier_counts = pd.DataFrame(rows)
    return OutlierResult(
        outlier_counts=outlier_counts,
        outliers_per_feature=outliers_per_feature,
    )


# ---------------------------------------------------------------------------
# Interpretability assessment
# ---------------------------------------------------------------------------


@dataclass
class InterpretabilityResult:
    """Interpretability assessment result."""

    assessment_df: pd.DataFrame


def assess_interpretability(
    feature_columns: Sequence[str],
    feature_descriptions: dict[str, str] | None = None,
) -> InterpretabilityResult:
    """Assess business interpretability of candidate features.

    Returns assessment based on feature name and description.

    Parameters
    ----------
    feature_columns : Sequence[str]
        Feature columns to assess.
    feature_descriptions : dict[str, str], optional
        Map of feature name to business description.

    Returns
    -------
    InterpretabilityResult
        Container with assessment DataFrame.
    """
    feature_descriptions = feature_descriptions or {}
    rows = []

    for col in feature_columns:
        description = feature_descriptions.get(col, "")
        # Heuristic: standard features are well-known RFM/behavioral
        interpretable_features = {
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
        is_interpretable = col in interpretable_features
        assessment = (
            "Interpretable" if is_interpretable else "Unknown - requires domain expert review"
        )
        rationale = (
            f"Feature {col!r} has standard business interpretation."
            if is_interpretable
            else f"Feature {col!r} is not in standard interpretable list. "
            "Requires domain expert review."
        )

        rows.append(
            {
                "Feature": col,
                "Description": description,
                "Interpretability": assessment,
                "Rationale": rationale,
            }
        )

    assessment_df = pd.DataFrame(rows)
    return InterpretabilityResult(assessment_df=assessment_df)


# ---------------------------------------------------------------------------
# Shapiro-Wilk normality test (optional diagnostic)
# ---------------------------------------------------------------------------


def shapiro_wilk_diagnostic(
    df: pd.DataFrame,
    feature_columns: Sequence[str],
    *,
    alpha: float = 0.05,
    max_sample_size: int = 5000,
    random_seed: int = 42,
) -> pd.DataFrame:
    """Run Shapiro-Wilk normality test (optional diagnostic only).

    Shapiro-Wilk is an OPTIONAL DIAGNOSTIC.
    Does NOT auto-decide KEEP/DROP features.

    Parameters
    ----------
    df : pandas.DataFrame
        Candidate DataFrame.
    feature_columns : Sequence[str]
        Numeric feature columns.
    alpha : float
        Significance level.
    max_sample_size : int
        Maximum sample size for Shapiro-Wilk (subsample if larger).
    random_seed : int
        Random seed for subsampling.

    Returns
    -------
    pandas.DataFrame
        Results with columns: Feature, Statistic, PValue, IsNormal (alpha=0.05).
    """
    rows = []
    rng = np.random.default_rng(random_seed)

    for col in feature_columns:
        series = df[col].dropna()
        if len(series) < 3:
            rows.append(
                {
                    "Feature": col,
                    "Statistic": np.nan,
                    "PValue": np.nan,
                    "SampleSize": len(series),
                    "IsNormal": "N/A",
                    "Note": "Sample too small for Shapiro-Wilk",
                }
            )
            continue

        # Subsample if too large
        if len(series) > max_sample_size:
            series = pd.Series(rng.choice(series.values, size=max_sample_size, replace=False))

        try:
            stat, p_value = stats.shapiro(series)
            is_normal = "Yes" if p_value > alpha else "No"
            rows.append(
                {
                    "Feature": col,
                    "Statistic": float(stat),
                    "PValue": float(p_value),
                    "SampleSize": len(series),
                    "IsNormal": is_normal,
                    "Note": "Optional diagnostic only - does not auto-decide KEEP/DROP",
                }
            )
        except Exception as exc:  # noqa: BLE001
            rows.append(
                {
                    "Feature": col,
                    "Statistic": np.nan,
                    "PValue": np.nan,
                    "SampleSize": len(series),
                    "IsNormal": "Error",
                    "Note": f"Shapiro-Wilk failed: {exc}",
                }
            )

    return pd.DataFrame(rows)
