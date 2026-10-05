"""Cluster number (K) survey orchestrator for EXP-02.

This module provides :class:`ClusterNumberRunner` that orchestrates a
controlled K-sweep experiment for the four K-parameterized clustering
algorithms (K-Means, Agglomerative, GMM, Fuzzy C-Means).

DBSCAN is recorded as a single diagnostic entry (no K-sweep).

EXP-02 design principles:

- K is the survey variable; all other factors are held fixed.
- The module reuses the EXP-01 metrics layer (silhouette, DBI, CH, WCSS)
  verbatim without modification.
- The module reuses the ML-01 ExperimentRunner for per-run execution.
- Candidate cluster numbers are evidence-based, NOT final/optimal/recommended.
- No "best", "winner", "optimal", "recommended", "best K" language anywhere.

Hard constraints (AGENTS.md §2, §3 "Clustering"):

- No ranking of algorithms or K values.
- No stability analysis (EXP-05 / EPIC-08 scope).
- WCSS uses arithmetic centroid from hard labels (not GMM Gaussian means
  or FCM fuzzy centroids).
- DBSCAN noise is excluded from internal metrics and WCSS.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from customer_segmentation.clustering.config import FrameworkConfig
from customer_segmentation.clustering.metrics import (
    METRIC_VALID,
    attach_metrics_with_status,
    compute_runtime_stats,
)
from customer_segmentation.clustering.registry import AlgorithmRegistry
from customer_segmentation.clustering.result import ClusterResult, ExperimentResult
from customer_segmentation.clustering.runner import ExperimentRunner, ExperimentSpec

__all__ = [
    "ClusterNumberSpec",
    "ClusterNumberResult",
    "ClusterNumberRunner",
    "ClusterNumberSweepResult",
    "generate_metric_curves",
    "generate_candidate_clusters",
]


# ---------------------------------------------------------------------------
# K-bearing algorithms and their K parameter names
# ---------------------------------------------------------------------------

ALGORITHMS_WITH_K: dict[str, str] = {
    "kmeans": "n_clusters",
    "agglomerative": "n_clusters",
    "gmm": "n_components",
    "fuzzy_cmeans": "n_clusters",
}

# DBSCAN is diagnostic only (no K parameter)
DIAGNOSTIC_ALGORITHMS: list[str] = ["dbscan"]

# Canonical order from EXP-01
CANONICAL_ORDER: list[str] = [
    "kmeans",
    "agglomerative",
    "dbscan",
    "gmm",
    "fuzzy_cmeans",
]


# ---------------------------------------------------------------------------
# Specification and result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ClusterNumberSpec:
    """Specification for a single (algorithm, K) combination."""

    experiment_id: str
    algorithm: str
    K: int
    hyperparameters: dict[str, Any]
    seed: int | None = None


@dataclass
class ClusterNumberResult:
    """Result of a single (algorithm, K) run."""

    experiment_id: str
    algorithm: str
    K: int | None  # None for diagnostic algorithms (e.g. DBSCAN)
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


# ---------------------------------------------------------------------------
# Candidate cluster number record
# ---------------------------------------------------------------------------


@dataclass
class CandidateClusterRecord:
    """Evidence-based candidate cluster number record."""

    algorithm: str
    feature_set: str
    K: int
    silhouette_value: float | None
    silhouette_status: str
    davies_bouldin_value: float | None
    davies_bouldin_status: str
    calinski_harabasz_value: float | None
    calinski_harabasz_status: str
    wcss_value: float | None
    wcss_status: str
    evidence_indicators: list[str]
    agreement_count: int


# ---------------------------------------------------------------------------
# Sweep result
# ---------------------------------------------------------------------------


@dataclass
class ClusterNumberSweepResult:
    """Result of a full K-sweep across all algorithms."""

    results: list[ClusterNumberResult]
    metric_curves: dict[str, dict[int, dict[str, Any]]]  # algo -> K -> metric dict
    candidates: list[CandidateClusterRecord]
    input_sha256: str | None
    config_sha256: str | None
    library_versions: dict[str, str]
    k_range: tuple[int, int]
    feature_set: str
    n_total_runs: int
    n_successful_runs: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_k_hyperparameters(
    algorithm: str,
    K: int,
    working_defaults: dict[str, Any],
    seed: int | None,
) -> dict[str, Any]:
    """Build hyperparameters for a (algorithm, K) combination.

    - K is passed via the correct parameter name (n_clusters or n_components).
    - Non-K hyperparameters come from working_defaults.
    - seed is injected for algorithms that support random_state.
    """
    k_param = ALGORITHMS_WITH_K.get(algorithm)
    hp = dict(working_defaults.get(algorithm, {}))
    if k_param is not None:
        hp[k_param] = K

    # Inject seed for algorithms that support random_state
    algo_cls = AlgorithmRegistry.get(algorithm)
    instance = algo_cls(**hp)
    if instance.supports_random_state() and seed is not None:
        hp["random_state"] = seed

    return hp


def _run_single(
    spec: ClusterNumberSpec,
    framework_cfg: FrameworkConfig,
    baseline_config: dict[str, Any],
    matrix_df: pd.DataFrame,
    customer_metadata_df: pd.DataFrame | None,
    n_repeat: int,
    exclude_noise: bool,
    noise_label: int,
    input_sha256: str | None,
    input_path: str | None,
    metadata_path: str | None,
    config_text: str | None,
) -> ClusterNumberResult:
    """Run a single (algorithm, K) experiment."""
    # Build experiment spec
    exp_spec = ExperimentSpec(
        experiment_id=spec.experiment_id,
        algorithm=spec.algorithm,
        hyperparameters=spec.hyperparameters,
        seed_override=spec.seed,
    )

    # Build runner
    runner = ExperimentRunner(
        framework_cfg,
        exp_spec,
        config_source=input_path,
        config_text=config_text,
    )

    # Collect raw runtimes across repetitions
    raw_runtimes: list[float] = []
    final_result: ExperimentResult | None = None

    for rep in range(n_repeat):
        rep_result = runner.run(
            matrix_df,
            customer_metadata_df,
            input_sha256=input_sha256,
            input_path=input_path,
            metadata_path=metadata_path,
            output_dir=None,  # No artifact writing during repetition
        )

        if rep_result.status == "SUCCESS" and rep_result.cluster_result is not None:
            raw_runtimes.append(rep_result.execution_time)

        if rep == n_repeat - 1:
            final_result = rep_result

    runtime_stats = compute_runtime_stats(raw_runtimes)

    if final_result is None or final_result.cluster_result is None:
        return ClusterNumberResult(
            experiment_id=spec.experiment_id,
            algorithm=spec.algorithm,
            K=spec.K,
            hyperparameters=spec.hyperparameters,
            n_clusters=None,
            noise_count=None,
            noise_ratio=None,
            cluster_result=None,
            runtime_stats=runtime_stats,
            input_sha256=input_sha256,
            config_sha256=None,
            library_versions=final_result.library_versions if final_result else {},
            status="FAILED",
            error=final_result.error if final_result else None,
        )

    # Get cluster result
    cluster_result = final_result.cluster_result

    # Compute metrics (reusing EXP-01 metrics layer)
    X = matrix_df.to_numpy(dtype=np.float64, copy=False)
    metric_start = time.perf_counter()
    cluster_result = attach_metrics_with_status(
        cluster_result,
        X,
        exclude_noise=exclude_noise,
        noise_label=noise_label,
        metric_computation_time=0.0,
        runtime_stats=runtime_stats,
    )
    metric_time = time.perf_counter() - metric_start
    cluster_result.metrics.extra["metric_computation_time_seconds"] = metric_time
    if cluster_result.metrics.runtime is not None:
        cluster_result.metrics.runtime["metric_computation"] = {"total_seconds": metric_time}

    return ClusterNumberResult(
        experiment_id=spec.experiment_id,
        algorithm=spec.algorithm,
        K=spec.K,
        hyperparameters=spec.hyperparameters,
        n_clusters=cluster_result.n_clusters,
        noise_count=cluster_result.noise_count,
        noise_ratio=cluster_result.noise_ratio,
        cluster_result=cluster_result,
        runtime_stats=runtime_stats,
        input_sha256=input_sha256,
        config_sha256=final_result.config_sha256,
        library_versions=final_result.library_versions,
        status="SUCCESS",
        error=None,
    )


def _run_diagnostic(
    algorithm: str,
    working_defaults: dict[str, Any],
    framework_cfg: FrameworkConfig,
    baseline_config: dict[str, Any],
    matrix_df: pd.DataFrame,
    customer_metadata_df: pd.DataFrame | None,
    n_repeat: int,
    exclude_noise: bool,
    noise_label: int,
    input_sha256: str | None,
    input_path: str | None,
    metadata_path: str | None,
    config_text: str | None,
) -> ClusterNumberResult:
    """Run a diagnostic algorithm (e.g. DBSCAN) without K-sweep."""
    experiment_id = f"EXP-02-{algorithm}-diagnostic"
    hp = dict(working_defaults.get(algorithm, {}))

    spec = ClusterNumberSpec(
        experiment_id=experiment_id,
        algorithm=algorithm,
        K=None,
        hyperparameters=hp,
        seed=None,
    )

    return _run_single(
        spec=spec,
        framework_cfg=framework_cfg,
        baseline_config=baseline_config,
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


# ---------------------------------------------------------------------------
# Metric curves builder
# ---------------------------------------------------------------------------


def generate_metric_curves(
    results: list[ClusterNumberResult],
) -> dict[str, dict[int, dict[str, Any]]]:
    """Build metric curves from K-sweep results.

    Returns
    -------
    curves : dict[str, dict[int, dict]]
        curves[algorithm][K] = {"silhouette": float|None, "davies_bouldin": float|None,
        "calinski_harabasz": float|None, "wcss": float|None,
        "silhouette_status": str, ...}
        Only K-bearing algorithms appear (DBSCAN diagnostic has K=None
        and is excluded from the K-curve structure).
    """
    curves: dict[str, dict[int, dict[str, Any]]] = {}

    for result in results:
        if result.K is None:
            # Diagnostic algorithm (e.g. DBSCAN) — not part of K-sweep curves
            continue

        if result.cluster_result is None:
            continue

        if result.algorithm not in curves:
            curves[result.algorithm] = {}

        m = result.cluster_result.metrics
        extra = m.extra
        curves[result.algorithm][result.K] = {
            "silhouette": m.silhouette,
            "silhouette_status": extra.get("silhouette_status", "MISSING"),
            "davies_bouldin": m.davies_bouldin,
            "davies_bouldin_status": extra.get("davies_bouldin_status", "MISSING"),
            "calinski_harabasz": m.calinski_harabasz,
            "calinski_harabasz_status": extra.get("calinski_harabasz_status", "MISSING"),
            "wcss": m.wcss,
            "wcss_status": extra.get("wcss_status", "MISSING"),
            "n_clusters": result.n_clusters,
            "noise_count": result.noise_count,
            "noise_ratio": result.noise_ratio,
            "runtime_mean": result.runtime_stats.get("mean_seconds"),
            "runtime_std": result.runtime_stats.get("std_seconds"),
        }

    return curves


# ---------------------------------------------------------------------------
# Candidate cluster number generator
# ---------------------------------------------------------------------------


def generate_candidate_clusters(
    curves: dict[str, dict[int, dict[str, Any]]],
    top_n: int = 3,
    elbow_drop_ratio: float = 0.2,
    min_agreement: int = 2,
) -> list[CandidateClusterRecord]:
    """Generate evidence-based candidate cluster numbers.

    Parameters
    ----------
    curves : dict
        Metric curves from :func:`generate_metric_curves`.
    top_n : int
        Number of top-K candidates per silhouette/DBI/CH indicator.
    elbow_drop_ratio : float
        WCSS drop ratio threshold for elbow indicator.
    min_agreement : int
        Minimum number of indicators that must flag a K for it to
        be a candidate.

    Returns
    -------
    candidates : list of CandidateClusterRecord
        Evidence-based candidate cluster numbers. NOT final/optimal/recommended.

    Notes
    -----
    This function implements transparent, deterministic heuristics to
    surface K values worth inspecting. It does NOT declare a winner.
    The candidate set is a *starting point* for downstream evaluation
    (EPIC-08) and mentor/human review.
    """
    candidates: list[CandidateClusterRecord] = []
    all_k_algorithms = [a for a in curves if any(k is not None for k in curves[a])]

    for algo in all_k_algorithms:
        k_data = curves[algo]
        k_values = sorted(k_data.keys())
        if len(k_values) < 2:
            continue

        # ---- Collect valid (K, metric) pairs ----
        sil_pairs = [
            (k, d["silhouette"])
            for k, d in k_data.items()
            if d.get("silhouette_status") == METRIC_VALID and d.get("silhouette") is not None
        ]
        dbi_pairs = [
            (k, d["davies_bouldin"])
            for k, d in k_data.items()
            if d.get("davies_bouldin_status") == METRIC_VALID
            and d.get("davies_bouldin") is not None
        ]
        ch_pairs = [
            (k, d["calinski_harabasz"])
            for k, d in k_data.items()
            if d.get("calinski_harabasz_status") == METRIC_VALID
            and d.get("calinski_harabasz") is not None
        ]
        wcss_pairs = [
            (k, d["wcss"])
            for k, d in k_data.items()
            if d.get("wcss_status") == METRIC_VALID and d.get("wcss") is not None
        ]

        # ---- Silhouette: top-N highest ----
        k_sil_high = set()
        if sil_pairs:
            sorted_sil = sorted(sil_pairs, key=lambda x: x[1], reverse=True)
            k_sil_high = {k for k, _ in sorted_sil[:top_n]}

        # ---- DBI: bottom-N lowest (DBI convention: lower is more compact) ----
        k_dbi_low = set()
        if dbi_pairs:
            sorted_dbi = sorted(dbi_pairs, key=lambda x: x[1])
            k_dbi_low = {k for k, _ in sorted_dbi[:top_n]}

        # ---- CH: top-N highest ----
        k_ch_high = set()
        if ch_pairs:
            sorted_ch = sorted(ch_pairs, key=lambda x: x[1], reverse=True)
            k_ch_high = {k for k, _ in sorted_ch[:top_n]}

        # ---- Elbow: significant WCSS drop ratio ----
        # For each consecutive K pair (k_i, k_{i+1}), compute
        # drop_ratio = (wcss[k_i] - wcss[k_{i+1}]) / wcss[k_i]
        k_elbow = set()
        if len(wcss_pairs) >= 2:
            wcss_dict = dict(wcss_pairs)
            sorted_wcss = sorted(wcss_dict)
            for i in range(len(sorted_wcss) - 1):
                k_curr = sorted_wcss[i]
                k_next = sorted_wcss[i + 1]
                wcss_curr = wcss_dict[k_curr]
                wcss_next = wcss_dict[k_next]
                if wcss_curr > 0:
                    drop_ratio = (wcss_curr - wcss_next) / wcss_curr
                    if drop_ratio >= elbow_drop_ratio:
                        k_elbow.add(k_next)  # The next K benefits from a big drop

        # ---- Build candidate records ----
        k_all_evidence: dict[int, list[str]] = {k: [] for k in k_values}

        for k in k_sil_high:
            if k in k_all_evidence:
                k_all_evidence[k].append("silhouette_top_n")
        for k in k_dbi_low:
            if k in k_all_evidence:
                k_all_evidence[k].append("davies_bouldin_low_n")
        for k in k_ch_high:
            if k in k_all_evidence:
                k_all_evidence[k].append("calinski_harabasz_top_n")
        for k in k_elbow:
            if k in k_all_evidence:
                k_all_evidence[k].append("wcss_elbow_drop")

        for k, indicators in k_all_evidence.items():
            if len(indicators) >= min_agreement:
                d = k_data[k]
                record = CandidateClusterRecord(
                    algorithm=algo,
                    feature_set="rfm_extended",
                    K=k,
                    silhouette_value=d.get("silhouette"),
                    silhouette_status=d.get("silhouette_status", "MISSING"),
                    davies_bouldin_value=d.get("davies_bouldin"),
                    davies_bouldin_status=d.get("davies_bouldin_status", "MISSING"),
                    calinski_harabasz_value=d.get("calinski_harabasz"),
                    calinski_harabasz_status=d.get("calinski_harabasz_status", "MISSING"),
                    wcss_value=d.get("wcss"),
                    wcss_status=d.get("wcss_status", "MISSING"),
                    evidence_indicators=sorted(indicators),
                    agreement_count=len(indicators),
                )
                candidates.append(record)

    # Sort by algorithm (canonical order) then by K
    algo_order = {a: i for i, a in enumerate(CANONICAL_ORDER)}
    candidates.sort(key=lambda c: (algo_order.get(c.algorithm, 999), c.K))

    return candidates


# ---------------------------------------------------------------------------
# ClusterNumberRunner
# ---------------------------------------------------------------------------


class ClusterNumberRunner:
    """Orchestrate EXP-02 cluster number survey experiment.

    Usage
    -----

    .. code-block:: python

        runner = ClusterNumberRunner(framework_cfg, exp02_config)
        result = runner.run(
            matrix_df,
            customer_metadata_df,
            input_sha256="...",
            k_range=(2, 10),
        )
        curves = generate_metric_curves(result.results)
        candidates = generate_candidate_clusters(curves)
    """

    def __init__(
        self,
        framework_cfg: FrameworkConfig,
        exp02_config: dict[str, Any],
        *,
        baseline_seed: int | None = None,
        n_repeat: int | None = None,
        exclude_noise: bool = True,
        noise_label: int | None = None,
    ) -> None:
        """Initialize ClusterNumberRunner.

        Parameters
        ----------
        framework_cfg : FrameworkConfig
            Framework configuration (from configs/clustering.yaml).
        exp02_config : dict
            EXP-02 configuration (from configs/exp02_cluster_number.yaml).
        baseline_seed : int or None
            Seed used for all (algorithm, K) runs. If ``None``, defaults
            to ``exp02_config['exp02']['runtime']['seed']`` (default 42).
        n_repeat : int or None
            Number of repetitions per (algorithm, K) for runtime
            measurement. If ``None``, defaults to
            ``exp02_config['exp02']['runtime']['repeat']`` (default 5).
        exclude_noise : bool
            Whether to exclude noise from metrics.
        noise_label : int or None
            Noise label value (defaults to -1 if not provided).
        """
        self.cfg = framework_cfg
        self.exp02_config = exp02_config
        runtime_cfg = exp02_config.get("exp02", {}).get("runtime", {})
        self.baseline_seed = (
            baseline_seed if baseline_seed is not None else int(runtime_cfg.get("seed", 42))
        )
        self.n_repeat = n_repeat if n_repeat is not None else int(runtime_cfg.get("repeat", 5))
        dbscan_cfg = exp02_config.get("exp02", {}).get("dbscan", {})
        self.exclude_noise = exclude_noise
        self.noise_label = (
            noise_label if noise_label is not None else int(dbscan_cfg.get("noise_label", -1))
        )

    def _get_working_defaults(self) -> dict[str, Any]:
        return self.exp02_config.get("working_defaults", {}) or self.exp02_config.get(
            "exp02", {}
        ).get("working_defaults", {})

    def _get_k_range(self) -> tuple[int, int]:
        k_cfg = self.exp02_config.get("exp02", {}).get("k_range", {})
        return int(k_cfg.get("min", 2)), int(k_cfg.get("max", 10))

    def run_single(
        self,
        algorithm: str,
        K: int,
        matrix_df: pd.DataFrame,
        customer_metadata_df: pd.DataFrame | None = None,
        *,
        input_sha256: str | None = None,
        input_path: str | None = None,
        metadata_path: str | None = None,
        config_text: str | None = None,
        output_dir: Path | None = None,
    ) -> ClusterNumberResult:
        """Run a single (algorithm, K) combination.

        Parameters
        ----------
        algorithm : str
            Algorithm name (must be in ALGORITHMS_WITH_K).
        K : int
            Number of clusters / components.
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
        output_dir : Path | None
            Output directory (currently unused in single-run; reserved).

        Returns
        -------
        ClusterNumberResult
            Result of the single run.
        """
        if algorithm not in ALGORITHMS_WITH_K:
            raise ValueError(
                f"Algorithm '{algorithm}' does not have a K parameter. "
                f"Use run_diagnostic() for diagnostic algorithms."
            )

        working_defaults = self._get_working_defaults()
        hp = _build_k_hyperparameters(algorithm, K, working_defaults, self.baseline_seed)

        spec = ClusterNumberSpec(
            experiment_id=f"EXP-02-{algorithm}-k{K}",
            algorithm=algorithm,
            K=K,
            hyperparameters=hp,
            seed=self.baseline_seed,
        )

        return _run_single(
            spec=spec,
            framework_cfg=self.cfg,
            baseline_config=self.exp02_config,
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

    def run_diagnostic(
        self,
        algorithm: str,
        matrix_df: pd.DataFrame,
        customer_metadata_df: pd.DataFrame | None = None,
        *,
        input_sha256: str | None = None,
        input_path: str | None = None,
        metadata_path: str | None = None,
        config_text: str | None = None,
    ) -> ClusterNumberResult:
        """Run a diagnostic algorithm (e.g. DBSCAN) without K-sweep.

        Parameters
        ----------
        algorithm : str
            Algorithm name (must be in DIAGNOSTIC_ALGORITHMS).
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

        Returns
        -------
        ClusterNumberResult
            Result of the diagnostic run.
        """
        if algorithm not in DIAGNOSTIC_ALGORITHMS:
            raise ValueError(
                f"Algorithm '{algorithm}' is not a diagnostic algorithm. "
                f"Diagnostic algorithms: {DIAGNOSTIC_ALGORITHMS}."
            )

        working_defaults = self._get_working_defaults()

        return _run_diagnostic(
            algorithm=algorithm,
            working_defaults=working_defaults,
            framework_cfg=self.cfg,
            baseline_config=self.exp02_config,
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

    def run_sweep(
        self,
        matrix_df: pd.DataFrame,
        customer_metadata_df: pd.DataFrame | None = None,
        *,
        input_sha256: str | None = None,
        input_path: str | None = None,
        metadata_path: str | None = None,
        config_text: str | None = None,
        feature_set: str = "rfm_extended",
    ) -> ClusterNumberSweepResult:
        """Run the full K-sweep across all K-bearing algorithms.

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
        ClusterNumberSweepResult
            Full sweep result with all results, metric curves, and candidates.
        """
        results: list[ClusterNumberResult] = []
        k_min, k_max = self._get_k_range()
        working_defaults = self._get_working_defaults()

        # ---- Iterate in canonical order so report is reproducible ----
        # Canonical order: kmeans, agglomerative, dbscan, gmm, fuzzy_cmeans.
        # K-bearing algorithms are emitted in canonical order; dbscan
        # diagnostic slot is interleaved AFTER agglomerative (before gmm).
        for algo in CANONICAL_ORDER:
            if algo in DIAGNOSTIC_ALGORITHMS:
                # ---- Diagnostic algorithm (e.g. DBSCAN) ----
                result = _run_diagnostic(
                    algorithm=algo,
                    working_defaults=working_defaults,
                    framework_cfg=self.cfg,
                    baseline_config=self.exp02_config,
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
                continue

            if algo not in ALGORITHMS_WITH_K:
                continue

            # ---- K-bearing algorithm ----
            for K in range(k_min, k_max + 1):
                hp = _build_k_hyperparameters(algo, K, working_defaults, self.baseline_seed)
                spec = ClusterNumberSpec(
                    experiment_id=f"EXP-02-{algo}-k{K}",
                    algorithm=algo,
                    K=K,
                    hyperparameters=hp,
                    seed=self.baseline_seed,
                )

                result = _run_single(
                    spec=spec,
                    framework_cfg=self.cfg,
                    baseline_config=self.exp02_config,
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

        # ---- Build metric curves ----
        curves = generate_metric_curves(results)

        # ---- Generate candidate cluster numbers ----
        heuristic_cfg = self.exp02_config.get("candidate_heuristic", {})
        top_n = int(heuristic_cfg.get("top_n_per_indicator", 3))
        elbow_drop = float(heuristic_cfg.get("elbow_drop_ratio_threshold", 0.2))
        min_agreement = int(heuristic_cfg.get("min_agreement_count", 2))
        candidates = generate_candidate_clusters(
            curves, top_n=top_n, elbow_drop_ratio=elbow_drop, min_agreement=min_agreement
        )

        n_total = len(results)
        n_success = sum(1 for r in results if r.status == "SUCCESS")
        first_success = next((r for r in results if r.status == "SUCCESS"), None)

        return ClusterNumberSweepResult(
            results=results,
            metric_curves=curves,
            candidates=candidates,
            input_sha256=input_sha256,
            config_sha256=None,
            library_versions=(first_success.library_versions if first_success else {}),
            k_range=(k_min, k_max),
            feature_set=feature_set,
            n_total_runs=n_total,
            n_successful_runs=n_success,
        )
