"""Experiment runner for the ML-01 framework.

The runner is the single entry point that turns

    FrameworkConfig + Algorithm Name + Hyperparameters

into

    ExperimentResult + on-disk artifacts + experiment log JSON.

It is intentionally generic: no if/elif over ``algorithm == "kmeans"``
etc. Each algorithm family encapsulates its own behaviour behind the
:class:`BaseClusterAlgorithm` interface.

Hard constraints:

- The runner NEVER calls algorithms that are not in the registry.
- The runner NEVER mutates the input matrix.
- The runner NEVER mutates the FE-06 final clustering dataset or
  customer metadata on disk (it may READ them, never WRITE them).
- The runner NEVER computes evaluation metrics. Metrics are
  placeholder fields for EPIC-07/08.
- The runner NEVER picks a "best" algorithm or declares a winner.
"""

from __future__ import annotations

import platform as platform_module
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from customer_segmentation.clustering.artifacts import write_experiment_artifacts
from customer_segmentation.clustering.base import BaseClusterAlgorithm
from customer_segmentation.clustering.config import (
    FrameworkConfig,
    compute_text_sha256,
)
from customer_segmentation.clustering.logging_utils import get_logger, now_utc_iso
from customer_segmentation.clustering.registry import AlgorithmRegistry
from customer_segmentation.clustering.result import (
    ClusterResult,
    ExperimentResult,
    ExperimentStatus,
    MetricsResult,
)
from customer_segmentation.clustering.validation import (
    ClusteringInputError,
    IdentifierLeakageError,
    ValidationReport,
    validate_clustering_matrix,
    validate_customer_alignment,
)

__all__ = [
    "ExperimentRunner",
    "RunnerError",
    "resolve_random_seed",
    "capture_library_versions",
    "capture_platform_info",
]


# ---------------------------------------------------------------------------
# Runner-level errors
# ---------------------------------------------------------------------------


class RunnerError(RuntimeError):
    """Raised when the runner itself fails (as opposed to the algorithm).

    Algorithm failures are caught and surfaced as
    :class:`ExperimentStatus.FAILED` in the :class:`ExperimentResult`.
    Runner errors are programming errors (e.g. algorithm not in
    registry, config malformed).
    """


# ---------------------------------------------------------------------------
# Environment snapshots
# ---------------------------------------------------------------------------


def capture_platform_info() -> dict[str, str]:
    """Snapshot the Python / OS environment."""
    return {
        "python": platform_module.python_version(),
        "system": platform_module.system(),
        "release": platform_module.release(),
        "machine": platform_module.machine(),
    }


def capture_library_versions() -> dict[str, str]:
    """Snapshot versions of the libraries the runner depends on."""
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


# ---------------------------------------------------------------------------
# Seed resolution
# ---------------------------------------------------------------------------


def resolve_random_seed(
    framework_cfg: FrameworkConfig,
    algorithm_name: str,
    override: int | None = None,
) -> tuple[int | None, int | None]:
    """Return ``(requested_seed, seed_to_pass)`` for the given algorithm.

    - ``override`` takes precedence over the YAML default.
    - Per-algorithm override in YAML takes precedence over the YAML
      default.
    - If the framework default is ``None`` and no override is given,
      ``(None, None)`` is returned (deterministic-only mode).
    """
    if override is not None:
        return override, override
    algo_override = framework_cfg.random_seed.per_algorithm_override.get(algorithm_name)
    if algo_override is not None:
        return algo_override, algo_override
    default = framework_cfg.random_seed.default
    return default, default


# ---------------------------------------------------------------------------
# ExperimentRunner
# ---------------------------------------------------------------------------


@dataclass
class ExperimentSpec:
    """Per-experiment overrides for the runner.

    Holds everything that varies between experiments but is fixed for
    a given experiment ID. Multiple experiments can share the same
    :class:`FrameworkConfig` and only differ in their
    :class:`ExperimentSpec`.
    """

    experiment_id: str
    algorithm: str
    hyperparameters: dict[str, Any] = field(default_factory=dict)
    seed_override: int | None = None


class ExperimentRunner:
    """Run a single clustering experiment end-to-end.

    Usage
    -----

    .. code-block:: python

        cfg = load_framework_config()
        spec = ExperimentSpec(
            experiment_id="ML-01-KMeans-k4-seed42",
            algorithm="kmeans",
            hyperparameters={"n_clusters": 4},
        )
        runner = ExperimentRunner(cfg, spec)
        result = runner.run(matrix_df, customer_metadata_df)
    """

    def __init__(
        self,
        framework_cfg: FrameworkConfig,
        spec: ExperimentSpec,
        *,
        config_source: str | None = None,
        config_text: str | None = None,
    ) -> None:
        self.cfg = framework_cfg
        self.spec = spec
        self.logger = get_logger()
        self.config_source = config_source
        self.config_text = config_text
        self.config_sha256: str | None = (
            compute_text_sha256(config_text) if config_text is not None else None
        )

    # ----- Public API -----
    def run(
        self,
        matrix_df: pd.DataFrame,
        customer_metadata_df: pd.DataFrame | None = None,
        *,
        input_sha256: str | None = None,
        input_path: str | None = None,
        metadata_path: str | None = None,
        output_dir: Path | None = None,
    ) -> ExperimentResult:
        """Run the experiment.

        Parameters
        ----------
        matrix_df : pandas.DataFrame
            Numeric feature matrix. MUST NOT contain identifiers.
        customer_metadata_df : pandas.DataFrame, optional
            Customer metadata carrying ``customer_key``. Used to align
            cluster labels back to ``CustomerID``.
        input_sha256 : str, optional
            SHA-256 of the input parquet file, recorded in the log.
        input_path : str, optional
            Path the matrix was loaded from, recorded in the log.
        metadata_path : str, optional
            Path the metadata was loaded from, recorded in the log.
        output_dir : pathlib.Path, optional
            Where to write artifacts. If ``None``, no artifacts are
            written; the caller is expected to handle persistence.

        Returns
        -------
        ExperimentResult
            Always returned. On failure, ``status == FAILED`` and
            ``cluster_result is None``.
        """
        # 1. Validate input matrix.
        matrix_validation = self._validate_matrix(matrix_df)

        # 2. Validate metadata alignment (only if metadata provided).
        alignment_validation: ValidationReport | None = None
        if customer_metadata_df is not None:
            alignment_validation = validate_customer_alignment(
                customer_metadata_df,
                matrix_df,
                customer_key=self.cfg.input.customer_key,
                source_label=(metadata_path or self.cfg.input.customer_metadata_path),
                fail_fast=False,  # runner records failure but continues
            )

        # 3. Resolve algorithm from registry.
        algorithm_cls = self._resolve_algorithm()

        # 4. Build adapter.
        adapter = self._build_adapter(algorithm_cls)

        # 5. Resolve seed.
        requested_seed, seed_to_pass = resolve_random_seed(
            self.cfg, self.spec.algorithm, override=self.spec.seed_override
        )
        # Pass seed only if the algorithm supports it.
        if seed_to_pass is not None and not adapter.supports_random_state():
            self.logger.info(
                "Algorithm '%s' does not support random_state; ignoring seed %s.",
                self.spec.algorithm,
                seed_to_pass,
            )
            seed_to_pass = None

        # 6. Fit.
        feature_set = list(matrix_df.columns)
        n_samples = len(matrix_df)
        n_features = len(matrix_df.columns)

        # If validation failed, abort before fit.
        hard_failures: list[str] = []
        if not matrix_validation.all_passed:
            hard_failures.extend(c.message for c in matrix_validation.failed())
        if alignment_validation is not None and not alignment_validation.all_passed:
            hard_failures.extend(c.message for c in alignment_validation.failed())

        if hard_failures:
            return self._build_failure_result(
                matrix_df=matrix_df,
                feature_set=feature_set,
                n_samples=n_samples,
                n_features=n_features,
                requested_seed=requested_seed,
                seed_to_pass=seed_to_pass,
                adapter=adapter,
                input_sha256=input_sha256,
                input_path=input_path,
                metadata_path=metadata_path,
                error_type=ClusteringInputError.__name__,
                error_message="; ".join(hard_failures),
                matrix_validation=matrix_validation,
                alignment_validation=alignment_validation,
                output_dir=output_dir,
                customer_metadata_df=customer_metadata_df,
            )

        cluster_result: ClusterResult | None = None
        error: dict[str, Any] | None = None
        execution_time = 0.0
        try:
            X = matrix_df.to_numpy(dtype=np.float64, copy=False)
            start = time.perf_counter()
            cluster_result = adapter.fit(X)
            execution_time = time.perf_counter() - start
        except Exception as exc:  # noqa: BLE001 - capture all failures
            error = {
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            }
            self.logger.exception("Algorithm '%s' failed: %s", self.spec.algorithm, exc)

        # 7. Build ExperimentResult.
        result = self._build_success_or_failure_result(
            cluster_result=cluster_result,
            error=error,
            execution_time=execution_time,
            feature_set=feature_set,
            n_samples=n_samples,
            n_features=n_features,
            requested_seed=requested_seed,
            seed_to_pass=seed_to_pass,
            adapter=adapter,
            input_sha256=input_sha256,
            input_path=input_path,
            metadata_path=metadata_path,
            matrix_validation=matrix_validation,
            alignment_validation=alignment_validation,
        )

        # 8. Write artifacts if requested.
        # The experiment log is ALWAYS written so failures are recorded.
        if output_dir is not None:
            artifact_paths = write_experiment_artifacts(
                output_dir,
                result,
                cluster_labels_filename=self.cfg.output.cluster_labels_filename,
                experiment_log_filename=self.cfg.output.experiment_log_filename,
                algorithm_output_filename=self.cfg.output.algorithm_output_filename,
                customer_metadata_df=customer_metadata_df,
                customer_key=self.cfg.input.customer_key,
                save_labels=(
                    self.cfg.output.save_labels
                    if result.status == ExperimentStatus.SUCCESS
                    else False
                ),
                save_metadata=self.cfg.output.save_metadata,
                save_algorithm_specific=(
                    self.cfg.output.save_algorithm_specific
                    if result.status == ExperimentStatus.SUCCESS
                    else False
                ),
            )
            result.artifact_paths.update(artifact_paths)

        return result

    # ----- Internal helpers -----
    def _validate_matrix(self, matrix_df: pd.DataFrame) -> ValidationReport:
        """Apply the framework's validation policy.

        Identifier leakage is treated as a **scope violation** and is
        raised immediately. Other validation failures are captured in
        the report so the runner can record them as a FAILED result.
        """
        report = validate_clustering_matrix(
            matrix_df,
            source_label=self.cfg.input.final_clustering_dataset_path,
            expected_features=None,
            min_samples=self.cfg.validation.min_samples,
            min_features=self.cfg.validation.min_features,
            fail_fast=False,
        )
        identifier_check = next(
            (c for c in report.checks if c.name == "no_identifier_in_matrix"),
            None,
        )
        if identifier_check is not None and identifier_check.status == "FAIL":
            self.logger.error("Identifier leakage detected: %s", identifier_check.message)
            raise IdentifierLeakageError(identifier_check.message)
        return report

    def _resolve_algorithm(self) -> type[BaseClusterAlgorithm]:
        """Look up the algorithm adapter in the registry."""
        try:
            return AlgorithmRegistry.get(self.spec.algorithm)
        except Exception as exc:  # AlgorithmRegistryError
            raise RunnerError(str(exc)) from exc

    def _build_adapter(
        self,
        algorithm_cls: type[BaseClusterAlgorithm],
    ) -> BaseClusterAlgorithm:
        """Instantiate the adapter with hyperparameters.

        If the adapter supports a ``random_state`` / ``seed`` keyword
        and ``resolve_random_seed`` returned a seed, we inject it.
        """
        params = dict(self.spec.hyperparameters)
        return algorithm_cls(**params)

    def _build_failure_result(
        self,
        *,
        matrix_df: pd.DataFrame,
        feature_set: list[str],
        n_samples: int,
        n_features: int,
        requested_seed: int | None,
        seed_to_pass: int | None,
        adapter: BaseClusterAlgorithm | None,
        input_sha256: str | None,
        input_path: str | None,
        metadata_path: str | None,
        error_type: str,
        error_message: str,
        matrix_validation: ValidationReport,
        alignment_validation: ValidationReport | None,
        output_dir: Path | None,
        customer_metadata_df: pd.DataFrame | None,
    ) -> ExperimentResult:
        """Build an ExperimentResult for a pre-fit failure (validation)."""
        # Record hyperparameters from the adapter (if built) so the log
        # still shows what would have been run.
        try:
            hp = adapter.get_params() if adapter is not None else dict(self.spec.hyperparameters)
        except Exception:  # pragma: no cover - defensive
            hp = dict(self.spec.hyperparameters)

        result = ExperimentResult(
            experiment_id=self.spec.experiment_id,
            status=ExperimentStatus.FAILED,
            algorithm=self.spec.algorithm,
            algorithm_version=adapter.version if adapter is not None else "",
            dataset_version=self.cfg.input.dataset_version,
            dataset_sha256=input_sha256,
            input_path=input_path,
            metadata_path=metadata_path,
            feature_set=feature_set,
            feature_count=n_features,
            n_samples=n_samples,
            hyperparameters=hp,
            random_seed=requested_seed,
            random_seed_used=seed_to_pass,
            n_clusters=None,
            cluster_labels=None,
            execution_time=0.0,
            timestamp=now_utc_iso(),
            cluster_result=None,
            metrics=MetricsResult(),
            artifact_paths={},
            error={
                "type": error_type,
                "message": error_message,
                "traceback": None,
                "matrix_validation": matrix_validation.to_dict(),
                "alignment_validation": (
                    alignment_validation.to_dict() if alignment_validation is not None else None
                ),
            },
            platform=capture_platform_info(),
            library_versions=capture_library_versions(),
            scope_boundaries=list(self.cfg.metadata.scope_boundaries),
            pending_review_notes=list(self.cfg.metadata.pending_review_notes),
            assumptions=list(self.cfg.metadata.assumptions),
            config_source=self.config_source,
            config_sha256=self.config_sha256,
        )

        if output_dir is not None:
            artifact_paths = write_experiment_artifacts(
                output_dir,
                result,
                cluster_labels_filename=self.cfg.output.cluster_labels_filename,
                experiment_log_filename=self.cfg.output.experiment_log_filename,
                algorithm_output_filename=self.cfg.output.algorithm_output_filename,
                customer_metadata_df=customer_metadata_df,
                customer_key=self.cfg.input.customer_key,
                save_labels=False,  # never save labels on failure
                save_metadata=self.cfg.output.save_metadata,
                save_algorithm_specific=False,
            )
            result.artifact_paths.update(artifact_paths)
        return result

    def _build_success_or_failure_result(
        self,
        *,
        cluster_result: ClusterResult | None,
        error: dict[str, Any] | None,
        execution_time: float,
        feature_set: list[str],
        n_samples: int,
        n_features: int,
        requested_seed: int | None,
        seed_to_pass: int | None,
        adapter: BaseClusterAlgorithm,
        input_sha256: str | None,
        input_path: str | None,
        metadata_path: str | None,
        matrix_validation: ValidationReport,
        alignment_validation: ValidationReport | None,
    ) -> ExperimentResult:
        """Build the ExperimentResult after fit() has been called."""
        if cluster_result is not None:
            return ExperimentResult(
                experiment_id=self.spec.experiment_id,
                status=ExperimentStatus.SUCCESS,
                algorithm=self.spec.algorithm,
                algorithm_version=adapter.version,
                dataset_version=self.cfg.input.dataset_version,
                dataset_sha256=input_sha256,
                input_path=input_path,
                metadata_path=metadata_path,
                feature_set=feature_set,
                feature_count=n_features,
                n_samples=n_samples,
                hyperparameters=adapter.get_params(),
                random_seed=requested_seed,
                random_seed_used=seed_to_pass,
                n_clusters=cluster_result.n_clusters,
                cluster_labels=cluster_result.cluster_labels,
                execution_time=execution_time,
                timestamp=now_utc_iso(),
                cluster_result=cluster_result,
                metrics=cluster_result.metrics,
                artifact_paths={},
                error=None,
                platform=capture_platform_info(),
                library_versions=capture_library_versions(),
                scope_boundaries=list(self.cfg.metadata.scope_boundaries),
                pending_review_notes=list(self.cfg.metadata.pending_review_notes),
                assumptions=list(self.cfg.metadata.assumptions),
                config_source=self.config_source,
                config_sha256=self.config_sha256,
            )

        # Fit failed.
        return ExperimentResult(
            experiment_id=self.spec.experiment_id,
            status=ExperimentStatus.FAILED,
            algorithm=self.spec.algorithm,
            algorithm_version=adapter.version,
            dataset_version=self.cfg.input.dataset_version,
            dataset_sha256=input_sha256,
            input_path=input_path,
            metadata_path=metadata_path,
            feature_set=feature_set,
            feature_count=n_features,
            n_samples=n_samples,
            hyperparameters=adapter.get_params(),
            random_seed=requested_seed,
            random_seed_used=seed_to_pass,
            n_clusters=None,
            cluster_labels=None,
            execution_time=execution_time,
            timestamp=now_utc_iso(),
            cluster_result=None,
            metrics=MetricsResult(),
            artifact_paths={},
            error=error,
            platform=capture_platform_info(),
            library_versions=capture_library_versions(),
            scope_boundaries=list(self.cfg.metadata.scope_boundaries),
            pending_review_notes=list(self.cfg.metadata.pending_review_notes),
            assumptions=list(self.cfg.metadata.assumptions),
            config_source=self.config_source,
            config_sha256=self.config_sha256,
        )
