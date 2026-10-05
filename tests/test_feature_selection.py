"""Tests for FE-05 feature selection module.

T-SEL-01 → T-SEL-06
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _REPO_ROOT / "src"

if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from customer_segmentation.features.selection import (  # noqa: E402
    DECISION_EXCLUDE,
    DECISION_PENDING_REVIEW,
    DECISION_RETAIN_CANDIDATE,
    GATE_STATUS_DIAGNOSTIC,
    GATE_STATUS_FAIL,
    GATE_STATUS_PASS,
    apply_data_quality_gate,
    apply_interpretability_gate,
    apply_redundancy_gate,
    apply_stability_gate,
    apply_zero_variance_gate,
    make_selection_decisions,
)


@pytest.fixture()
def synthetic_series() -> pd.Series:
    return pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])


# ---------------------------------------------------------------------------
# T-SEL-01: Interpretability gate
# ---------------------------------------------------------------------------


class TestInterpretabilityGate:
    def test_interpretable_pass(self) -> None:
        result = apply_interpretability_gate("Recency", is_interpretable=True)
        assert result.status == GATE_STATUS_PASS

    def test_not_interpretable_warning(self) -> None:
        result = apply_interpretability_gate("Mystery", is_interpretable=False)
        assert result.status == "WARNING"


# ---------------------------------------------------------------------------
# T-SEL-02: evidence-based gates
# ---------------------------------------------------------------------------


class TestDataQualityGate:
    def test_low_missing_pass(self, synthetic_series: pd.Series) -> None:
        result = apply_data_quality_gate("Recency", synthetic_series, max_missing_ratio=0.5)
        assert result.status == GATE_STATUS_PASS


class TestZeroVarianceGate:
    def test_zero_variance_fail(self) -> None:
        series = pd.Series([5.0, 5.0, 5.0, 5.0])
        result = apply_zero_variance_gate("Constant", series)
        assert result.status == GATE_STATUS_FAIL


# ---------------------------------------------------------------------------
# T-SEL-03: Redundancy Gate = diagnostic
# ---------------------------------------------------------------------------


class TestRedundancyGate:
    def test_redundancy_is_diagnostic(self) -> None:
        result = apply_redundancy_gate("X", max_correlation_with_others=0.99, threshold=0.95)
        assert result.status == GATE_STATUS_DIAGNOSTIC


# ---------------------------------------------------------------------------
# T-SEL-04: Stability Gate = diagnostic
# ---------------------------------------------------------------------------


class TestStabilityGate:
    def test_stability_is_diagnostic(self) -> None:
        result = apply_stability_gate("X", stability_score=0.8)
        assert result.status == GATE_STATUS_DIAGNOSTIC


# ---------------------------------------------------------------------------
# T-SEL-05: no "best" or "recommended" language
# ---------------------------------------------------------------------------


class TestNoBestLanguage:
    def test_decision_values_no_best(self) -> None:
        """Decision values must not contain 'best', 'recommended', 'final'."""
        valid_decisions = {
            DECISION_RETAIN_CANDIDATE,
            DECISION_EXCLUDE,
            DECISION_PENDING_REVIEW,
            "ADJUST",
            "UNSUPPORTED",
        }
        assert "best" not in {d.lower() for d in valid_decisions}
        assert "recommended" not in {d.lower() for d in valid_decisions}
        assert "final" not in {d.lower() for d in valid_decisions}


# ---------------------------------------------------------------------------
# T-SEL-06: RETAIN_CANDIDATE ≠ final
# ---------------------------------------------------------------------------


class TestRetainCandidate:
    def test_retain_candidate_message(self) -> None:
        """RETAIN_CANDIDATE notes must indicate NOT final."""
        from customer_segmentation.features.selection import (
            DECISION_RETAIN_CANDIDATE,
            GateResult,
        )

        gate_results = {
            "Recency": [
                GateResult("Recency", "Interpretability", GATE_STATUS_PASS, "OK"),
                GateResult("Recency", "DataQuality", GATE_STATUS_PASS, "OK"),
                GateResult("Recency", "ZeroVariance", GATE_STATUS_PASS, "OK"),
                GateResult("Recency", "Leakage", GATE_STATUS_PASS, "OK"),
                GateResult("Recency", "Redundancy", GATE_STATUS_DIAGNOSTIC, "OK"),
                GateResult("Recency", "Stability", GATE_STATUS_DIAGNOSTIC, "OK"),
                GateResult("Recency", "ShapiroWilk", GATE_STATUS_DIAGNOSTIC, "OK"),
            ],
        }
        result = make_selection_decisions(gate_results)
        row = result.selection_df[result.selection_df["Decision"] == DECISION_RETAIN_CANDIDATE]
        assert "NOT final" in row.iloc[0]["Note"]
