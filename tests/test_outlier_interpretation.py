"""Unit tests for :mod:`customer_segmentation.outlier_analysis.interpretation`.

Uses synthetic DistributionProfile objects. No raw data, no FE-02.
"""

from __future__ import annotations

import pandas as pd
import pytest

from customer_segmentation.outlier_analysis.distribution import distribution_profile
from customer_segmentation.outlier_analysis.interpretation import (
    InterpretationDecision,
    interpret_outliers,
    top_n_candidates,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def quantity_profile_all_rows() -> pd.Series:
    return pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 100.0, -10.0], name="Quantity")


@pytest.fixture()
def quantity_profile_clean_purchase() -> pd.Series:
    return pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 100.0], name="Quantity")


@pytest.fixture()
def unitprice_profile_clean() -> pd.Series:
    return pd.Series([0.5, 1.0, 2.0, 3.0, 5.0, 100.0, 1000.0], name="UnitPrice")


@pytest.fixture()
def unitprice_profile_zero() -> pd.Series:
    return pd.Series([0.0, 1.0, 2.0, 5.0], name="UnitPrice")


@pytest.fixture()
def linerevenue_profile() -> pd.Series:
    return pd.Series([-10.0, -5.0, 0.0, 1.0, 2.0, 5.0, 100.0, 1000.0, 5000.0], name="LineRevenue")


# ---------------------------------------------------------------------------
# Interpretation dispatch
# ---------------------------------------------------------------------------


class TestInterpretQuantity:
    def test_clean_purchase_skewed(self, quantity_profile_clean_purchase: pd.Series) -> None:
        prof = distribution_profile(quantity_profile_clean_purchase)
        decision = interpret_outliers(prof, filter_mode="clean_purchase", candidates=1, rate=0.125)
        assert isinstance(decision, InterpretationDecision)
        assert decision.feature == "Quantity"
        assert decision.filter_mode == "clean_purchase"
        # We expect KEEP / AMBIGUOUS / PENDING_MENTOR_REVIEW by default.
        assert decision.recommendation == "KEEP"
        assert decision.status == "PENDING_MENTOR_REVIEW"

    def test_all_rows_with_negatives(self, quantity_profile_all_rows: pd.Series) -> None:
        prof = distribution_profile(quantity_profile_all_rows)
        decision = interpret_outliers(prof, filter_mode="all_rows", candidates=2, rate=0.22)
        assert decision.verdict in {"AMBIGUOUS", "INSUFFICIENT_EVIDENCE"}
        assert decision.recommendation == "KEEP"
        # The evidence list must mention negatives.
        assert any("negative" in e.lower() for e in decision.evidence)

    def test_zero_candidates(self) -> None:
        prof = distribution_profile(pd.Series([1.0, 2.0, 3.0], name="Quantity"))
        decision = interpret_outliers(prof, filter_mode="clean_purchase", candidates=0, rate=0.0)
        assert decision.verdict == "INSUFFICIENT_EVIDENCE"
        assert decision.recommendation == "KEEP"


class TestInterpretUnitPrice:
    def test_clean_unitprice(self, unitprice_profile_clean: pd.Series) -> None:
        prof = distribution_profile(unitprice_profile_clean)
        decision = interpret_outliers(prof, filter_mode="all_rows", candidates=2, rate=0.28)
        assert decision.verdict == "AMBIGUOUS"
        assert decision.recommendation == "KEEP"
        assert decision.status == "PENDING_MENTOR_REVIEW"

    def test_zero_unitprice_data_error(self, unitprice_profile_zero: pd.Series) -> None:
        prof = distribution_profile(unitprice_profile_zero)
        decision = interpret_outliers(prof, filter_mode="all_rows", candidates=0, rate=0.0)
        assert decision.verdict == "DATA_ERROR"
        assert decision.recommendation == "KEEP"
        assert decision.status == "WORKING_ASSUMPTION"
        # Notes mention FE-02 ownership.
        assert "FE-02" in decision.notes


class TestInterpretLineRevenue:
    def test_negatives_present(self, linerevenue_profile: pd.Series) -> None:
        prof = distribution_profile(linerevenue_profile)
        decision = interpret_outliers(prof, filter_mode="all_rows", candidates=2, rate=0.22)
        assert decision.verdict == "AMBIGUOUS"
        assert decision.recommendation == "KEEP"
        assert any("negative" in e.lower() for e in decision.evidence)


class TestInterpretUnknownFeature:
    def test_unknown_feature_falls_back(self) -> None:
        s = pd.Series([1.0, 2.0, 3.0], name="CustomFeature")
        prof = distribution_profile(s)
        decision = interpret_outliers(prof, filter_mode="all_rows", candidates=1, rate=0.33)
        assert decision.feature == "CustomFeature"
        assert decision.verdict == "INSUFFICIENT_EVIDENCE"
        assert decision.recommendation == "KEEP"
        assert decision.status == "PENDING_MENTOR_REVIEW"


# ---------------------------------------------------------------------------
# to_dict()
# ---------------------------------------------------------------------------


class TestDecisionSerialization:
    def test_to_dict_round_trip(self) -> None:
        d = InterpretationDecision(
            feature="Quantity",
            verdict="AMBIGUOUS",
            recommendation="KEEP",
            status="PENDING_MENTOR_REVIEW",
            evidence=("a", "b"),
            filter_mode="clean_purchase",
            candidates=3,
            rate=0.1,
            notes="",
        )
        out = d.to_dict()
        assert out["feature"] == "Quantity"
        assert out["verdict"] == "AMBIGUOUS"
        assert out["recommendation"] == "KEEP"
        assert out["status"] == "PENDING_MENTOR_REVIEW"
        assert out["evidence"] == "a; b"
        assert out["candidates"] == 3
        assert out["rate"] == 0.1
        assert out["filter_mode"] == "clean_purchase"
        assert out["notes"] == ""


# ---------------------------------------------------------------------------
# top_n_candidates
# ---------------------------------------------------------------------------


class TestTopNCandidates:
    def test_returns_n_largest_by_abs_max(self) -> None:
        df = pd.DataFrame(
            {
                "Quantity": [1.0, 2.0, 100.0, 50.0, -200.0],
                "UnitPrice": [5.0, 5.0, 1.0, 2.0, 1.0],
            }
        )
        mask = pd.Series([True, True, True, True, True])
        out = top_n_candidates(df, mask, columns=["Quantity", "UnitPrice"], n=3)
        assert len(out) == 3
        # The largest absolute quantity (-200) must be in the top 3.
        assert -200.0 in out["Quantity"].tolist()

    def test_empty_mask(self) -> None:
        df = pd.DataFrame({"Quantity": [1.0, 2.0]})
        mask = pd.Series([False, False])
        out = top_n_candidates(df, mask, columns=["Quantity"])
        assert out.empty

    def test_missing_columns(self) -> None:
        df = pd.DataFrame({"A": [1.0]})
        mask = pd.Series([True])
        out = top_n_candidates(df, mask, columns=["Quantity", "UnitPrice"])
        assert out.empty

    def test_smaller_n(self) -> None:
        df = pd.DataFrame({"Quantity": [1.0, 2.0, 100.0, 200.0, 300.0]})
        mask = pd.Series([True] * 5)
        out = top_n_candidates(df, mask, columns=["Quantity"], n=2)
        assert len(out) == 2
        assert float(out["Quantity"].iloc[0]) == 300.0
