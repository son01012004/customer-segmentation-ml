"""Feature eligibility gate for FE-06.

Determines which features from customer_candidates.parquet are eligible
for the final clustering matrix, based on:
- Layer classification from FE-05 (CANDIDATE only)
- FE-05 selection status (RETAIN_CANDIDATE / PENDING_REVIEW)
- Numeric dtype
- Variance > 0
- Missing ratio <= threshold
- No identifier leakage

Hard constraints:
- CustomerID is NEVER included in the clustering matrix.
- BASE_REFERENCE features are NOT included.
- UNSUPPORTED features are NOT included.
- PENDING_REVIEW features are included as ELIGIBLE_WORKING_ASSUMPTION (not final).
- Redundancy is DIAGNOSTIC ONLY — no auto-drop.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from customer_segmentation.features.config_loader import (
    load_feature_engineering_config,
    resolve_feature_engineering_config_path,
)

__all__ = [
    "EligibilityStatus",
    "FeatureEligibility",
    "apply_feature_eligibility",
]


class EligibilityStatus:
    """FE-06 eligibility status."""

    ELIGIBLE = "ELIGIBLE"
    ELIGIBLE_WORKING_ASSUMPTION = "ELIGIBLE_WORKING_ASSUMPTION"
    EXCLUDED = "EXCLUDED"
    PENDING_HUMAN = "PENDING_HUMAN"  # Escalate to FE-05


@dataclass
class FeatureEligibility:
    """Eligibility result for a single feature."""

    feature: str
    fe05_layer: str | None
    fe05_decision: str | None
    fe06_status: str
    eligibility_reason: str
    variance: float | None
    missing_ratio: float | None
    is_numeric: bool


@dataclass
class EligibilityResult:
    """Result of feature eligibility gate."""

    eligible_features: list[str]
    excluded_features: list[str]
    eligibility_details: dict[str, FeatureEligibility]
    metadata_features: list[str]  # CustomerID only


def _get_fe05_candidate_features(config) -> set[str]:
    """Get set of CANDIDATE feature names from FE-05 config."""
    return set(config.layer_classification.CANDIDATE)


def _get_fe05_status_map(feature_selection_csv_path: str | Path) -> dict[str, str]:
    """Read FE-05 feature selection decisions from CSV.

    Parameters
    ----------
    feature_selection_csv_path : str | Path
        Path to reports/fe05/feature_selection_report.csv

    Returns
    -------
    dict[str, str]
        Map of feature name -> Decision.
    """

    path = Path(feature_selection_csv_path)
    if not path.exists():
        # Return empty map if file not available
        return {}

    df = pd.read_csv(path, dtype=str)
    if "Feature" not in df.columns or "Decision" not in df.columns:
        return {}

    return dict(zip(df["Feature"].tolist(), df["Decision"].tolist(), strict=False))


def _map_fe05_decision_to_fe06_status(
    fe05_decision: str | None,
) -> tuple[str, str]:
    """Map FE-05 decision to FE-06 eligibility status.

    Parameters
    ----------
    fe05_decision : str | None
        FE-05 decision (RETAIN_CANDIDATE, PENDING_REVIEW, EXCLUDE, ADJUST, UNSUPPORTED).

    Returns
    -------
    tuple[str, str]
        (fe06_status, reason).
    """
    if fe05_decision is None:
        return EligibilityStatus.ELIGIBLE_WORKING_ASSUMPTION, "no FE-05 decision found"

    decision_map = {
        "RETAIN_CANDIDATE": (EligibilityStatus.ELIGIBLE, "FE-05 RETAIN_CANDIDATE"),
        "PENDING_REVIEW": (
            EligibilityStatus.ELIGIBLE_WORKING_ASSUMPTION,
            "FE-05 PENDING_REVIEW — WORKING_ASSUMPTION",
        ),
        "EXCLUDE": (EligibilityStatus.EXCLUDED, "FE-05 EXCLUDE"),
        "ADJUST": (EligibilityStatus.PENDING_HUMAN, "FE-05 ADJUST — escalate to FE-05"),
        "UNSUPPORTED": (EligibilityStatus.EXCLUDED, "FE-05 UNSUPPORTED"),
    }
    return decision_map.get(
        fe05_decision,
        (EligibilityStatus.ELIGIBLE_WORKING_ASSUMPTION, f"unknown FE-05 decision: {fe05_decision}"),
    )


def apply_feature_eligibility(
    df: pd.DataFrame,
    customer_key: str = "CustomerID",
    feature_selection_csv_path: str | Path | None = None,
    max_missing_ratio: float = 0.5,
) -> EligibilityResult:
    """Apply feature eligibility gate.

    Parameters
    ----------
    df : pandas.DataFrame
        Customer candidates DataFrame.
    customer_key : str
        Customer ID column name.
    feature_selection_csv_path : str | Path | None
        Path to FE-05 feature_selection_report.csv.
        If None, uses default path.
    max_missing_ratio : float
        Maximum allowed missing ratio (default 0.5).

    Returns
    -------
    EligibilityResult
        Eligibility decisions for all columns.
    """
    # Load FE-05 config
    fe05_config_path = resolve_feature_engineering_config_path()
    if fe05_config_path and fe05_config_path.exists():
        fe05_config = load_feature_engineering_config(fe05_config_path)
        candidate_features = _get_fe05_candidate_features(fe05_config)
    else:
        candidate_features = set()

    # Load FE-05 selection decisions
    if feature_selection_csv_path is None:
        default_path = Path("reports/fe05/feature_selection_report.csv")
        fe05_decisions = _get_fe05_status_map(default_path) if default_path.exists() else {}
    else:
        fe05_decisions = _get_fe05_status_map(feature_selection_csv_path)

    details: dict[str, FeatureEligibility] = {}
    eligible_features: list[str] = []
    excluded_features: list[str] = []
    metadata_features: list[str] = []

    for col in df.columns:
        if col == customer_key:
            # CustomerID is always metadata, never clustering feature
            metadata_features.append(col)
            details[col] = FeatureEligibility(
                feature=col,
                fe05_layer=None,
                fe05_decision=None,
                fe06_status="METADATA_ONLY",
                eligibility_reason="CustomerID is identifier; never in clustering matrix",
                variance=None,
                missing_ratio=0.0,
                is_numeric=pd.api.types.is_numeric_dtype(df[col]),
            )
            continue

        if col not in candidate_features:
            # Not in CANDIDATE layer
            excluded_features.append(col)
            details[col] = FeatureEligibility(
                feature=col,
                fe05_layer=None,
                fe05_decision=fe05_decisions.get(col),
                fe06_status=EligibilityStatus.EXCLUDED,
                eligibility_reason="not in FE-05 CANDIDATE layer",
                variance=None,
                missing_ratio=0.0,
                is_numeric=pd.api.types.is_numeric_dtype(df[col]),
            )
            continue

        # Feature is in CANDIDATE layer
        fe05_decision = fe05_decisions.get(col)
        fe06_status, reason = _map_fe05_decision_to_fe06_status(fe05_decision)

        if fe06_status == EligibilityStatus.EXCLUDED:
            excluded_features.append(col)
            details[col] = FeatureEligibility(
                feature=col,
                fe05_layer="CANDIDATE",
                fe05_decision=fe05_decision,
                fe06_status=fe06_status,
                eligibility_reason=reason,
                variance=None,
                missing_ratio=0.0,
                is_numeric=pd.api.types.is_numeric_dtype(df[col]),
            )
            continue

        if fe06_status == EligibilityStatus.PENDING_HUMAN:
            excluded_features.append(col)
            details[col] = FeatureEligibility(
                feature=col,
                fe05_layer="CANDIDATE",
                fe05_decision=fe05_decision,
                fe06_status=fe06_status,
                eligibility_reason=reason + " — escalate to FE-05",
                variance=None,
                missing_ratio=0.0,
                is_numeric=pd.api.types.is_numeric_dtype(df[col]),
            )
            continue

        # Numeric check
        if not pd.api.types.is_numeric_dtype(df[col]):
            excluded_features.append(col)
            details[col] = FeatureEligibility(
                feature=col,
                fe05_layer="CANDIDATE",
                fe05_decision=fe05_decision,
                fe06_status=EligibilityStatus.EXCLUDED,
                eligibility_reason="non-numeric dtype",
                variance=None,
                missing_ratio=0.0,
                is_numeric=False,
            )
            continue

        # Variance check
        valid = df[col].dropna()
        variance = 0.0 if len(valid) <= 1 else float(valid.var(ddof=1))
        if variance == 0:
            excluded_features.append(col)
            details[col] = FeatureEligibility(
                feature=col,
                fe05_layer="CANDIDATE",
                fe05_decision=fe05_decision,
                fe06_status=EligibilityStatus.EXCLUDED,
                eligibility_reason="zero variance",
                variance=variance,
                missing_ratio=0.0,
                is_numeric=True,
            )
            continue

        # Missing ratio check
        missing_ratio = float(df[col].isna().sum() / max(len(df), 1))
        if missing_ratio > max_missing_ratio:
            excluded_features.append(col)
            details[col] = FeatureEligibility(
                feature=col,
                fe05_layer="CANDIDATE",
                fe05_decision=fe05_decision,
                fe06_status=EligibilityStatus.EXCLUDED,
                eligibility_reason=f"missing_ratio={missing_ratio:.3f} > {max_missing_ratio}",
                variance=variance,
                missing_ratio=missing_ratio,
                is_numeric=True,
            )
            continue

        # All checks passed — eligible
        eligible_features.append(col)
        details[col] = FeatureEligibility(
            feature=col,
            fe05_layer="CANDIDATE",
            fe05_decision=fe05_decision,
            fe06_status=fe06_status,
            eligibility_reason=reason,
            variance=variance,
            missing_ratio=missing_ratio,
            is_numeric=True,
        )

    return EligibilityResult(
        eligible_features=eligible_features,
        excluded_features=excluded_features,
        eligibility_details=details,
        metadata_features=metadata_features,
    )
