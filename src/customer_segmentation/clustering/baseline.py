"""Baseline experiment orchestrator for EXP-01.

This module provides :class:`BaselineRunner` that orchestrates the
EXP-01 baseline experiment across 5 clustering algorithms:

1. K-Means
2. Agglomerative Clustering
3. DBSCAN
4. Gaussian Mixture Model
5. Fuzzy C-Means

Baseline Protocol
-----------------

Each algorithm is run with:

- Working defaults from configs/clustering.yaml.
- Baseline seed = 42.
- n_repeat = 5 repetitions for runtime measurement.

Each repetition:
1. Validate input (via ExperimentRunner).
2. Fit algorithm (EXCLUDES artifact writing).
3. Measure ONLY algorithm execution time (perf_counter around fit).
4. Discard ClusterResult except for the final repetition.

After all repetitions:
1. Take final ClusterResult.
2. Compute metrics (silhouette, DBI, CH, WCSS).
3. Attach MetricsResult with status metadata.
4. Return BaselineResult with runtime statistics.

Hard constraints (AGENTS.md §2, §3 "Clustering"):

- No "best/recommended/optimal/winner" language.
- No algorithm ranking or comparison.
- No stability analysis (EXP-05 generates evidence; EPIC-08 analyzes).
- Runtime protocol strictly separates algorithm execution, metric
  computation, and artifact writing.

Scope boundaries
---------------

EXP-01 DOES:
- Run 5 algorithms on the same FE-06 dataset.
- Compute unified metrics (silhouette, DBI, CH, WCSS) with status.
- Measure algorithm execution runtime with repetition statistics.
- Record reproducibility metadata (SHA, config, seed, library versions).

EXP-01 DOES NOT:
- Sweep hyperparameters (EPIC-07 scope).
- Rank or compare algorithms (EPIC-08 scope).
- Compute stability metrics (EXP-05 / EPIC-08 scope).
- Profile customer segments (EPIC-09 scope).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from customer_segmentation.clustering.config import (
    FrameworkConfig,
)
from customer_segmentation.clustering.metrics import (
    attach_metrics_with_status,
    compute_runtime_stats,
)
from customer_segmentation.clustering.registry import AlgorithmRegistry
from customer_segmentation.clustering.result import ClusterResult, ExperimentResult
from customer_segmentation.clustering.runner import ExperimentRunner, ExperimentSpec

__all__ = [
    "BaselineSpec",
    "BaselineResult",
    "BaselineRunner",
]


# ---------------------------------------------------------------------------
# Canonical algorithm order (matches configs/exp01_baseline.yaml)
# ---------------------------------------------------------------------------

CANONICAL_ALGORITHMS: list[str] = [
    "kmeans",
    "agglomerative",
    "dbscan",
    "gmm",
    "fuzzy_cmeans",
]


# ---------------------------------------------------------------------------
# Baseline specification and result
# ---------------------------------------------------------------------------


@dataclass
class BaselineSpec:
    """Specification for a single baseline run."""

    experiment_id: str
    algorithm: str
    hyperparameters: dict[str, Any]
    seed: int | None = None


@dataclass
class BaselineResult:
    """Result of a single baseline algorithm run."""

    experiment_id: str
    algorithm: str
    algorithm_version: str
    hyperparameters: dict[str, Any]
    n_clusters: int | None
    noise_count: int | None
    noise_ratio: float | None
    cluster_result: ClusterResult
    runtime_stats: dict[str, Any]
    input_sha256: str | None
    config_sha256: str | None
    library_versions: dict[str, str]
    status: str = "SUCCESS"
    error: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# BaselineRunner
# ---------------------------------------------------------------------------


class BaselineRunner:
    """Orchestrate EXP-01 baseline experiment.

    Usage
    -----

    .. code-block:: python

        runner = BaselineRunner(framework_config, baseline_config)
        result = runner.run(
            spec=BaselineSpec(...),
            matrix_df=df,
            customer_metadata_df=metadata,
            n_repeat=5,
        )
    """

    def __init__(
        self,
        framework_cfg: FrameworkConfig,
        baseline_config: dict[str, Any],
        *,
        baseline_seed: int = 42,
        n_repeat: int = 5,
        exclude_noise: bool = True,
        noise_label: int = -1,
    ) -> None:
        """Initialize BaselineRunner.

        Parameters
        ----------
        framework_cfg : FrameworkConfig
            Framework configuration (from configs/clustering.yaml).
        baseline_config : dict
            Baseline configuration (from configs/exp01_baseline.yaml).
        baseline_seed : int
            Baseline seed used for all algorithms.
        n_repeat : int
            Number of repetitions for runtime measurement.
        exclude_noise : bool
            Whether to exclude noise from metrics.
        noise_label : int
            Noise label value (-1 for sklearn convention).
        """
        self.cfg = framework_cfg
        self.baseline_config = baseline_config
        self.baseline_seed = baseline_seed
        self.n_repeat = n_repeat
        self.exclude_noise = exclude_noise
        self.noise_label = noise_label

    def run(
        self,
        spec: BaselineSpec,
        matrix_df: pd.DataFrame,
        customer_metadata_df: pd.DataFrame | None = None,
        *,
        input_sha256: str | None = None,
        input_path: str | None = None,
        metadata_path: str | None = None,
        config_text: str | None = None,
        output_dir: Path | None = None,
    ) -> BaselineResult:
        """Run baseline experiment for a single algorithm.

        Parameters
        ----------
        spec : BaselineSpec
            Algorithm specification.
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
            Output directory for artifacts.

        Returns
        -------
        BaselineResult
            Baseline result with metrics and runtime statistics.
        """
        # Resolve algorithm from registry
        try:
            algo_cls = AlgorithmRegistry.get(spec.algorithm)
        except Exception as exc:
            return BaselineResult(
                experiment_id=spec.experiment_id,
                algorithm=spec.algorithm,
                algorithm_version="",
                hyperparameters=spec.hyperparameters,
                n_clusters=None,
                noise_count=None,
                noise_ratio=None,
                cluster_result=ClusterResult(
                    algorithm=spec.algorithm,
                    algorithm_version="",
                    algorithm_family="unknown",
                    n_samples=len(matrix_df),
                    n_features=len(matrix_df.columns),
                    cluster_labels=np.array([], dtype=np.int64),
                    n_clusters=None,
                ),
                runtime_stats={},
                input_sha256=input_sha256,
                config_sha256=None,
                library_versions={},
                status="FAILED",
                error={"type": "RegistryError", "message": str(exc)},
            )

        # Collect raw runtimes
        raw_runtimes: list[float] = []
        final_result: ExperimentResult | None = None

        for rep in range(self.n_repeat):
            # Build experiment spec
            exp_spec = ExperimentSpec(
                experiment_id=f"{spec.experiment_id}_rep{rep}",
                algorithm=spec.algorithm,
                hyperparameters=spec.hyperparameters,
                seed_override=spec.seed,
            )

            # Build runner (output_dir=None for non-final repetitions)
            runner = ExperimentRunner(
                self.cfg,
                exp_spec,
                config_source=input_path,
                config_text=config_text,
            )

            # Run WITHOUT artifact writing for non-final repetitions
            rep_output_dir = output_dir if rep == self.n_repeat - 1 else None

            rep_result = runner.run(
                matrix_df,
                customer_metadata_df,
                input_sha256=input_sha256,
                input_path=input_path,
                metadata_path=metadata_path,
                output_dir=rep_output_dir,
            )

            if rep_result.status == "SUCCESS" and rep_result.cluster_result is not None:
                raw_runtimes.append(rep_result.execution_time)

            # Keep final result
            if rep == self.n_repeat - 1:
                final_result = rep_result

        # Compute runtime statistics
        runtime_stats = compute_runtime_stats(raw_runtimes)

        # Handle failure case
        if final_result is None or final_result.cluster_result is None:
            return BaselineResult(
                experiment_id=spec.experiment_id,
                algorithm=spec.algorithm,
                algorithm_version=algo_cls.version,
                hyperparameters=spec.hyperparameters,
                n_clusters=None,
                noise_count=None,
                noise_ratio=None,
                cluster_result=ClusterResult(
                    algorithm=spec.algorithm,
                    algorithm_version=algo_cls.version,
                    algorithm_family=algo_cls.family,
                    n_samples=len(matrix_df),
                    n_features=len(matrix_df.columns),
                    cluster_labels=np.array([], dtype=np.int64),
                    n_clusters=None,
                ),
                runtime_stats=runtime_stats,
                input_sha256=input_sha256,
                config_sha256=final_result.config_sha256 if final_result else None,
                library_versions=final_result.library_versions if final_result else {},
                status="FAILED",
                error=final_result.error if final_result else None,
            )

        # Get final cluster result
        cluster_result = final_result.cluster_result

        # Convert matrix to numpy for metrics computation
        X = matrix_df.to_numpy(dtype=np.float64, copy=False)

        # Compute metrics with timing
        metric_start = time.perf_counter()
        cluster_result = attach_metrics_with_status(
            cluster_result,
            X,
            exclude_noise=self.exclude_noise,
            noise_label=self.noise_label,
            metric_computation_time=0.0,  # Will be updated below
            runtime_stats=runtime_stats,
        )
        metric_time = time.perf_counter() - metric_start

        # Update metric computation time
        cluster_result.metrics.extra["metric_computation_time_seconds"] = metric_time
        if cluster_result.metrics.runtime is not None:
            cluster_result.metrics.runtime["metric_computation"] = {
                "total_seconds": metric_time,
            }

        # Compute config SHA if config text provided
        config_sha = None
        if config_text is not None:
            from customer_segmentation.clustering.config import compute_text_sha256

            config_sha = compute_text_sha256(config_text)

        return BaselineResult(
            experiment_id=spec.experiment_id,
            algorithm=spec.algorithm,
            algorithm_version=algo_cls.version,
            hyperparameters=spec.hyperparameters,
            n_clusters=cluster_result.n_clusters,
            noise_count=cluster_result.noise_count,
            noise_ratio=cluster_result.noise_ratio,
            cluster_result=cluster_result,
            runtime_stats=runtime_stats,
            input_sha256=input_sha256,
            config_sha256=config_sha,
            library_versions=final_result.library_versions,
            status="SUCCESS",
            error=None,
        )

    def run_all(
        self,
        matrix_df: pd.DataFrame,
        customer_metadata_df: pd.DataFrame | None = None,
        *,
        input_sha256: str | None = None,
        input_path: str | None = None,
        metadata_path: str | None = None,
        config_text: str | None = None,
        output_dir: Path | None = None,
    ) -> list[BaselineResult]:
        """Run baseline experiment for all canonical algorithms.

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
        output_dir : Path | None
            Output directory for artifacts.

        Returns
        -------
        list[BaselineResult]
            List of baseline results for all algorithms.
        """
        results: list[BaselineResult] = []
        working_defaults = self.baseline_config.get("working_defaults", {})

        for algo in CANONICAL_ALGORITHMS:
            # Build spec with working defaults
            hp = working_defaults.get(algo, {}).copy()
            # Add random_state for algorithms that support it
            algo_cls = AlgorithmRegistry.get(algo)
            # Instantiate to check supports_random_state (instance method)
            instance = algo_cls(**hp)
            if instance.supports_random_state():
                hp["random_state"] = self.baseline_seed

            spec = BaselineSpec(
                experiment_id=f"EXP-01-{algo}",
                algorithm=algo,
                hyperparameters=hp,
                seed=self.baseline_seed,
            )

            result = self.run(
                spec,
                matrix_df,
                customer_metadata_df,
                input_sha256=input_sha256,
                input_path=input_path,
                metadata_path=metadata_path,
                config_text=config_text,
                output_dir=output_dir,
            )
            results.append(result)

        return results
