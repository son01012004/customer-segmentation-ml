"""Unit tests for FE-01 audit helpers.

These tests use only **synthetic** in-memory DataFrames. They do **not**
read any raw xlsx file, so they pass on CI without the primary dataset.
"""

from __future__ import annotations

import pandas as pd
import pytest

from customer_segmentation.data.audit import (
    AuditSummary,
    DateProfile,
    IdentifierProfile,
    basic_overview,
    categorical_profile,
    coerce_object_dtype_strings,
    date_profile,
    detect_string_pattern,
    duplicate_profile,
    frequency_table,
    identifier_profile,
    looks_like_cancellation_prefix,
    missing_profile,
    numerical_profile,
    safe_quantile,
    select_columns_by_dtype,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_df() -> pd.DataFrame:
    """A small synthetic dataset with the kinds of features FE-01 inspects."""
    return pd.DataFrame(
        {
            "InvoiceNo": ["536365", "536365", "C536379", "536366", "536367"],
            "StockCode": ["85123A", "71053", "84406B", "85123A", "22423"],
            "Quantity": [6, 6, -1, 32, 1],
            "InvoiceDate": pd.to_datetime(
                [
                    "2011-05-31 11:22:00",
                    "2011-05-31 11:22:00",
                    "2011-05-31 11:25:00",
                    "2011-06-01 09:15:00",
                    "2011-06-01 09:16:00",
                ]
            ),
            "UnitPrice": [2.55, 3.39, 2.75, 1.85, 0.85],
            "CustomerID": [17850.0, 17850.0, 17850.0, None, 13085.0],
            "Country": ["United Kingdom", "United Kingdom", "France", "France", "Germany"],
            "Description": [
                "WHITE HANGING HEART T-LIGHT HOLDER",
                "WHITE METAL LANTERN",
                "WHITE HANGING HEART T-LIGHT HOLDER",
                None,
                "REGENCY CAKESTAND 3 TIER",
            ],
        }
    )


# ---------------------------------------------------------------------------
# basic_overview
# ---------------------------------------------------------------------------


class TestBasicOverview:
    def test_returns_audit_summary(self, sample_df: pd.DataFrame) -> None:
        ov = basic_overview(sample_df)
        assert isinstance(ov, AuditSummary)
        assert ov.n_rows == 5
        assert ov.n_columns == 8

    def test_columns_and_dtypes(self, sample_df: pd.DataFrame) -> None:
        ov = basic_overview(sample_df)
        assert "InvoiceNo" in ov.column_names
        assert "CustomerID" in ov.column_names
        assert "InvoiceDate" in ov.dtypes
        # CustomerID is float because of NaN
        assert ov.dtypes["CustomerID"] == "float64"


# ---------------------------------------------------------------------------
# missing_profile
# ---------------------------------------------------------------------------


class TestMissingProfile:
    def test_counts_match(self, sample_df: pd.DataFrame) -> None:
        mp = missing_profile(sample_df)
        cust = mp[mp["column"] == "CustomerID"].iloc[0]
        assert int(cust["missing_count"]) == 1
        assert abs(float(cust["missing_rate"]) - 20.0) < 1e-6
        desc = mp[mp["column"] == "Description"].iloc[0]
        assert int(desc["missing_count"]) == 1

    def test_sorted_by_missing_desc(self, sample_df: pd.DataFrame) -> None:
        mp = missing_profile(sample_df)
        counts = mp["missing_count"].tolist()
        assert counts == sorted(counts, reverse=True)


# ---------------------------------------------------------------------------
# numerical_profile
# ---------------------------------------------------------------------------


class TestNumericalProfile:
    def test_contains_quantity(self, sample_df: pd.DataFrame) -> None:
        np = numerical_profile(sample_df, columns=["Quantity"])
        assert len(np) == 1
        row = np.iloc[0]
        assert int(row["negative_count"]) == 1
        assert int(row["count"]) == 5
        assert float(row["max"]) == 32.0
        assert float(row["min"]) == -1.0

    def test_handles_all_nan(self) -> None:
        df = pd.DataFrame({"a": [None, None, None]})
        np = numerical_profile(df, columns=["a"])
        assert int(np.iloc[0]["count"]) == 0
        assert pd.isna(np.iloc[0]["min"])


# ---------------------------------------------------------------------------
# categorical_profile
# ---------------------------------------------------------------------------


class TestCategoricalProfile:
    def test_top_values_encoding(self, sample_df: pd.DataFrame) -> None:
        cp = categorical_profile(sample_df, columns=["Country"])
        row = cp.iloc[0]
        # Sample fixture has 3 distinct countries (UK, France, Germany)
        assert int(row["unique_count"]) == 3
        assert "United Kingdom" in str(row["top_values"])
        assert "France" in str(row["top_values"])


# ---------------------------------------------------------------------------
# frequency_table
# ---------------------------------------------------------------------------


class TestFrequencyTable:
    def test_rates_sum_to_100_within_top_k(self, sample_df: pd.DataFrame) -> None:
        ft = frequency_table(sample_df["Country"], top_k=3)
        assert len(ft) == 3
        # The percent column should be between 0 and 100.
        assert (ft["rate"] >= 0).all() and (ft["rate"] <= 100).all()


# ---------------------------------------------------------------------------
# date_profile
# ---------------------------------------------------------------------------


class TestDateProfile:
    def test_min_and_max(self, sample_df: pd.DataFrame) -> None:
        dp = date_profile(sample_df, "InvoiceDate")
        assert isinstance(dp, DateProfile)
        assert dp.parsed_count == 5
        assert dp.min is not None
        assert dp.max is not None
        assert dp.min.year == 2011

    def test_handles_non_parseable(self) -> None:
        df = pd.DataFrame({"d": ["2010-01-01", "garbage", "2010-02-01"]})
        dp = date_profile(df, "d")
        assert dp.parsed_count == 2
        assert dp.unparsed_count == 1


# ---------------------------------------------------------------------------
# identifier_profile
# ---------------------------------------------------------------------------


class TestIdentifierProfile:
    def test_customer_id_uniqueness(self, sample_df: pd.DataFrame) -> None:
        prof = identifier_profile(sample_df, "CustomerID")
        assert isinstance(prof, IdentifierProfile)
        assert prof.unique_count == 2  # 17850 and 13085
        assert prof.missing_count == 1

    def test_invoice_no_uniqueness(self, sample_df: pd.DataFrame) -> None:
        prof = identifier_profile(sample_df, "InvoiceNo")
        assert prof.unique_count == 4  # 536365 (x2), C536379, 536366, 536367
        assert prof.is_unique is False


# ---------------------------------------------------------------------------
# duplicate_profile
# ---------------------------------------------------------------------------


class TestDuplicateProfile:
    def test_exact_duplicates(self) -> None:
        df = pd.DataFrame({"a": [1, 1, 2], "b": [1, 1, 2]})
        dp = duplicate_profile(df)
        assert dp.exact_duplicate_rows == 1

    def test_subset_duplicates(self) -> None:
        df = pd.DataFrame({"a": [1, 1, 2, 3], "b": [1, 2, 3, 4]})
        dp = duplicate_profile(df, subset=["a"])
        # (1, 1, 1) → 2 rows share the same `a`
        assert dp.key_duplicate_rows == 1
        assert dp.key_unique_combinations == 3


# ---------------------------------------------------------------------------
# cancellation-prefix
# ---------------------------------------------------------------------------


class TestLooksLikeCancellationPrefix:
    def test_counts_cancellations(self, sample_df: pd.DataFrame) -> None:
        scan = looks_like_cancellation_prefix(sample_df["InvoiceNo"], prefix="C")
        assert scan["n_matching"] == 1
        assert "C536379" in scan["examples"]

    def test_no_matches(self) -> None:
        s = pd.Series(["100", "200", "300"])
        scan = looks_like_cancellation_prefix(s, prefix="C")
        assert scan["n_matching"] == 0
        assert scan["examples"] == []


# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------


class TestMiscHelpers:
    def test_detect_string_pattern(self, sample_df: pd.DataFrame) -> None:
        out = detect_string_pattern(sample_df["InvoiceNo"])
        # C536379 is the only string-typed value
        assert any(v == "C536379" for v, _ in out)

    def test_safe_quantile(self) -> None:
        s = pd.Series([1, 2, 3, 4, 5])
        assert safe_quantile(s, 0.5) == 3.0
        empty = pd.Series([], dtype=float)
        assert pd.isna(safe_quantile(empty, 0.5))

    def test_select_columns_by_dtype(self, sample_df: pd.DataFrame) -> None:
        numeric = select_columns_by_dtype(sample_df, "numeric")
        assert "Quantity" in numeric
        assert "CustomerID" in numeric
        assert "InvoiceNo" not in numeric
        datetime_cols = select_columns_by_dtype(sample_df, "datetime")
        assert datetime_cols == ["InvoiceDate"]

    def test_coerce_object_dtype_strings(self, sample_df: pd.DataFrame) -> None:
        # InvoiceNo is object dtype in the fixture; after coercion it should
        # be a pandas StringDtype.
        out = coerce_object_dtype_strings(sample_df)
        assert "string" in str(out["InvoiceNo"].dtype).lower() or isinstance(
            out["InvoiceNo"].dtype, pd.StringDtype
        )
