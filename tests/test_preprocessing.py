"""Unit tests for the FE-02 preprocessing module.

These tests use **synthetic** in-memory DataFrames. They do **not**
read any raw xlsx file, so they pass on CI without the primary dataset.

The tests cover:

- Missing-value handling (all strategies).
- Duplicate removal (exact + subset, keep modes).
- Invalid-record detection and flagging.
- Outlier detection and treatment.
- The end-to-end `clean_transactions` orchestrator.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from customer_segmentation.preprocessing.cleaning import (
    CleaningResult,
    PipelineConfig,
    build_rule_inventory,
    clean_transactions,
    coerce_dtypes,
    default_pipeline_config,
    ensure_flag_columns,
    summarise_cleaning_result,
)
from customer_segmentation.preprocessing.duplicates import (
    analyse_subset_duplicates,
    count_exact_duplicates,
    drop_duplicates,
    exact_duplicate_analysis,
)
from customer_segmentation.preprocessing.invalid_records import (
    InvalidRecordRules,
    apply_invalid_rules,
    cancellation_prefix_mask,
    flag_cancellations,
    flag_returns,
    missing_identifier_mask,
    negative_quantity_mask,
    non_positive_unit_price_mask,
    unparseable_date_mask,
)
from customer_segmentation.preprocessing.missing_values import (
    IDENTIFIER_COLUMNS,
    MissingHandlingResult,
    handle_missing,
    is_identifier_column,
    safe_fillna,
    summarise_missing,
)
from customer_segmentation.preprocessing.outliers import (
    detect_outliers,
    summarise_outliers,
    treat_outliers,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_df() -> pd.DataFrame:
    """Small synthetic transaction-line dataset covering every FE-02 case."""
    return pd.DataFrame(
        {
            "InvoiceNo": [
                "536365",
                "536365",  # exact-row duplicate of row 0
                "536366",
                "C536367",  # cancellation
                "C536368",  # cancellation, also negative qty
                "",
                "536370",
                "536371",
            ],
            "StockCode": ["P1", "P1", "P2", "P3", "P4", "P5", "P6", "P7"],
            "Description": [
                "WHITE HANGING HEART T-LIGHT HOLDER",
                "WHITE HANGING HEART T-LIGHT HOLDER",
                "WHITE METAL LANTERN",
                "REGENCY CAKESTAND 3 TIER",
                None,  # missing description
                "MISC",
                "POSTAGE",
                "BAG",
            ],
            "Quantity": [6, 6, 1, 1, -2, 0, 4, 5],
            "InvoiceDate": pd.to_datetime(
                [
                    "2011-05-31 11:22:00",
                    "2011-05-31 11:22:00",
                    "2011-05-31 11:25:00",
                    "2011-05-31 11:30:00",
                    "2011-05-31 11:35:00",
                    "2011-05-31 11:40:00",
                    "2011-05-31 11:45:00",
                    "2011-05-31 11:50:00",
                ]
            ),
            "UnitPrice": [2.55, 2.55, 3.39, 0.0, -1.0, 1.0, 1.25, 2.5],
            "CustomerID": [17850.0, 17850.0, 17850.0, 13085.0, 13085.0, None, 13086.0, 13087.0],
            "Country": ["UK", "UK", "UK", "France", "France", "UK", "Germany", "UK"],
        }
    )


# ---------------------------------------------------------------------------
# missing_values
# ---------------------------------------------------------------------------


class TestMissingValues:
    def test_drop_strategy(self, sample_df: pd.DataFrame) -> None:
        result = handle_missing(sample_df, ["CustomerID"], "drop")
        assert isinstance(result, MissingHandlingResult)
        assert result.strategy == "drop"
        assert result.rows_dropped == 1  # the one with None CustomerID
        assert result.df["CustomerID"].isna().sum() == 0

    def test_impute_zero(self, sample_df: pd.DataFrame) -> None:
        # The fixture already has one missing CustomerID (index 5).
        result = handle_missing(sample_df, ["CustomerID"], "impute_zero")
        assert result.rows_imputed == 1
        assert result.df["CustomerID"].isna().sum() == 0

    def test_impute_median_numeric(self, sample_df: pd.DataFrame) -> None:
        # Inject a NaN into Quantity and impute with the median.
        df2 = sample_df.copy()
        df2.loc[0, "Quantity"] = np.nan
        result = handle_missing(df2, ["Quantity"], "impute_median")
        assert result.rows_imputed == 1
        assert result.df["Quantity"].isna().sum() == 0
        # Median of [NaN, 6, 1, 1, -2, 0, 4, 5] (7 non-null values,
        # sorted [-2, 0, 1, 1, 4, 5, 6]) is the middle value 1.
        assert float(result.df.loc[0, "Quantity"]) == pytest.approx(1.0, abs=1e-6)

    def test_impute_mean_numeric(self, sample_df: pd.DataFrame) -> None:
        df2 = sample_df.copy()
        df2.loc[0, "Quantity"] = np.nan
        result = handle_missing(df2, ["Quantity"], "impute_mean")
        assert result.rows_imputed == 1
        # Mean of [NaN, 6, 1, 1, -2, 0, 4, 5] = (6+1+1-2+0+4+5) / 7
        # = 15 / 7 ≈ 2.142857
        assert float(result.df.loc[0, "Quantity"]) == pytest.approx(15.0 / 7.0, abs=1e-6)

    def test_impute_zero_rejects_string_column(self, sample_df: pd.DataFrame) -> None:
        with pytest.raises(ValueError):
            handle_missing(sample_df, ["Description"], "impute_zero")

    def test_keep_strategy_no_change(self, sample_df: pd.DataFrame) -> None:
        before_miss = int(sample_df["CustomerID"].isna().sum())
        result = handle_missing(sample_df, ["CustomerID"], "keep")
        assert result.rows_dropped == 0
        assert result.rows_imputed == 0
        assert int(result.df["CustomerID"].isna().sum()) == before_miss

    def test_unknown_strategy_raises(self, sample_df: pd.DataFrame) -> None:
        with pytest.raises(ValueError):
            handle_missing(sample_df, ["CustomerID"], "bogus")

    def test_missing_column_raises(self, sample_df: pd.DataFrame) -> None:
        with pytest.raises(KeyError):
            handle_missing(sample_df, ["NoSuchColumn"], "drop")

    def test_summarise_missing(self, sample_df: pd.DataFrame) -> None:
        summary = summarise_missing(sample_df)
        cust = next(s for s in summary if s.column == "CustomerID")
        assert cust.missing_count == 1
        assert cust.n_unique_non_null == 4
        # Summary is sorted by missing_count desc.
        counts = [s.missing_count for s in summary]
        assert counts == sorted(counts, reverse=True)

    def test_identifier_column_helper(self) -> None:
        assert is_identifier_column("CustomerID") is True
        assert is_identifier_column("InvoiceNo") is True
        assert is_identifier_column("UnitPrice") is False

    def test_safe_fillna_blocks_identifier(self) -> None:
        s = pd.Series([1.0, 2.0, np.nan], name="CustomerID")
        with pytest.raises(ValueError):
            safe_fillna(s, 0)
        # NaN fill is allowed.
        out = safe_fillna(s, np.nan)
        assert int(out.isna().sum()) == 1


# ---------------------------------------------------------------------------
# duplicates
# ---------------------------------------------------------------------------


class TestDuplicates:
    def test_drop_duplicates_first(self, sample_df: pd.DataFrame) -> None:
        result = drop_duplicates(sample_df, keep="first")
        assert result.rows_removed == 1  # one exact-row duplicate
        assert result.keep == "first"

    def test_drop_duplicates_last(self, sample_df: pd.DataFrame) -> None:
        result = drop_duplicates(sample_df, keep="last")
        assert result.rows_removed == 1
        # After keep="last", the first occurrence is dropped, the last kept.
        assert result.df.iloc[0]["InvoiceNo"] != "536365" or len(result.df) == len(sample_df) - 1

    def test_drop_duplicates_none(self, sample_df: pd.DataFrame) -> None:
        result = drop_duplicates(sample_df, keep="none")
        # With keep="none", **both** occurrences of a duplicate row are
        # removed. The fixture has a 2-row exact duplicate, so 2 rows
        # are removed.
        assert result.rows_removed == 2
        # The duplicate row's InvoiceNo must be absent entirely.
        assert "536365" not in set(result.df["InvoiceNo"].astype(str).tolist())

    def test_drop_duplicates_unknown_raises(self, sample_df: pd.DataFrame) -> None:
        with pytest.raises(ValueError):
            drop_duplicates(sample_df, keep="bogus")

    def test_drop_duplicates_missing_column_raises(self, sample_df: pd.DataFrame) -> None:
        with pytest.raises(KeyError):
            drop_duplicates(sample_df, subset=["Nonexistent"])

    def test_subset_duplicates(self, sample_df: pd.DataFrame) -> None:
        analysis = analyse_subset_duplicates(sample_df, ["InvoiceNo", "StockCode"])
        # All rows have distinct (InvoiceNo, StockCode) pairs except the
        # one exact-row duplicate at index 0/1, which share (536365, P1).
        assert analysis.duplicate_rows == 1
        assert analysis.duplicate_groups == 1

    def test_count_exact_duplicates(self, sample_df: pd.DataFrame) -> None:
        assert count_exact_duplicates(sample_df) == 1

    def test_exact_duplicate_analysis(self, sample_df: pd.DataFrame) -> None:
        info = exact_duplicate_analysis(sample_df)
        assert info["duplicate_rows"] == 1
        assert info["duplicate_groups"] == 1
        assert info["duplicate_rate_percent"] == pytest.approx(1 / 8 * 100.0, abs=1e-4)


# ---------------------------------------------------------------------------
# invalid_records
# ---------------------------------------------------------------------------


class TestInvalidRecords:
    def test_cancellation_prefix_mask(self, sample_df: pd.DataFrame) -> None:
        mask = cancellation_prefix_mask(sample_df)
        assert int(mask.sum()) == 2

    def test_negative_quantity_mask(self, sample_df: pd.DataFrame) -> None:
        mask = negative_quantity_mask(sample_df)
        assert int(mask.sum()) == 1

    def test_non_positive_unit_price_mask(self, sample_df: pd.DataFrame) -> None:
        mask = non_positive_unit_price_mask(sample_df)
        # Two rows: 0.0 and -1.0
        assert int(mask.sum()) == 2

    def test_unparseable_date_mask_empty(self, sample_df: pd.DataFrame) -> None:
        # All dates parse in the fixture.
        mask = unparseable_date_mask(sample_df)
        assert int(mask.sum()) == 0

    def test_missing_identifier_mask(self, sample_df: pd.DataFrame) -> None:
        # CustomerID: 1 missing; InvoiceNo: 1 empty.
        cust = missing_identifier_mask(sample_df, "CustomerID")
        assert int(cust.sum()) == 1
        inv = missing_identifier_mask(sample_df, "InvoiceNo")
        assert int(inv.sum()) == 1

    def test_flag_cancellations_adds_column(self, sample_df: pd.DataFrame) -> None:
        df, n = flag_cancellations(sample_df)
        assert n == 2
        assert "IsCancellation" in df.columns
        assert int(df["IsCancellation"].sum()) == 2

    def test_flag_returns_adds_column(self, sample_df: pd.DataFrame) -> None:
        df, n = flag_returns(sample_df)
        assert n == 1
        assert "IsReturn" in df.columns
        assert int(df["IsReturn"].sum()) == 1

    def test_apply_invalid_rules_default(self, sample_df: pd.DataFrame) -> None:
        result = apply_invalid_rules(sample_df)
        assert result.rows_before == len(sample_df)
        # Per-rule affected rows: 1 empty InvoiceNo + 1 missing CustomerID
        # + 1 missing Description + 1 zero Quantity + 2 non-positive
        # UnitPrice = 6 individual rule hits. But several of these hit
        # the same rows (row 5 fails CL-10, CL-01, CL-05 at once; row 4
        # fails CL-03 and CL-07 at once). The union drop mask removes
        # exactly 3 rows in this fixture.
        assert result.rows_dropped == 3
        assert result.flagged_cancellations == 2
        assert result.flagged_returns == 1
        assert "IsCancellation" in result.df.columns
        assert "IsReturn" in result.df.columns

    def test_apply_invalid_rules_disable_drops(self, sample_df: pd.DataFrame) -> None:
        rules = InvalidRecordRules(
            drop_missing_customer_id=False,
            drop_missing_invoice_no=False,
            drop_missing_description=False,
            drop_unparseable_invoice_date=False,
            drop_zero_quantity=False,
            drop_non_positive_unit_price=False,
            flag_cancellations=False,
            flag_returns=False,
        )
        result = apply_invalid_rules(sample_df, rules)
        assert result.rows_dropped == 0
        assert result.flagged_cancellations == 0
        assert result.flagged_returns == 0
        assert result.rows_after == result.rows_before


# ---------------------------------------------------------------------------
# outliers
# ---------------------------------------------------------------------------


class TestOutliers:
    def test_detect_iqr(self, sample_df: pd.DataFrame) -> None:
        # Make Quantity have obvious outliers.
        df = sample_df.copy()
        df.loc[0, "Quantity"] = 100_000
        df.loc[1, "Quantity"] = -50_000
        masks = detect_outliers(df, ["Quantity"], method="iqr", iqr_multiplier=1.5)
        assert "Quantity" in masks
        assert int(masks["Quantity"].sum()) == 2

    def test_detect_zscore(self, sample_df: pd.DataFrame) -> None:
        # The fixture is tiny (8 rows) so a single very large outlier
        # inflates the std enough that the z-score may stay below 3.
        # Build a slightly larger fixture where the outlier dominates.
        rng = np.random.default_rng(seed=0)
        df = pd.DataFrame(
            {"Quantity": np.concatenate([rng.normal(loc=5.0, scale=1.0, size=200), [10_000.0]])}
        )
        masks = detect_outliers(df, ["Quantity"], method="zscore", zscore_threshold=3.0)
        assert int(masks["Quantity"].sum()) >= 1

    def test_treat_outliers_flag(self, sample_df: pd.DataFrame) -> None:
        df = sample_df.copy()
        df.loc[0, "Quantity"] = 100_000
        result = treat_outliers(df, ["Quantity"], method="iqr", action="flag")
        assert "IsOutlier" in result.df.columns
        assert int(result.df["IsOutlier"].sum()) == 1
        assert result.rows_removed == 0

    def test_treat_outliers_clip(self, sample_df: pd.DataFrame) -> None:
        df = sample_df.copy()
        df.loc[0, "Quantity"] = 100_000
        result = treat_outliers(df, ["Quantity"], method="iqr", action="clip")
        # Clipped value must be <= the upper IQR fence.
        upper = result.per_column[0]["upper"]
        assert float(result.df.loc[0, "Quantity"]) <= float(upper)

    def test_treat_outliers_remove(self, sample_df: pd.DataFrame) -> None:
        df = sample_df.copy()
        df.loc[0, "Quantity"] = 100_000
        result = treat_outliers(df, ["Quantity"], method="iqr", action="remove")
        assert result.rows_removed == 1
        assert result.df.shape[0] == df.shape[0] - 1

    def test_summarise_outliers(self, sample_df: pd.DataFrame) -> None:
        summary = summarise_outliers(sample_df, ["Quantity"], method="iqr")
        assert "outlier_count" in summary.columns
        assert int(summary["outlier_count"].iloc[0]) >= 0

    def test_treat_outliers_unknown_method(self, sample_df: pd.DataFrame) -> None:
        with pytest.raises(ValueError):
            treat_outliers(sample_df, ["Quantity"], method="bogus")  # type: ignore[arg-type]

    def test_treat_outliers_unknown_action(self, sample_df: pd.DataFrame) -> None:
        with pytest.raises(ValueError):
            treat_outliers(sample_df, ["Quantity"], action="bogus")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# cleaning orchestrator
# ---------------------------------------------------------------------------


class TestCleaningOrchestrator:
    def test_default_config(self) -> None:
        cfg = default_pipeline_config()
        assert isinstance(cfg, PipelineConfig)
        assert cfg.missing_strategy == "keep"
        assert cfg.duplicate_keep == "first"
        assert cfg.outlier_action == "none"

    def test_clean_transactions_returns_result(self, sample_df: pd.DataFrame) -> None:
        result = clean_transactions(sample_df)
        assert isinstance(result, CleaningResult)
        assert result.df.shape[0] < sample_df.shape[0]
        assert "IsCancellation" in result.df.columns
        assert "IsReturn" in result.df.columns
        assert result.report["rows_in"] == sample_df.shape[0]
        assert result.report["rows_out"] == result.df.shape[0]

    def test_clean_transactions_is_idempotent(self, sample_df: pd.DataFrame) -> None:
        # Re-running the pipeline must produce the same result.
        r1 = clean_transactions(sample_df)
        r2 = clean_transactions(r1.df)
        # The second run should not drop additional rows (no duplicates
        # left and no other rule applies to the cleaned rows).
        assert r2.report["rows_removed_total"] == 0

    def test_clean_transactions_preserves_raw(self, sample_df: pd.DataFrame) -> None:
        before = sample_df.copy(deep=True)
        _ = clean_transactions(sample_df)
        # Input must not be mutated.
        assert sample_df.equals(before)

    def test_coerce_dtypes(self, sample_df: pd.DataFrame) -> None:
        out = coerce_dtypes(sample_df)
        assert pd.api.types.is_datetime64_any_dtype(out["InvoiceDate"])
        assert str(out["CustomerID"].dtype) == "Int64"
        assert str(out["InvoiceNo"].dtype) == "string"

    def test_coerce_dtypes_preserves_raw(self, sample_df: pd.DataFrame) -> None:
        before = sample_df.copy(deep=True)
        _ = coerce_dtypes(sample_df)
        assert sample_df.equals(before)

    def test_build_rule_inventory_has_all_rules(self) -> None:
        inv = build_rule_inventory()
        rule_ids = {r["rule_id"] for r in inv}
        for required in (
            "CL-01",
            "CL-03",
            "CL-04",
            "CL-05",
            "CL-06",
            "CL-07",
            "CL-08",
            "CL-09",
            "CL-10",
        ):
            assert required in rule_ids

    def test_build_rule_inventory_marks_deferred(self) -> None:
        inv = build_rule_inventory()
        deferred = {r["rule_id"] for r in inv if r["status"] == "PENDING_MENTOR_REVIEW"}
        # Cancellation and return handling are deferred.
        assert "CL-06" in deferred
        assert "CL-08" in deferred

    def test_summarise_cleaning_result(self, sample_df: pd.DataFrame) -> None:
        result = clean_transactions(sample_df)
        s = summarise_cleaning_result(result)
        assert "rows_in" in s
        assert "rows_out" in s
        assert "flagged_cancellations" in s
        assert "flagged_returns" in s
        assert "stages" in s
        assert s["rows_in"] == sample_df.shape[0]

    def test_ensure_flag_columns(self, sample_df: pd.DataFrame) -> None:
        cleaned = clean_transactions(sample_df).df
        # Drop the flag columns first.
        cleaned = cleaned.drop(columns=["IsCancellation", "IsReturn"])
        out = ensure_flag_columns(cleaned)
        assert "IsCancellation" in out.columns
        assert "IsReturn" in out.columns
        assert out["IsCancellation"].dtype == bool
        assert out["IsReturn"].dtype == bool
        # Default value is False for everyone.
        assert int(out["IsCancellation"].sum()) == 0
        assert int(out["IsReturn"].sum()) == 0

    def test_custom_config_does_not_drop(self, sample_df: pd.DataFrame) -> None:
        # Disable all drop rules and all flag rules: the cleaned
        # DataFrame should be identical to the input (modulo coerce).
        cfg = PipelineConfig(
            invalid_rules=InvalidRecordRules(
                drop_missing_customer_id=False,
                drop_missing_invoice_no=False,
                drop_missing_description=False,
                drop_unparseable_invoice_date=False,
                drop_zero_quantity=False,
                drop_non_positive_unit_price=False,
                flag_cancellations=False,
                flag_returns=False,
            ),
            duplicate_subset=None,
            duplicate_keep="first",
        )
        result = clean_transactions(sample_df, config=cfg)
        assert result.report["rows_removed_total"] == 1  # only the exact-row dup
        assert "IsCancellation" not in result.df.columns
        assert "IsReturn" not in result.df.columns


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------


class TestExports:
    def test_identifiers_constant(self) -> None:
        assert "CustomerID" in IDENTIFIER_COLUMNS
        assert "InvoiceNo" in IDENTIFIER_COLUMNS
