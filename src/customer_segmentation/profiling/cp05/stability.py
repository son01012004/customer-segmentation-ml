"""CP-05 stability evaluation (per plan §9).

CHỈ sử dụng evidence hiện có từ EXP-05. KHÔNG compute ARI / AMI /
NMI / Hungarian. Phân biệt cứng: reproducibility ≠ stability.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from customer_segmentation.profiling.cp05.provenance import (
    Cp04EvidenceBundle,
    Cp05AnalysisUnit,
)

# Stability status taxonomy.
REPRO_VERIFIED_NO_METRIC = "REPRODUCIBILITY_VERIFIED_NO_STABILITY_METRIC"
REPRO_VERIFIED_PENDING = "REPRODUCIBILITY_VERIFIED_STABILITY_PENDING_EPIC08"
REPRO_NOT_VERIFIED = "REPRODUCIBILITY_NOT_VERIFIED"
STAB_PARTIAL = "STABILITY_RAW_EVIDENCE_PARTIAL"
STAB_NOT_ASSESSABLE = "STABILITY_NOT_ASSESSABLE"
NOT_APPLICABLE = "NOT_APPLICABLE"

# Algorithms with seed axis (Block S applicable).
SEEDED_ALGORITHMS = frozenset({"kmeans", "gmm", "fuzzy_cmeans"})


@dataclass(frozen=True)
class StabilityResult:
    """Per-segment stability evaluation result."""

    unit_id: str
    algorithm: str
    source_experiment: str
    cluster_id: int
    cluster_label: str
    reproducibility_status: str
    seed_stability_status: str
    perturbation_status: str
    n_seeds_observed: int
    n_sigmas_observed: int
    stability_status: str
    stability_evidence_note: str
    limitations: str
    is_noise: bool


def _load_reproducibility_results(exp05_dir: Path) -> pd.DataFrame | None:
    """Load EXP-05 reproducibility results (Block R)."""
    candidates = list(exp05_dir.glob("exp05_reproducibility*.csv"))
    if not candidates:
        return None
    return pd.read_csv(candidates[0])


def _load_seed_sweep(exp05_dir: Path) -> pd.DataFrame | None:
    candidates = list(exp05_dir.glob("exp05_seed_sweep*.csv"))
    if not candidates:
        return None
    return pd.read_csv(candidates[0])


def _load_noise_perturbation(exp05_dir: Path) -> pd.DataFrame | None:
    candidates = list(exp05_dir.glob("exp05_noise_perturbation*.csv"))
    if not candidates:
        return None
    return pd.read_csv(candidates[0])


def evaluate_stability(
    bundle: Cp04EvidenceBundle,
    *,
    exp05_dir: Path | None = None,
) -> list[StabilityResult]:
    """Evaluate stability cho một analysis unit.

    Parameters
    ----------
    bundle : Cp04EvidenceBundle
    exp05_dir : Path | None
        Thư mục EXP-05 (optional — nếu không có, status =
        ``STABILITY_NOT_ASSESSABLE``).

    Returns
    -------
    list[StabilityResult]
    """
    unit: Cp05AnalysisUnit = bundle.unit
    repro_status = STAB_NOT_ASSESSABLE
    seed_status = STAB_NOT_ASSESSABLE
    perturb_status = STAB_NOT_ASSESSABLE
    n_seeds = 0
    n_sigmas = 0

    if exp05_dir is not None and exp05_dir.exists():
        repro_df = _load_reproducibility_results(exp05_dir)
        if repro_df is not None and "algorithm" in repro_df.columns:
            algo_repro = repro_df[repro_df["algorithm"] == unit.algorithm]
            if not algo_repro.empty:
                # Default: REPRODUCIBILITY_VERIFIED if status field == VERIFIED.
                status_field = None
                for col in ("reproducibility_status", "status", "decision_status"):
                    if col in algo_repro.columns:
                        status_field = algo_repro.iloc[0][col]
                        break
                if status_field is not None and "VERIFIED" in str(status_field).upper():
                    repro_status = "VERIFIED"
                else:
                    repro_status = "NOT_VERIFIED"

        seed_df = _load_seed_sweep(exp05_dir)
        if seed_df is not None and "algorithm" in seed_df.columns:
            algo_seed = seed_df[seed_df["algorithm"] == unit.algorithm]
            if not algo_seed.empty:
                n_seeds = (
                    algo_seed["random_seed"].nunique()
                    if "random_seed" in algo_seed.columns
                    else len(algo_seed)
                )
                if n_seeds >= 5:
                    seed_status = "RAW_EVIDENCE_AVAILABLE_NO_METRIC"
                elif n_seeds > 0:
                    seed_status = "PARTIAL_RAW_EVIDENCE"
            elif unit.algorithm not in SEEDED_ALGORITHMS:
                seed_status = "DETERMINISTIC_NO_SEED_AXIS"

        perturb_df = _load_noise_perturbation(exp05_dir)
        if perturb_df is not None and "algorithm" in perturb_df.columns:
            algo_perturb = perturb_df[perturb_df["algorithm"] == unit.algorithm]
            if not algo_perturb.empty:
                n_sigmas = algo_perturb["sigma"].nunique() if "sigma" in algo_perturb.columns else 0
                if n_sigmas >= 3:
                    perturb_status = "RAW_EVIDENCE_AVAILABLE_NO_METRIC"
                elif n_sigmas > 0:
                    perturb_status = "PARTIAL_RAW_EVIDENCE"

    # Roll up.
    if repro_status == "VERIFIED":
        if (
            seed_status == "RAW_EVIDENCE_AVAILABLE_NO_METRIC"
            or perturb_status == "RAW_EVIDENCE_AVAILABLE_NO_METRIC"
        ):
            stability_status = REPRO_VERIFIED_PENDING
        else:
            stability_status = REPRO_VERIFIED_NO_METRIC
    elif repro_status == "NOT_VERIFIED":
        stability_status = REPRO_NOT_VERIFIED
    elif repro_status == STAB_NOT_ASSESSABLE and (
        seed_status != STAB_NOT_ASSESSABLE or perturb_status != STAB_NOT_ASSESSABLE
    ):
        stability_status = STAB_PARTIAL
    else:
        stability_status = STAB_NOT_ASSESSABLE

    note = (
        "Segment-level stability remains pending EPIC-08. "
        "CP-05 KHÔNG compute ARI/AMI/NMI/Hungarian."
    )

    out: list[StabilityResult] = []
    for _, row in bundle.size_df.iterrows():
        cid = int(row["cluster_id"])
        is_noise = cid == -1
        cluster_label = "noise (-1)" if is_noise else f"C{cid}"

        status = stability_status
        if is_noise:
            status = NOT_APPLICABLE

        out.append(
            StabilityResult(
                unit_id=unit.unit_id,
                algorithm=unit.algorithm,
                source_experiment=unit.source_experiment,
                cluster_id=cid,
                cluster_label=cluster_label,
                reproducibility_status=(repro_status if not is_noise else NOT_APPLICABLE),
                seed_stability_status=(seed_status if not is_noise else NOT_APPLICABLE),
                perturbation_status=(perturb_status if not is_noise else NOT_APPLICABLE),
                n_seeds_observed=n_seeds,
                n_sigmas_observed=n_sigmas,
                stability_status=status,
                stability_evidence_note=(
                    note if not is_noise else "DBSCAN noise KHÔNG phải Customer Segment."
                ),
                limitations=(
                    "Reproducibility ≠ stability. CP-05 chỉ báo cáo evidence "
                    "availability; ARI/AMI/NMI/Hungarian deferred to EPIC-08."
                    if not is_noise
                    else ""
                ),
                is_noise=is_noise,
            )
        )

    return out


def stability_results_to_rows(
    results: Iterable[StabilityResult],
) -> list[dict]:
    rows: list[dict] = []
    for r in results:
        rows.append(
            {
                "unit_id": r.unit_id,
                "algorithm": r.algorithm,
                "source_experiment": r.source_experiment,
                "cluster_id": r.cluster_id,
                "cluster_label": r.cluster_label,
                "reproducibility_status": r.reproducibility_status,
                "seed_stability_status": r.seed_stability_status,
                "perturbation_status": r.perturbation_status,
                "n_seeds_observed": r.n_seeds_observed,
                "n_sigmas_observed": r.n_sigmas_observed,
                "stability_status": r.stability_status,
                "stability_evidence_note": r.stability_evidence_note,
                "limitations": r.limitations,
            }
        )
    return rows
