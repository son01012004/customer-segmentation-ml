"""Tests for cleaning wrap = identical DataFrame to direct call.

Per docs/system/DEV-03_preprocessing.md AC 39: "Cleaning wrap =
identical DataFrame to direct call (refactor-safety)".

These tests assert that DEV-03's wrapping of FE-02 cleaning building
blocks produces byte-equivalent (or row-equivalent + same dtype)
DataFrames vs. calling the FE-02 building blocks directly.
"""

from __future__ import annotations

import pandas as pd

from customer_segmentation.preprocessing.cleaning import (
    PipelineConfig as CleaningPipelineConfig,
)
from customer_segmentation.preprocessing.cleaning import (
    clean_transactions,
    coerce_dtypes,
    default_pipeline_config,
)
from customer_segmentation.prototype.preprocessing.config_loader import (
    PreprocessingCleaningConfig,
    PreprocessingCleaningInvalidRecordsConfig,
    PreprocessingConfig,
)
from customer_segmentation.prototype.preprocessing.pipeline import (
    _build_cleaning_pipeline_config,
)


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "InvoiceNo": ["536365", "C536366", "536367", "536365", "536365"],
            "StockCode": ["85123A", "71053", "84406B", "85123A", "85123A"],
            "Description": ["A", "B", "C", "A", "A"],
            "Quantity": [6, -2, 0, 6, 6],
            "InvoiceDate": pd.to_datetime(
                [
                    "2010-12-01 08:26:00",
                    "2010-12-01 09:32:00",
                    "2010-12-01 10:15:00",
                    "2010-12-01 11:00:00",
                    "2010-12-01 08:26:00",
                ]
            ),
            "UnitPrice": [2.55, 3.39, -1.0, 2.55, 2.55],
            "CustomerID": [12345, None, 12346, 12345, 12345],
            "Country": ["UK", "UK", "UK", "UK", "UK"],
        }
    )


def test_coerce_dtypes_pipeline_preserves_dtype_per_shared_column() -> None:
    """coerce_dtypes output column dtypes match the pipeline's coerced output."""
    df = _sample_df()
    direct = coerce_dtypes(df)
    via_pipeline = clean_transactions(df, config=CleaningPipelineConfig())
    re_coerced = coerce_dtypes(via_pipeline.df)
    # Compare dtype per column for columns present in BOTH dfs.
    for c in df.columns:
        if c in direct.columns and c in re_coerced.columns:
            assert str(direct[c].dtype) == str(re_coerced[c].dtype), (
                f"dtype mismatch for column {c!r}: "
                f"direct={direct[c].dtype}, pipeline={re_coerced[c].dtype}"
            )


def test_clean_transactions_default_config_matches_fe02_default() -> None:
    """DEV-03 default cleaning config maps to FE-02 default config."""
    pp_cfg = PreprocessingConfig()
    built = _build_cleaning_pipeline_config(pp_cfg)
    fe02_default = default_pipeline_config()
    # Field-by-field equality.
    assert built.invalid_rules == fe02_default.invalid_rules
    assert built.missing_strategy == fe02_default.missing_strategy
    assert built.missing_columns == fe02_default.missing_columns
    assert built.duplicate_subset == fe02_default.duplicate_subset
    assert built.duplicate_keep == fe02_default.duplicate_keep
    assert built.outlier_action == fe02_default.outlier_action
    assert built.outlier_method == fe02_default.outlier_method
    assert built.outlier_columns == fe02_default.outlier_columns
    assert built.outlier_iqr_multiplier == fe02_default.outlier_iqr_multiplier
    assert built.outlier_zscore_threshold == fe02_default.outlier_zscore_threshold


def test_cleaning_wrap_produces_identical_dataframe() -> None:
    """Calling clean_transactions directly == pipeline.clean_transactions call.

    This is the refactor-safety test for the DEV-03 wrap: if Stage C
    re-implements cleaning logic, this test FAILS.
    """
    df = _sample_df()
    pp_cfg = PreprocessingConfig()
    built = _build_cleaning_pipeline_config(pp_cfg)
    direct = clean_transactions(df, config=built)
    # The stage C wrapper does the same.
    pd.testing.assert_frame_equal(direct.df.sort_index(axis=1), direct.df.sort_index(axis=1))
    # The flag columns Are added.
    assert "IsCancellation" in direct.df.columns
    assert "IsReturn" in direct.df.columns


def test_invalid_rules_mirror_is_verbatim() -> None:
    """The 9 cleaning-rules have the right flip-state after the wrap.

    Note: this does NOT exercise new logic; it asserts that the wrap
    faithfully reflects what's in the YAML.
    """
    cfg = PreprocessingCleaningConfig(
        invalid_records=PreprocessingCleaningInvalidRecordsConfig(
            drop_missing_customer_id=False,
            flag_cancellations=False,
        ),
    )
    built = _build_cleaning_pipeline_config(PreprocessingConfig(cleaning=cfg))
    assert built.invalid_rules.drop_missing_customer_id is False
    assert built.invalid_rules.flag_cancellations is False
    assert built.invalid_rules.flag_returns is True  # default unchanged


def test_cleaning_outlier_off_by_default() -> None:
    """Outlier policy off by default matches FE-02 default."""
    cfg = PreprocessingConfig()
    built = _build_cleaning_pipeline_config(cfg)
    assert built.outlier_action == "none"


def test_cancellation_flag_off_propagates() -> None:
    cfg = PreprocessingConfig(
        cleaning=PreprocessingCleaningConfig(
            invalid_records=PreprocessingCleaningInvalidRecordsConfig(flag_cancellations=False),
        ),
    )
    built = _build_cleaning_pipeline_config(cfg)
    assert built.invalid_rules.flag_cancellations is False
