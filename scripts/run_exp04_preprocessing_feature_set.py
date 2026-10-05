#!/usr/bin/env python3
"""EXP-04 Preprocessing & Feature Set Sensitivity Runner.

CLI entry point for EXP-04 Family B (preprocessing sensitivity on
the RFM Extended feature set). EXP-04 Family A (feature set
sensitivity) is DEFERRED pending FE-06 materialization; this
runner does not produce any RFM-only artifact.

This script performs the FULL EXP-04 research execution only when
explicitly invoked. Implementation-only phases must call the
underlying module directly without invoking this CLI.

Hard constraints (AGENTS.md §2, EXP-04 Plan R2):

- FE-05 / FE-06 outputs are READ-ONLY. SHA-256 verified before and
  after the run.
- Family A (Feature Set Sensitivity) is NOT executed; only Family B
  (Preprocessing Sensitivity) on RFM Extended is run.
- Decision status uses ONLY the taxonomy
  {CANDIDATE_SCENARIO, TIED_SCENARIOS, PENDING_REVIEW, DEFERRED}.
- No "best/optimal/superior/winner/recommended/final" labels.
- No composite scoring, no algorithm ranking, no K-sweep.

Output artifacts (under reports/exp04/):

- exp04_manifest.json
- exp04_run_summary.json
- exp04_scenario_results.csv         (per scenario x repeat)
- exp04_preprocessing_sensitivity.csv (per scenario aggregate)
- exp04_analysis.md                  (Vietnamese narrative report)
- exp04_deferred.json                (Family A deferred evidence)
- exp04_pending_review.json          (PENDING_REVIEW items)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform as platform_module
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

# Add src to path
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _REPO_ROOT / "src"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from customer_segmentation.clustering.config import (  # noqa: E402
    compute_text_sha256,
    load_framework_config,
)
from customer_segmentation.clustering.preprocessing_feature_sensitivity import (  # noqa: E402
    DECISION_STATUS_PENDING_REVIEW,
    FORBIDDEN_DECISION_LABELS,
    PERMITTED_DECISION_STATUSES,
    PreprocessingFeatureSensitivityRunner,
    ScenarioAggregateRecord,
    ScenarioRepeatRecord,
    SensitivitySweepResult,
)

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

_EXP04_CONFIG_PATH = _REPO_ROOT / "configs" / "exp04_preprocessing_feature_set.yaml"
_FRAMEWORK_CONFIG_PATH = _REPO_ROOT / "configs" / "clustering.yaml"
_REPORTS_DIR = _REPO_ROOT / "reports" / "exp04"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_utc_iso() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(UTC).isoformat()


def _compute_file_sha256(path: Path) -> str:
    """Compute SHA-256 of a file."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _library_versions() -> dict[str, str]:
    """Snapshot versions of libraries EXP-04 depends on."""
    import numpy
    import pandas
    import pyarrow
    import scipy
    import sklearn

    return {
        "numpy": numpy.__version__,
        "pandas": pandas.__version__,
        "scipy": scipy.__version__,
        "scikit-learn": sklearn.__version__,
        "pyarrow": pyarrow.__version__,
    }


def _platform_info() -> dict[str, str]:
    """Snapshot Python / OS environment."""
    return {
        "python": platform_module.python_version(),
        "system": platform_module.system(),
        "release": platform_module.release(),
        "machine": platform_module.machine(),
    }


def _write_json(data: dict[str, Any], path: Path) -> None:
    """Write JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=False, default=str)


def _write_csv(df: pd.DataFrame, path: Path) -> None:
    """Write CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")


def _write_markdown(content: str, path: Path) -> None:
    """Write Markdown file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(content)


# ---------------------------------------------------------------------------
# Artifact generators
# ---------------------------------------------------------------------------


def _generate_manifest(
    sweep: SensitivitySweepResult,
    exp04_config: dict[str, Any],
    config_sha: str,
    candidates_sha: str,
    metadata_sha: str,
    input_integrity_ok: bool,
) -> dict[str, Any]:
    """Generate EXP-04 manifest JSON."""
    exp04_section = exp04_config.get("exp04", {})
    return {
        "experiment_id": "EXP-04",
        "name": exp04_section.get("name", "EXP-04 Preprocessing & Feature Set Sensitivity"),
        "description": exp04_section.get("description", ""),
        "plan_revision": exp04_section.get("metadata", {}).get("plan_revision", "R2"),
        "timestamp": _now_utc_iso(),
        "dataset_version": exp04_section.get("dataset", {}).get("version", "FE06-v1.0"),
        "input_sha256": candidates_sha,
        "customer_metadata_sha256": metadata_sha,
        "config_sha256": config_sha,
        "feature_set": sweep.feature_set,
        "feature_set_sha256": sweep.feature_set_sha256,
        "algorithm": sweep.algorithm,
        "n_clusters": sweep.n_clusters,
        "seed": sweep.seed,
        "n_repeat": sweep.n_repeat,
        "n_total_records": len(sweep.records),
        "n_successful_records": sum(1 for r in sweep.records if r.status == "SUCCESS"),
        "n_aggregates": len(sweep.aggregates),
        "library_versions": sweep.library_versions,
        "platform": sweep.platform_info,
        "input_integrity_verified": input_integrity_ok,
        "decision_status_options": sorted(PERMITTED_DECISION_STATUSES),
        "forbidden_decision_labels": sorted(FORBIDDEN_DECISION_LABELS),
        "scope_boundaries": exp04_section.get("metadata", {}).get("scope_boundaries", []),
        "pending_review_notes": exp04_section.get("metadata", {}).get("pending_review_notes", []),
        "family_a_status": exp04_section.get("family_a", {}).get("status", "DEFERRED"),
        "family_b_status": exp04_section.get("family_b", {}).get("status", "EXECUTED"),
        "reproducibility_note": (
            "REPRODUCIBILITY_VERIFICATION (seed=42, n_repeat=5). " "NOT stability analysis."
        ),
        "records": [_repeat_record_to_dict(r) for r in sweep.records],
        "aggregates": [_aggregate_to_dict(a) for a in sweep.aggregates],
    }


def _generate_run_summary(
    sweep: SensitivitySweepResult,
    config_sha: str,
    candidates_sha: str,
    metadata_sha: str,
) -> dict[str, Any]:
    """Generate EXP-04 run summary JSON."""
    successful = sum(1 for r in sweep.records if r.status == "SUCCESS")
    failed = sum(1 for r in sweep.records if r.status != "SUCCESS")
    return {
        "experiment_id": "EXP-04",
        "timestamp": _now_utc_iso(),
        "input_sha256": candidates_sha,
        "customer_metadata_sha256": metadata_sha,
        "config_sha256": config_sha,
        "feature_set": sweep.feature_set,
        "feature_set_sha256": sweep.feature_set_sha256,
        "algorithm": sweep.algorithm,
        "n_clusters": sweep.n_clusters,
        "seed": sweep.seed,
        "n_repeat": sweep.n_repeat,
        "n_total_records": len(sweep.records),
        "n_successful_records": successful,
        "n_failed_records": failed,
        "all_success": failed == 0,
        "results_by_status": {"SUCCESS": successful, "FAILED": failed},
        "n_aggregates": len(sweep.aggregates),
        "aggregates_summary": [
            {
                "scenario_id": a.scenario_id,
                "config_id": a.config_id,
                "transformation": a.transformation,
                "scaling": a.scaling,
                "silhouette": a.silhouette,
                "davies_bouldin": a.davies_bouldin,
                "calinski_harabasz": a.calinski_harabasz,
                "wcss": a.wcss,
                "runtime_mean_seconds": a.runtime_mean_seconds,
                "runtime_std_seconds": a.runtime_std_seconds,
                "determinism_verified": a.determinism_verified,
                "decision_status": a.decision_status,
            }
            for a in sweep.aggregates
        ],
        "library_versions": sweep.library_versions,
        "reproducibility_note": (
            "REPRODUCIBILITY_VERIFICATION (seed=42, n_repeat=5). " "NOT stability analysis."
        ),
    }


def _repeat_record_to_dict(r: ScenarioRepeatRecord) -> dict[str, Any]:
    """Serialise a per-repeat record to JSON-friendly dict."""
    return {
        "scenario_id": r.scenario_id,
        "config_id": r.config_id,
        "role": r.role,
        "repeat_index": r.repeat_index,
        "feature_set": r.feature_set,
        "feature_set_sha256": r.feature_set_sha256,
        "transformation": r.transformation,
        "scaling": r.scaling,
        "imputation": r.imputation,
        "algorithm": r.algorithm,
        "n_clusters": r.n_clusters,
        "random_seed": r.random_seed,
        "hyperparameters": r.hyperparameters,
        "status": r.status,
        "failure_reason": r.failure_reason,
        "silhouette": r.silhouette,
        "silhouette_status": r.silhouette_status,
        "davies_bouldin": r.davies_bouldin,
        "davies_bouldin_status": r.davies_bouldin_status,
        "calinski_harabasz": r.calinski_harabasz,
        "calinski_harabasz_status": r.calinski_harabasz_status,
        "wcss": r.wcss,
        "wcss_status": r.wcss_status,
        "runtime_seconds": r.runtime_seconds,
        "labels_hash": r.labels_hash,
        "n_clusters_realized": r.n_clusters_realized,
        "input_sha256": r.input_sha256,
        "customer_metadata_sha256": r.customer_metadata_sha256,
        "config_sha256": r.config_sha256,
        "library_versions": r.library_versions,
        "platform_info": r.platform_info,
    }


def _aggregate_to_dict(a: ScenarioAggregateRecord) -> dict[str, Any]:
    """Serialise an aggregate record to JSON-friendly dict."""
    return {
        "scenario_id": a.scenario_id,
        "config_id": a.config_id,
        "role": a.role,
        "feature_set": a.feature_set,
        "transformation": a.transformation,
        "scaling": a.scaling,
        "imputation": a.imputation,
        "algorithm": a.algorithm,
        "n_clusters": a.n_clusters,
        "silhouette": a.silhouette,
        "davies_bouldin": a.davies_bouldin,
        "calinski_harabasz": a.calinski_harabasz,
        "wcss": a.wcss,
        "runtime_mean_seconds": a.runtime_mean_seconds,
        "runtime_std_seconds": a.runtime_std_seconds,
        "labels_hash": a.labels_hash,
        "determinism_verified": a.determinism_verified,
        "n_successful_repeats": a.n_successful_repeats,
        "n_total_repeats": a.n_total_repeats,
        "decision_status": a.decision_status,
        "evidence_note": a.evidence_note,
    }


def _scenario_results_dataframe(sweep: SensitivitySweepResult) -> pd.DataFrame:
    """Build per-repeat CSV DataFrame."""
    rows: list[dict[str, Any]] = []
    for r in sweep.records:
        row = _repeat_record_to_dict(r)
        # Drop nested dicts for CSV flatness.
        row.pop("hyperparameters", None)
        row.pop("library_versions", None)
        row.pop("platform_info", None)
        rows.append(row)
    return pd.DataFrame(rows)


def _aggregate_dataframe(sweep: SensitivitySweepResult) -> pd.DataFrame:
    """Build per-scenario aggregate CSV DataFrame."""
    rows: list[dict[str, Any]] = []
    for a in sweep.aggregates:
        rows.append(_aggregate_to_dict(a))
    return pd.DataFrame(rows)


def _generate_markdown_report(
    sweep: SensitivitySweepResult,
    exp04_config: dict[str, Any],
    candidates_sha: str,
    metadata_sha: str,
    config_sha: str,
    input_integrity_ok: bool,
) -> str:
    """Generate EXP-04 analysis markdown report (Vietnamese)."""
    exp04_section = exp04_config.get("exp04", {})
    family_a = exp04_section.get("family_a", {})
    algo_cfg = exp04_section.get("algorithm", {})

    successful_aggregates = [
        a for a in sweep.aggregates if a.decision_status != DECISION_STATUS_PENDING_REVIEW
    ]
    pending_review_aggregates = [
        a for a in sweep.aggregates if a.decision_status == DECISION_STATUS_PENDING_REVIEW
    ]
    deterministic = [a for a in sweep.aggregates if a.determinism_verified]
    nondeterministic = [a for a in sweep.aggregates if not a.determinism_verified]

    md = f"""# EXP-04 Preprocessing & Feature Set Sensitivity Report

**Generated:** {_now_utc_iso()}
**Plan revision:** {exp04_section.get('metadata', {}).get('plan_revision', 'R2')}

## 1. Mục tiêu

EXP-04 đánh giá có kiểm soát ảnh hưởng của preprocessing configuration
đến clustering quality trên RFM Extended feature set. EXP-04 cũng
document gap về feature set sensitivity (Family A) đang DEFERRED.

**EXP-04-v1 KHÔNG**:
- Rank algorithms / chọn "best algorithm".
- Chạy lại K-sweep K = 2..10.
- Stability analysis.
- Composite score / weighted ranking.
- Gọi scenario nào là "best/optimal/superior/winner/recommended/final".

## 2. Family A — Feature Set Sensitivity

| Field | Value |
|-------|-------|
| Status | **{family_a.get('status', 'DEFERRED')}** |
| Deferred reason | {family_a.get('deferred_reason', '').strip()} |
| Owner | {family_a.get('owner', 'FE-06')} |
| Scenarios blocked | {', '.join(s['id'] for s in family_a.get('scenarios_blocked', []))} |
| RQ2 completeness | {family_a.get('rq2_completeness', 'PARTIAL')} |

**Lưu ý:** EXP-04-v1 KHÔNG tạo RFM-only dataset ad-hoc. Việc
materialize RFM-only thuộc FE-06 (cần ADR).

## 3. Family B — Preprocessing Sensitivity

### 3.1. Controls cố định

| Variable | Value | Tag |
|----------|-------|-----|
| Algorithm | `{algo_cfg.get('name', 'kmeans')}` | CONTROLLED_REFERENCE_ALGORITHM |
| K | `{algo_cfg.get('hyperparameters', {}).get('n_clusters', 4)}` | CONTROLLED_REFERENCE_K |
| Imputation | `median` (FE-06 C7 fitted values) | CONTROLLED_REFERENCE_IMPUTATION |
| Seed | `{sweep.seed}` | CONTROLLED_VARIABLE |
| n_repeat | `{sweep.n_repeat}` | REPRODUCIBILITY_VERIFICATION |

**Lưu ý:** KHÔNG stability analysis. Cùng seed → cùng labels_hash
và cùng metric values; chỉ wall-clock runtime có thể thay đổi.

### 3.2. Scenario matrix

| Scenario ID | Config ID | Transformation | Scaling | Role |
|-------------|-----------|----------------|---------|------|
"""

    for a in sweep.aggregates:
        md += (
            f"| {a.scenario_id} | {a.config_id} | `{a.transformation}` | "
            f"`{a.scaling}` | {a.role} |\n"
        )

    md += """
### 3.3. Kết quả aggregate

| Scenario | Silhouette | DBI | CH | WCSS | Runtime mean (s) | Runtime std (s) | Determinism | Decision |
|----------|------------|-----|-----|------|-------------------|-----------------|-------------|----------|
"""

    for a in sweep.aggregates:
        sil = f"{a.silhouette:.4f}" if a.silhouette is not None else "N/A"
        dbi = f"{a.davies_bouldin:.4f}" if a.davies_bouldin is not None else "N/A"
        ch = f"{a.calinski_harabasz:.2f}" if a.calinski_harabasz is not None else "N/A"
        wcss = f"{a.wcss:.2f}" if a.wcss is not None else "N/A"
        rm = f"{a.runtime_mean_seconds:.4f}" if a.runtime_mean_seconds is not None else "N/A"
        rs = f"{a.runtime_std_seconds:.4f}" if a.runtime_std_seconds is not None else "N/A"
        det = "True" if a.determinism_verified else "False"
        md += (
            f"| {a.scenario_id} | {sil} | {dbi} | {ch} | {wcss} | "
            f"{rm} | {rs} | {det} | {a.decision_status} |\n"
        )

    md += f"""
### 3.4. Determinism verification

- Deterministic scenarios: **{len(deterministic)}** / {len(sweep.aggregates)}
- Non-deterministic scenarios: **{len(nondeterministic)}** / {len(sweep.aggregates)}

Nếu có scenario nào non-deterministic, xem cột `evidence_note` trong
`exp04_preprocessing_sensitivity.csv` để biết chi tiết.

### 3.5. Decision status taxonomy

Các label được phép (chỉ những label này):

- `CANDIDATE_SCENARIO` — successful deterministic run.
- `TIED_SCENARIOS` — nhiều scenarios có metric aligned (ghi evidence).
- `PENDING_REVIEW` — không đủ evidence / metrics disagreement / determinism fail.
- `DEFERRED` — dành cho Family A (chưa execute).

**Các label bị CẤM**: BEST, OPTIMAL, WINNER, SUPERIOR, RECOMMENDED, FINAL.

## 4. Aggregate summary

| Metric | Value |
|--------|-------|
| Successful aggregates (non-PENDING_REVIEW) | {len(successful_aggregates)} |
| PENDING_REVIEW aggregates | {len(pending_review_aggregates)} |
| Total scenarios | {len(sweep.aggregates)} |
| Total per-repeat records | {len(sweep.records)} |
| Successful per-repeat records | {sum(1 for r in sweep.records if r.status == "SUCCESS")} |
| Failed per-repeat records | {sum(1 for r in sweep.records if r.status != "SUCCESS")} |
| Determinism verified (aggregates) | {len(deterministic)} |
| Determinism failed (aggregates) | {len(nondeterministic)} |

## 5. Provenance

| Field | Value |
|-------|-------|
| Dataset version | {exp04_section.get('dataset', {}).get('version', 'FE06-v1.0')} |
| customer_candidates.parquet SHA-256 | `{candidates_sha}` |
| customer_metadata.parquet SHA-256 | `{metadata_sha}` |
| Framework config SHA-256 | `{config_sha}` |
| Input integrity verified | {input_integrity_ok} |
| Library versions | {json.dumps(sweep.library_versions, sort_keys=True)} |
| Platform | {json.dumps(sweep.platform_info, sort_keys=True)} |

## 6. PENDING_REVIEW items

"""
    for note in exp04_section.get("metadata", {}).get("pending_review_notes", []):
        md += f"- **{note.get('id')}** ({note.get('status')}): {note.get('decision')}\n"

    md += """
## 7. Scope boundaries (cumulative)

### EXP-04 THỰC HIỆN

- Family A documentation as DEFERRED (no execution).
- Family B preprocessing sensitivity trên RFM Extended với 6 full-matrix scenarios.
- K-Means như CONTROLLED_REFERENCE_ALGORITHM (EXP-01 working defaults).
- K = 4 như CONTROLLED_REFERENCE_K; KHÔNG rerun K-sweep.
- Median imputation với FE-06 C7 fitted values (CONTROLLED_REFERENCE_IMPUTATION).
- REPRODUCIBILITY_VERIFICATION qua n_repeat=5, seed=42.
- Determinism verification per scenario (labels_hash + metrics).
- Decision status taxonomy: CANDIDATE_SCENARIO / TIED_SCENARIOS / PENDING_REVIEW / DEFERRED.
- FE-05 / FE-06 outputs READ-ONLY (SHA verified).

### EXP-04 KHÔNG THỰC HIỆN

- Không rank algorithms.
- Không "best/optimal/superior/winner/recommended/final" labels.
- Không composite score / weighted ranking.
- Không rerun K-sweep K = 2..10.
- Không stability analysis / ARI / AMI / bootstrap.
- Không dùng EXP-03 working / selected configurations.
- Không tạo RFM-only dataset ad-hoc.
- Không profiling customer / segment naming.
- Không mutate FE-05 / FE-06 outputs.
"""
    return md


def _generate_deferred(exp04_config: dict[str, Any]) -> dict[str, Any]:
    """Generate exp04_deferred.json (Family A deferred evidence)."""
    family_a = exp04_config.get("exp04", {}).get("family_a", {})
    return {
        "experiment_id": "EXP-04",
        "family_a": {
            "name": family_a.get("name", "feature_set_sensitivity"),
            "status": family_a.get("status", "DEFERRED"),
            "deferred_reason": family_a.get("deferred_reason", "").strip(),
            "owner": family_a.get("owner", "FE-06"),
            "scenarios_blocked": family_a.get("scenarios_blocked", []),
            "rq2_completeness": family_a.get(
                "rq2_completeness",
                "PARTIAL — preprocessing sensitivity completed; feature set sensitivity pending FE-06",
            ),
        },
        "timestamp": _now_utc_iso(),
        "notes": [
            "RFM-only dataset not present in repository.",
            "EXP-04 does NOT create RFM-only dataset ad-hoc.",
            "Feature Set Sensitivity (RFM vs RFM Extended) is DEFERRED.",
            "Dependency / ownership belongs to FE-06 (future ADR).",
            "EXP-04-v1 chỉ thực nghiệm preprocessing sensitivity trên RFM Extended.",
        ],
    }


def _generate_pending_review(exp04_config: dict[str, Any]) -> dict[str, Any]:
    """Generate exp04_pending_review.json from YAML pending_review_notes."""
    notes = exp04_config.get("exp04", {}).get("metadata", {}).get("pending_review_notes", [])
    return {
        "experiment_id": "EXP-04",
        "timestamp": _now_utc_iso(),
        "pending_review": notes,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _load_yaml_text(path: Path) -> str:
    """Read YAML file as text."""
    with path.open("r", encoding="utf-8") as fh:
        return fh.read()


def main() -> int:
    """Run EXP-04 Family B preprocessing sensitivity sweep."""
    parser = argparse.ArgumentParser(
        description="EXP-04 Preprocessing & Feature Set Sensitivity Runner"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=_EXP04_CONFIG_PATH,
        help="Path to EXP-04 YAML config.",
    )
    parser.add_argument(
        "--framework-config",
        type=Path,
        default=_FRAMEWORK_CONFIG_PATH,
        help="Path to ML-01 framework config (clustering.yaml).",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=_REPORTS_DIR,
        help="Where to write EXP-04 artifacts.",
    )
    args = parser.parse_args()

    print("[EXP-04] Starting preprocessing & feature set sensitivity sweep...")
    print(f"[EXP-04] Repository root: {_REPO_ROOT}")

    # Verify config files.
    if not args.config.exists():
        print(f"[EXP-04] ERROR: Config not found: {args.config}")
        return 1
    if not args.framework_config.exists():
        print(f"[EXP-04] ERROR: Framework config not found: {args.framework_config}")
        return 1

    # Load configs.
    exp04_config_text = _load_yaml_text(args.config)
    framework_config_text = _load_yaml_text(args.framework_config)
    exp04_config = yaml.safe_load(exp04_config_text)
    framework_config = load_framework_config(args.framework_config)

    config_sha = compute_text_sha256(framework_config_text)

    # Verify input SHAs (READ-ONLY).
    exp04_section = exp04_config.get("exp04", {})
    ds_cfg = exp04_section.get("dataset", {})
    candidates_rel = ds_cfg.get(
        "customer_candidates_path", "./data/processed/customer_candidates.parquet"
    )
    candidates_path = (_REPO_ROOT / candidates_rel).resolve()

    metadata_rel = ds_cfg.get(
        "customer_metadata_path", "./data/processed/customer_metadata.parquet"
    )
    metadata_path = (_REPO_ROOT / metadata_rel).resolve()

    if not candidates_path.exists():
        print(f"[EXP-04] ERROR: customer_candidates.parquet not found: {candidates_path}")
        return 1
    if not metadata_path.exists():
        print(f"[EXP-04] ERROR: customer_metadata.parquet not found: {metadata_path}")
        return 1

    print("[EXP-04] Computing input SHAs (READ-ONLY)...")
    candidates_sha = _compute_file_sha256(candidates_path)
    metadata_sha = _compute_file_sha256(metadata_path)
    expected_candidates_sha = ds_cfg.get("customer_candidates_sha256")
    expected_metadata_sha = ds_cfg.get("customer_metadata_sha256")
    if expected_candidates_sha and candidates_sha != expected_candidates_sha:
        print(
            f"[EXP-04] ERROR: customer_candidates.parquet SHA mismatch. "
            f"Expected {expected_candidates_sha}, got {candidates_sha}."
        )
        return 1
    if expected_metadata_sha and metadata_sha != expected_metadata_sha:
        print(
            f"[EXP-04] ERROR: customer_metadata.parquet SHA mismatch. "
            f"Expected {expected_metadata_sha}, got {metadata_sha}."
        )
        return 1
    print(f"[EXP-04] customer_candidates.parquet SHA-256: {candidates_sha}")
    print(f"[EXP-04] customer_metadata.parquet SHA-256: {metadata_sha}")
    print(f"[EXP-04] Framework config SHA-256: {config_sha}")

    # Snapshot input SHAs for post-run verification.
    pre_run_shas = {
        "customer_candidates.parquet": candidates_sha,
        "customer_metadata.parquet": metadata_sha,
    }

    # Load inputs.
    print("[EXP-04] Loading FE-05 candidates and FE-06 metadata (READ-ONLY)...")
    candidates_df = pd.read_parquet(candidates_path)
    metadata_df = pd.read_parquet(metadata_path)
    print(
        f"[EXP-04] candidates: {len(candidates_df)} rows x " f"{len(candidates_df.columns)} columns"
    )
    print(f"[EXP-04] customer_metadata: {len(metadata_df)} rows")

    # Initialize runner.
    runner = PreprocessingFeatureSensitivityRunner(
        framework_config,
        exp04_config,
        framework_config_text=framework_config_text,
        exp04_config_text=exp04_config_text,
    )

    # Run Family B sweep.
    print("[EXP-04] Running Family B preprocessing sensitivity sweep...")
    sweep = runner.run(
        candidates_df,
        metadata_df,
        candidates_sha256=candidates_sha,
        metadata_sha256=metadata_sha,
    )

    # Print summary.
    print("\n[EXP-04] Sweep summary:")
    print("-" * 70)
    print(f"  Total per-repeat records: {len(sweep.records)}")
    print(
        f"  Successful per-repeat records: {sum(1 for r in sweep.records if r.status == 'SUCCESS')}"
    )
    print(f"  Aggregates: {len(sweep.aggregates)}")
    for a in sweep.aggregates:
        sil = f"{a.silhouette:.4f}" if a.silhouette is not None else "N/A"
        det = "True" if a.determinism_verified else "False"
        print(
            f"  {a.scenario_id} ({a.config_id}): silhouette={sil} "
            f"determinism_verified={det} status={a.decision_status}"
        )
    print("-" * 70)

    # Verify post-run SHAs.
    post_run_shas = {
        "customer_candidates.parquet": _compute_file_sha256(candidates_path),
        "customer_metadata.parquet": _compute_file_sha256(metadata_path),
    }
    input_integrity_ok = pre_run_shas == post_run_shas
    if not input_integrity_ok:
        print("[EXP-04] ERROR: FE-05 / FE-06 outputs were mutated during run. Aborting.")
        return 1
    print("[EXP-04] Input integrity verified: NO mutation of FE-05 / FE-06 outputs.")

    # Write artifacts.
    print(f"\n[EXP-04] Writing artifacts to {args.reports_dir}...")
    args.reports_dir.mkdir(parents=True, exist_ok=True)

    manifest = _generate_manifest(
        sweep, exp04_config, config_sha, candidates_sha, metadata_sha, input_integrity_ok
    )
    _write_json(manifest, args.reports_dir / "exp04_manifest.json")
    print("  - Written: exp04_manifest.json")

    run_summary = _generate_run_summary(sweep, config_sha, candidates_sha, metadata_sha)
    _write_json(run_summary, args.reports_dir / "exp04_run_summary.json")
    print("  - Written: exp04_run_summary.json")

    scenario_results = _scenario_results_dataframe(sweep)
    _write_csv(scenario_results, args.reports_dir / "exp04_scenario_results.csv")
    print("  - Written: exp04_scenario_results.csv")

    aggregate_df = _aggregate_dataframe(sweep)
    _write_csv(aggregate_df, args.reports_dir / "exp04_preprocessing_sensitivity.csv")
    print("  - Written: exp04_preprocessing_sensitivity.csv")

    md_report = _generate_markdown_report(
        sweep, exp04_config, candidates_sha, metadata_sha, config_sha, input_integrity_ok
    )
    _write_markdown(md_report, args.reports_dir / "exp04_analysis.md")
    print("  - Written: exp04_analysis.md")

    deferred = _generate_deferred(exp04_config)
    _write_json(deferred, args.reports_dir / "exp04_deferred.json")
    print("  - Written: exp04_deferred.json")

    pending_review = _generate_pending_review(exp04_config)
    _write_json(pending_review, args.reports_dir / "exp04_pending_review.json")
    print("  - Written: exp04_pending_review.json")

    print("\n[EXP-04] Preprocessing & feature set sensitivity sweep completed!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
