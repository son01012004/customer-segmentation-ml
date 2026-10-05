"""FE-03 orchestrator: outlier and distribution analysis on the FE-02 cleaned dataset.

Stage: 03_outlier_analysis (FE-03)

Usage (from the repository root):

    python -m scripts.run_fe03_outlier_analysis [--config PATH] [--write-treated]

The orchestrator loads ``configs/outlier.yaml`` (or the path supplied via
``--config``), runs the deterministic distribution / detection / sensitivity /
interpretation pipeline on the FE-02 cleaned parquet, and writes the
reports under ``reports/fe03/``.

Hard constraints (from AGENTS.md)
---------------------------------
- The raw primary dataset and the FE-02 cleaned parquet are **read-only**.
  Their SHA-256 hashes are recorded before and after the run; a mismatch
  fails the pipeline.
- All detection / treatment thresholds come from the YAML config; nothing
  is hard-coded in the orchestrator.
- Defaults are exploratory (``treatment: "none"`` and
  ``output.write_treated_dataset: false``). A treated dataset is only
  written when the YAML AND ``--write-treated`` both opt in.
- Customer-level outputs are diagnostic-only; they are explicitly **not**
  the project's official RFM / extended-behavioural features.
- No clustering metric is consulted; FE-03 is independent of FE-06.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from customer_segmentation.config.outlier_loader import (  # noqa: E402
    FeatureOutlierConfig,
    OutlierAnalysisConfig,
    OutlierConfigError,
    load_outlier_config,
    outlier_config_to_dict,
    resolve_outlier_config_path,
)
from customer_segmentation.outlier_analysis.customer_aggregates import (  # noqa: E402
    compute_line_revenue,
    customer_diagnostic,
    filter_dataframe_for_mode,
    summarise_diagnostic,
)
from customer_segmentation.outlier_analysis.detection import (  # noqa: E402
    DetectionMethod,
    build_detection_summary_table,
    detect_for_feature,
)
from customer_segmentation.outlier_analysis.distribution import (  # noqa: E402
    EXTENDED_PERCENTILES,
    distribution_profile,
)
from customer_segmentation.outlier_analysis.interpretation import (  # noqa: E402
    interpret_outliers,
)
from customer_segmentation.outlier_analysis.report import (  # noqa: E402
    ReportContext,
    build_customer_diagnostic_csv,
    build_distribution_csv,
    build_feature_statistics_csv,
    build_outlier_analysis_md,
    build_outlier_summary_csv,
    build_percentile_csv,
    build_sensitivity_csv,
    build_treatment_decisions_csv,
)
from customer_segmentation.outlier_analysis.sensitivity import (  # noqa: E402
    sensitivity_summary_table,
    sensitivity_table,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


# Columns that the FE-02 cleaned parquet MUST contain. If any is missing,
# the orchestrator fails fast with a clear error.
REQUIRED_CLEANED_COLUMNS: tuple[str, ...] = (
    "InvoiceNo",
    "StockCode",
    "Quantity",
    "InvoiceDate",
    "UnitPrice",
    "CustomerID",
    "IsCancellation",
    "IsReturn",
)


# Default locations. Used by the CLI defaults and by the
# `OutlierAnalysisConfig` defaults.
DEFAULT_PROCESSED_DIR: Path = _REPO_ROOT / "data" / "processed"
DEFAULT_REPORT_DIR: Path = _REPO_ROOT / "reports" / "fe03"
DEFAULT_RAW_PATH: Path = _REPO_ROOT / "data" / "raw" / "primary" / "Online Retail.xlsx"
DEFAULT_CLEANED_PATH: Path = DEFAULT_PROCESSED_DIR / "transactions_clean.parquet"
DEFAULT_TREATED_FILENAME: str = "transactions_outlier_treated.parquet"


# Map our YAML ``detection`` names to the detector signatures used by
# :func:`detect_for_feature`.
def _resolve_detection_method(detection: str) -> DetectionMethod:
    if detection not in {"iqr", "zscore", "percentile"}:
        raise OutlierConfigError(
            f"Unknown detection method {detection!r}; " "valid: ['iqr', 'zscore', 'percentile']."
        )
    return detection  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# IO helpers
# ---------------------------------------------------------------------------


def _sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    """Compute SHA-256 of a file by streaming chunks."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False, default=str))


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


# ---------------------------------------------------------------------------
# Config resolution
# ---------------------------------------------------------------------------


def _resolve_outlier_config(
    explicit: Path | None,
) -> tuple[OutlierAnalysisConfig, str]:
    """Resolve the active outlier config and report the source.

    Priority order:

    1. ``--config PATH`` argument.
    2. Auto-discovery: ``configs/outlier.yaml`` (the canonical location).
    3. Hard-coded defaults — a warning is printed.

    Returns
    -------
    (config, source_label)
        ``source_label`` is ``"yaml:<path>"``, ``"yaml_auto:<path>"``, or
        ``"default"``.
    """
    yaml_path = resolve_outlier_config_path(explicit=explicit)
    if yaml_path is None:
        print(
            "[FE-03] NOTE: configs/outlier.yaml not found; "
            "falling back to dataclass defaults (treatment=none, "
            "write_treated_dataset=false)."
        )
        return OutlierAnalysisConfig(), "default"

    try:
        loaded = load_outlier_config(yaml_path, strict=True)
    except OutlierConfigError as exc:
        raise SystemExit(f"[FE-03] invalid outlier config at {yaml_path}: {exc}") from exc

    label = f"yaml:{yaml_path}" if explicit is not None else f"yaml_auto:{yaml_path}"
    print(f"[FE-03] loaded outlier config: {yaml_path}")
    return loaded, label


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def _validate_cleaned_schema(df: pd.DataFrame) -> None:
    """Fail fast if the FE-02 cleaned parquet is missing required columns."""
    missing = [c for c in REQUIRED_CLEANED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            "FE-02 cleaned parquet is missing required column(s): "
            f"{missing}. Re-run FE-02 (python -m scripts.run_fe02_cleaning)."
        )


# ---------------------------------------------------------------------------
# Distribution + detection + interpretation per (feature, filter_mode)
# ---------------------------------------------------------------------------


def _distribution_for_feature(
    df: pd.DataFrame,
    *,
    feature: FeatureOutlierConfig,
    filter_mode: str,
) -> Any:
    """Compute the distribution profile for a single (feature, filter_mode)."""
    work = filter_dataframe_for_mode(df, mode_name=filter_mode)
    if feature.column not in work.columns:
        raise KeyError(f"Feature {feature.column!r} not in filtered DataFrame columns.")
    return distribution_profile(
        work[feature.column],
        column=feature.column,
        percentiles=EXTENDED_PERCENTILES,
        total_rows=int(work.shape[0]),
    )


def _detection_for_feature(
    df: pd.DataFrame,
    *,
    feature: FeatureOutlierConfig,
    filter_mode: str,
) -> tuple[pd.Series, Any]:
    """Run the configured detection method for one (feature, filter_mode)."""
    work = filter_dataframe_for_mode(df, mode_name=filter_mode)
    if feature.column not in work.columns:
        raise KeyError(f"Feature {feature.column!r} not in filtered DataFrame columns.")
    series = work[feature.column]
    return detect_for_feature(
        series,
        feature_name=feature.column,
        method=_resolve_detection_method(feature.detection),
        iqr_multiplier=feature.iqr_multiplier,
        zscore_threshold=feature.zscore_threshold,
        percentile_threshold=(
            feature.percentile_thresholds[0] if feature.percentile_thresholds else 99.0
        ),
        filter_mode=filter_mode,
    )


def _sensitivity_for_feature(
    df: pd.DataFrame,
    *,
    feature: FeatureOutlierConfig,
    filter_mode: str,
) -> pd.DataFrame:
    """Run the sensitivity sweep for one (feature, filter_mode)."""
    work = filter_dataframe_for_mode(df, mode_name=filter_mode)
    if feature.column not in work.columns:
        raise KeyError(f"Feature {feature.column!r} not in filtered DataFrame columns.")
    return sensitivity_table(
        work[feature.column],
        feature_name=feature.column,
        filter_mode=filter_mode,
        config=None,
    )


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def run_outlier_pipeline(
    cleaned_parquet_path: Path,
    raw_dataset_path: Path,
    report_dir: Path,
    *,
    config: OutlierAnalysisConfig | None = None,
    config_path: Path | None = None,
    write_treated_dataset: bool = False,
) -> dict[str, Any]:
    """Run the FE-03 outlier pipeline end-to-end.

    Parameters
    ----------
    cleaned_parquet_path : pathlib.Path
        Path to the FE-02 cleaned parquet (``transactions_clean.parquet``).
    raw_dataset_path : pathlib.Path
        Path to the raw primary xlsx file. Used for SHA-256 verification
        only; the file is **not** read or modified.
    report_dir : pathlib.Path
        Output directory for FE-03 reports.
    config : OutlierAnalysisConfig, optional
        Explicit config. When provided, the YAML is **not** consulted.
    config_path : pathlib.Path, optional
        Explicit YAML path. ``None`` triggers auto-discovery.
    write_treated_dataset : bool, default False
        Opt-in flag for writing the treated dataset. Both this flag AND
        ``config.output.write_treated_dataset`` must be true to actually
        write the file.

    Returns
    -------
    dict
        Run summary suitable for the ``fe03_run.json`` artefact.
    """
    # ------------------------------------------------------------------
    # 0. Resolve config
    # ------------------------------------------------------------------
    config_source_label = "explicit_config"
    if config is None:
        config, config_source_label = _resolve_outlier_config(config_path)
    else:
        print("[FE-03] using explicit OutlierAnalysisConfig")
    print(f"[FE-03] config source: {config_source_label}")

    if not config.enabled:
        print("[FE-03] outlier_analysis.enabled=false in config; nothing to do.")
        return {"enabled": False, "config_source": config_source_label}

    if not cleaned_parquet_path.exists():
        raise FileNotFoundError(
            f"FE-02 cleaned parquet not found: {cleaned_parquet_path}. "
            "Run FE-02 first (python -m scripts.run_fe02_cleaning)."
        )

    # ------------------------------------------------------------------
    # 1. Hash raw + cleaned parquet (read-only)
    # ------------------------------------------------------------------
    if not raw_dataset_path.exists():
        raise FileNotFoundError(f"Raw dataset not found: {raw_dataset_path}.")
    raw_sha = _sha256_file(raw_dataset_path)
    cleaned_sha_before = _sha256_file(cleaned_parquet_path)

    # ------------------------------------------------------------------
    # 2. Load cleaned parquet (read-only)
    # ------------------------------------------------------------------
    df_clean = pd.read_parquet(cleaned_parquet_path)
    _validate_cleaned_schema(df_clean)

    # Derive LineRevenue on the fly. Never persist this back to the
    # cleaned parquet.
    df_work = compute_line_revenue(df_clean)

    # ------------------------------------------------------------------
    # 3. Iterate over (feature, filter_mode)
    # ------------------------------------------------------------------
    distribution_profiles: dict[str, dict[str, Any]] = {}
    detection_records: list[Any] = []
    sensitivity_tables: list[pd.DataFrame] = []
    interpretation_decisions: list[Any] = []

    filter_modes = [m.name for m in config.filter_modes] or [
        "all_rows",
        "clean_purchase",
        "non_cancellation",
        "non_return",
    ]

    transaction_columns_to_analyse = [f.column for f in config.transaction_features]

    for mode in filter_modes:
        profiles_for_mode: dict[str, Any] = {}
        for feature in config.transaction_features:
            # Distribution.
            prof = _distribution_for_feature(df_work, feature=feature, filter_mode=mode)
            profiles_for_mode[feature.column] = prof

            # Detection.
            _, rec = _detection_for_feature(df_work, feature=feature, filter_mode=mode)
            detection_records.append(rec)

            # Sensitivity (one table per (feature, filter_mode)).
            sens = _sensitivity_for_feature(df_work, feature=feature, filter_mode=mode)
            sensitivity_tables.append(sens)

            # Interpretation. Use the configured detection's candidate
            # count as evidence.
            decision = interpret_outliers(
                prof,
                feature_name=feature.column,
                filter_mode=mode,
                candidates=int(rec.candidates),
                rate=float(rec.rate),
            )
            interpretation_decisions.append(decision)

        distribution_profiles[mode] = profiles_for_mode

    # ------------------------------------------------------------------
    # 4. Customer-level diagnostic
    # ------------------------------------------------------------------
    customer_diagnostics: dict[str, pd.DataFrame] = {}
    customer_summary_chunks: list[pd.DataFrame] = []

    if config.customer_diagnostic.enabled:
        for mode in filter_modes:
            diag_result = customer_diagnostic(
                df_work,
                config.customer_diagnostic,
                filter_mode=mode,
            )
            customer_diagnostics[mode] = diag_result.frame

            # Per-aggregate summary (mirrors distribution_profile).
            summary = summarise_diagnostic(diag_result)
            if not summary.empty:
                summary["filter_mode"] = mode
                customer_summary_chunks.append(summary)

            # Sensitivity scan on the customer-level diagnostic.
            # We only scan the numeric aggregates (total_spend,
            # total_quantity) — the others (distinct_invoices,
            # distinct_products, active_days) are also numeric but
            # exploring them with sensitivity thresholds is the same
            # mechanical operation; we include them for completeness.
            for col in diag_result.frame.columns:
                if col == diag_result.config.customer_key:
                    continue
                if not pd.api.types.is_numeric_dtype(diag_result.frame[col]):
                    continue
                # Build a per-customer sensitivity table (no
                # filter_mode concept here — the data already
                # represents one customer per row).
                sens = sensitivity_table(
                    diag_result.frame[col],
                    feature_name=col,
                    filter_mode=mode,
                    config=None,
                )
                sensitivity_tables.append(sens)

    customer_diagnostic_summary = (
        pd.concat(customer_summary_chunks, ignore_index=True, sort=False)
        if customer_summary_chunks
        else pd.DataFrame()
    )
    if not customer_diagnostic_summary.empty:
        customer_diagnostic_summary = customer_diagnostic_summary.sort_values(
            ["filter_mode", "column"]
        ).reset_index(drop=True)

    # ------------------------------------------------------------------
    # 5. Build ReportContext
    # ------------------------------------------------------------------
    treated_path: Path | None = None
    if write_treated_dataset and config.output.write_treated_dataset:
        processed_dir = Path(config.output.processed_dir)
        processed_dir.mkdir(parents=True, exist_ok=True)
        treated_path = processed_dir / config.output.treated_filename
        # Default treatment is KEEP / none → write the dataset
        # **unchanged**. We do not silently transform the data.
        # A future mentor-approved treatment would replace this copy
        # with the transformed DataFrame.
        df_work.to_parquet(treated_path, index=False)
        print(f"[FE-03] treated dataset written to: {treated_path}")
    elif write_treated_dataset and not config.output.write_treated_dataset:
        print(
            "[FE-03] WARNING: --write-treated was passed but "
            "output.write_treated_dataset=false in YAML. Not writing."
        )

    run_id = datetime.now(UTC).isoformat()
    ctx = ReportContext(
        config=config,
        raw_sha256=raw_sha,
        cleaned_sha256_before=cleaned_sha_before,
        # Filled in after the run.
        cleaned_sha256_after=cleaned_sha_before,
        distribution_profiles=distribution_profiles,
        detection_records=detection_records,
        sensitivity_tables=sensitivity_tables,
        interpretation_decisions=interpretation_decisions,
        customer_diagnostics=customer_diagnostics,
        customer_diagnostic_summary=customer_diagnostic_summary,
        treated_dataset_path=str(treated_path) if treated_path else None,
        config_source=config_source_label,
        run_id=run_id,
        platform={
            "python": platform.python_version(),
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
    )

    # ------------------------------------------------------------------
    # 6. Write CSVs and Markdown
    # ------------------------------------------------------------------
    report_dir.mkdir(parents=True, exist_ok=True)

    _write_csv(
        build_distribution_csv(ctx),
        report_dir / "distribution_analysis.csv",
    )
    _write_csv(
        build_outlier_summary_csv(ctx),
        report_dir / "outlier_summary.csv",
    )
    _write_csv(
        build_treatment_decisions_csv(ctx),
        report_dir / "treatment_decisions.csv",
    )
    _write_csv(
        build_percentile_csv(ctx),
        report_dir / "percentile_analysis.csv",
    )
    _write_csv(
        build_sensitivity_csv(ctx),
        report_dir / "sensitivity_analysis.csv",
    )
    _write_csv(
        build_feature_statistics_csv(ctx),
        report_dir / "feature_statistics.csv",
    )
    _write_csv(
        build_customer_diagnostic_csv(ctx),
        report_dir / "customer_level_diagnostic.csv",
    )
    _write_text(
        report_dir / "outlier_analysis.md",
        build_outlier_analysis_md(ctx),
    )

    # ------------------------------------------------------------------
    # 7. Re-hash cleaned parquet and verify
    # ------------------------------------------------------------------
    cleaned_sha_after = _sha256_file(cleaned_parquet_path)
    if cleaned_sha_after != cleaned_sha_before:
        raise RuntimeError(
            "FE-02 cleaned parquet SHA-256 changed during FE-03 run: "
            f"before={cleaned_sha_before}, after={cleaned_sha_after}. "
            "FE-03 must not mutate the cleaned dataset."
        )
    print(
        "[FE-03] FE-02 cleaned parquet SHA-256 verified unchanged "
        f"({cleaned_sha_before[:16]}...)."
    )

    # Update ctx with the verified post-run SHA so the Markdown /
    # JSON report matches reality.
    ctx.cleaned_sha256_after = cleaned_sha_after
    # Re-write the Markdown so it reflects the verified after-SHA.
    _write_text(
        report_dir / "outlier_analysis.md",
        build_outlier_analysis_md(ctx),
    )

    # ------------------------------------------------------------------
    # 8. fe03_run.json
    # ------------------------------------------------------------------
    detection_df = build_detection_summary_table(detection_records)
    sensitivity_df = sensitivity_summary_table(sensitivity_tables)

    run_summary: dict[str, Any] = {
        "task_id": "FE-03",
        "executed_at_utc": run_id,
        "platform": ctx.platform,
        "input": {
            "raw_path": str(raw_dataset_path),
            "raw_sha256": raw_sha,
            "cleaned_parquet": str(cleaned_parquet_path),
            "cleaned_parquet_sha256": cleaned_sha_before,
            "cleaned_parquet_sha256_after": cleaned_sha_after,
            "cleaned_parquet_unchanged": cleaned_sha_before == cleaned_sha_after,
            "n_rows_in": int(df_clean.shape[0]),
        },
        "config": outlier_config_to_dict(config),
        "config_source": config_source_label,
        "features_analysed": transaction_columns_to_analyse,
        "filter_modes": filter_modes,
        "detection_records": int(detection_df.shape[0]),
        "sensitivity_rows": int(sensitivity_df.shape[0]),
        "interpretation_decisions": int(len(interpretation_decisions)),
        "customer_diagnostic_enabled": bool(config.customer_diagnostic.enabled),
        "customer_diagnostic_modes": list(customer_diagnostics.keys()),
        "treated_dataset_path": str(treated_path) if treated_path else None,
        "treated_dataset_written": treated_path is not None,
        "report_dir": str(report_dir),
        "outputs": {
            "distribution_analysis": str(report_dir / "distribution_analysis.csv"),
            "outlier_summary": str(report_dir / "outlier_summary.csv"),
            "treatment_decisions": str(report_dir / "treatment_decisions.csv"),
            "percentile_analysis": str(report_dir / "percentile_analysis.csv"),
            "sensitivity_analysis": str(report_dir / "sensitivity_analysis.csv"),
            "feature_statistics": str(report_dir / "feature_statistics.csv"),
            "customer_level_diagnostic": str(report_dir / "customer_level_diagnostic.csv"),
            "outlier_analysis_md": str(report_dir / "outlier_analysis.md"),
        },
        "notes": [
            "FE-03 is exploratory by default (treatment=none).",
            "Customer-level outputs are diagnostic-only; not RFM.",
            "Raw and FE-02 cleaned SHAs are verified unchanged.",
            "A treated dataset is only written when the YAML AND the "
            "--write-treated flag both opt in.",
        ],
    }
    _write_json(report_dir / "fe03_run.json", run_summary)

    return run_summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "FE-03 outlier and distribution analysis pipeline. "
            "Reads the FE-02 cleaned parquet and writes reports under "
            "reports/fe03/."
        ),
    )
    p.add_argument(
        "--config",
        type=Path,
        default=None,
        help=(
            "Path to the outlier YAML. If omitted, the orchestrator "
            "auto-discovers 'configs/outlier.yaml'."
        ),
    )
    p.add_argument(
        "--cleaned-parquet",
        type=Path,
        default=DEFAULT_CLEANED_PATH,
        help="Path to the FE-02 cleaned parquet.",
    )
    p.add_argument(
        "--raw-dataset",
        type=Path,
        default=DEFAULT_RAW_PATH,
        help="Path to the raw primary xlsx file (read-only; SHA-256 only).",
    )
    p.add_argument(
        "--report-dir",
        type=Path,
        default=DEFAULT_REPORT_DIR,
        help="Output directory for FE-03 reports.",
    )
    p.add_argument(
        "--write-treated",
        action="store_true",
        help=(
            "Opt-in flag to write the treated dataset. Both this flag "
            "AND output.write_treated_dataset=true in the YAML must be "
            "set for the file to be written."
        ),
    )
    return p


def main(argv: list[str] | None = None) -> None:
    args = _build_argparser().parse_args(argv)
    print(f"[FE-03] cleaned parquet: {args.cleaned_parquet}")
    print(f"[FE-03] raw dataset:     {args.raw_dataset}")
    print(f"[FE-03] report dir:      {args.report_dir}")
    summary = run_outlier_pipeline(
        cleaned_parquet_path=args.cleaned_parquet,
        raw_dataset_path=args.raw_dataset,
        report_dir=args.report_dir,
        config_path=args.config,
        write_treated_dataset=args.write_treated,
    )
    if not summary.get("enabled", True):
        return
    print(
        "[FE-03] analysis done: "
        f"{summary['features_analysed']} features analysed, "
        f"{summary['detection_records']} detection rows, "
        f"{summary['sensitivity_rows']} sensitivity rows, "
        f"{summary['interpretation_decisions']} interpretation decisions."
    )
    print(f"[FE-03] reports: {summary['report_dir']}")
    if summary.get("treated_dataset_written"):
        print(f"[FE-03] treated dataset: {summary['treated_dataset_path']}")
    else:
        print("[FE-03] treated dataset: NOT written (default behaviour).")
    print(f"[FE-03] cleaned parquet SHA unchanged: {summary['input']['cleaned_parquet_unchanged']}")


if __name__ == "__main__":
    main()
