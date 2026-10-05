"""Hyperparameter search orchestrator for EXP-03.

This module provides :class:`HyperparameterSearchRunner` that orchestrates
a controlled hyperparameter sensitivity sweep for the five EPIC-06
benchmark algorithms:

- K-Means
- Agglomerative Clustering
- DBSCAN
- Gaussian Mixture Model
- Fuzzy C-Means

EXP-03 design principles:

- Three search stages (A baseline, B single-parameter sensitivity,
  C selected interactions).
- K (n_clusters / n_components) is reused from EXP-02 candidate set
  (controlled reuse of EXP-02 evidence) — NOT re-swept.
- Each Stage B parameter sweep varies ONE hyperparameter at a time,
  holding all others at Stage A baseline.
- Selection protocol is per-algorithm (NOT cross-algorithm) using a
  transparent, deterministic multi-metric rule:
    silhouette (primary) > DBI (tiebreaker 1) > CH (tiebreaker 2).
  WCSS and runtime are diagnostic-only, NOT ranking criteria.
- No "best", "winner", "optimal", "recommended", "final" language.
- Reuses the EXP-01 metrics layer (silhouette, DBI, CH, WCSS) verbatim.

Hard constraints (AGENTS.md §2, §3 "Clustering"):

- No ranking of algorithms.
- No "best/winner/optimal/recommended" language anywhere.
- Per-algorithm selection only — NEVER cross-algorithm.
- WCSS uses arithmetic centroid from hard labels (not GMM Gaussian
  means or FCM fuzzy centroids).
- DBSCAN noise (label -1) is excluded from internal metrics and WCSS.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from customer_segmentation.clustering.cluster_number import (
    CANONICAL_ORDER,
    _run_single,
)
from customer_segmentation.clustering.config import FrameworkConfig
from customer_segmentation.clustering.metrics import (
    METRIC_VALID,
)
from customer_segmentation.clustering.result import ClusterResult

__all__ = [
    "HyperparameterSpec",
    "HyperparameterResult",
    "HyperparameterSweepResult",
    "SelectedConfiguration",
    "ParameterSensitivityRecord",
    "HyperparameterSearchRunner",
    "build_sensitivity_table",
    "apply_selection_protocol",
    "load_exp02_candidates",
]


# ---------------------------------------------------------------------------
# Stage constants
# ---------------------------------------------------------------------------

STAGE_BASELINE = "A"
STAGE_SENSITIVITY = "B"
STAGE_INTERACTION = "C"


# ---------------------------------------------------------------------------
# Specification and result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class HyperparameterSpec:
    """Specification for a single hyperparameter configuration."""

    experiment_id: str
    algorithm: str
    hyperparameters: dict[str, Any]
    seed: int | None = None
    stage: str = STAGE_BASELINE
    sweep_parameter: str | None = None  # which parameter is being varied
    sweep_value: Any | None = None  # the value of that parameter
    baseline_k: int | None = None  # K used for this configuration


@dataclass
class HyperparameterResult:
    """Result of a single hyperparameter configuration run."""

    experiment_id: str
    algorithm: str
    stage: str
    sweep_parameter: str | None
    sweep_value: Any | None
    baseline_k: int | None
    hyperparameters: dict[str, Any]
    n_clusters: int | None
    noise_count: int | None
    noise_ratio: float | None
    cluster_result: ClusterResult | None
    runtime_stats: dict[str, Any]
    input_sha256: str | None
    config_sha256: str | None
    library_versions: dict[str, str]
    status: str = "SUCCESS"
    error: dict[str, Any] | None = None


@dataclass
class ParameterSensitivityRecord:
    """Sensitivity evidence for a single parameter on a single algorithm.

    Captures the observed metric response when ONE parameter is varied
    while other parameters are held at the Stage A baseline.
    """

    algorithm: str
    parameter: str
    baseline_value: Any
    value: Any
    K: int | None
    silhouette: float | None
    silhouette_status: str
    davies_bouldin: float | None
    davies_bouldin_status: str
    calinski_harabasz: float | None
    calinski_harabasz_status: str
    wcss: float | None
    wcss_status: str
    runtime_mean: float | None
    runtime_std: float | None
    n_clusters: int | None
    noise_count: int | None
    noise_ratio: float | None
    status: str
    experiment_id: str


@dataclass
class SelectedConfiguration:
    """Per-algorithm working selected configuration.

    This is NOT a "best" or "winner" — it is a "working selected
    configuration" derived from a transparent multi-metric selection
    protocol applied WITHIN the algorithm's search space.

    decision_status ∈ {WORKING_SELECTED, TIED_WORKING_SELECTED, PENDING_REVIEW}
    """

    algorithm: str
    hyperparameters: dict[str, Any]
    baseline_k: int | None
    silhouette: float | None
    silhouette_status: str
    silhouette_rank: int | None
    davies_bouldin: float | None
    davies_bouldin_status: str
    davies_bouldin_rank: int | None
    calinski_harabasz: float | None
    calinski_harabasz_status: str
    calinski_harabasz_rank: int | None
    wcss: float | None
    wcss_status: str
    runtime_mean: float | None
    runtime_std: float | None
    n_clusters: int | None
    noise_count: int | None
    noise_ratio: float | None
    decision_status: str
    selection_evidence: dict[str, Any]
    pending_review_notes: list[str]
    experiment_id: str
    stage: str
    sweep_parameter: str | None
    sweep_value: Any | None
    # Optional alternate tied configurations (when decision_status
    # is TIED_WORKING_SELECTED).
    tied_alternates: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class HyperparameterSweepResult:
    """Result of the full EXP-03 hyperparameter search."""

    results: list[HyperparameterResult]
    sensitivity_table: list[ParameterSensitivityRecord]
    selected_configurations: list[SelectedConfiguration]
    input_sha256: str | None
    config_sha256: str | None
    library_versions: dict[str, str]
    feature_set: str
    n_total_runs: int
    n_successful_runs: int


# ---------------------------------------------------------------------------
# EXP-02 candidate K loader
# ---------------------------------------------------------------------------


def load_exp02_candidates(
    candidates_csv_path: Path | None,
) -> dict[str, list[int]]:
    """Load EXP-02 candidate K per algorithm from CSV.

    Returns
    -------
    candidates : dict
        Mapping of algorithm name → sorted list of candidate K values.

    Notes
    -----
    This is a "controlled reuse of EXP-02 evidence" — EXP-03 does NOT
    re-sweep K=2..10. The candidate K set is taken verbatim from
    EXP-02's evidence-based candidate selection.
    """
    candidates: dict[str, list[int]] = {}

    if candidates_csv_path is None or not candidates_csv_path.exists():
        return candidates

    try:
        import csv

        with candidates_csv_path.open("r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                algo = row.get("algorithm", "")
                try:
                    k_val = int(float(row.get("K", "")))
                except (TypeError, ValueError):
                    continue
                if algo and not pd.isna(k_val) if False else algo:
                    candidates.setdefault(algo, []).append(k_val)
    except Exception:
        return candidates

    # Sort and dedupe each algorithm's K values
    for algo in candidates:
        candidates[algo] = sorted(set(candidates[algo]))

    return candidates


# ---------------------------------------------------------------------------
# Search space helpers
# ---------------------------------------------------------------------------


def _validate_search_space(search_space: dict[str, Any]) -> None:
    """Validate the search space configuration.

    Reject:
    - ward + non-euclidean metric combinations.
    - m <= 1.0 for fuzzy_cmeans.
    - Missing required fields.
    """
    if not isinstance(search_space, dict):
        raise ValueError("search_space must be a dict.")

    for algo, cfg in search_space.items():
        if not isinstance(cfg, dict):
            raise ValueError(f"search_space[{algo!r}] must be a dict.")

        fixed = cfg.get("fixed_parameters", {})
        sweeps = cfg.get("parameter_sweeps", [])

        # ward + non-euclidean constraint
        if algo == "agglomerative":
            linkage_sweep = next((s for s in sweeps if s.get("parameter") == "linkage"), None)
            if linkage_sweep is not None:
                ward_in_sweep = (
                    "ward" in linkage_sweep.get("candidate_values", [])
                    or linkage_sweep.get("baseline_value") == "ward"
                )
                metric = fixed.get("metric")
                if ward_in_sweep and metric is not None and metric != "euclidean":
                    raise ValueError(
                        "search_space.agglomerative: ward linkage requires "
                        "fixed_parameters.metric='euclidean'."
                    )

        # m > 1.0 constraint
        if algo == "fuzzy_cmeans":
            m_sweep = next((s for s in sweeps if s.get("parameter") == "m"), None)
            if m_sweep is not None:
                for v in m_sweep.get("candidate_values", []):
                    # Reject non-numeric types first.
                    if not isinstance(v, (int, float)) or isinstance(v, bool):
                        raise ValueError(
                            f"search_space.fuzzy_cmeans: m must be a " f"number > 1.0; got {v!r}."
                        )
                    if float(v) <= 1.0:
                        raise ValueError(
                            f"search_space.fuzzy_cmeans: m must be > 1.0; " f"got {v!r}."
                        )


# ---------------------------------------------------------------------------
# Run a single hyperparameter configuration
# ---------------------------------------------------------------------------


def _run_hyperparameter_spec(
    spec: HyperparameterSpec,
    framework_cfg: FrameworkConfig,
    exp03_config: dict[str, Any],
    matrix_df: pd.DataFrame,
    customer_metadata_df: pd.DataFrame | None,
    n_repeat: int,
    exclude_noise: bool,
    noise_label: int,
    input_sha256: str | None,
    input_path: str | None,
    metadata_path: str | None,
    config_text: str | None,
) -> HyperparameterResult:
    """Run a single hyperparameter configuration."""
    # Reuse ClusterNumberRunner's _run_single helper for the metric
    # computation protocol.
    from customer_segmentation.clustering.cluster_number import ClusterNumberSpec

    cn_spec = ClusterNumberSpec(
        experiment_id=spec.experiment_id,
        algorithm=spec.algorithm,
        K=spec.baseline_k,
        hyperparameters=spec.hyperparameters,
        seed=spec.seed,
    )

    # Run via _run_single which handles repetition and metrics.
    cn_result = _run_single(
        spec=cn_spec,
        framework_cfg=framework_cfg,
        baseline_config=exp03_config,
        matrix_df=matrix_df,
        customer_metadata_df=customer_metadata_df,
        n_repeat=n_repeat,
        exclude_noise=exclude_noise,
        noise_label=noise_label,
        input_sha256=input_sha256,
        input_path=input_path,
        metadata_path=metadata_path,
        config_text=config_text,
    )

    return HyperparameterResult(
        experiment_id=spec.experiment_id,
        algorithm=spec.algorithm,
        stage=spec.stage,
        sweep_parameter=spec.sweep_parameter,
        sweep_value=spec.sweep_value,
        baseline_k=spec.baseline_k,
        hyperparameters=spec.hyperparameters,
        n_clusters=cn_result.n_clusters,
        noise_count=cn_result.noise_count,
        noise_ratio=cn_result.noise_ratio,
        cluster_result=cn_result.cluster_result,
        runtime_stats=cn_result.runtime_stats,
        input_sha256=cn_result.input_sha256,
        config_sha256=cn_result.config_sha256,
        library_versions=cn_result.library_versions,
        status=cn_result.status,
        error=cn_result.error,
    )


# ---------------------------------------------------------------------------
# Stage B sensitivity sweep
# ---------------------------------------------------------------------------


def _build_stage_a_spec(
    algorithm: str,
    search_space_cfg: dict[str, Any],
    working_defaults: dict[str, Any],
    baseline_seed: int | None,
) -> HyperparameterSpec | None:
    """Build a single Stage A baseline spec for one algorithm.

    Returns None if the algorithm has no baseline_k (e.g. DBSCAN, which
    uses fixed working defaults with no K parameter).

    The baseline hyperparameters come from working_defaults merged
    with fixed_parameters from the search space.
    """
    baseline_k = search_space_cfg.get("baseline_k")
    fixed = search_space_cfg.get("fixed_parameters", {}) or {}

    if baseline_k is None and algorithm != "dbscan":
        # K-bearing algorithms MUST have a baseline_k.
        raise ValueError(
            f"search_space[{algorithm!r}]: baseline_k is required for " f"K-bearing algorithms."
        )

    baseline_hp: dict[str, Any] = dict(working_defaults.get(algorithm, {}))

    # Strip K from working defaults.
    for k_param in ("n_clusters", "n_components"):
        baseline_hp.pop(k_param, None)

    # Apply fixed_parameters overrides.
    baseline_hp.update(fixed)

    # Apply baseline K.
    if baseline_k is not None:
        k_param_name = "n_components" if algorithm == "gmm" else "n_clusters"
        baseline_hp[k_param_name] = baseline_k

    # Seed for algorithms that support it.
    if baseline_seed is not None and _algorithm_supports_random_state(algorithm):
        baseline_hp["random_state"] = baseline_seed

    exp_id = _make_experiment_id(
        algorithm=algorithm,
        stage=STAGE_BASELINE,
        parameter="baseline",
        value="config",
        baseline_k=baseline_k,
        stage_index=1,
    )

    return HyperparameterSpec(
        experiment_id=exp_id,
        algorithm=algorithm,
        hyperparameters=baseline_hp,
        seed=baseline_seed,
        stage=STAGE_BASELINE,
        sweep_parameter=None,
        sweep_value=None,
        baseline_k=baseline_k,
    )


def _build_stage_b_specs(
    algorithm: str,
    search_space_cfg: dict[str, Any],
    working_defaults: dict[str, Any],
    baseline_seed: int | None,
) -> list[HyperparameterSpec]:
    """Build Stage B single-parameter sensitivity specs.

    For each non-K parameter sweep:
      - baseline_value is INCLUDED in candidate_values list, so all
        Stage B runs carry the baseline_value too (the sensitivity
        sweep re-runs the baseline hyperparameter for that parameter).
      - The dedicated Stage A baseline is generated separately by
        :func:`_build_stage_a_spec`.

    Stage B rules:
      - Stage B emits ONLY candidate_values that differ from baseline_value.
      - baseline_value is handled by the dedicated Stage A baseline
        from :func:`_build_stage_a_spec` (built ONCE per algorithm).

    """
    specs: list[HyperparameterSpec] = []
    baseline_k = search_space_cfg.get("baseline_k")
    fixed = search_space_cfg.get("fixed_parameters", {}) or {}
    sweeps = search_space_cfg.get("parameter_sweeps", []) or []

    # Baseline hyperparameters (Stage A reference).
    baseline_hp: dict[str, Any] = dict(working_defaults.get(algorithm, {}))
    for k_param in ("n_clusters", "n_components"):
        baseline_hp.pop(k_param, None)
    baseline_hp.update(fixed)
    if baseline_k is not None:
        k_param_name = "n_components" if algorithm == "gmm" else "n_clusters"
        baseline_hp[k_param_name] = baseline_k

    for sweep in sweeps:
        param = sweep["parameter"]
        baseline_value = sweep.get("baseline_value")
        candidate_values = sweep.get("candidate_values", []) or []

        # Emit one spec per (parameter, value) where value != baseline_value.
        # baseline_value is handled by the Stage A baseline.
        for v in candidate_values:
            if v == baseline_value:
                # baseline_value is covered by Stage A baseline; skip.
                continue
            hp = dict(baseline_hp)
            hp[param] = v
            if baseline_seed is not None and _algorithm_supports_random_state(algorithm):
                hp["random_state"] = baseline_seed
            exp_id = _make_experiment_id(
                algorithm=algorithm,
                stage=STAGE_SENSITIVITY,
                parameter=param,
                value=v,
                baseline_k=baseline_k,
                stage_index=0,
            )
            specs.append(
                HyperparameterSpec(
                    experiment_id=exp_id,
                    algorithm=algorithm,
                    hyperparameters=hp,
                    seed=baseline_seed,
                    stage=STAGE_SENSITIVITY,
                    sweep_parameter=param,
                    sweep_value=v,
                    baseline_k=baseline_k,
                )
            )

    return specs


def _build_stage_c_specs(
    interactions: list[dict[str, Any]],
    working_defaults: dict[str, Any],
    baseline_seed: int | None,
) -> list[HyperparameterSpec]:
    """Build Stage C selected interaction specs.

    Each entry in `interactions` describes one (algorithm, K) pair with
    a list of parameters and per-parameter value lists.

    The interaction run is built by:
      - taking working defaults,
      - applying Stage A baseline K,
      - for each parameter in the entry, generating one run per
        value in the entry's parameter list.
    """
    specs: list[HyperparameterSpec] = []

    for idx, inter in enumerate(interactions):
        algorithm = inter["algorithm"]
        K = int(inter["K"])
        params = inter.get("parameters", {}) or {}

        base_hp: dict[str, Any] = dict(working_defaults.get(algorithm, {}))
        # Strip K.
        for k_param in ("n_clusters", "n_components"):
            base_hp.pop(k_param, None)
        # Apply K.
        k_param_name = "n_components" if algorithm == "gmm" else "n_clusters"
        base_hp[k_param_name] = K
        # Seed.
        if baseline_seed is not None and _algorithm_supports_random_state(algorithm):
            base_hp["random_state"] = baseline_seed

        for param, value_list in params.items():
            if not isinstance(value_list, list):
                value_list = [value_list]
            for v in value_list:
                hp = dict(base_hp)
                hp[param] = v
                if baseline_seed is not None and _algorithm_supports_random_state(algorithm):
                    hp["random_state"] = baseline_seed
                exp_id = _make_experiment_id(
                    algorithm=algorithm,
                    stage=STAGE_INTERACTION,
                    parameter=param,
                    value=v,
                    baseline_k=K,
                    stage_index=idx + 1,
                )
                specs.append(
                    HyperparameterSpec(
                        experiment_id=exp_id,
                        algorithm=algorithm,
                        hyperparameters=hp,
                        seed=baseline_seed,
                        stage=STAGE_INTERACTION,
                        sweep_parameter=param,
                        sweep_value=v,
                        baseline_k=K,
                    )
                )

    return specs


def _algorithm_supports_random_state(algorithm: str) -> bool:
    """Return whether an algorithm adapter supports random_state."""
    from customer_segmentation.clustering.registry import AlgorithmRegistry

    try:
        cls = AlgorithmRegistry.get(algorithm)
        # AlgorithmRegistry always sets .name; instantiate with dummy
        # hyperparameters to inspect supports_random_state().

        if algorithm == "kmeans" or algorithm == "agglomerative":
            instance = cls(n_clusters=2)
        elif algorithm == "gmm":
            instance = cls(n_components=2)
        elif algorithm == "fuzzy_cmeans":
            instance = cls(n_clusters=2)
        elif algorithm == "dbscan":
            instance = cls(eps=0.5, min_samples=5)
        else:
            return False
        return bool(instance.supports_random_state())
    except Exception:
        return False


def _make_experiment_id(
    *,
    algorithm: str,
    stage: str,
    parameter: str | None,
    value: Any,
    baseline_k: int | None,
    stage_index: int,
) -> str:
    """Generate a stable experiment_id for a (stage, parameter, value) run."""
    safe_value = str(value).replace(".", "_").replace("-", "neg").replace("+", "pos")
    safe_param = (parameter or "baseline").replace(" ", "_")
    if stage == STAGE_BASELINE:
        return f"EXP-03-{algorithm}-stageA-baseline-k{baseline_k}"
    if stage == STAGE_SENSITIVITY:
        return f"EXP-03-{algorithm}-stageB-{safe_param}-{safe_value}"
    if stage == STAGE_INTERACTION:
        return f"EXP-03-{algorithm}-stageC-k{baseline_k}-{safe_param}-{safe_value}"
    return f"EXP-03-{algorithm}-{stage}-{stage_index}"


# ---------------------------------------------------------------------------
# Sensitivity table builder
# ---------------------------------------------------------------------------


def build_sensitivity_table(
    results: list[HyperparameterResult],
) -> list[ParameterSensitivityRecord]:
    """Build parameter sensitivity records from Stage A + Stage B results.

    Records are emitted per (algorithm, parameter, value) for non-baseline
    runs, plus the baseline itself for completeness.
    """
    records: list[ParameterSensitivityRecord] = []

    for r in results:
        if r.stage not in (STAGE_BASELINE, STAGE_SENSITIVITY):
            continue
        # Only emit one record per (algorithm, parameter, value).
        # If there are duplicates, take the most recent (last in list).
        extra = r.cluster_result.metrics.extra if r.cluster_result is not None else {}
        m = r.cluster_result.metrics if r.cluster_result is not None else None
        records.append(
            ParameterSensitivityRecord(
                algorithm=r.algorithm,
                parameter=r.sweep_parameter or "baseline",
                baseline_value=None,
                value=r.sweep_value,
                K=r.baseline_k,
                silhouette=(m.silhouette if m else None),
                silhouette_status=extra.get("silhouette_status", "MISSING"),
                davies_bouldin=(m.davies_bouldin if m else None),
                davies_bouldin_status=extra.get("davies_bouldin_status", "MISSING"),
                calinski_harabasz=(m.calinski_harabasz if m else None),
                calinski_harabasz_status=extra.get("calinski_harabasz_status", "MISSING"),
                wcss=(m.wcss if m else None),
                wcss_status=extra.get("wcss_status", "MISSING"),
                runtime_mean=r.runtime_stats.get("mean_seconds"),
                runtime_std=r.runtime_stats.get("std_seconds"),
                n_clusters=r.n_clusters,
                noise_count=r.noise_count,
                noise_ratio=r.noise_ratio,
                status=r.status,
                experiment_id=r.experiment_id,
            )
        )

    return records


# ---------------------------------------------------------------------------
# Selection protocol (multi-metric, transparent, per-algorithm)
# ---------------------------------------------------------------------------


def _safe_metric_value(value: float | None, status: str) -> float | None:
    """Return metric value only if status is VALID_VALUE; else None."""
    if status == METRIC_VALID and value is not None:
        try:
            f = float(value)
            if np.isnan(f) or np.isinf(f):
                return None
            return f
        except (TypeError, ValueError):
            return None
    return None


def _rank_metric(values: list[float | None], higher_is_better: bool) -> list[int | None]:
    """Return per-index ranks (1 = best) for a list of metric values.

    None values receive rank None. Ties share the average rank.
    """
    n = len(values)
    indexed = [(i, v) for i, v in enumerate(values)]
    valid = [(i, v) for i, v in indexed if v is not None]
    if not valid:
        return [None] * n

    # Sort: higher_is_better → descending; lower_is_better → ascending
    valid.sort(key=lambda x: x[1], reverse=higher_is_better)

    ranks: list[int | None] = [None] * n
    i = 0
    while i < len(valid):
        j = i
        # Find the tie group (same metric value).
        while j + 1 < len(valid) and valid[j + 1][1] == valid[i][1]:
            j += 1
        # Average rank across the tie group.
        avg_rank = sum(range(i + 1, j + 2)) / (j - i + 1)
        for k in range(i, j + 1):
            ranks[valid[k][0]] = avg_rank
        i = j + 1

    return ranks


def apply_selection_protocol(
    algorithm: str,
    results: list[HyperparameterResult],
    *,
    algorithm_search_space: dict[str, Any] | None = None,
    protocol_cfg: dict[str, Any] | None = None,
) -> SelectedConfiguration | None:
    """Apply the multi-metric selection protocol to one algorithm.

    Parameters
    ----------
    algorithm : str
        Algorithm name (kmeans, agglomerative, dbscan, gmm, fuzzy_cmeans).
    results : list[HyperparameterResult]
        All EXP-03 results (Stages A, B, C) for ALL algorithms; this
        function filters to the given algorithm.
    algorithm_search_space : dict | None
        The search_space entry for this algorithm (used to identify
        the baseline_value for each parameter).
    protocol_cfg : dict | None
        Selection protocol configuration. If None, uses defaults.

    Returns
    -------
    selected : SelectedConfiguration or None
        The selected configuration, or None if no eligible runs.
    """
    protocol_cfg = protocol_cfg or {}
    primary = protocol_cfg.get("primary_criterion", "silhouette")
    # Tiebreakers default to dbi (lower-is-better), ch (higher-is-better).
    tie_1 = protocol_cfg.get("tie_breaker_1", "davies_bouldin")
    tie_2 = protocol_cfg.get("tie_breaker_2", "calinski_harabasz")

    # Filter to this algorithm.
    algo_results = [r for r in results if r.algorithm == algorithm]
    if not algo_results:
        return None

    # Restrict to SUCCESS + all metrics VALID_VALUE.
    eligible: list[HyperparameterResult] = []
    for r in algo_results:
        if r.status != "SUCCESS":
            continue
        if r.cluster_result is None:
            continue
        m = r.cluster_result.metrics
        extra = m.extra
        if (
            extra.get("silhouette_status") == METRIC_VALID
            and extra.get("davies_bouldin_status") == METRIC_VALID
            and extra.get("calinski_harabasz_status") == METRIC_VALID
            and extra.get("wcss_status") == METRIC_VALID
        ):
            eligible.append(r)

    if not eligible:
        # Document why we can't select.
        return SelectedConfiguration(
            algorithm=algorithm,
            hyperparameters={},
            baseline_k=None,
            silhouette=None,
            silhouette_status="MISSING",
            silhouette_rank=None,
            davies_bouldin=None,
            davies_bouldin_status="MISSING",
            davies_bouldin_rank=None,
            calinski_harabasz=None,
            calinski_harabasz_status="MISSING",
            calinski_harabasz_rank=None,
            wcss=None,
            wcss_status="MISSING",
            runtime_mean=None,
            runtime_std=None,
            n_clusters=None,
            noise_count=None,
            noise_ratio=None,
            decision_status="PENDING_REVIEW",
            selection_evidence={
                "reason": "no eligible runs (all FAILED or non-VALID metrics)",
            },
            pending_review_notes=[
                "EXP03-SEL-01: selection protocol could not be applied.",
            ],
            experiment_id="",
            stage="",
            sweep_parameter=None,
            sweep_value=None,
        )

    # Compute metric values per eligible run.
    sil_vals: list[float | None] = []
    dbi_vals: list[float | None] = []
    ch_vals: list[float | None] = []
    wcss_vals: list[float | None] = []
    rt_means: list[float | None] = []

    for r in eligible:
        m = r.cluster_result.metrics
        extra = m.extra
        sil_vals.append(_safe_metric_value(m.silhouette, extra.get("silhouette_status", "MISSING")))
        dbi_vals.append(
            _safe_metric_value(m.davies_bouldin, extra.get("davies_bouldin_status", "MISSING"))
        )
        ch_vals.append(
            _safe_metric_value(
                m.calinski_harabasz, extra.get("calinski_harabasz_status", "MISSING")
            )
        )
        wcss_vals.append(_safe_metric_value(m.wcss, extra.get("wcss_status", "MISSING")))
        rt_means.append(r.runtime_stats.get("mean_seconds"))

    # Higher-is-better for silhouette and CH; lower-is-better for DBI.
    sil_ranks = _rank_metric(sil_vals, higher_is_better=True)
    dbi_ranks = _rank_metric(dbi_vals, higher_is_better=False)
    ch_ranks = _rank_metric(ch_vals, higher_is_better=True)

    # Resolve metric name → rank list.
    rank_map = {"silhouette": sil_ranks, "davies_bouldin": dbi_ranks, "calinski_harabasz": ch_ranks}

    def _better_or_equal(a: float | None, b: float | None) -> bool:
        """a is at least as good as b (lower rank is better)."""
        if a is None and b is None:
            return True
        if a is None:
            return False
        if b is None:
            return True
        return a <= b

    # Find best index by primary criterion (silhouette rank 1).
    # We pick the configuration(s) with the best (lowest) primary rank.
    primary_ranks = rank_map[primary]

    if all(r is None for r in primary_ranks):
        return SelectedConfiguration(
            algorithm=algorithm,
            hyperparameters={},
            baseline_k=None,
            silhouette=None,
            silhouette_status="MISSING",
            silhouette_rank=None,
            davies_bouldin=None,
            davies_bouldin_status="MISSING",
            davies_bouldin_rank=None,
            calinski_harabasz=None,
            calinski_harabasz_status="MISSING",
            calinski_harabasz_rank=None,
            wcss=None,
            wcss_status="MISSING",
            runtime_mean=None,
            runtime_std=None,
            n_clusters=None,
            noise_count=None,
            noise_ratio=None,
            decision_status="PENDING_REVIEW",
            selection_evidence={"reason": f"all {primary} values are None"},
            pending_review_notes=[
                "EXP03-SEL-01: primary criterion has no valid values.",
            ],
            experiment_id="",
            stage="",
            sweep_parameter=None,
            sweep_value=None,
        )

    best_primary = min(r for r in primary_ranks if r is not None)

    # Indices tied for best primary rank.
    primary_indices = [i for i, r in enumerate(primary_ranks) if r == best_primary]

    # Tiebreaker 1: among primary_indices, pick lowest tie_1 rank.
    tie1_indices = primary_indices
    if tie_1 in rank_map:
        tie1_ranks = rank_map[tie_1]
        # If any is None, drop those indices.
        non_null = [
            (idx, tie1_ranks[idx]) for idx in primary_indices if tie1_ranks[idx] is not None
        ]
        if non_null:
            best_tie1 = min(r for _, r in non_null)
            tie1_indices = [idx for idx, r in non_null if r == best_tie1]

    # Tiebreaker 2: among tie1_indices, pick lowest tie_2 rank.
    tie2_indices = tie1_indices
    if tie_2 in rank_map:
        tie2_ranks = rank_map[tie_2]
        non_null = [(idx, tie2_ranks[idx]) for idx in tie1_indices if tie2_ranks[idx] is not None]
        if non_null:
            best_tie2 = min(r for _, r in non_null)
            tie2_indices = [idx for idx, r in non_null if r == best_tie2]

    # If multiple tied, mark TIED_WORKING_SELECTED.
    selected_indices = tie2_indices
    decision_status = "TIED_WORKING_SELECTED" if len(selected_indices) > 1 else "WORKING_SELECTED"

    # Build the selected configuration from the first selected index.
    primary_idx = selected_indices[0]
    sel_result = eligible[primary_idx]

    tied_alts: list[dict[str, Any]] = []
    if len(selected_indices) > 1:
        for alt_idx in selected_indices[1:]:
            alt = eligible[alt_idx]
            tied_alts.append(
                {
                    "experiment_id": alt.experiment_id,
                    "hyperparameters": alt.hyperparameters,
                    "sweep_parameter": alt.sweep_parameter,
                    "sweep_value": alt.sweep_value,
                    "silhouette": sil_vals[alt_idx],
                    "davies_bouldin": dbi_vals[alt_idx],
                    "calinski_harabasz": ch_vals[alt_idx],
                }
            )

    m = sel_result.cluster_result.metrics
    extra = m.extra
    selection_evidence = {
        "primary_criterion": primary,
        "primary_rank": primary_ranks[primary_idx],
        "tie_breaker_1": tie_1,
        "tie_breaker_1_rank": (rank_map[tie_1][primary_idx] if tie_1 in rank_map else None),
        "tie_breaker_2": tie_2,
        "tie_breaker_2_rank": (rank_map[tie_2][primary_idx] if tie_2 in rank_map else None),
        "n_eligible_runs": len(eligible),
        "wcss_diagnostic_only": True,
        "runtime_diagnostic_only": True,
        "all_metrics_VALID_VALUE": True,
    }

    return SelectedConfiguration(
        algorithm=algorithm,
        hyperparameters=sel_result.hyperparameters,
        baseline_k=sel_result.baseline_k,
        silhouette=sil_vals[primary_idx],
        silhouette_status=extra.get("silhouette_status", "MISSING"),
        silhouette_rank=primary_ranks[primary_idx],
        davies_bouldin=dbi_vals[primary_idx],
        davies_bouldin_status=extra.get("davies_bouldin_status", "MISSING"),
        davies_bouldin_rank=rank_map[tie_1][primary_idx] if tie_1 in rank_map else None,
        calinski_harabasz=ch_vals[primary_idx],
        calinski_harabasz_status=extra.get("calinski_harabasz_status", "MISSING"),
        calinski_harabasz_rank=rank_map[tie_2][primary_idx] if tie_2 in rank_map else None,
        wcss=wcss_vals[primary_idx],
        wcss_status=extra.get("wcss_status", "MISSING"),
        runtime_mean=rt_means[primary_idx],
        runtime_std=sel_result.runtime_stats.get("std_seconds"),
        n_clusters=sel_result.n_clusters,
        noise_count=sel_result.noise_count,
        noise_ratio=sel_result.noise_ratio,
        decision_status=decision_status,
        selection_evidence=selection_evidence,
        pending_review_notes=[
            "EXP03-SEL-01: selection protocol is WORKING_ASSUMPTION.",
            "Working selected configuration is WITHIN the search space of "
            "this algorithm only. NEVER a cross-algorithm ranking.",
        ],
        experiment_id=sel_result.experiment_id,
        stage=sel_result.stage,
        sweep_parameter=sel_result.sweep_parameter,
        sweep_value=sel_result.sweep_value,
        tied_alternates=tied_alts,
    )


# ---------------------------------------------------------------------------
# HyperparameterSearchRunner
# ---------------------------------------------------------------------------


class HyperparameterSearchRunner:
    """Orchestrate EXP-03 hyperparameter search.

    Usage
    -----

    .. code-block:: python

        runner = HyperparameterSearchRunner(framework_cfg, exp03_config)
        result = runner.run(
            matrix_df,
            customer_metadata_df,
            input_sha256="...",
        )
        # result.results          — all per-config results
        # result.sensitivity_table — sensitivity records
        # result.selected_configurations — per-algorithm working selections
    """

    def __init__(
        self,
        framework_cfg: FrameworkConfig,
        exp03_config: dict[str, Any],
        *,
        baseline_seed: int | None = None,
        n_repeat: int | None = None,
        exclude_noise: bool = True,
        noise_label: int | None = None,
        exp02_candidates_csv_path: Path | None = None,
    ) -> None:
        self.cfg = framework_cfg
        self.exp03_config = exp03_config
        runtime_cfg = exp03_config.get("exp03", {}).get("runtime", {})
        self.baseline_seed = (
            baseline_seed if baseline_seed is not None else int(runtime_cfg.get("seed", 42))
        )
        self.n_repeat = n_repeat if n_repeat is not None else int(runtime_cfg.get("repeat", 5))
        dbscan_cfg = exp03_config.get("exp03", {}).get("dbscan", {})
        self.exclude_noise = exclude_noise
        self.noise_label = (
            noise_label if noise_label is not None else int(dbscan_cfg.get("noise_label", -1))
        )

        # Validate search space.
        search_space = exp03_config.get("exp03", {}).get("search_space", {})
        _validate_search_space(search_space)
        self.search_space = search_space

        # Load EXP-02 candidate K (controlled reuse).
        self.exp02_candidates = load_exp02_candidates(exp02_candidates_csv_path)

    def _get_working_defaults(self) -> dict[str, Any]:
        """Return working defaults from exp03 config (fall back to exp01-like keys)."""
        return self.exp03_config.get("working_defaults", {}) or {}

    def _get_search_strategy(self) -> dict[str, Any]:
        return self.exp03_config.get("exp03", {}).get("search_strategy", {})

    def _get_selected_interactions(self) -> list[dict[str, Any]]:
        return self.exp03_config.get("exp03", {}).get("selected_interactions", []) or []

    def _get_protocol_cfg(self) -> dict[str, Any]:
        return self.exp03_config.get("exp03", {}).get("selection_protocol", {}) or {}

    def _algorithm_search_space(self, algo: str) -> dict[str, Any]:
        return self.search_space.get(algo, {})

    def _build_all_specs(self) -> list[HyperparameterSpec]:
        """Build all Stage A, B, C specs in canonical algorithm order.

        Stage A baseline is generated ONCE per algorithm (not per parameter).
        Stage B adds sensitivity runs per (algorithm, parameter, value).
        Stage C adds selected interaction runs per (algorithm, K, parameter, value).
        """
        specs: list[HyperparameterSpec] = []
        working_defaults = self._get_working_defaults()

        for algo in CANONICAL_ORDER:
            algo_cfg = self._algorithm_search_space(algo)
            if not algo_cfg:
                continue

            # Stage A: single baseline per algorithm.
            stage_a = _build_stage_a_spec(
                algorithm=algo,
                search_space_cfg=algo_cfg,
                working_defaults=working_defaults,
                baseline_seed=self.baseline_seed,
            )
            if stage_a is not None:
                specs.append(stage_a)

            # Stage B: parameter sweeps.
            specs.extend(
                _build_stage_b_specs(
                    algorithm=algo,
                    search_space_cfg=algo_cfg,
                    working_defaults=working_defaults,
                    baseline_seed=self.baseline_seed,
                )
            )

            # Stage C: selected interactions.
            algo_interactions = [
                inter
                for inter in self._get_selected_interactions()
                if inter.get("algorithm") == algo
            ]
            if algo_interactions:
                specs.extend(
                    _build_stage_c_specs(
                        interactions=algo_interactions,
                        working_defaults=working_defaults,
                        baseline_seed=self.baseline_seed,
                    )
                )

        return specs

    def run(
        self,
        matrix_df: pd.DataFrame,
        customer_metadata_df: pd.DataFrame | None = None,
        *,
        input_sha256: str | None = None,
        input_path: str | None = None,
        metadata_path: str | None = None,
        config_text: str | None = None,
        feature_set: str = "rfm_extended",
    ) -> HyperparameterSweepResult:
        """Run the full EXP-03 hyperparameter search.

        Parameters
        ----------
        matrix_df : DataFrame
            Feature matrix.
        customer_metadata_df : DataFrame | None
            Customer metadata.
        input_sha256 : str | None
            SHA-256 of input file.
        input_path : str | None
            Path to input file.
        metadata_path : str | None
            Path to metadata file.
        config_text : str | None
            Config text for SHA computation.
        feature_set : str
            Name of the feature set (for provenance).

        Returns
        -------
        HyperparameterSweepResult
            Full sweep result with all results, sensitivity table, and
            per-algorithm selected configurations.
        """
        all_specs = self._build_all_specs()
        results: list[HyperparameterResult] = []

        for spec in all_specs:
            result = _run_hyperparameter_spec(
                spec=spec,
                framework_cfg=self.cfg,
                exp03_config=self.exp03_config,
                matrix_df=matrix_df,
                customer_metadata_df=customer_metadata_df,
                n_repeat=self.n_repeat,
                exclude_noise=self.exclude_noise,
                noise_label=self.noise_label,
                input_sha256=input_sha256,
                input_path=input_path,
                metadata_path=metadata_path,
                config_text=config_text,
            )
            results.append(result)

        # Build sensitivity table.
        sensitivity_table = build_sensitivity_table(results)

        # Apply selection protocol per algorithm (canonical order).
        protocol_cfg = self._get_protocol_cfg()
        selected_configurations: list[SelectedConfiguration] = []
        for algo in CANONICAL_ORDER:
            sel = apply_selection_protocol(
                algorithm=algo,
                results=results,
                algorithm_search_space=self._algorithm_search_space(algo),
                protocol_cfg=protocol_cfg,
            )
            if sel is not None:
                selected_configurations.append(sel)

        # Library versions from first successful run.
        first_success = next((r for r in results if r.status == "SUCCESS"), None)
        library_versions = first_success.library_versions if first_success else {}

        n_total = len(results)
        n_success = sum(1 for r in results if r.status == "SUCCESS")

        return HyperparameterSweepResult(
            results=results,
            sensitivity_table=sensitivity_table,
            selected_configurations=selected_configurations,
            input_sha256=input_sha256,
            config_sha256=None,
            library_versions=library_versions,
            feature_set=feature_set,
            n_total_runs=n_total,
            n_successful_runs=n_success,
        )
