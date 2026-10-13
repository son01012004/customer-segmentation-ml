"""Single-stage driver for DEV-03 Stage F (Feature Generation).

This module WRAPS the research core FE-04 (aggregation) and FE-05
(feature engineering). It does NOT fork the research core and does
NOT introduce new feature definitions.

The Stage F orchestration follows the **canonical FE-05 order**
mirrored from ``scripts/run_fe05_feature_engineering.py:222-430``:

    1. compute_reference_date (default = max(InvoiceDate) + 1 day)
    2. compute_recency
    3. compute_frequency_variants + materialize_frequency (default =
       Frequency_ByInvoice, "by_invoice" mode)
    4. compute_monetary_variants + materialize_one_monetary_candidate
       (default = MonetarySigned, "signed" variant)
    5. compute_signed_quantity_set, rename columns
       (TotalQuantity_Signed → TotalQuantity, etc.)
    6. compute_tenure_days
    7. compute_purchase_interval (ddof=1; NaN for < 2 invoices)
    8. compute_active_days
    9. interim candidate = merge(df_base, recency, freq, monetary)
   10. compute_average_invoice_value (Monetary / Frequency)
   11. compute_diversity_features (ProductsPerInvoice)
   12. compute_cancellation_features (CancellationRate, ReturnRate)
   13. build_candidate_features (11 separate DataFrames → final)
   14. validate_candidate_dataset (6 checks)

Hard rules
----------
- ONE Monetary materialized (default: MonetarySigned, "signed"
  variant).
- ONE Frequency materialized (default: Frequency_ByInvoice,
  "by_invoice" mode).
- ONE Quantity working set materialized (default: signed).
- PurchaseIntervalMean/Std: ddof=1; NaN for < 2 invoices (NOT
  filled with 0).
- CategoryCount is NOT materialized (FE-05 hard constraint).
- ProductsPerInvoice is a ratio proxy (not a standard diversity metric).
- No "best / winner / recommended / optimal" language.
- Stage F3 (optional transform/scale on customer-level) is exposed
  but defaults to ``transformation=none, scaling=none, imputation=median``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC
from typing import Any

import numpy as np
import pandas as pd

from customer_segmentation.aggregation import (
    AggregationConfig as _AggConfig,
)
from customer_segmentation.aggregation import (
    AggregationSpec,
    LineRevenueColumns,
    aggregate_customer_base,
    validate_base_dataset,
)
from customer_segmentation.aggregation import (
    MetadataConfig as AggMetadataConfig,
)
from customer_segmentation.aggregation import (
    OutputConfig as AggOutputConfig,
)
from customer_segmentation.aggregation import (
    SourceConfig as AggSourceConfig,
)
from customer_segmentation.features import (
    build_candidate_features,
    compute_active_days,
    compute_all_monetary_variants,
    compute_cancellation_features,
    compute_diversity_features,
    compute_frequency_variants,
    compute_purchase_interval,
    compute_recency,
    compute_reference_date,
    compute_signed_quantity_set,
    compute_tenure_days,
    materialize_frequency,
    materialize_one_monetary_candidate,
    validate_candidate_dataset,
    validate_purchase_interval_na,
    validate_unique_customers,
)
from customer_segmentation.prototype.feature_generation.manifest_block import (
    FeatureGenerationBlock,
    build_feature_generation_block,
)
from customer_segmentation.prototype.feature_generation.scope import (
    FeatureGenerationOutcome,
)
from customer_segmentation.prototype.preprocessing.config_loader import (
    FeatureGenerationAggregationConfig,
    FeatureGenerationBlockConfig,
    FeatureGenerationOptionalTransformConfig,
)

__all__ = [
    "FeatureGenerationPipelineResult",
    "FeatureGenerationStageLogEntry",
    "run_feature_generation_pipeline",
]


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------


@dataclass
class FeatureGenerationStageLogEntry:
    """One entry per Stage F sub-step."""

    sub_step: str
    outcome: str
    timestamp_utc: str
    summary: dict[str, Any]


@dataclass
class FeatureGenerationPipelineResult:
    """Top-level Stage F result.

    Attributes
    ----------
    outcome : str
        Aggregate outcome (PASS / WARNING / FAIL).
    customer_count : int
        Number of unique CustomerID rows in the candidate matrix.
    candidate_feature_count : int
        Number of CANDIDATE features emitted (excludes CustomerID).
    candidate_df : pandas.DataFrame
        The customer-level feature matrix (CustomerID + candidate features).
    manifest_block : FeatureGenerationBlock
        The manifest block (built by ``build_feature_generation_block``).
    reference_date : datetime
        The reference date used for RFM.Recency.
    f1_input_row_count : int
        Transaction-level rows going into Stage F1 aggregation.
    f2_base_row_count : int
        Customer-level rows after Stage F1.
    validation_passed : bool
        True if all 6 candidate_dataset checks pass.
    errors : list[str]
        Per-stage error messages (only populated on FAIL).
    warnings : list[str]
        Per-stage warning messages.
    stage_logs : list[FeatureGenerationStageLogEntry]
        Per sub-step log entry.
    """

    outcome: str
    customer_count: int
    candidate_feature_count: int
    candidate_df: pd.DataFrame
    manifest_block: FeatureGenerationBlock
    reference_date: Any  # datetime.datetime
    f1_input_row_count: int
    f2_base_row_count: int
    validation_passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stage_logs: list[FeatureGenerationStageLogEntry] = field(default_factory=list)

    def to_manifest_block(self) -> FeatureGenerationBlock:
        """Return the manifest block (alias for `self.manifest_block`)."""
        return self.manifest_block


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_aggregation_config(
    feature_gen_cfg: FeatureGenerationAggregationConfig,
) -> _AggConfig:
    """Translate the DEV-03 aggregation sub-config into a FE-04 AggregationConfig.

    The 9 canonical FE-04 aggregations are reproduced verbatim from
    ``configs/aggregation.yaml``. Their per-spec status is
    ``WORKING_ASSUMPTION`` (inherited from FE-04). DEV-03 does NOT
    introduce new aggregation logic.
    """
    return _AggConfig(
        enabled=True,
        random_seed=42,
        source=AggSourceConfig(
            role=feature_gen_cfg.source.get("role", "primary"),
            cleaned_dataset_path=feature_gen_cfg.source.get("cleaned_dataset_path", ""),
            raw_dataset_path=feature_gen_cfg.source.get("raw_dataset_path", ""),
        ),
        aggregations=[
            AggregationSpec(
                name="TotalQuantity",
                source="Quantity",
                fn="sum",
                status="WORKING_ASSUMPTION",
                description="FE-04 baseline (mirrors configs/aggregation.yaml).",
            ),
            AggregationSpec(
                name="TotalMonetary",
                source="LineRevenue",
                fn="sum",
                status="WORKING_ASSUMPTION",
                description="FE-04 baseline (mirrors configs/aggregation.yaml).",
            ),
            AggregationSpec(
                name="FirstPurchaseDate",
                source="InvoiceDate",
                fn="min",
                status="WORKING_ASSUMPTION",
                description="FE-04 baseline.",
            ),
            AggregationSpec(
                name="LastPurchaseDate",
                source="InvoiceDate",
                fn="max",
                status="WORKING_ASSUMPTION",
                description="FE-04 baseline.",
            ),
            AggregationSpec(
                name="PurchaseFrequency",
                source="InvoiceNo",
                fn="nunique",
                status="WORKING_ASSUMPTION",
                description="FE-04 baseline working proxy.",
            ),
            AggregationSpec(
                name="AverageTransactionValue",
                source="LineRevenue",
                fn="avg_by_invoice",
                status="WORKING_ASSUMPTION",
                description="FE-04 baseline.",
            ),
            AggregationSpec(
                name="TransactionLineCount",
                source="InvoiceNo",
                fn="count",
                status="WORKING_ASSUMPTION",
                description="FE-04 baseline.",
            ),
            AggregationSpec(
                name="DistinctInvoiceCount",
                source="InvoiceNo",
                fn="nunique",
                status="WORKING_ASSUMPTION",
                description="FE-04 baseline (used as Frequency denominator).",
            ),
            AggregationSpec(
                name="DistinctProducts",
                source="StockCode",
                fn="nunique",
                status="WORKING_ASSUMPTION",
                description="FE-04 baseline.",
            ),
            AggregationSpec(
                name="CancellationInvoiceCount",
                source="InvoiceNo",
                fn="conditional_nunique_cancellation",
                status="WORKING_ASSUMPTION",
                description="FE-04 baseline; mirrors CL-08.",
            ),
            AggregationSpec(
                name="ReturnInvoiceCount",
                source="InvoiceNo",
                fn="conditional_nunique_return",
                status="WORKING_ASSUMPTION",
                description="FE-04 baseline; mirrors CL-06.",
            ),
        ],
        customer_key=feature_gen_cfg.customer_key,
        line_revenue_columns=LineRevenueColumns(
            quantity=feature_gen_cfg.line_revenue_quantity_column,
            unit_price=feature_gen_cfg.line_revenue_unit_price_column,
            output=feature_gen_cfg.line_revenue_output_column,
        ),
        output=AggOutputConfig(
            processed_dir="./data/processed",
            customer_base_filename="customer_base.parquet",
            report_dir="./reports/fe04",
        ),
        metadata=AggMetadataConfig(
            stage="FE-04",
            task_description="",
            scope_boundaries=[],
            notes=[],
        ),
    )


def _compute_average_invoice_value(
    df_base: pd.DataFrame,
    monetary_series: pd.Series,
    frequency_series: pd.Series,
    customer_key: str = "CustomerID",
) -> pd.DataFrame:
    """Compute AverageInvoiceValue (FE-05 candidate) without circular imports.

    Mirrors ``scripts/run_fe05_feature_engineering.py:_compute_ave_inv``.
    """
    result = df_base[[customer_key]].copy()
    monetary = monetary_series.astype(float)
    frequency = pd.to_numeric(frequency_series, errors="coerce")
    freq_safe = frequency.replace(0, pd.NA)
    avg = monetary / freq_safe
    avg = avg.replace([float("inf"), float("-inf")], pd.NA)
    result["AverageInvoiceValue"] = avg
    return result[[customer_key, "AverageInvoiceValue"]]


# ---------------------------------------------------------------------------
# Stage F1 — aggregation
# ---------------------------------------------------------------------------


def _empty_aggregation_config() -> _AggConfig:
    """Build a minimal valid AggregationConfig with empty aggregations.

    Used by early-return paths (Stage F1 on empty input) where we want
    a sentinel to return alongside ``pd.DataFrame()``.
    """
    return _AggConfig(
        enabled=True,
        random_seed=42,
        source=AggSourceConfig(
            role="primary",
            cleaned_dataset_path="",
            raw_dataset_path="",
        ),
        aggregations=[],
        customer_key="CustomerID",
        line_revenue_columns=LineRevenueColumns(
            quantity="Quantity",
            unit_price="UnitPrice",
            output="LineRevenue",
        ),
        output=AggOutputConfig(
            processed_dir="./data/processed",
            customer_base_filename="customer_base.parquet",
            report_dir="./reports/fe04",
        ),
        metadata=AggMetadataConfig(
            stage="FE-04",
            task_description="",
            scope_boundaries=[],
            notes=[],
        ),
    )


def _stage_f1_aggregation(
    df_transactions: pd.DataFrame,
    cfg: FeatureGenerationAggregationConfig,
    logger: Any | None,
) -> tuple[pd.DataFrame, _AggConfig, list[str], list[str]]:
    """Stage F1: aggregate to customer-level base dataset (FE-04 wrap)."""
    errors: list[str] = []
    warnings: list[str] = []
    if df_transactions.empty:
        errors.append("Stage F1 received an empty transaction DataFrame.")
        return pd.DataFrame(), _empty_aggregation_config(), errors, warnings

    # Wrap the cleaned transaction-level data into a "FE-02-clean" shape.
    # The aggregation config takes a path; we don't write one to disk —
    # we call the FE-04 ``aggregate_customer_base`` directly with the
    # in-memory DataFrame (the function does not require a path; only
    # the FE-04 orchestrator does).
    if cfg.line_revenue_output_column not in df_transactions.columns:
        # Derive LineRevenue in-memory (mirrors FE-04 compute_line_revenue).
        from customer_segmentation.aggregation.base_dataset import compute_line_revenue

        df_transactions = compute_line_revenue(
            df_transactions,
            quantity_column=cfg.line_revenue_quantity_column,
            unit_price_column=cfg.line_revenue_unit_price_column,
            out_column=cfg.line_revenue_output_column,
        )

    agg_config = _build_aggregation_config(cfg)
    result = aggregate_customer_base(df_transactions, agg_config)
    df_base = result.df

    # Run V-01..V-11 validation; warn on FAIL.
    val_result = validate_base_dataset(df_base, agg_config)
    for check in val_result.checks:
        if check.status == "FAIL":
            errors.append(f"V-FE04: {check.check_id} {check.description}: {check.message}")
        elif check.status == "WARNING":
            warnings.append(f"V-FE04: {check.check_id} {check.description}: {check.message}")

    if logger is not None:
        logger.info(
            "F1 aggregation completed: n_customers=%d, n_features=%d",
            int(df_base.shape[0]),
            int(df_base.shape[1]),
        )
    return df_base, agg_config, errors, warnings


# ---------------------------------------------------------------------------
# Stage F2 — feature engineering
# ---------------------------------------------------------------------------


def _stage_f2_features(
    df_transactions: pd.DataFrame,
    df_base: pd.DataFrame,
    cfg: FeatureGenerationBlockConfig,
    logger: Any | None,
) -> tuple[pd.DataFrame, list[str], Any, str, list[str], list[str], dict[str, Any]]:
    """Stage F2: RFM + behavioral + cancellation + diversity features.

    Returns (candidate_df, candidate_features, reference_date, outcome,
    errors, warnings, summary).
    """
    errors: list[str] = []
    warnings: list[str] = []
    summary: dict[str, Any] = {}
    customer_key = cfg.aggregation.customer_key or "CustomerID"
    features_cfg = cfg.features

    if df_base.empty:
        errors.append("Stage F2 received an empty base DataFrame.")
        return (
            pd.DataFrame(),
            [],
            None,
            FeatureGenerationOutcome.FAIL.value,
            errors,
            warnings,
            summary,
        )

    # 1. reference date
    reference_date = compute_reference_date(df_transactions)
    if cfg.reference_date.mode == "from_config" and cfg.reference_date.fixed_iso_date:
        try:
            from datetime import datetime as _dt

            reference_date = _dt.fromisoformat(cfg.reference_date.fixed_iso_date)
        except (TypeError, ValueError) as exc:
            errors.append(f"reference_date.fixed_iso_date invalid: {exc}")
            return (
                pd.DataFrame(),
                [],
                reference_date,
                FeatureGenerationOutcome.FAIL.value,
                errors,
                warnings,
                summary,
            )
    summary["reference_date_iso"] = reference_date.isoformat()

    # 2. Recency
    try:
        recency_df = compute_recency(
            df_base, reference_date, last_purchase_column="LastPurchaseDate"
        )
    except Exception as exc:
        errors.append(f"compute_recency failed: {exc}")
        return (
            pd.DataFrame(),
            [],
            reference_date,
            FeatureGenerationOutcome.FAIL.value,
            errors,
            warnings,
            summary,
        )

    # 3-4. Frequency / Monetary variants + materialize
    try:
        frequency_variants = compute_frequency_variants(
            df_transactions, df_base, customer_key=customer_key
        )
        frequency_materialized = materialize_frequency(
            frequency_variants,
            df_base,
            customer_key=customer_key,
            mode=features_cfg.frequency_mode,
            output_column="Frequency",
        )

        monetary_variants = compute_all_monetary_variants(
            df_transactions, df_base, customer_key=customer_key
        )
        monetary_materialized = materialize_one_monetary_candidate(
            monetary_variants,
            df_base,
            variant=features_cfg.monetary_strategy,
            output_column="Monetary",
            customer_key=customer_key,
        )
    except Exception as exc:
        errors.append(f"RFM variants/materialization failed: {exc}")
        return (
            pd.DataFrame(),
            [],
            reference_date,
            FeatureGenerationOutcome.FAIL.value,
            errors,
            warnings,
            summary,
        )

    # 5. quantity set
    try:
        signed_set = compute_signed_quantity_set(
            df_transactions, df_base, customer_key=customer_key
        )
        quantity_set = signed_set.rename(
            columns={
                "TotalQuantity_Signed": "TotalQuantity",
                "AverageQuantity_Signed": "AverageQuantity",
                "BasketSize_Signed": "BasketSize",
            }
        )[[customer_key, "TotalQuantity", "AverageQuantity", "BasketSize"]]
    except Exception as exc:
        errors.append(f"quantity_set failed: {exc}")
        return (
            pd.DataFrame(),
            [],
            reference_date,
            FeatureGenerationOutcome.FAIL.value,
            errors,
            warnings,
            summary,
        )

    # 6. tenure_days
    try:
        tenure_df = compute_tenure_days(df_base, customer_key=customer_key)
    except Exception as exc:
        errors.append(f"compute_tenure_days failed: {exc}")
        return (
            pd.DataFrame(),
            [],
            reference_date,
            FeatureGenerationOutcome.FAIL.value,
            errors,
            warnings,
            summary,
        )

    # 7. purchase_interval (NaN for < 2 invoices, ddof=1)
    try:
        purchase_interval_df = compute_purchase_interval(df_transactions, customer_key=customer_key)
    except Exception as exc:
        errors.append(f"compute_purchase_interval failed: {exc}")
        return (
            pd.DataFrame(),
            [],
            reference_date,
            FeatureGenerationOutcome.FAIL.value,
            errors,
            warnings,
            summary,
        )

    # 8. active_days
    try:
        active_days_df = compute_active_days(df_transactions, customer_key=customer_key)
    except Exception as exc:
        errors.append(f"compute_active_days failed: {exc}")
        return (
            pd.DataFrame(),
            [],
            reference_date,
            FeatureGenerationOutcome.FAIL.value,
            errors,
            warnings,
            summary,
        )

    # 9. interim candidate (df_base + rfm + freq + monetary)
    interim_df = df_base[[customer_key]].copy()
    if "CancellationInvoiceCount" in df_base.columns:
        interim_df = interim_df.merge(
            df_base[[customer_key, "CancellationInvoiceCount", "ReturnInvoiceCount"]],
            on=customer_key,
            how="left",
        )
    interim_df = interim_df.merge(frequency_materialized, on=customer_key, how="left")
    interim_df = interim_df.merge(monetary_materialized, on=customer_key, how="left")

    # 10. average_invoice_value
    try:
        average_invoice_value_df = _compute_average_invoice_value(
            df_base,
            monetary_materialized["Monetary"],
            frequency_materialized["Frequency"],
            customer_key=customer_key,
        )
    except Exception as exc:
        errors.append(f"_compute_average_invoice_value failed: {exc}")
        return (
            pd.DataFrame(),
            [],
            reference_date,
            FeatureGenerationOutcome.FAIL.value,
            errors,
            warnings,
            summary,
        )

    # 11. diversity (ProductsPerInvoice = DistinctProducts / DistinctInvoiceCount)
    try:
        diversity_df = compute_diversity_features(df_base, customer_key=customer_key)
    except Exception as exc:
        errors.append(f"compute_diversity_features failed: {exc}")
        return (
            pd.DataFrame(),
            [],
            reference_date,
            FeatureGenerationOutcome.FAIL.value,
            errors,
            warnings,
            summary,
        )

    # 12. cancellation / return
    try:
        cancellation_df = compute_cancellation_features(interim_df, customer_key=customer_key)
    except Exception as exc:
        errors.append(f"compute_cancellation_features failed: {exc}")
        return (
            pd.DataFrame(),
            [],
            reference_date,
            FeatureGenerationOutcome.FAIL.value,
            errors,
            warnings,
            summary,
        )

    # 13. build_candidate_features
    try:
        candidate_result = build_candidate_features(
            df_base,
            recency_df,
            frequency_materialized,
            monetary_materialized,
            quantity_set,
            tenure_df,
            purchase_interval_df,
            active_days_df,
            average_invoice_value_df,
            diversity_df,
            cancellation_df,
            customer_key=customer_key,
        )
    except Exception as exc:
        errors.append(f"build_candidate_features failed: {exc}")
        return (
            pd.DataFrame(),
            [],
            reference_date,
            FeatureGenerationOutcome.FAIL.value,
            errors,
            warnings,
            summary,
        )

    # 14. validate_candidate_dataset
    validation_checks = validate_candidate_dataset(candidate_result)
    pi_check = validate_purchase_interval_na(candidate_result.df)
    if pi_check.status == "FAIL":
        errors.append(f"validate_purchase_interval_na FAIL: {pi_check.message}")
    uniq_check = validate_unique_customers(candidate_result.df)
    if uniq_check.status == "FAIL":
        errors.append(f"validate_unique_customers FAIL: {uniq_check.message}")
    if any(c.get("status") == "FAIL" for c in validation_checks.values()):
        errors.append("validate_candidate_dataset has at least one FAIL.")

    summary["validation_checks"] = validation_checks
    summary["purchase_interval_check_status"] = pi_check.status
    summary["unique_customers_check_status"] = uniq_check.status

    outcome = (
        FeatureGenerationOutcome.FAIL.value
        if errors
        else (
            FeatureGenerationOutcome.WARNING.value
            if warnings
            else FeatureGenerationOutcome.PASS.value
        )
    )
    return (
        candidate_result.df,
        candidate_result.candidate_features,
        reference_date,
        outcome,
        errors,
        warnings,
        summary,
    )


# ---------------------------------------------------------------------------
# Stage F3 — optional post-aggregation transform / scale / imputation
# ---------------------------------------------------------------------------


def _stage_f3_optional_transform(
    df: pd.DataFrame,
    cfg: FeatureGenerationOptionalTransformConfig,
    customer_key: str,
    logger: Any | None,
) -> tuple[pd.DataFrame, list[str], list[str]]:
    """Stage F3: optional transform/scale on customer-level matrix.

    Default (``transformation=none, scaling=none``) is identity.
    ``imputation`` defaults to ``median`` (no-op if no NaN in
    numeric columns). Each option is ``WORKING_ASSUMPTION``.
    """
    out = df
    columns_processed: list[str] = []
    columns_skipped: list[str] = []

    numeric_cols: list[str] = []
    for c in df.columns:
        if c == customer_key:
            continue
        try:
            if pd.api.types.is_numeric_dtype(df[c]):
                numeric_cols.append(c)
        except Exception:
            continue

    # imputation step (median by default; only applied when NaN present)
    if cfg.imputation != "none" and numeric_cols:
        for c in numeric_cols:
            try:
                if out[c].isna().any():
                    if cfg.imputation == "median":
                        out[c] = out[c].fillna(out[c].median())
                    elif cfg.imputation == "mean":
                        out[c] = out[c].fillna(out[c].mean())
            except (TypeError, ValueError):
                columns_skipped.append(c)
                continue
            columns_processed.append(c)

    # transformation
    if cfg.transformation != "none" and numeric_cols:
        try:
            if cfg.transformation == "log1p":
                for c in numeric_cols:
                    out[c] = np.log1p(pd.to_numeric(out[c], errors="coerce"))
            elif cfg.transformation == "yeo_johnson":
                from sklearn.preprocessing import PowerTransformer  # noqa: F401

                pt = PowerTransformer(method="yeo-johnson", standardize=False)
                values = out[numeric_cols].apply(pd.to_numeric, errors="coerce")
                if values.isna().any().any():
                    raise ValueError("Stage F3 yeo_johnson requires no NaN; impute first.")
                transformed = pt.fit_transform(values.to_numpy())
                out = out.copy()
                for i, c in enumerate(numeric_cols):
                    out[c] = transformed[:, i]
        except Exception as exc:
            raise ValueError(f"Stage F3 transformation failed: {exc}.") from exc

    # scaling
    if cfg.scaling != "none" and numeric_cols:
        try:
            from sklearn.preprocessing import (  # noqa: F401
                MinMaxScaler,
                RobustScaler,
                StandardScaler,
            )

            if cfg.scaling == "standard":
                scaler = StandardScaler()
            elif cfg.scaling == "minmax":
                scaler = MinMaxScaler()
            elif cfg.scaling == "robust":
                scaler = RobustScaler()
            else:
                raise ValueError(f"unknown scaling: {cfg.scaling!r}")
            values = out[numeric_cols].apply(pd.to_numeric, errors="coerce")
            if values.isna().any().any():
                raise ValueError("Stage F3 scaling requires no NaN; impute first.")
            scaled = scaler.fit_transform(values.to_numpy())
            out = out.copy()
            for i, c in enumerate(numeric_cols):
                out[c] = scaled[:, i]
        except Exception as exc:
            raise ValueError(f"Stage F3 scaling failed: {exc}.") from exc

    if logger is not None:
        logger.info(
            "F3 optional transform/scale complete: trans=%s, scale=%s, imp=%s, n_cols=%d",
            cfg.transformation,
            cfg.scaling,
            cfg.imputation,
            len(numeric_cols),
        )
    return out, columns_processed, columns_skipped


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_feature_generation_pipeline(
    df_transactions: pd.DataFrame,
    *,
    config: FeatureGenerationBlockConfig | None = None,
) -> FeatureGenerationPipelineResult:
    """Run the DEV-03 Stage F pipeline (F1 + F2 + F3).

    Parameters
    ----------
    df_transactions : pandas.DataFrame
        Cleaned transaction-level DataFrame (Stage C output).
    config : FeatureGenerationBlockConfig, optional
        Stage F config; ``None`` uses the canonical default.

    Returns
    -------
    FeatureGenerationPipelineResult
        Top-level Stage F result (never raises on FAIL — caller
        must inspect ``outcome``).
    """
    import logging as _logging
    from datetime import datetime

    cfg = config or FeatureGenerationBlockConfig()
    logger = _logging.getLogger("customer_segmentation.prototype.preprocessing")
    stage_logs: list[FeatureGenerationStageLogEntry] = []

    def sub_start():
        return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Initialise as None so the except path can reference it.
    df_base: pd.DataFrame = pd.DataFrame()

    def _stamp(sub_step: str, outcome: str, summary: dict[str, Any]) -> None:
        stage_logs.append(
            FeatureGenerationStageLogEntry(
                sub_step=sub_step,
                outcome=outcome,
                timestamp_utc=sub_start(),
                summary=summary,
            )
        )

    # ----- F1: aggregation ------------------------------------------
    df_base, agg_config, f1_errors, f1_warnings = _stage_f1_aggregation(
        df_transactions, cfg.aggregation, logger
    )
    _stamp(
        "F1",
        (
            FeatureGenerationOutcome.PASS.value
            if not f1_errors
            else FeatureGenerationOutcome.FAIL.value
        ),
        {
            "n_customers": int(df_base.shape[0]),
            "n_features": int(df_base.shape[1]),
            "errors": f1_errors,
            "warnings": f1_warnings,
        },
    )
    if f1_errors:
        return FeatureGenerationPipelineResult(
            outcome=FeatureGenerationOutcome.FAIL.value,
            customer_count=0,
            candidate_feature_count=0,
            candidate_df=pd.DataFrame(),
            manifest_block=build_feature_generation_block(
                cfg,
                reference_date_iso="",
                customer_count=0,
                candidate_feature_count=0,
                outcome=FeatureGenerationOutcome.FAIL.value,
            ),
            reference_date=None,
            f1_input_row_count=int(df_transactions.shape[0]),
            f2_base_row_count=0,
            validation_passed=False,
            errors=f1_errors,
            warnings=f1_warnings,
            stage_logs=stage_logs,
        )

    # ----- F2: features ----------------------------------------------
    (
        candidate_df,
        candidate_features,
        reference_date,
        f2_outcome,
        f2_errors,
        f2_warnings,
        f2_summary,
    ) = _stage_f2_features(df_transactions, df_base, cfg, logger)
    _stamp(
        "F2",
        f2_outcome,
        {
            "n_candidate_features": len(candidate_features),
            "errors": f2_errors,
            "warnings": f2_warnings,
        },
    )
    if f2_outcome == FeatureGenerationOutcome.FAIL.value:
        return FeatureGenerationPipelineResult(
            outcome=FeatureGenerationOutcome.FAIL.value,
            customer_count=0,
            candidate_feature_count=0,
            candidate_df=pd.DataFrame(),
            manifest_block=build_feature_generation_block(
                cfg,
                reference_date_iso=(reference_date.isoformat() if reference_date else ""),
                customer_count=0,
                candidate_feature_count=0,
                outcome=FeatureGenerationOutcome.FAIL.value,
            ),
            reference_date=reference_date,
            f1_input_row_count=int(df_transactions.shape[0]),
            f2_base_row_count=int(df_base.shape[0]),
            validation_passed=False,
            errors=f2_errors,
            warnings=f2_warnings,
            stage_logs=stage_logs,
        )

    # ----- F3: optional post-aggregation transform/scale ------------
    try:
        final_df, processed, skipped = _stage_f3_optional_transform(
            candidate_df,
            cfg.optional_transform,
            customer_key=cfg.aggregation.customer_key or "CustomerID",
            logger=logger,
        )
        f3_errors: list[str] = []
        f3_warnings: list[str] = []
    except Exception as exc:
        return FeatureGenerationPipelineResult(
            outcome=FeatureGenerationOutcome.FAIL.value,
            customer_count=int(candidate_df.shape[0]),
            candidate_feature_count=len(candidate_features),
            candidate_df=pd.DataFrame(),
            manifest_block=build_feature_generation_block(
                cfg,
                reference_date_iso=(reference_date.isoformat() if reference_date else ""),
                customer_count=int(candidate_df.shape[0]),
                candidate_feature_count=len(candidate_features),
                outcome=FeatureGenerationOutcome.FAIL.value,
            ),
            reference_date=reference_date,
            f1_input_row_count=int(df_transactions.shape[0]),
            f2_base_row_count=int(df_base.shape[0]),
            validation_passed=False,
            errors=[str(exc)],
            warnings=[],
            stage_logs=stage_logs,
        )

    _stamp(
        "F3",
        FeatureGenerationOutcome.PASS.value,
        {
            "transformation": cfg.optional_transform.transformation,
            "scaling": cfg.optional_transform.scaling,
            "imputation": cfg.optional_transform.imputation,
            "columns_processed": processed,
        },
    )

    aggregate_errors = f1_errors + f2_errors + f3_errors
    aggregate_warnings = f1_warnings + f2_warnings + f3_warnings

    outcome_final = (
        FeatureGenerationOutcome.FAIL.value
        if aggregate_errors
        else (
            FeatureGenerationOutcome.WARNING.value
            if aggregate_warnings
            else FeatureGenerationOutcome.PASS.value
        )
    )

    manifest_block = build_feature_generation_block(
        cfg,
        reference_date_iso=(reference_date.isoformat() if reference_date else ""),
        customer_count=int(final_df.shape[0]),
        candidate_feature_count=len(candidate_features),
        outcome=outcome_final,
    )

    return FeatureGenerationPipelineResult(
        outcome=outcome_final,
        customer_count=int(final_df.shape[0]),
        candidate_feature_count=len(candidate_features),
        candidate_df=final_df,
        manifest_block=manifest_block,
        reference_date=reference_date,
        f1_input_row_count=int(df_transactions.shape[0]),
        f2_base_row_count=int(df_base.shape[0]),
        validation_passed=(f2_outcome != FeatureGenerationOutcome.FAIL.value),
        errors=aggregate_errors,
        warnings=aggregate_warnings,
        stage_logs=stage_logs,
    )


__ = (Any,)
