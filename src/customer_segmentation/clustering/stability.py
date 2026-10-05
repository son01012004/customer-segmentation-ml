"""Stability & Reproducibility runner for EXP-05.

EXP-05 generates raw **stability evidence** and **reproducibility
evidence** for the 5 EPIC-06 clustering algorithms on the FE-06
final clustering matrix via three independent blocks:

- Block R — Reproducibility: 5 algorithms × n_repeat=5 × seed=42.
  Verifies ``labels_hash`` and metric values are deterministic.
  This is REPRODUCIBILITY_VERIFICATION, NOT stability analysis.
- Block S — Random Seed Stability: K-Means + GMM + FCM (the 3
  algorithms with a random axis) × 5 seeds. Fixed hyperparameters.
  Records metrics, cluster sizes, ``labels_hash``. Agglomerative
  and DBSCAN are deterministic in sklearn; they are NOT included.
- Block N — Feature Perturbation: in-memory Gaussian noise on the
  FE-06 final clustering matrix at ``sigma = 0, 0.01, 0.05`` ×
  feature std. ``sigma=0`` = sanity (reproduces EXP-01 baseline).
  ``sigma=0.01, 0.05`` × 3 perturbation seeds each.

EXP-05 is EVIDENCE GENERATION, NOT stability analysis:

- ARI / AMI computation → EPIC-08.
- Hungarian matching → EPIC-08.
- Statistical tests across seeds → EPIC-08.
- Confidence intervals → EPIC-08.
- Cross-algorithm ranking / "best" / "winner" claims → FORBIDDEN.

The module exposes:

- :func:`compute_labels_hash` — deterministic SHA-256 over a label
  vector (re-exported from the EXP-04 module to avoid duplication).
- :func:`perturb_in_memory` — Gaussian perturbation scaled by
  column-wise std. NEVER persists perturbed matrix to disk.
- :func:`aggregate_variation_stats` — mean / std / min / max / CV /
  unique_count over a numeric sequence.
- :class:`BlockRRecord` / :class:`BlockSRecord` / :class:`BlockNRecord`
  — per-run dataclasses (carries ``cluster_labels`` in memory for the
  label artifact).
- :class:`BlockRAggregate` / :class:`BlockSAggregate` /
  :class:`BlockNAggregate` — per-block aggregate dataclasses.
- :class:`LabelArtifactRow` — schema for
  ``exp05_cluster_labels.parquet``.
- :class:`StabilityResult` — top-level container.
- :class:`StabilityReproducibilityRunner` — orchestrator that runs
  all three blocks.

Hard constraints (AGENTS.md §2, EXP-05 Plan R1):

- NO mutation of FE-05 / FE-06 outputs. SHA-256 verified pre/post.
- NO perturbation persistence to disk.
- NO composite score, cross-algorithm ranking, or "best/winner" claims.
- NO ARI / AMI computation.
- NO K sweep / hyperparameter sweep / preprocessing sweep.
- CustomerID alignment via ``validate_customer_alignment``.
"""

from __future__ import annotations

import math
import platform as platform_module
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from customer_segmentation.clustering.config import (
    FrameworkConfig,
    compute_text_sha256,
)
from customer_segmentation.clustering.metrics import (
    attach_metrics_with_status,
    compute_runtime_stats,
)
from customer_segmentation.clustering.preprocessing_feature_sensitivity import (
    compute_labels_hash,
)
from customer_segmentation.clustering.runner import ExperimentRunner, ExperimentSpec

__all__ = [
    # Constants
    "BLOCK_R",
    "BLOCK_S",
    "BLOCK_N",
    "DECISION_STATUS_REPRO_VERIFIED",
    "DECISION_STATUS_REPRO_FAILED",
    "DECISION_STATUS_STABILITY_EVIDENCE",
    "DECISION_STATUS_PERTURBATION_EVIDENCE",
    "DECISION_STATUS_SIGMA_ZERO_MATCH",
    "DECISION_STATUS_SIGMA_ZERO_MISMATCH",
    "DECISION_STATUS_PENDING_REVIEW",
    "PERMITTED_DECISION_STATUSES",
    "FORBIDDEN_DECISION_LABELS",
    "EXP05_CANONICAL_ALGORITHMS",
    "EXP05_SEEDS_BLOCK_S",
    "EXP05_SIGMA_GRID_BLOCK_N",
    "EXP05_PERTURBATION_SEEDS_BLOCK_N",
    "EXP05_ALGORITHMS_BLOCK_S",
    # Helpers
    "compute_labels_hash",
    "perturb_in_memory",
    "aggregate_variation_stats",
    # Dataclasses
    "BlockRRecord",
    "BlockSRecord",
    "BlockNRecord",
    "LabelArtifactRow",
    "BlockRAggregate",
    "BlockSAggregate",
    "BlockNAggregate",
    "StabilityResult",
    # Runner
    "StabilityReproducibilityRunner",
]


# ---------------------------------------------------------------------------
# Block identifiers
# ---------------------------------------------------------------------------

BLOCK_R = "R"
BLOCK_S = "S"
BLOCK_N = "N"


# ---------------------------------------------------------------------------
# Decision status taxonomy (Plan §9.2)
# ---------------------------------------------------------------------------

DECISION_STATUS_REPRO_VERIFIED = "REPRODUCIBILITY_VERIFIED"
DECISION_STATUS_REPRO_FAILED = "REPRODUCIBILITY_FAILED"
DECISION_STATUS_STABILITY_EVIDENCE = "STABILITY_EVIDENCE_GENERATED"
DECISION_STATUS_PERTURBATION_EVIDENCE = "PERTURBATION_EVIDENCE_GENERATED"
DECISION_STATUS_SIGMA_ZERO_MATCH = "SIGMA_ZERO_BASELINE_MATCH"
DECISION_STATUS_SIGMA_ZERO_MISMATCH = "SIGMA_ZERO_BASELINE_MISMATCH"
DECISION_STATUS_PENDING_REVIEW = "PENDING_REVIEW"

PERMITTED_DECISION_STATUSES: frozenset[str] = frozenset(
    {
        DECISION_STATUS_REPRO_VERIFIED,
        DECISION_STATUS_REPRO_FAILED,
        DECISION_STATUS_STABILITY_EVIDENCE,
        DECISION_STATUS_PERTURBATION_EVIDENCE,
        DECISION_STATUS_SIGMA_ZERO_MATCH,
        DECISION_STATUS_SIGMA_ZERO_MISMATCH,
        DECISION_STATUS_PENDING_REVIEW,
    }
)

FORBIDDEN_DECISION_LABELS: frozenset[str] = frozenset(
    {"BEST", "OPTIMAL", "WINNER", "SUPERIOR", "RECOMMENDED", "FINAL"}
)


# ---------------------------------------------------------------------------
# Plan defaults (mirrored from configs/exp05_stability_reproducibility.yaml)
# ---------------------------------------------------------------------------

EXP05_CANONICAL_ALGORITHMS: tuple[str, ...] = (
    "kmeans",
    "agglomerative",
    "dbscan",
    "gmm",
    "fuzzy_cmeans",
)

# Block S only includes the 3 algorithms with a random axis.
EXP05_ALGORITHMS_BLOCK_S: tuple[str, ...] = ("kmeans", "gmm", "fuzzy_cmeans")

EXP05_SEEDS_BLOCK_S: tuple[int, ...] = (42, 7, 123, 2024, 1729)

EXP05_SIGMA_GRID_BLOCK_N: tuple[float, ...] = (0.0, 0.01, 0.05)

EXP05_PERTURBATION_SEEDS_BLOCK_N: tuple[int, ...] = (42, 43, 44)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _library_versions() -> dict[str, str]:
    """Snapshot versions of libraries EXP-05 depends on."""
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


def _safe_float(value: Any) -> float | None:
    """Convert a value to float, returning None for NaN / Inf / None."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def perturb_in_memory(
    X: np.ndarray,
    sigma: float,
    perturbation_seed: int,
    *,
    feature_std: np.ndarray | None = None,
) -> np.ndarray:
    """Apply in-memory Gaussian noise to a numeric matrix.

    The perturbation is::

        noise = rng.normal(loc=0.0, scale=1.0, size=X.shape)
        X_perturbed = X + sigma * noise * feature_std

    where ``feature_std`` is the column-wise standard deviation of
    ``X`` (default: computed from ``X``).

    Parameters
    ----------
    X : numpy.ndarray
        2-D numeric matrix of shape (n_samples, n_features).
    sigma : float
        Scaling factor. ``sigma=0`` returns a copy of ``X``.
    perturbation_seed : int
        Seed for ``numpy.random.default_rng``.
    feature_std : numpy.ndarray, optional
        Column-wise standard deviations. If ``None``, computed from
        ``X`` with ``ddof=0``.

    Returns
    -------
    numpy.ndarray
        New perturbed matrix. ``X`` is NEVER mutated.

    Notes
    -----
    - The output is a fresh copy; the input is NEVER mutated.
    - This function NEVER persists the perturbed matrix to disk.
    - With ``sigma=0`` the output is bit-identical to the input
      (modulo RNG overhead; the noise array is zero-multiplied).
    """
    if sigma < 0.0:
        raise ValueError(f"sigma must be non-negative; got {sigma}.")
    X_arr = np.asarray(X, dtype=np.float64)
    if X_arr.ndim != 2:
        raise ValueError(f"X must be 2-D; got shape {X_arr.shape}.")
    if feature_std is None:
        std = np.std(X_arr, axis=0, ddof=0)
    else:
        std = np.asarray(feature_std, dtype=np.float64)
        if std.shape != (X_arr.shape[1],):
            raise ValueError(f"feature_std must have shape (n_features,); got {std.shape}.")
    if sigma == 0.0:
        # No noise; return a copy to make the API consistent.
        return X_arr.copy()
    rng = np.random.default_rng(seed=perturbation_seed)
    noise = rng.normal(loc=0.0, scale=1.0, size=X_arr.shape)
    return X_arr + sigma * noise * std


def aggregate_variation_stats(values: list[float] | list[int]) -> dict[str, Any]:
    """Compute mean / std / min / max / CV / unique_count over a sequence.

    Parameters
    ----------
    values : list of numeric
        Sequence of metric values across runs.

    Returns
    -------
    dict
        Stats: ``mean``, ``std``, ``min``, ``max``, ``cv``,
        ``unique_count``, ``n`` (length of input).
        ``mean`` and ``std`` are ``None`` when ``values`` is empty.
        ``cv`` is coefficient of variation = std / mean (None when
        mean=0 or when there are fewer than 2 points).
    """
    n = len(values)
    if n == 0:
        return {
            "mean": None,
            "std": None,
            "min": None,
            "max": None,
            "cv": None,
            "unique_count": 0,
            "n": 0,
        }
    arr = np.asarray(values, dtype=np.float64)
    mean = float(np.mean(arr))
    std = float(np.std(arr, ddof=1)) if n > 1 else 0.0
    cv = (std / mean) if (n > 1 and mean != 0.0) else None
    unique_count = len({float(v) for v in values if v is not None})
    return {
        "mean": mean,
        "std": std,
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "cv": cv,
        "unique_count": unique_count,
        "n": n,
    }


# ---------------------------------------------------------------------------
# Per-run dataclasses
# ---------------------------------------------------------------------------


@dataclass
class _BaseRecord:
    """Common fields shared by Block R / S / N records.

    The ``cluster_labels`` field is in-memory only; it is intentionally
    NOT serialised to JSON. It is used by the label-artifact builder
    to construct the parquet output required by EPIC-08.
    """

    run_id: str
    block: str
    algorithm: str
    seed: int
    repeat_index: int

    feature_set: str
    feature_set_sha256: str
    customer_metadata_sha256: str
    config_sha256: str | None

    hyperparameters: dict[str, Any]

    status: str
    failure_reason: str | None

    silhouette: float | None
    silhouette_status: str
    davies_bouldin: float | None
    davies_bouldin_status: str
    calinski_harabasz: float | None
    calinski_harabasz_status: str
    wcss: float | None
    wcss_status: str

    runtime_seconds: float
    labels_hash: str | None
    n_clusters_realized: int | None
    noise_count: int | None
    noise_ratio: float | None
    cluster_sizes: dict[str, int]

    library_versions: dict[str, str]
    platform_info: dict[str, str]

    cluster_labels: np.ndarray | None = field(default=None, repr=False)


@dataclass
class BlockRRecord(_BaseRecord):
    """Per-(algorithm × repeat) Block R record."""

    sigma: float | None = None
    perturbation_seed: int | None = None


@dataclass
class BlockSRecord(_BaseRecord):
    """Per-(algorithm × seed) Block S record."""

    sigma: float | None = None
    perturbation_seed: int | None = None


@dataclass
class BlockNRecord(_BaseRecord):
    """Per-(algorithm × sigma × perturbation_seed) Block N record."""

    sigma: float = 0.0
    perturbation_seed: int | None = None


@dataclass
class LabelArtifactRow:
    """Row schema for ``exp05_cluster_labels.parquet``.

    Required columns (per EXP-05 Plan §7.1):

    - run_id
    - block
    - algorithm
    - seed
    - sigma
    - perturbation_seed
    - repeat_index
    - CustomerID
    - cluster_label
    """

    run_id: str
    block: str
    algorithm: str
    seed: int
    sigma: float | None
    perturbation_seed: int | None
    repeat_index: int
    customer_id: int
    cluster_label: int


# ---------------------------------------------------------------------------
# Aggregate dataclasses
# ---------------------------------------------------------------------------


@dataclass
class BlockRAggregate:
    """Per-algorithm aggregate for Block R."""

    algorithm: str
    n_repeat: int
    n_successful: int
    n_failed: int

    silhouette_stats: dict[str, Any]
    davies_bouldin_stats: dict[str, Any]
    calinski_harabasz_stats: dict[str, Any]
    wcss_stats: dict[str, Any]
    runtime_stats: dict[str, Any]

    labels_hash_unique_count: int
    n_clusters_unique_count: int
    labels_hash_values: list[str]

    decision_status: str
    evidence_note: str


@dataclass
class BlockSAggregate:
    """Per-algorithm aggregate for Block S."""

    algorithm: str
    n_seeds: int
    n_successful: int
    n_failed: int

    silhouette_stats: dict[str, Any]
    davies_bouldin_stats: dict[str, Any]
    calinski_harabasz_stats: dict[str, Any]
    wcss_stats: dict[str, Any]
    runtime_stats: dict[str, Any]

    labels_hash_unique_count: int
    n_clusters_unique_count: int
    labels_hash_values: list[str]
    cluster_size_distributions: list[dict[str, int]]

    decision_status: str
    evidence_note: str


@dataclass
class BlockNAggregate:
    """Per-(algorithm × sigma) aggregate for Block N."""

    algorithm: str
    sigma: float
    n_perturbation_seeds: int
    n_successful: int
    n_failed: int

    silhouette_stats: dict[str, Any]
    davies_bouldin_stats: dict[str, Any]
    calinski_harabasz_stats: dict[str, Any]
    wcss_stats: dict[str, Any]
    runtime_stats: dict[str, Any]

    labels_hash_unique_count: int
    n_clusters_unique_count: int
    labels_hash_values: list[str]

    sigma_zero_baseline_match: bool | None  # True/False for sigma=0; None otherwise
    decision_status: str
    evidence_note: str


# ---------------------------------------------------------------------------
# Top-level result
# ---------------------------------------------------------------------------


@dataclass
class StabilityResult:
    """Container for the EXP-05 sweep."""

    block_r_records: list[BlockRRecord]
    block_s_records: list[BlockSRecord]
    block_n_records: list[BlockNRecord]
    block_r_aggregates: list[BlockRAggregate]
    block_s_aggregates: list[BlockSAggregate]
    block_n_aggregates: list[BlockNAggregate]

    label_artifact_rows: list[LabelArtifactRow]

    feature_set: str
    feature_set_sha256: str
    customer_metadata_sha256: str

    config_sha256: str | None
    exp05_config_sha256: str | None
    library_versions: dict[str, str]
    platform_info: dict[str, str]

    # Block-level parameters (for provenance)
    block_r_seed: int
    block_r_n_repeat: int
    block_s_seeds: tuple[int, ...]
    block_s_n_repeat: int
    block_n_algorithm_seed: int
    block_n_sigma_grid: tuple[float, ...]
    block_n_perturbation_seeds: tuple[int, ...]
    block_n_n_repeat: int

    sigma_zero_baseline_labels_hash: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


class StabilityReproducibilityRunner:
    """Run EXP-05 (Reproducibility / Seed Stability / Perturbation).

    Parameters
    ----------
    framework_cfg : FrameworkConfig
        ML-01 framework configuration (clustering.yaml).
    exp05_config : dict
        Parsed EXP-05 YAML configuration.
    framework_config_text : str, optional
        Raw text of ``configs/clustering.yaml`` for SHA computation.
    exp05_config_text : str, optional
        Raw text of ``configs/exp05_stability_reproducibility.yaml``
        for SHA computation.
    """

    def __init__(
        self,
        framework_cfg: FrameworkConfig,
        exp05_config: dict[str, Any],
        *,
        framework_config_text: str | None = None,
        exp05_config_text: str | None = None,
    ) -> None:
        self.framework_cfg = framework_cfg
        self.exp05_config = exp05_config
        self.framework_config_text = framework_config_text
        self.exp05_config_text = exp05_config_text
        self.framework_config_sha256 = (
            compute_text_sha256(framework_config_text) if framework_config_text else None
        )
        self.exp05_config_sha256 = (
            compute_text_sha256(exp05_config_text) if exp05_config_text else None
        )

    # ----- Public configuration accessors -----

    def block_r_seed(self) -> int:
        """Return seed used for Block R."""
        return int(self.exp05_config.get("exp05", {}).get("block_r", {}).get("seed", 42))

    def block_r_n_repeat(self) -> int:
        """Return n_repeat for Block R."""
        return int(self.exp05_config.get("exp05", {}).get("block_r", {}).get("n_repeat", 5))

    def block_s_seeds(self) -> tuple[int, ...]:
        """Return seeds for Block S."""
        seeds = self.exp05_config.get("exp05", {}).get("block_s", {}).get("seeds", [])
        if not seeds:
            return EXP05_SEEDS_BLOCK_S
        return tuple(int(s) for s in seeds)

    def block_s_n_repeat(self) -> int:
        """Return n_repeat per seed in Block S."""
        return int(self.exp05_config.get("exp05", {}).get("block_s", {}).get("n_repeat", 1))

    def block_n_algorithm_seed(self) -> int:
        """Return seed for the algorithm in Block N."""
        return int(self.exp05_config.get("exp05", {}).get("block_n", {}).get("algorithm_seed", 42))

    def block_n_sigma_grid(self) -> tuple[float, ...]:
        """Return sigma grid for Block N."""
        grid = (
            self.exp05_config.get("exp05", {})
            .get("block_n", {})
            .get("sigma_grid", list(EXP05_SIGMA_GRID_BLOCK_N))
        )
        return tuple(float(s) for s in grid)

    def block_n_perturbation_seeds(self) -> tuple[int, ...]:
        """Return perturbation seeds for Block N."""
        seeds = (
            self.exp05_config.get("exp05", {})
            .get("block_n", {})
            .get("nonzero_perturbation_seeds", list(EXP05_PERTURBATION_SEEDS_BLOCK_N))
        )
        return tuple(int(s) for s in seeds)

    def working_defaults(self) -> dict[str, dict[str, Any]]:
        """Return per-algorithm hyperparameters from EXP-05 YAML."""
        return dict(self.exp05_config.get("exp05", {}).get("working_defaults", {}))

    def feature_set_name(self) -> str:
        """Return feature set name (default: rfm_extended)."""
        return str(
            self.exp05_config.get("exp05", {}).get("dataset", {}).get("version", "FE06-v1.0")
        )

    # ----- Main entry point -----

    def run(
        self,
        matrix_df: pd.DataFrame,
        customer_metadata_df: pd.DataFrame | None,
        *,
        input_sha256: str,
        metadata_sha256: str,
    ) -> StabilityResult:
        """Run all three EXP-05 blocks.

        Parameters
        ----------
        matrix_df : pandas.DataFrame
            FE-06 final clustering matrix. NEVER mutated.
        customer_metadata_df : pandas.DataFrame, optional
            Customer metadata carrying ``CustomerID``.
        input_sha256 : str
            SHA-256 of the source FE-06 file.
        metadata_sha256 : str
            SHA-256 of the customer metadata file.

        Returns
        -------
        StabilityResult
            Aggregated EXP-05 result with all per-run records and
            aggregates, plus the label-artifact rows.
        """
        X = matrix_df.to_numpy(dtype=np.float64, copy=False)

        # Block R
        block_r_records = self._run_block_r(
            X=X,
            matrix_df=matrix_df,
            customer_metadata_df=customer_metadata_df,
            input_sha256=input_sha256,
            metadata_sha256=metadata_sha256,
        )

        # Block S
        block_s_records = self._run_block_s(
            X=X,
            matrix_df=matrix_df,
            customer_metadata_df=customer_metadata_df,
            input_sha256=input_sha256,
            metadata_sha256=metadata_sha256,
        )

        # Block N (in-memory perturbation; FE-06 SHA must not change)
        block_n_records, sigma_zero_labels = self._run_block_n(
            X=X,
            matrix_df=matrix_df,
            customer_metadata_df=customer_metadata_df,
            input_sha256=input_sha256,
            metadata_sha256=metadata_sha256,
        )

        # Build aggregates (per-algorithm for R/S, per-(algorithm × sigma) for N)
        block_r_aggregates = self._aggregate_records_block_r(block_r_records)
        block_s_aggregates = self._aggregate_records_block_s(block_s_records)
        block_n_aggregates = self._aggregate_records_block_n(block_n_records, sigma_zero_labels)

        # Build label artifact rows
        label_artifact_rows = self._collect_label_artifact_rows(
            block_r_records=block_r_records,
            block_s_records=block_s_records,
            block_n_records=block_n_records,
            customer_metadata_df=customer_metadata_df,
        )

        return StabilityResult(
            block_r_records=block_r_records,
            block_s_records=block_s_records,
            block_n_records=block_n_records,
            block_r_aggregates=block_r_aggregates,
            block_s_aggregates=block_s_aggregates,
            block_n_aggregates=block_n_aggregates,
            label_artifact_rows=label_artifact_rows,
            feature_set=self.feature_set_name(),
            feature_set_sha256=input_sha256,
            customer_metadata_sha256=metadata_sha256,
            config_sha256=self.framework_config_sha256,
            exp05_config_sha256=self.exp05_config_sha256,
            library_versions=_library_versions(),
            platform_info=_platform_info(),
            block_r_seed=self.block_r_seed(),
            block_r_n_repeat=self.block_r_n_repeat(),
            block_s_seeds=self.block_s_seeds(),
            block_s_n_repeat=self.block_s_n_repeat(),
            block_n_algorithm_seed=self.block_n_algorithm_seed(),
            block_n_sigma_grid=self.block_n_sigma_grid(),
            block_n_perturbation_seeds=self.block_n_perturbation_seeds(),
            block_n_n_repeat=1,
            sigma_zero_baseline_labels_hash=sigma_zero_labels,
        )

    # ----- Block runners -----

    def _run_block_r(
        self,
        *,
        X: np.ndarray,
        matrix_df: pd.DataFrame,
        customer_metadata_df: pd.DataFrame | None,
        input_sha256: str,
        metadata_sha256: str,
    ) -> list[BlockRRecord]:
        """Block R — Reproducibility."""
        records: list[BlockRRecord] = []
        seed = self.block_r_seed()
        n_repeat = self.block_r_n_repeat()
        library_versions = _library_versions()
        platform_info = _platform_info()
        feature_set = self.feature_set_name()
        for algorithm in EXP05_CANONICAL_ALGORITHMS:
            base_hp = self._resolved_hyperparameters(algorithm)
            for repeat_index in range(n_repeat):
                record = self._run_single(
                    block=BLOCK_R,
                    algorithm=algorithm,
                    seed=seed,
                    sigma=None,
                    perturbation_seed=None,
                    repeat_index=repeat_index,
                    matrix_df=matrix_df,
                    X_override=X,
                    customer_metadata_df=customer_metadata_df,
                    input_sha256=input_sha256,
                    metadata_sha256=metadata_sha256,
                    hyperparameters=base_hp,
                    library_versions=library_versions,
                    platform_info=platform_info,
                    feature_set=feature_set,
                )
                records.append(record)  # type: ignore[arg-type]
        return records

    def _run_block_s(
        self,
        *,
        X: np.ndarray,
        matrix_df: pd.DataFrame,
        customer_metadata_df: pd.DataFrame | None,
        input_sha256: str,
        metadata_sha256: str,
    ) -> list[BlockSRecord]:
        """Block S — Random Seed Stability."""
        records: list[BlockSRecord] = []
        seeds = self.block_s_seeds()
        n_repeat = self.block_s_n_repeat()
        library_versions = _library_versions()
        platform_info = _platform_info()
        feature_set = self.feature_set_name()
        for algorithm in EXP05_ALGORITHMS_BLOCK_S:
            base_hp = self._resolved_hyperparameters(algorithm)
            for seed in seeds:
                for repeat_index in range(n_repeat):
                    record = self._run_single(
                        block=BLOCK_S,
                        algorithm=algorithm,
                        seed=seed,
                        sigma=None,
                        perturbation_seed=None,
                        repeat_index=repeat_index,
                        matrix_df=matrix_df,
                        X_override=X,
                        customer_metadata_df=customer_metadata_df,
                        input_sha256=input_sha256,
                        metadata_sha256=metadata_sha256,
                        hyperparameters=base_hp,
                        library_versions=library_versions,
                        platform_info=platform_info,
                        feature_set=feature_set,
                    )
                    records.append(record)  # type: ignore[arg-type]
        return records

    def _run_block_n(
        self,
        *,
        X: np.ndarray,
        matrix_df: pd.DataFrame,
        customer_metadata_df: pd.DataFrame | None,
        input_sha256: str,
        metadata_sha256: str,
    ) -> tuple[list[BlockNRecord], dict[str, str]]:
        """Block N — Feature Perturbation.

        Returns the list of records plus a mapping
        ``algorithm -> labels_hash`` of the sigma=0 baseline (for
        downstream comparison). The perturbed matrix is NEVER
        persisted to disk.
        """
        records: list[BlockNRecord] = []
        sigma_zero_labels: dict[str, str] = {}
        algo_seed = self.block_n_algorithm_seed()
        sigma_grid = self.block_n_sigma_grid()
        pert_seeds = self.block_n_perturbation_seeds()
        library_versions = _library_versions()
        platform_info = _platform_info()
        feature_set = self.feature_set_name()

        for algorithm in EXP05_CANONICAL_ALGORITHMS:
            base_hp = self._resolved_hyperparameters(algorithm)
            for sigma in sigma_grid:
                if sigma == 0.0:
                    # Sanity run: only 1 run.
                    record = self._run_single(
                        block=BLOCK_N,
                        algorithm=algorithm,
                        seed=algo_seed,
                        sigma=0.0,
                        perturbation_seed=None,
                        repeat_index=0,
                        matrix_df=matrix_df,
                        X_override=X,
                        customer_metadata_df=customer_metadata_df,
                        input_sha256=input_sha256,
                        metadata_sha256=metadata_sha256,
                        hyperparameters=base_hp,
                        library_versions=library_versions,
                        platform_info=platform_info,
                        feature_set=feature_set,
                    )
                    records.append(record)  # type: ignore[arg-type]
                    if record.labels_hash is not None:
                        sigma_zero_labels[algorithm] = record.labels_hash
                else:
                    for pert_seed in pert_seeds:
                        X_perturbed = perturb_in_memory(X, sigma=sigma, perturbation_seed=pert_seed)
                        # In-memory perturbation only. The perturbed
                        # matrix is NEVER written to data/processed/ or
                        # any other on-disk location.
                        perturbed_df = pd.DataFrame(
                            X_perturbed,
                            columns=list(matrix_df.columns),
                            copy=False,
                        )
                        record = self._run_single(
                            block=BLOCK_N,
                            algorithm=algorithm,
                            seed=algo_seed,
                            sigma=sigma,
                            perturbation_seed=pert_seed,
                            repeat_index=0,
                            matrix_df=perturbed_df,
                            X_override=X_perturbed,
                            customer_metadata_df=customer_metadata_df,
                            input_sha256=input_sha256,
                            metadata_sha256=metadata_sha256,
                            hyperparameters=base_hp,
                            library_versions=library_versions,
                            platform_info=platform_info,
                            feature_set=feature_set,
                        )
                        records.append(record)  # type: ignore[arg-type]

        return records, sigma_zero_labels

    # ----- Single-run helper -----

    def _run_single(
        self,
        *,
        block: str,
        algorithm: str,
        seed: int,
        sigma: float | None,
        perturbation_seed: int | None,
        repeat_index: int,
        matrix_df: pd.DataFrame,
        X_override: np.ndarray | None,
        customer_metadata_df: pd.DataFrame | None,
        input_sha256: str,
        metadata_sha256: str,
        hyperparameters: dict[str, Any],
        library_versions: dict[str, str],
        platform_info: dict[str, str],
        feature_set: str,
    ) -> BlockRRecord | BlockSRecord | BlockNRecord:
        """Run a single clustering experiment and wrap it as a record."""
        run_id = self._make_run_id(
            block=block,
            algorithm=algorithm,
            seed=seed,
            sigma=sigma,
            perturbation_seed=perturbation_seed,
            repeat_index=repeat_index,
        )

        hp = dict(hyperparameters)
        # Inject seed for algorithms that consume it.
        hp = self._inject_seed(hp, algorithm, seed)

        exp_spec = ExperimentSpec(
            experiment_id=run_id,
            algorithm=algorithm,
            hyperparameters=hp,
            seed_override=seed,
        )
        runner = ExperimentRunner(
            self.framework_cfg,
            exp_spec,
            config_source=None,
            config_text=self.framework_config_text,
        )

        try:
            result = runner.run(
                matrix_df,
                customer_metadata_df,
                input_sha256=input_sha256,
                input_path=None,
                metadata_path=None,
                output_dir=None,
            )
        except Exception as exc:  # noqa: BLE001
            return self._make_failed_record(
                cls=self._record_class(block),
                run_id=run_id,
                block=block,
                algorithm=algorithm,
                seed=seed,
                repeat_index=repeat_index,
                feature_set=feature_set,
                feature_set_sha256=input_sha256,
                customer_metadata_sha256=metadata_sha256,
                config_sha256=self.framework_config_sha256,
                hyperparameters=hp,
                sigma=sigma,
                perturbation_seed=perturbation_seed,
                failure_reason=f"{type(exc).__name__}: {exc}",
                library_versions=library_versions,
                platform_info=platform_info,
            )

        if (
            result.status != "SUCCESS"
            or result.cluster_result is None
            or result.cluster_result.cluster_labels is None
        ):
            return self._make_failed_record(
                cls=self._record_class(block),
                run_id=run_id,
                block=block,
                algorithm=algorithm,
                seed=seed,
                repeat_index=repeat_index,
                feature_set=feature_set,
                feature_set_sha256=input_sha256,
                customer_metadata_sha256=metadata_sha256,
                config_sha256=self.framework_config_sha256,
                hyperparameters=hp,
                sigma=sigma,
                perturbation_seed=perturbation_seed,
                failure_reason=((result.error or {}).get("message") if result.error else "unknown"),
                library_versions=library_versions,
                platform_info=platform_info,
            )

        cluster_result = result.cluster_result
        labels = cluster_result.cluster_labels

        # Compute metrics via the EXP-01 metrics layer.
        X_for_metrics = (
            X_override
            if X_override is not None
            else matrix_df.to_numpy(dtype=np.float64, copy=False)
        )
        cluster_result = attach_metrics_with_status(
            cluster_result,
            X_for_metrics,
            exclude_noise=True,
            noise_label=-1,
            runtime_stats=compute_runtime_stats([float(result.execution_time)]),
        )
        metrics = cluster_result.metrics
        extra = metrics.extra
        labels_hash = compute_labels_hash(labels)

        # Cluster sizes (from labels)
        cluster_sizes = self._cluster_sizes(labels, noise_label=-1)

        return self._record_class(block)(
            run_id=run_id,
            block=block,
            algorithm=algorithm,
            seed=int(seed),
            repeat_index=int(repeat_index),
            feature_set=feature_set,
            feature_set_sha256=input_sha256,
            customer_metadata_sha256=metadata_sha256,
            config_sha256=self.framework_config_sha256,
            hyperparameters=hp,
            status="SUCCESS",
            failure_reason=None,
            silhouette=_safe_float(metrics.silhouette),
            silhouette_status=extra.get("silhouette_status", "MISSING"),
            davies_bouldin=_safe_float(metrics.davies_bouldin),
            davies_bouldin_status=extra.get("davies_bouldin_status", "MISSING"),
            calinski_harabasz=_safe_float(metrics.calinski_harabasz),
            calinski_harabasz_status=extra.get("calinski_harabasz_status", "MISSING"),
            wcss=_safe_float(metrics.wcss),
            wcss_status=extra.get("wcss_status", "MISSING"),
            runtime_seconds=float(result.execution_time),
            labels_hash=labels_hash,
            n_clusters_realized=(
                int(cluster_result.n_clusters) if cluster_result.n_clusters is not None else None
            ),
            noise_count=(
                int(cluster_result.noise_count) if cluster_result.noise_count is not None else None
            ),
            noise_ratio=(
                float(cluster_result.noise_ratio)
                if cluster_result.noise_ratio is not None
                else None
            ),
            cluster_sizes=cluster_sizes,
            library_versions=library_versions,
            platform_info=platform_info,
            cluster_labels=labels,
            sigma=sigma,
            perturbation_seed=perturbation_seed,
        )

    @staticmethod
    def _record_class(block: str):
        """Return the dataclass for a given block."""
        if block == BLOCK_R:
            return BlockRRecord
        if block == BLOCK_S:
            return BlockSRecord
        if block == BLOCK_N:
            return BlockNRecord
        raise ValueError(f"Unknown block: {block!r}.")

    def _make_failed_record(
        self,
        *,
        cls,
        run_id: str,
        block: str,
        algorithm: str,
        seed: int,
        repeat_index: int,
        feature_set: str,
        feature_set_sha256: str,
        customer_metadata_sha256: str,
        config_sha256: str | None,
        hyperparameters: dict[str, Any],
        sigma: float | None,
        perturbation_seed: int | None,
        failure_reason: str,
        library_versions: dict[str, str],
        platform_info: dict[str, str],
    ):
        """Build a FAILED record (status != SUCCESS)."""
        return cls(
            run_id=run_id,
            block=block,
            algorithm=algorithm,
            seed=int(seed),
            repeat_index=int(repeat_index),
            feature_set=feature_set,
            feature_set_sha256=feature_set_sha256,
            customer_metadata_sha256=customer_metadata_sha256,
            config_sha256=config_sha256,
            hyperparameters=hyperparameters,
            status="FAILED",
            failure_reason=failure_reason,
            silhouette=None,
            silhouette_status="MISSING",
            davies_bouldin=None,
            davies_bouldin_status="MISSING",
            calinski_harabasz=None,
            calinski_harabasz_status="MISSING",
            wcss=None,
            wcss_status="MISSING",
            runtime_seconds=0.0,
            labels_hash=None,
            n_clusters_realized=None,
            noise_count=None,
            noise_ratio=None,
            cluster_sizes={},
            library_versions=library_versions,
            platform_info=platform_info,
            cluster_labels=None,
            sigma=sigma,
            perturbation_seed=perturbation_seed,
        )

    # ----- Hyperparameter resolution -----

    def _resolved_hyperparameters(self, algorithm: str) -> dict[str, Any]:
        """Return the canonical hyperparameters for an algorithm."""
        hp = self.working_defaults().get(algorithm, {})
        if not hp:
            raise ValueError(f"EXP-05 working_defaults missing for algorithm {algorithm!r}.")
        return dict(hp)

    @staticmethod
    def _inject_seed(hp: dict[str, Any], algorithm: str, seed: int) -> dict[str, Any]:
        """Inject random_state / seed into hyperparameters if supported."""
        if algorithm in ("kmeans", "gmm", "fuzzy_cmeans"):
            hp["random_state"] = int(seed)
        return hp

    @staticmethod
    def _make_run_id(
        *,
        block: str,
        algorithm: str,
        seed: int,
        sigma: float | None,
        perturbation_seed: int | None,
        repeat_index: int,
    ) -> str:
        """Build a deterministic run_id string."""
        if block == BLOCK_R:
            return f"EXP05-R-{algorithm}-seed{seed}-r{repeat_index:02d}"
        if block == BLOCK_S:
            return f"EXP05-S-{algorithm}-seed{seed}-r{repeat_index:02d}"
        if block == BLOCK_N:
            sigma_str = f"{sigma:.4f}".rstrip("0").rstrip(".") if sigma is not None else "0"
            sigma_str = sigma_str or "0"
            if sigma == 0.0 or sigma is None:
                return f"EXP05-N-{algorithm}-sigma{sigma_str}-sanity"
            return (
                f"EXP05-N-{algorithm}-sigma{sigma_str}-pseed{perturbation_seed}-r{repeat_index:02d}"
            )
        raise ValueError(f"Unknown block: {block!r}.")

    @staticmethod
    def _cluster_sizes(labels: np.ndarray, *, noise_label: int = -1) -> dict[str, int]:
        """Return per-cluster customer counts as a JSON-friendly dict."""
        counts: dict[str, int] = {}
        for label, count in zip(*np.unique(labels, return_counts=True), strict=False):
            key = "noise" if int(label) == noise_label else str(int(label))
            counts[key] = int(count)
        return counts

    # ----- Aggregators -----

    def _aggregate_records_block_r(self, records: list[BlockRRecord]) -> list[BlockRAggregate]:
        """Build Block R aggregates (one per algorithm)."""
        grouped: dict[str, list[BlockRRecord]] = {}
        order: list[str] = []
        for r in records:
            if r.algorithm not in grouped:
                grouped[r.algorithm] = []
                order.append(r.algorithm)
            grouped[r.algorithm].append(r)
        return [self._aggregate_block_r(grouped[algo]) for algo in order]

    def _aggregate_records_block_s(self, records: list[BlockSRecord]) -> list[BlockSAggregate]:
        """Build Block S aggregates (one per algorithm)."""
        grouped: dict[str, list[BlockSRecord]] = {}
        order: list[str] = []
        for r in records:
            if r.algorithm not in grouped:
                grouped[r.algorithm] = []
                order.append(r.algorithm)
            grouped[r.algorithm].append(r)
        return [self._aggregate_block_s(grouped[algo]) for algo in order]

    def _aggregate_records_block_n(
        self,
        records: list[BlockNRecord],
        sigma_zero_labels: dict[str, str],
    ) -> list[BlockNAggregate]:
        """Build Block N aggregates (one per (algorithm × sigma))."""
        grouped: dict[tuple[str, float], list[BlockNRecord]] = {}
        order: list[tuple[str, float]] = []
        for r in records:
            key = (r.algorithm, float(r.sigma))
            if key not in grouped:
                grouped[key] = []
                order.append(key)
            grouped[key].append(r)
        return [self._aggregate_block_n(grouped[key], sigma_zero_labels) for key in order]

    def _aggregate_block_r(self, records: list[BlockRRecord]) -> BlockRAggregate:
        """Aggregate Block R per-algorithm."""
        successful = [r for r in records if r.status == "SUCCESS"]
        failed = [r for r in records if r.status != "SUCCESS"]
        sil_values = [r.silhouette for r in successful if r.silhouette is not None]
        dbi_values = [r.davies_bouldin for r in successful if r.davies_bouldin is not None]
        ch_values = [r.calinski_harabasz for r in successful if r.calinski_harabasz is not None]
        wcss_values = [r.wcss for r in successful if r.wcss is not None]
        runtimes = [float(r.runtime_seconds) for r in successful]
        labels_hashes = [r.labels_hash for r in successful if r.labels_hash is not None]
        n_clusters_values = [
            r.n_clusters_realized for r in successful if r.n_clusters_realized is not None
        ]

        runtime_stats = compute_runtime_stats(runtimes)

        labels_hash_unique_count = len(set(labels_hashes))
        n_clusters_unique_count = len(set(n_clusters_values))
        deterministic_metrics = (
            len(set(sil_values)) <= 1
            and len(set(dbi_values)) <= 1
            and len(set(ch_values)) <= 1
            and len(set(wcss_values)) <= 1
        )
        if not successful:
            decision_status = DECISION_STATUS_PENDING_REVIEW
            note = "All Block R repeats failed."
        elif labels_hash_unique_count == 1 and deterministic_metrics:
            decision_status = DECISION_STATUS_REPRO_VERIFIED
            note = (
                "labels_hash and metric values are identical across all "
                "n_repeat runs; REPRODUCIBILITY_VERIFIED."
            )
        else:
            decision_status = DECISION_STATUS_REPRO_FAILED
            parts: list[str] = []
            if labels_hash_unique_count > 1:
                parts.append(
                    f"labels_hash varied across {labels_hash_unique_count} distinct values"
                )
            if len(set(sil_values)) > 1:
                parts.append("silhouette varied across repeats")
            if len(set(dbi_values)) > 1:
                parts.append("DBI varied across repeats")
            if len(set(ch_values)) > 1:
                parts.append("CH varied across repeats")
            if len(set(wcss_values)) > 1:
                parts.append("WCSS varied across repeats")
            note = "REPRODUCIBILITY_FAILED: " + "; ".join(parts) + "."

        return BlockRAggregate(
            algorithm=records[0].algorithm if records else "",
            n_repeat=len(records),
            n_successful=len(successful),
            n_failed=len(failed),
            silhouette_stats=aggregate_variation_stats(sil_values),
            davies_bouldin_stats=aggregate_variation_stats(dbi_values),
            calinski_harabasz_stats=aggregate_variation_stats(ch_values),
            wcss_stats=aggregate_variation_stats(wcss_values),
            runtime_stats=runtime_stats,
            labels_hash_unique_count=labels_hash_unique_count,
            n_clusters_unique_count=n_clusters_unique_count,
            labels_hash_values=labels_hashes,
            decision_status=decision_status,
            evidence_note=note,
        )

    def _aggregate_block_s(self, records: list[BlockSRecord]) -> BlockSAggregate:
        """Aggregate Block S per-algorithm."""
        successful = [r for r in records if r.status == "SUCCESS"]
        failed = [r for r in records if r.status != "SUCCESS"]
        sil_values = [r.silhouette for r in successful if r.silhouette is not None]
        dbi_values = [r.davies_bouldin for r in successful if r.davies_bouldin is not None]
        ch_values = [r.calinski_harabasz for r in successful if r.calinski_harabasz is not None]
        wcss_values = [r.wcss for r in successful if r.wcss is not None]
        runtimes = [float(r.runtime_seconds) for r in successful]
        labels_hashes = [r.labels_hash for r in successful if r.labels_hash is not None]
        n_clusters_values = [
            r.n_clusters_realized for r in successful if r.n_clusters_realized is not None
        ]
        cluster_size_distributions = [r.cluster_sizes for r in successful]

        runtime_stats = compute_runtime_stats(runtimes)
        labels_hash_unique_count = len(set(labels_hashes))
        n_clusters_unique_count = len(set(n_clusters_values))

        if successful:
            decision_status = DECISION_STATUS_STABILITY_EVIDENCE
            note = (
                f"STABILITY_EVIDENCE_GENERATED across {len(successful)} seeds; "
                f"labels_hash_unique_count={labels_hash_unique_count}; "
                "evidence passed to EPIC-08 for ARI/AMI analysis. NOT stability analysis."
            )
        else:
            decision_status = DECISION_STATUS_PENDING_REVIEW
            note = "All Block S seeds failed."

        return BlockSAggregate(
            algorithm=records[0].algorithm if records else "",
            n_seeds=len(records),
            n_successful=len(successful),
            n_failed=len(failed),
            silhouette_stats=aggregate_variation_stats(sil_values),
            davies_bouldin_stats=aggregate_variation_stats(dbi_values),
            calinski_harabasz_stats=aggregate_variation_stats(ch_values),
            wcss_stats=aggregate_variation_stats(wcss_values),
            runtime_stats=runtime_stats,
            labels_hash_unique_count=labels_hash_unique_count,
            n_clusters_unique_count=n_clusters_unique_count,
            labels_hash_values=labels_hashes,
            cluster_size_distributions=cluster_size_distributions,
            decision_status=decision_status,
            evidence_note=note,
        )

    def _aggregate_block_n(
        self,
        records: list[BlockNRecord],
        sigma_zero_labels: dict[str, str],
    ) -> BlockNAggregate:
        """Aggregate Block N per-(algorithm × sigma)."""
        if not records:
            raise ValueError("Block N: no records to aggregate.")
        successful = [r for r in records if r.status == "SUCCESS"]
        failed = [r for r in records if r.status != "SUCCESS"]
        sil_values = [r.silhouette for r in successful if r.silhouette is not None]
        dbi_values = [r.davies_bouldin for r in successful if r.davies_bouldin is not None]
        ch_values = [r.calinski_harabasz for r in successful if r.calinski_harabasz is not None]
        wcss_values = [r.wcss for r in successful if r.wcss is not None]
        runtimes = [float(r.runtime_seconds) for r in successful]
        labels_hashes = [r.labels_hash for r in successful if r.labels_hash is not None]
        n_clusters_values = [
            r.n_clusters_realized for r in successful if r.n_clusters_realized is not None
        ]
        runtime_stats = compute_runtime_stats(runtimes)

        sigma = records[0].sigma
        algorithm = records[0].algorithm
        baseline_labels_hash = sigma_zero_labels.get(algorithm)

        if sigma == 0.0:
            # Sanity run.
            if (
                successful
                and baseline_labels_hash is not None
                and successful[0].labels_hash is not None
            ):
                sigma_zero_match = successful[0].labels_hash == baseline_labels_hash
            else:
                sigma_zero_match = None
            if sigma_zero_match is True:
                decision_status = DECISION_STATUS_SIGMA_ZERO_MATCH
                note = (
                    "sigma=0 sanity run reproduces baseline labels_hash "
                    "(perturbation pipeline correctly wired)."
                )
            elif sigma_zero_match is False:
                decision_status = DECISION_STATUS_SIGMA_ZERO_MISMATCH
                note = (
                    "sigma=0 sanity run produced labels_hash that DIFFERS "
                    "from baseline; perturbation pipeline may not be wired correctly."
                )
            else:
                decision_status = DECISION_STATUS_PENDING_REVIEW
                note = "sigma=0 sanity run FAILED; cannot compare to baseline."
        else:
            sigma_zero_match = None  # only defined for sigma=0
            if successful:
                decision_status = DECISION_STATUS_PERTURBATION_EVIDENCE
                note = (
                    f"PERTURBATION_EVIDENCE_GENERATED at sigma={sigma} across "
                    f"{len(successful)} perturbation seeds; "
                    "evidence passed to EPIC-08 for analysis. "
                    "Labels may or may not change under perturbation; that is "
                    "an empirical observation, NOT a pre-specified expectation."
                )
            else:
                decision_status = DECISION_STATUS_PENDING_REVIEW
                note = f"All Block N perturbation runs at sigma={sigma} failed."

        return BlockNAggregate(
            algorithm=algorithm,
            sigma=float(sigma),
            n_perturbation_seeds=len(records),
            n_successful=len(successful),
            n_failed=len(failed),
            silhouette_stats=aggregate_variation_stats(sil_values),
            davies_bouldin_stats=aggregate_variation_stats(dbi_values),
            calinski_harabasz_stats=aggregate_variation_stats(ch_values),
            wcss_stats=aggregate_variation_stats(wcss_values),
            runtime_stats=runtime_stats,
            labels_hash_unique_count=len(set(labels_hashes)),
            n_clusters_unique_count=len(set(n_clusters_values)),
            labels_hash_values=labels_hashes,
            sigma_zero_baseline_match=sigma_zero_match,
            decision_status=decision_status,
            evidence_note=note,
        )

    # ----- Label artifact collection -----

    def _collect_label_artifact_rows(
        self,
        *,
        block_r_records: list[BlockRRecord],
        block_s_records: list[BlockSRecord],
        block_n_records: list[BlockNRecord],
        customer_metadata_df: pd.DataFrame | None,
    ) -> list[LabelArtifactRow]:
        """Build the label-artifact rows for the parquet output.

        For each successful record, this expands the cluster_labels
        vector into one row per CustomerID. CustomerID comes from
        ``customer_metadata_df`` (FE-06 metadata). If the metadata
        is missing or lacks CustomerID, this raises.
        """
        customer_key = self.framework_cfg.input.customer_key
        if customer_metadata_df is None or customer_key not in customer_metadata_df.columns:
            raise ValueError(
                "Cannot build label artifact without CustomerID metadata; "
                f"EXP-05 requires customer_metadata.parquet with a {customer_key!r} column."
            )
        customer_ids = customer_metadata_df[customer_key].to_numpy()

        rows: list[LabelArtifactRow] = []
        for records in (block_r_records, block_s_records, block_n_records):
            for record in records:
                if record.status != "SUCCESS" or record.cluster_labels is None:
                    continue
                labels = record.cluster_labels
                if len(labels) != len(customer_ids):
                    raise ValueError(
                        f"CustomerID/label length mismatch for run {record.run_id}: "
                        f"{len(customer_ids)} customers vs {len(labels)} labels."
                    )
                for cid, label in zip(customer_ids, labels, strict=True):
                    rows.append(
                        LabelArtifactRow(
                            run_id=record.run_id,
                            block=record.block,
                            algorithm=record.algorithm,
                            seed=int(record.seed),
                            sigma=(float(record.sigma) if record.sigma is not None else None),
                            perturbation_seed=(
                                int(record.perturbation_seed)
                                if record.perturbation_seed is not None
                                else None
                            ),
                            repeat_index=int(record.repeat_index),
                            customer_id=int(cid),
                            cluster_label=int(label),
                        )
                    )
        return rows
