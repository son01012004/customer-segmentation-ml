"""FE-05 orchestrator: candidate feature engineering & feature selection.

Stage: 05_feature_engineering (FE-05)

Usage (from the repository root):

    python -m scripts.run_fe05_feature_engineering
    python -m scripts.run_fe05_feature_engineering --config PATH

Outputs
-------
Written under ``data/processed/``:

- ``customer_candidates.parquet`` — the candidate dataset Tầng 2
  (1 row per CustomerID). Input cho FE-06.

Written under ``reports/fe05/``:

- ``rfm_report.md`` — RFM narrative report
- ``monetary_definition_comparison.csv`` — 4 monetary variants comparison
- ``quantity_variants_comparison.csv`` — signed vs purchase-only comparison
- ``frequency_variants_comparison.csv`` — FREQ-01 vs FREQ-02 comparison
- ``candidate_feature_report.md`` — candidate features summary
- ``distribution_analysis.csv`` — distribution statistics
- ``variance_analysis.csv`` — variance statistics (CV)
- ``correlation_matrix_pearson.csv`` — Pearson correlation
- ``correlation_matrix_spearman.csv`` — Spearman correlation
- ``redundancy_report.csv`` — high-correlation pairs
- ``outlier_detection.csv`` — IQR outlier detection
- ``feature_selection_report.csv`` — evidence-based selection
- ``business_interpretability.csv`` — interpretability assessment
- ``feature_dictionary.csv`` — feature definitions
- ``fe05_run.json`` — full run metadata + SHA-256
- ``narrative_report.md`` — Vietnamese narrative report

Hard constraints (AGENTS.md / Plan V5):
- Input customer_base.parquet and transactions_clean.parquet are READ-ONLY.
- SHA-256 cả hai input giống trước/after.
- SHA-256 cả hai input + output được ghi nhận trong fe05_run.json.
- ONE Monetary materialized (default: MonetarySigned).
- ONE Frequency materialized (default: Frequency_ByInvoice).
- ONE Quantity working set materialized (default: signed).
- PurchaseInterval uses ddof=1; NaN for < 2 invoices (NOT filled with 0).
- FE-04 AverageTransactionValue NOT modified.
- CategoryCount NOT materialized.
- Empty input fail-fast.
- No clustering, no scaling, no transformation.
- No "best/recommended/final" language.
"""

from __future__ import annotations

import argparse
import hashlib
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from customer_segmentation.features import (  # noqa: E402
    DECISION_RETAIN_CANDIDATE,
    DEFAULT_INTERPRETABLE_FEATURES,
    FeatureEngineeringConfig,
    FeatureEngineeringConfigError,
    apply_data_quality_gate,
    apply_interpretability_gate,
    apply_leakage_gate,
    apply_redundancy_gate,
    apply_shapiro_wilk_gate,
    apply_stability_gate,
    apply_zero_variance_gate,
    assess_interpretability,
    build_candidate_features,
    build_feature_selection_report,
    compute_active_days,
    compute_all_monetary_variants,
    compute_cancellation_features,
    compute_correlation_matrices,
    compute_distribution_stats,
    compute_diversity_features,
    compute_frequency_variants,
    compute_purchase_interval,
    compute_recency,
    compute_reference_date,
    compute_tenure_days,
    compute_variance_stats,
    detect_outliers,
    detect_redundancy,
    load_feature_engineering_config,
    make_selection_decisions,
    materialize_frequency,
    materialize_one_monetary_candidate,
    resolve_feature_engineering_config_path,
    select_numeric_candidate_columns,
    shapiro_wilk_diagnostic,
    validate_candidate_dataset,
    validate_purchase_interval_na,
    validate_unique_customers,
    write_all_fe05_reports,
)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_PROCESSED_DIR: Path = _REPO_ROOT / "data" / "processed"
DEFAULT_REPORT_DIR: Path = _REPO_ROOT / "reports" / "fe05"
DEFAULT_CUSTOMER_BASE_PATH: Path = DEFAULT_PROCESSED_DIR / "customer_base.parquet"
DEFAULT_TRANSACTIONS_CLEAN_PATH: Path = DEFAULT_PROCESSED_DIR / "transactions_clean.parquet"
DEFAULT_CANDIDATE_FILENAME: str = "customer_candidates.parquet"

# Columns that the FE-04 customer_base MUST contain.
REQUIRED_BASE_COLUMNS: tuple[str, ...] = (
    "CustomerID",
    "TotalQuantity",
    "TotalMonetary",
    "FirstPurchaseDate",
    "LastPurchaseDate",
    "PurchaseFrequency",
    "AverageTransactionValue",
    "TransactionLineCount",
    "DistinctInvoiceCount",
    "DistinctProducts",
    "CancellationInvoiceCount",
    "ReturnInvoiceCount",
)

# Columns that the FE-02 transactions_clean MUST contain.
REQUIRED_TRANSACTIONS_COLUMNS: tuple[str, ...] = (
    "InvoiceNo",
    "Quantity",
    "InvoiceDate",
    "UnitPrice",
    "CustomerID",
    "IsCancellation",
    "IsReturn",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    """Compute SHA-256 of a file by streaming chunks."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def _validate_base_schema(df: pd.DataFrame) -> None:
    """Fail fast if FE-04 customer_base is missing required columns."""
    missing = [c for c in REQUIRED_BASE_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"FE-04 customer_base is missing required column(s): {missing}. "
            "Re-run FE-04 first (python -m scripts.run_fe04_aggregation)."
        )


def _validate_transactions_schema(df: pd.DataFrame) -> None:
    """Fail fast if FE-02 transactions_clean is missing required columns."""
    missing = [c for c in REQUIRED_TRANSACTIONS_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"FE-02 transactions_clean is missing required column(s): {missing}. "
            "Re-run FE-02 first (python -m scripts.run_fe02_cleaning)."
        )


def _resolve_config(config_path: Path | None) -> tuple[FeatureEngineeringConfig, str]:
    """Resolve feature engineering config."""
    yaml_path = resolve_feature_engineering_config_path(explicit=config_path)
    if yaml_path is None:
        raise SystemExit(
            "[FE-05] ERROR: configs/feature_engineering.yaml not found. "
            "Run from the repository root or pass --config."
        )
    try:
        loaded = load_feature_engineering_config(yaml_path, strict=True)
    except FeatureEngineeringConfigError as exc:
        raise SystemExit(f"[FE-05] ERROR: invalid feature engineering config: {exc}") from exc
    label = f"yaml:{yaml_path}"
    print(f"[FE-05] loaded feature engineering config: {yaml_path}")
    return loaded, label


def _compute_ave_inv(
    df_base: pd.DataFrame,
    monetary_series: pd.Series,
    frequency_series: pd.Series,
    customer_key: str = "CustomerID",
) -> pd.DataFrame:
    """Compute AverageInvoiceValue (FE-05 candidate) without circular imports."""
    result = df_base[[customer_key]].copy()
    monetary = monetary_series.astype(float)
    frequency = pd.to_numeric(frequency_series, errors="coerce")

    # Replace 0 with NaN in denominator to avoid division by zero (no inf)
    freq_safe = frequency.replace(0, pd.NA)
    avg = monetary / freq_safe
    # Replace inf with NaN
    avg = avg.replace([float("inf"), float("-inf")], pd.NA)

    result["AverageInvoiceValue"] = avg
    return result[[customer_key, "AverageInvoiceValue"]]


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def run_fe05_pipeline(
    customer_base_path: Path,
    transactions_clean_path: Path,
    processed_dir: Path,
    report_dir: Path,
    *,
    config: FeatureEngineeringConfig | None = None,
    config_path: Path | None = None,
) -> dict:
    """Run the FE-05 feature engineering pipeline end-to-end.

    Parameters
    ----------
    customer_base_path : pathlib.Path
        Path to the FE-04 customer_base.parquet.
    transactions_clean_path : pathlib.Path
        Path to the FE-02 transactions_clean.parquet.
    processed_dir : pathlib.Path
        Output directory for the candidate dataset.
    report_dir : pathlib.Path
        Output directory for FE-05 reports.
    config : FeatureEngineeringConfig, optional
        Explicit config.
    config_path : pathlib.Path, optional
        Explicit YAML path.

    Returns
    -------
    dict
        Run summary suitable for the fe05_run.json artefact.
    """
    # ------------------------------------------------------------------
    # 0. Resolve config
    # ------------------------------------------------------------------
    config_source_label = "explicit_config"
    if config is None:
        config, config_source_label = _resolve_config(config_path)
    else:
        print("[FE-05] using explicit FeatureEngineeringConfig")

    if not config.enabled:
        print("[FE-05] features.enabled=false in config; nothing to do.")
        return {"enabled": False, "config_source": config_source_label}

    # Validate input paths
    if not customer_base_path.exists():
        raise FileNotFoundError(
            f"FE-04 customer_base not found: {customer_base_path}. "
            "Run FE-04 first (python -m scripts.run_fe04_aggregation)."
        )
    if not transactions_clean_path.exists():
        raise FileNotFoundError(
            f"FE-02 transactions_clean not found: {transactions_clean_path}. "
            "Run FE-02 first (python -m scripts.run_fe02_cleaning)."
        )

    # ------------------------------------------------------------------
    # 1. SHA-256 before
    # ------------------------------------------------------------------
    input_sha_base_before = _sha256_file(customer_base_path)
    input_sha_trans_before = _sha256_file(transactions_clean_path)

    # ------------------------------------------------------------------
    # 2. Load inputs (read-only)
    # ------------------------------------------------------------------
    df_base = pd.read_parquet(customer_base_path)
    _validate_base_schema(df_base)

    df_transactions = pd.read_parquet(transactions_clean_path)
    _validate_transactions_schema(df_transactions)

    # Fail-fast if either input is empty
    if df_base.empty:
        raise ValueError(
            f"FE-04 customer_base is empty ({customer_base_path}). "
            "Cannot engineer features from empty base dataset."
        )
    if df_transactions.empty:
        raise ValueError(
            f"FE-02 transactions_clean is empty ({transactions_clean_path}). "
            "Cannot engineer features from empty transactions."
        )

    print(
        f"[FE-05] loaded: customer_base {df_base.shape[0]:,} rows × "
        f"{df_base.shape[1]} cols; "
        f"transactions_clean {df_transactions.shape[0]:,} rows × "
        f"{df_transactions.shape[1]} cols."
    )

    # ------------------------------------------------------------------
    # 3. Reference Date (deterministic)
    # ------------------------------------------------------------------
    reference_date = compute_reference_date(df_transactions)
    print(f"[FE-05] reference date: {reference_date.isoformat()}")

    # ------------------------------------------------------------------
    # 4. RFM
    # ------------------------------------------------------------------
    print("[FE-05] computing RFM features...")

    # Recency
    recency_df = compute_recency(
        df_base,
        reference_date,
        last_purchase_column=config.rfm.recency_column,
    )
    print(f"[FE-05] Recency computed: {recency_df.shape[0]:,} customers")

    # Frequency (FREQ-01 vs FREQ-02 comparison; materialize ONE)
    frequency_variants = compute_frequency_variants(
        df_transactions,
        df_base,
        customer_key=config.customer_key or "CustomerID",
    )
    frequency_materialized = materialize_frequency(
        frequency_variants,
        df_base,
        customer_key=config.customer_key or "CustomerID",
        mode=config.rfm.frequency_mode,
        output_column=config.rfm.frequency_output_column,
    )
    print(f"[FE-05] Frequency materialized: {frequency_materialized.shape[0]:,} customers")

    # Monetary (4 variants comparison; materialize ONE)
    monetary_variants = compute_all_monetary_variants(
        df_transactions,
        df_base,
        customer_key=config.customer_key or "CustomerID",
    )
    monetary_materialized = materialize_one_monetary_candidate(
        monetary_variants,
        df_base,
        variant=config.rfm.monetary_default_variant,
        output_column=config.rfm.monetary_output_column,
        customer_key=config.customer_key or "CustomerID",
    )
    print(f"[FE-05] Monetary materialized: {monetary_materialized.shape[0]:,} customers")

    # ------------------------------------------------------------------
    # 5. Extended behavioral features
    # ------------------------------------------------------------------
    print("[FE-05] computing extended behavioral features...")

    # Build interim candidate df for cancellation/return rate computation
    interim_df = df_base[
        [config.customer_key or "CustomerID", "CancellationInvoiceCount", "ReturnInvoiceCount"]
    ].copy()
    interim_df = interim_df.merge(
        frequency_materialized, on=config.customer_key or "CustomerID", how="left"
    )
    interim_df = interim_df.merge(
        monetary_materialized, on=config.customer_key or "CustomerID", how="left"
    )

    # AverageInvoiceValue (FE-05 candidate; uses Monetary / Frequency)
    average_invoice_value_df = _compute_ave_inv(
        df_base,
        monetary_materialized[config.rfm.monetary_output_column],
        frequency_materialized[config.rfm.frequency_output_column],
        customer_key=config.customer_key or "CustomerID",
    )

    # Transaction behavior: tenure, interval, active days
    tenure_df = compute_tenure_days(df_base, customer_key=config.customer_key or "CustomerID")
    purchase_interval_df = compute_purchase_interval(
        df_transactions, customer_key=config.customer_key or "CustomerID"
    )
    active_days_df = compute_active_days(
        df_transactions, customer_key=config.customer_key or "CustomerID"
    )

    # Quantity working set (signed vs purchase-only comparison; materialize signed)
    from customer_segmentation.features.transaction_behavior import (
        compute_purchase_only_quantity_set,
        compute_signed_quantity_set,
    )

    signed_set = compute_signed_quantity_set(
        df_transactions, df_base, customer_key=config.customer_key or "CustomerID"
    )
    purchase_only_set = compute_purchase_only_quantity_set(
        df_transactions, df_base, customer_key=config.customer_key or "CustomerID"
    )

    # Use signed quantity set for candidate dataset
    quantity_set = signed_set.rename(
        columns={
            "TotalQuantity_Signed": "TotalQuantity",
            "AverageQuantity_Signed": "AverageQuantity",
            "BasketSize_Signed": "BasketSize",
        }
    )[[config.customer_key or "CustomerID", "TotalQuantity", "AverageQuantity", "BasketSize"]]

    # Diversity: ProductsPerInvoice
    diversity_df = compute_diversity_features(
        df_base, customer_key=config.customer_key or "CustomerID"
    )

    # Cancellation/Return: CancellationRate, ReturnRate
    cancellation_df = compute_cancellation_features(
        interim_df, customer_key=config.customer_key or "CustomerID"
    )

    # ------------------------------------------------------------------
    # 6. Build candidate dataset Tầng 2
    # ------------------------------------------------------------------
    print("[FE-05] building candidate dataset Tầng 2...")
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
        customer_key=config.customer_key or "CustomerID",
    )

    # Validate candidate dataset
    validation_checks = validate_candidate_dataset(candidate_result)
    purchase_interval_check = validate_purchase_interval_na(candidate_result.df)
    unique_customers_check = validate_unique_customers(candidate_result.df)

    print(
        f"[FE-05] candidate dataset: {candidate_result.customer_count:,} customers, "
        f"{len(candidate_result.candidate_features)} candidate features."
    )

    # ------------------------------------------------------------------
    # 7. Write output (read-only inputs must remain unchanged)
    # ------------------------------------------------------------------
    processed_dir.mkdir(parents=True, exist_ok=True)
    candidate_path = processed_dir / config.output.candidate_filename
    candidate_result.df.to_parquet(candidate_path, index=False)
    output_sha_candidate = _sha256_file(candidate_path)
    print(f"[FE-05] candidate dataset written: {candidate_path}")

    # ------------------------------------------------------------------
    # 8. SHA-256 after (verify input unchanged)
    # ------------------------------------------------------------------
    input_sha_base_after = _sha256_file(customer_base_path)
    input_sha_trans_after = _sha256_file(transactions_clean_path)

    if input_sha_base_after != input_sha_base_before:
        raise RuntimeError(
            f"FE-04 customer_base SHA-256 changed during FE-05 run: "
            f"before={input_sha_base_before}, after={input_sha_base_after}. "
            "FE-05 must not mutate the FE-04 input."
        )
    if input_sha_trans_after != input_sha_trans_before:
        raise RuntimeError(
            f"FE-02 transactions_clean SHA-256 changed during FE-05 run: "
            f"before={input_sha_trans_before}, after={input_sha_trans_after}. "
            "FE-05 must not mutate the FE-02 input."
        )
    print(
        f"[FE-05] input SHA-256 verified unchanged: "
        f"customer_base={input_sha_base_before[:16]}..., "
        f"transactions_clean={input_sha_trans_before[:16]}..."
    )

    # ------------------------------------------------------------------
    # 9. Analysis (only numeric CANDIDATE features)
    # ------------------------------------------------------------------
    print("[FE-05] running analysis (numeric CANDIDATE features only)...")

    numeric_features = select_numeric_candidate_columns(
        candidate_result.df,
        candidate_result.candidate_features,
        include_date_features=config.analysis_scope.include_date_features,
    )
    print(f"[FE-05] numeric candidate features: {len(numeric_features)}")

    # Distribution analysis
    distribution = compute_distribution_stats(candidate_result.df, numeric_features)

    # Variance analysis
    variance = compute_variance_stats(candidate_result.df, numeric_features)

    # Correlation matrices (Pearson + Spearman)
    correlation = compute_correlation_matrices(candidate_result.df, numeric_features)

    # Redundancy detection
    redundancy = detect_redundancy(
        correlation.pearson, threshold=config.selection.redundancy_gate.threshold or 0.95
    )

    # Outlier detection
    outliers = detect_outliers(candidate_result.df, numeric_features)

    # Interpretability
    interpretability = assess_interpretability(
        candidate_result.candidate_features,
        feature_descriptions={},  # No descriptions in this version
    )

    # Shapiro-Wilk (optional diagnostic)
    shapiro_results = shapiro_wilk_diagnostic(
        candidate_result.df,
        numeric_features,
        alpha=config.selection.shapiro_wilk_gate.alpha or 0.05,
        random_seed=config.random_seed,
    )

    # ------------------------------------------------------------------
    # 10. Feature Selection (evidence-based gates)
    # ------------------------------------------------------------------
    print("[FE-05] running evidence-based feature selection...")

    gate_results: dict[str, list] = {}

    for feat in candidate_result.candidate_features:
        results = []

        # Interpretability gate
        is_interpretable = feat in DEFAULT_INTERPRETABLE_FEATURES
        results.append(apply_interpretability_gate(feat, is_interpretable=is_interpretable))

        # Data quality gate
        results.append(
            apply_data_quality_gate(
                feat,
                candidate_result.df[feat],
                max_missing_ratio=config.selection.data_quality_gate.max_missing_ratio or 0.5,
            )
        )

        # Leakage gate
        results.append(apply_leakage_gate(feat, is_potential_leakage=False))

        # Zero-variance gate
        results.append(apply_zero_variance_gate(feat, candidate_result.df[feat]))

        # Redundancy gate (DIAGNOSTIC ONLY)
        max_corr = (
            redundancy.pairs_df.loc[
                (redundancy.pairs_df["Feature1"] == feat)
                | (redundancy.pairs_df["Feature2"] == feat),
                "AbsCorrelation",
            ].max()
            if not redundancy.pairs_df.empty
            else None
        )
        max_corr_val = None if pd.isna(max_corr) else float(max_corr)

        results.append(
            apply_redundancy_gate(
                feat,
                max_correlation_with_others=max_corr_val if max_corr_val is not None else 0.0,
                threshold=config.selection.redundancy_gate.threshold or 0.95,
            )
        )

        # Stability gate (DIAGNOSTIC ONLY - skipped here)
        results.append(apply_stability_gate(feat, stability_score=None))

        # Shapiro-Wilk gate (DIAGNOSTIC ONLY)
        sw_row = shapiro_results[shapiro_results["Feature"] == feat]
        is_normal = None
        if not sw_row.empty:
            is_normal_val = sw_row.iloc[0]["IsNormal"]
            is_normal = is_normal_val == "Yes" if is_normal_val in ("Yes", "No") else None
        results.append(apply_shapiro_wilk_gate(feat, is_normal=is_normal))

        gate_results[feat] = results

    selection_result = make_selection_decisions(gate_results, redundancy.pairs_df)

    unsupported_features = [u.name for u in config.unsupported]
    selection_df = build_feature_selection_report(selection_result, unsupported_features)

    print(
        f"[FE-05] selection: "
        f"{selection_result.retain_count} RETAIN_CANDIDATE, "
        f"{selection_result.pending_count} PENDING_REVIEW."
    )

    # ------------------------------------------------------------------
    # 11. Build feature layer map for dictionary
    # ------------------------------------------------------------------
    feature_layer_map: dict[str, str] = {}
    layer_cfg = config.layer_classification
    for layer_name, features in [
        ("IDENTIFIER_ONLY", layer_cfg.IDENTIFIER_ONLY),
        ("SOURCE_ONLY", layer_cfg.SOURCE_ONLY),
        ("BASE_REFERENCE", layer_cfg.BASE_REFERENCE),
        ("CANDIDATE", layer_cfg.CANDIDATE),
        ("UNSUPPORTED", layer_cfg.UNSUPPORTED),
    ]:
        for feat in features:
            feature_layer_map[feat] = layer_name

    # Mark candidate features that were in the candidate dataset
    for feat in candidate_result.candidate_features:
        if feat not in feature_layer_map:
            feature_layer_map[feat] = "CANDIDATE"

    # ------------------------------------------------------------------
    # 12. PENDING_REVIEW notes
    # ------------------------------------------------------------------
    pending_review_notes = [
        "ReferenceDate strategy (snapshot_max): MENTOR_REVIEW_PENDING",
        "Recency (transaction recency): WORKING_ASSUMPTION; purchase-only recency PENDING_REVIEW",
        "Frequency (Frequency_ByInvoice = FREQ-01 default): WORKING_ASSUMPTION",
        "Monetary (MonetarySigned default): WORKING_ASSUMPTION",
        "Quantity (signed default): WORKING_ASSUMPTION; purchase-only comparison required",
        "ProductsPerInvoice is ratio proxy (not standard diversity metric): WORKING_ASSUMPTION",
        "CancellationRate / ReturnRate denominator = Frequency: WORKING_ASSUMPTION",
        "PurchaseIntervalMean / PurchaseIntervalStd NaN semantics (< 2 invoices): WORKING_ASSUMPTION",
        "Feature Selection gates are evidence-based; no numerical score/rank/weight.",
        "RETAIN_CANDIDATE means eligible for FE-06, NOT final.",
        "Shapiro-Wilk, Redundancy, Stability gates are diagnostic only.",
        "CategoryCount NOT materialized (dataset lacks official taxonomy).",
    ]

    # ------------------------------------------------------------------
    # 13. Write reports
    # ------------------------------------------------------------------
    print("[FE-05] writing reports...")

    executed_at_utc = datetime.now(UTC).isoformat()
    platform_info = {
        "python": platform.python_version(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
    }

    # Build frequency comparison DataFrame
    frequency_comparison_df = frequency_variants.comparison_df.rename(
        columns={
            "Frequency_ByInvoice": "FREQ_01_ByInvoice",
            "Frequency_ByTransactionLine": "FREQ_02_ByTransactionLine",
        }
    )

    # Build monetary comparison DataFrame (with overlap info)
    monetary_comparison_df = monetary_variants.comparison_df.copy()

    # Build quantity comparison DataFrame
    quantity_comparison_df = signed_set.merge(
        purchase_only_set,
        on=config.customer_key or "CustomerID",
        how="left",
        suffixes=("", "_purchase_only"),
    )
    quantity_comparison_df["TotalQuantity_Diff"] = (
        quantity_comparison_df["TotalQuantity_Signed"]
        - quantity_comparison_df["TotalQuantity_PurchaseOnly"]
    )

    # Feature selection summary
    feature_selection_summary = {
        "RETAIN_CANDIDATE": int((selection_df["Decision"] == DECISION_RETAIN_CANDIDATE).sum()),
        "EXCLUDE": int((selection_df["Decision"] == "EXCLUDE").sum()),
        "ADJUST": int((selection_df["Decision"] == "ADJUST").sum()),
        "PENDING_REVIEW": int((selection_df["Decision"] == "PENDING_REVIEW").sum()),
        "UNSUPPORTED": int((selection_df["Decision"] == "UNSUPPORTED").sum()),
    }

    # Config dict
    config_dict = {
        "enabled": config.enabled,
        "random_seed": config.random_seed,
        "reference_date_mode": config.reference_date.mode,
        "reference_date_status": config.reference_date.status,
        "frequency_mode": config.rfm.frequency_mode,
        "monetary_default_variant": config.rfm.monetary_default_variant,
        "quantity_default_variant": config.quantity.default_variant,
        "selection_redundancy_threshold": config.selection.redundancy_gate.threshold,
        "selection_max_missing_ratio": config.selection.data_quality_gate.max_missing_ratio,
    }

    # Validation results for narrative
    validation_results = {
        "unique_customers": validation_checks["unique_customers"],
        "no_category_count": validation_checks["no_category_count"],
        "one_monetary": validation_checks["one_monetary"],
        "one_frequency": validation_checks["one_frequency"],
        "one_quantity_set": validation_checks["one_quantity_set"],
        "purchase_interval_na": {
            "status": purchase_interval_check.status,
            "message": purchase_interval_check.message,
        },
        "unique_customers_check": {
            "status": unique_customers_check.status,
            "message": unique_customers_check.message,
        },
    }

    report_paths = write_all_fe05_reports(
        report_dir,
        reference_date=reference_date,
        customer_count=candidate_result.customer_count,
        candidate_features=candidate_result.candidate_features,
        recency_df=recency_df,
        frequency_variants_df=frequency_comparison_df,
        monetary_variants_df=monetary_comparison_df,
        quantity_comparison_df=quantity_comparison_df,
        distribution_df=distribution.stats_df,
        variance_df=variance.stats_df,
        correlation_pearson=correlation.pearson,
        correlation_spearman=correlation.spearman,
        redundancy_pairs=redundancy.pairs_df,
        outlier_counts=outliers.outlier_counts,
        feature_selection_df=selection_df,
        interpretability_df=interpretability.assessment_df,
        feature_layer_map=feature_layer_map,
        feature_descriptions={},
        feature_status_map={},
        input_sha256_customer_base=input_sha_base_before,
        input_sha256_transactions=input_sha_trans_before,
        output_sha256_candidate=output_sha_candidate,
        config_source=config_source_label,
        config_dict=config_dict,
        pending_review_notes=pending_review_notes,
        feature_selection_summary=feature_selection_summary,
        validation_results=validation_results,
        executed_at_utc=executed_at_utc,
        platform_info=platform_info,
    )
    print(f"[FE-05] reports written: {report_dir}")

    # ------------------------------------------------------------------
    # 14. Return summary
    # ------------------------------------------------------------------
    return {
        "task_id": "FE-05",
        "enabled": True,
        "config_source": config_source_label,
        "input_sha256_customer_base": input_sha_base_before,
        "input_sha256_customer_base_unchanged": input_sha_base_before == input_sha_base_after,
        "input_sha256_transactions_clean": input_sha_trans_before,
        "input_sha256_transactions_clean_unchanged": input_sha_trans_before
        == input_sha_trans_after,
        "output_sha256_candidate": output_sha_candidate,
        "candidate_dataset_path": str(candidate_path),
        "report_dir": str(report_dir),
        "customer_count": candidate_result.customer_count,
        "candidate_feature_count": len(candidate_result.candidate_features),
        "reference_date": reference_date.isoformat(),
        "feature_selection_summary": feature_selection_summary,
        "validation": validation_results,
        "executed_at_utc": executed_at_utc,
        "platform": platform_info,
        "reports": {k: str(v) for k, v in report_paths.all_paths().items()},
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "FE-05 feature engineering pipeline. "
            "Reads FE-04 customer_base.parquet and FE-02 transactions_clean.parquet. "
            "Writes customer_candidates.parquet and reports under reports/fe05/."
        ),
    )
    p.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to the feature engineering YAML. "
        "If omitted, auto-discovers 'configs/feature_engineering.yaml'.",
    )
    p.add_argument(
        "--customer-base",
        type=Path,
        default=DEFAULT_CUSTOMER_BASE_PATH,
        help="Path to the FE-04 customer_base.parquet.",
    )
    p.add_argument(
        "--transactions-clean",
        type=Path,
        default=DEFAULT_TRANSACTIONS_CLEAN_PATH,
        help="Path to the FE-02 transactions_clean.parquet.",
    )
    p.add_argument(
        "--processed-dir",
        type=Path,
        default=DEFAULT_PROCESSED_DIR,
        help="Output directory for the candidate dataset.",
    )
    p.add_argument(
        "--report-dir",
        type=Path,
        default=DEFAULT_REPORT_DIR,
        help="Output directory for FE-05 reports.",
    )
    return p


def main(argv: list[str] | None = None) -> None:
    args = _build_argparser().parse_args(argv)
    print(f"[FE-05] customer_base:      {args.customer_base}")
    print(f"[FE-05] transactions_clean: {args.transactions_clean}")
    print(f"[FE-05] output dir:         {args.processed_dir}")
    print(f"[FE-05] report dir:         {args.report_dir}")

    summary = run_fe05_pipeline(
        customer_base_path=args.customer_base,
        transactions_clean_path=args.transactions_clean,
        processed_dir=args.processed_dir,
        report_dir=args.report_dir,
        config_path=args.config,
    )

    if not summary.get("enabled", True):
        return

    print(
        f"[FE-05] candidate dataset: "
        f"{summary['customer_count']:,} customers, "
        f"{summary['candidate_feature_count']} candidate features."
    )
    print(f"[FE-05] reference date:     {summary['reference_date']}")
    print(f"[FE-05] candidate dataset:  {summary['candidate_dataset_path']}")
    print(f"[FE-05] reports:            {summary['report_dir']}")
    print(
        f"[FE-05] input SHA-256 unchanged: "
        f"customer_base={summary['input_sha256_customer_base_unchanged']}, "
        f"transactions_clean={summary['input_sha256_transactions_clean_unchanged']}"
    )
    fs = summary.get("feature_selection_summary", {})
    print(
        f"[FE-05] selection: "
        f"{fs.get('RETAIN_CANDIDATE', 0)} RETAIN_CANDIDATE, "
        f"{fs.get('PENDING_REVIEW', 0)} PENDING_REVIEW, "
        f"{fs.get('EXCLUDE', 0)} EXCLUDE, "
        f"{fs.get('UNSUPPORTED', 0)} UNSUPPORTED."
    )


if __name__ == "__main__":
    main()
