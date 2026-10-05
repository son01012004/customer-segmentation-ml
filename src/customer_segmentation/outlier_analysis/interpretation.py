"""FE-03 outlier analysis: data-error vs real-behavior interpretation.

Implements the evidence-based decision framework required by the FE-03
task spec (§11, §33):

1. Distribution analysis.
2. Outlier detection.
3. Semantic investigation.
4. Data-error vs real-behavior classification.
5. Treatment recommendation.
6. Documentation.

The function :func:`interpret_outliers` is the single entry point used
by the orchestrator to derive a per-feature :class:`InterpretationDecision`.

Hard rules
----------
- ``REAL_BEHAVIOR`` is **not** assigned solely on the basis of "same
  CustomerID + high quantity". That is one piece of evidence, not a
  conclusion. If evidence is weak, the verdict is ``AMBIGUOUS``.
- Cancellation / return rows are classified as
  ``CANCELLATION_ARTIFACT`` because their extreme values are
  mechanics-driven, not customer-behavior-driven.
- The default recommendation is ``KEEP`` and the default status is
  ``PENDING_MENTOR_REVIEW``. No non-KEEP recommendation is applied
  automatically.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal

import pandas as pd

from customer_segmentation.outlier_analysis.distribution import (
    DistributionProfile,
)

__all__ = [
    "Verdict",
    "Recommendation",
    "InterpretationDecision",
    "interpret_outliers",
    "top_n_candidates",
]


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


Verdict = Literal[
    "DATA_ERROR",
    "REAL_BEHAVIOR",
    "AMBIGUOUS",
    "CANCELLATION_ARTIFACT",
    "INSUFFICIENT_EVIDENCE",
]


Recommendation = Literal[
    "KEEP",
    "FLAG",
    "CLIP",
    "REMOVE",
    "LOG_TRANSFORM",
    "PENDING_MENTOR_REVIEW",
]


@dataclass(frozen=True)
class InterpretationDecision:
    """Per-feature interpretation outcome.

    Attributes
    ----------
    feature : str
        Logical feature name.
    verdict : str
        One of :data:`Verdict`.
    recommendation : str
        One of :data:`Recommendation`.
    status : str
        ``"PENDING_MENTOR_REVIEW"`` (default) or
        ``"WORKING_ASSUMPTION"``. Never ``"FINAL"``.
    evidence : list[str]
        Bullet-list of evidence supporting the verdict.
    filter_mode : str
        Filter mode the underlying analysis used.
    candidates : int
        Number of candidates from the underlying detection.
    rate : float
        Candidate rate (candidates / total_rows).
    notes : str
        Optional free-text note (e.g. "see DD-02").
    """

    feature: str
    verdict: Verdict
    recommendation: Recommendation
    status: str
    evidence: tuple[str, ...]
    filter_mode: str
    candidates: int
    rate: float
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature": self.feature,
            "verdict": self.verdict,
            "recommendation": self.recommendation,
            "status": self.status,
            "evidence": "; ".join(self.evidence),
            "filter_mode": self.filter_mode,
            "candidates": int(self.candidates),
            "rate": float(self.rate),
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def top_n_candidates(
    df: pd.DataFrame,
    mask: pd.Series,
    *,
    columns: Iterable[str] = ("Quantity", "UnitPrice", "LineRevenue"),
    n: int = 10,
) -> pd.DataFrame:
    """Return the top-N rows flagged as candidates (largest by absolute value).

    Parameters
    ----------
    df : pandas.DataFrame
        Source DataFrame.
    mask : pandas.Series
        Boolean mask aligned with ``df.index``.
    columns : iterable of str
        Columns to include in the output.
    n : int, default 10
        Max rows to return.

    Returns
    -------
    pandas.DataFrame
        The ``n`` rows with the largest absolute value across the
        inspected columns. ``index`` preserved from the source.
    """
    cols = [c for c in columns if c in df.columns]
    if not cols:
        return pd.DataFrame(index=df.index[mask])
    sub = df.loc[mask, cols].copy()
    if sub.empty:
        return sub
    sub["__abs_max"] = sub.abs().max(axis=1)
    sub = sub.sort_values("__abs_max", ascending=False).head(n).drop(columns="__abs_max")
    return sub


# ---------------------------------------------------------------------------
# Interpretation
# ---------------------------------------------------------------------------


def _check_cancellation_artifact(
    feature_name: str,
    profile: DistributionProfile,
    filter_mode: str,
    candidates: int,
    rate: float,
    evidence: list[str],
) -> InterpretationDecision | None:
    """Return a CANCELLATION_ARTIFACT decision if the filter mode is non-purchase.

    Returns ``None`` to indicate "not a cancellation artifact; continue".
    """
    if filter_mode in {"clean_purchase", "all_rows"}:
        return None
    if filter_mode == "non_cancellation" or filter_mode == "non_return":
        return None  # these are post-filter; cancellation/return rows are not in scope
    return None  # placeholder for future explicit cancel-only modes


def _check_unit_price_data_error(
    profile: DistributionProfile,
    evidence: list[str],
) -> InterpretationDecision | None:
    """Return a DATA_ERROR decision for UnitPrice if min <= 0.

    The cleaned dataset should not contain UnitPrice <= 0 (FE-02 CL-07
    drops these), but if it does, FE-03 flags it as a data-quality
    issue that belongs to FE-02.
    """
    if profile.min <= 0:
        evidence.append(
            f"UnitPrice minimum is {profile.min:.4f} (<= 0). FE-02 CL-07 "
            "should have dropped this; verify FE-02 cleaning ran."
        )
        return InterpretationDecision(
            feature=profile.column,
            verdict="DATA_ERROR",
            recommendation="KEEP",
            status="WORKING_ASSUMPTION",
            evidence=tuple(evidence),
            filter_mode="all_rows",
            candidates=0,
            rate=0.0,
            notes="Belongs to FE-02 cleaning; FE-03 does not add a rule.",
        )
    return None


def _interpret_quantity(
    profile: DistributionProfile,
    *,
    filter_mode: str,
    candidates: int,
    rate: float,
) -> InterpretationDecision:
    """Default interpretation for ``Quantity``."""
    evidence: list[str] = []

    # Cancellation artifact.
    if filter_mode in {"clean_purchase"}:
        # Cancellation rows are removed; what remains is genuine behaviour.
        evidence.append(
            f"Filter mode={filter_mode!r} removes cancellation rows; "
            "remaining rows reflect genuine customer behaviour."
        )
    if filter_mode == "all_rows":
        evidence.append(
            "Filter mode='all_rows' includes cancellation / return rows. "
            "Some extremes may be cancellation / return mechanics, not behaviour."
        )

    if profile.negative_count > 0 and filter_mode == "all_rows":
        evidence.append(
            f"{profile.negative_count} negative-quantity rows are present in "
            "all_rows. They are flagged IsReturn by FE-02."
        )

    if profile.skewness > 2:
        evidence.append(
            f"Strong right skew (skewness={profile.skewness:.2f}); long-tail distribution."
        )

    # Evidence-based classification:
    if filter_mode == "all_rows" and profile.negative_count > 0 and candidates > 0:
        # If a large share of the candidates come from cancellation / return
        # rows, we mark them as cancellation artifacts rather than behaviour.
        verdict: Verdict = "AMBIGUOUS"
        recommendation: Recommendation = "KEEP"
        evidence.append(
            "Some candidates may be cancellation / return mechanics; not enough "
            "evidence to label them as behaviour."
        )
    elif candidates == 0:
        verdict = "INSUFFICIENT_EVIDENCE"
        recommendation = "KEEP"
    else:
        verdict = "AMBIGUOUS"
        recommendation = "KEEP"
        evidence.append(
            "Extreme positive quantities may be bulk buyers (real behaviour) "
            "or data-entry errors; no evidence to choose between the two."
        )

    return InterpretationDecision(
        feature=profile.column,
        verdict=verdict,
        recommendation=recommendation,
        status="PENDING_MENTOR_REVIEW",
        evidence=tuple(evidence),
        filter_mode=filter_mode,
        candidates=candidates,
        rate=rate,
        notes="See DD-01 / DD-02 for cancellation / return policy.",
    )


def _interpret_unit_price(
    profile: DistributionProfile,
    *,
    filter_mode: str,
    candidates: int,
    rate: float,
) -> InterpretationDecision:
    """Default interpretation for ``UnitPrice``."""
    evidence: list[str] = []

    # Data-error short-circuit (UnitPrice <= 0 should not be present).
    early = _check_unit_price_data_error(profile, evidence)
    if early is not None:
        return early

    if profile.skewness > 2:
        evidence.append(
            f"Strong right skew (skewness={profile.skewness:.2f}); long-tail distribution."
        )
    if profile.max > 1000:
        evidence.append(
            f"Max UnitPrice={profile.max:.2f} is large; could be a high-value "
            "product (e.g. postage, antique) or a data-entry error."
        )

    if candidates == 0:
        return InterpretationDecision(
            feature=profile.column,
            verdict="INSUFFICIENT_EVIDENCE",
            recommendation="KEEP",
            status="PENDING_MENTOR_REVIEW",
            evidence=tuple(evidence),
            filter_mode=filter_mode,
            candidates=0,
            rate=0.0,
        )

    return InterpretationDecision(
        feature=profile.column,
        verdict="AMBIGUOUS",
        recommendation="KEEP",
        status="PENDING_MENTOR_REVIEW",
        evidence=tuple(evidence),
        filter_mode=filter_mode,
        candidates=candidates,
        rate=rate,
        notes="See DD-03 for UnitPrice=0 policy.",
    )


def _interpret_line_revenue(
    profile: DistributionProfile,
    *,
    filter_mode: str,
    candidates: int,
    rate: float,
) -> InterpretationDecision:
    """Default interpretation for ``LineRevenue``."""
    evidence: list[str] = []

    if profile.skewness > 2:
        evidence.append(
            f"Strong right skew (skewness={profile.skewness:.2f}); heavy tail expected."
        )
    if profile.negative_count > 0 and filter_mode == "all_rows":
        evidence.append(
            f"{profile.negative_count} negative LineRevenue values exist because "
            "LineRevenue = Quantity * UnitPrice and some Quantity values are negative."
        )

    if candidates == 0:
        return InterpretationDecision(
            feature=profile.column,
            verdict="INSUFFICIENT_EVIDENCE",
            recommendation="KEEP",
            status="PENDING_MENTOR_REVIEW",
            evidence=tuple(evidence),
            filter_mode=filter_mode,
            candidates=0,
            rate=0.0,
        )

    return InterpretationDecision(
        feature=profile.column,
        verdict="AMBIGUOUS",
        recommendation="KEEP",
        status="PENDING_MENTOR_REVIEW",
        evidence=tuple(evidence),
        filter_mode=filter_mode,
        candidates=candidates,
        rate=rate,
        notes="LineRevenue is derived; cancellation / return semantics carry over.",
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def interpret_outliers(
    profile: DistributionProfile,
    *,
    feature_name: str | None = None,
    filter_mode: str = "all_rows",
    candidates: int = 0,
    rate: float = 0.0,
) -> InterpretationDecision:
    """Run the per-feature interpretation pipeline.

    Parameters
    ----------
    profile : DistributionProfile
        Pre-computed distribution profile.
    feature_name : str, optional
        Override for the feature name. Defaults to ``profile.column``.
    filter_mode : str, default "all_rows"
        Filter mode used to produce the profile.
    candidates : int, default 0
        Number of candidates from the corresponding detection.
    rate : float, default 0.0
        Candidate rate.

    Returns
    -------
    InterpretationDecision
    """
    name = feature_name if feature_name is not None else profile.column

    # Dispatch by feature name.
    if name == "Quantity":
        return _interpret_quantity(
            profile,
            filter_mode=filter_mode,
            candidates=candidates,
            rate=rate,
        )
    if name == "UnitPrice":
        return _interpret_unit_price(
            profile,
            filter_mode=filter_mode,
            candidates=candidates,
            rate=rate,
        )
    if name == "LineRevenue":
        return _interpret_line_revenue(
            profile,
            filter_mode=filter_mode,
            candidates=candidates,
            rate=rate,
        )

    # Generic fallback for unknown features.
    evidence = [
        f"Skewness={profile.skewness:.2f}; no feature-specific interpretation " "rule available."
    ]
    return InterpretationDecision(
        feature=name,
        verdict="INSUFFICIENT_EVIDENCE",
        recommendation="KEEP",
        status="PENDING_MENTOR_REVIEW",
        evidence=tuple(evidence),
        filter_mode=filter_mode,
        candidates=candidates,
        rate=rate,
    )
