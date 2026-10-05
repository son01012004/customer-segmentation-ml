"""Unified result schema for the ML-01 experiment framework.

Why a unified schema
--------------------
Different clustering algorithm families produce different kinds of
output:

- **Hard clustering** (K-Means, K-Medoids, Agglomerative):
  ``labels_`` is a 1-D array of integer cluster IDs in ``[0, k-1]``.

- **Density-based clustering** (DBSCAN):
  ``labels_`` contains integer cluster IDs **and** a dedicated
  noise label (``-1`` by sklearn convention). We must preserve the
  noise label exactly.

- **Model-based clustering** (GMM):
  in addition to ``labels_``, ``predict_proba_`` returns posterior
  probabilities of shape ``(n_samples, n_components)``.

- **Fuzzy clustering** (Fuzzy C-Means):
  exposes a *membership* matrix of shape ``(n_samples, c)`` whose
  rows sum to 1. A hard label can be derived as ``argmax`` of the
  membership, but the membership itself is the primary output.

The unified schema MUST therefore support all four without losing
information. The design below uses **optional fields** that are
populated only by the algorithm families that need them.

The schema is **value-neutral**: it carries no "best" claim and no
research interpretation. Metrics (``silhouette``, ``davies_bouldin``,
``calinski_harabasz``) are *placeholders* in ML-01 — they exist so
downstream evaluation (EPIC-07/08) has a structured place to record
values, but ML-01 itself does NOT compute them.

Hard constraints (AGENTS.md §2, §3 "Clustering"):

- No "best/recommended/optimal/winner" language.
- ML-01 does NOT compute evaluation metrics. The :class:`MetricsResult`
  is a container that the framework serialises but does not populate.
- All randomness is recorded (``random_seed``, ``random_seed_used``,
  ``supports_random_state``) so the experiment is reproducible in the
  sense that a future reader can see exactly what was tried.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

import numpy as np

__all__ = [
    "AlgorithmFamily",
    "ClusterResult",
    "MetricsResult",
    "ExperimentStatus",
    "ExperimentResult",
    "ClusterResultEncoder",
    "cluster_result_to_dict",
]


# ---------------------------------------------------------------------------
# Algorithm family enum
# ---------------------------------------------------------------------------


class AlgorithmFamily(StrEnum):
    """Clustering algorithm family — used to populate result metadata.

    Values match the methodology's fixed benchmark set where applicable.
    """

    HARD = "hard"  # K-Means, K-Medoids, Agglomerative
    DENSITY_BASED = "density_based"  # DBSCAN
    MODEL_BASED = "model_based"  # GMM
    FUZZY = "fuzzy"  # Fuzzy C-Means
    OTHER = "other"  # Reserved for future algorithm families


# ---------------------------------------------------------------------------
# Metrics placeholder (EPIC-07/08 will populate, ML-01 never computes)
# ---------------------------------------------------------------------------


@dataclass
class MetricsResult:
    """Container for evaluation metrics.

    ML-01 leaves all fields ``None``. Downstream evaluation stages
    (EPIC-07/08) will populate the appropriate fields. The presence of
    this container in :class:`ClusterResult` makes the schema
    forward-compatible without ML-01 having to compute anything.

    Attributes
    ----------
    silhouette : float or None
        Silhouette score (sklearn convention: ``[-1, 1]``).
        ``None`` means ML-01 did not compute it; downstream evaluation
        may set it later. ``NaN`` means downstream tried and the metric
        was undefined (e.g. all-noise DBSCAN, single cluster).
    davies_bouldin : float or None
        Davies-Bouldin index. ``None`` if not computed; ``NaN`` if
        undefined.
    calinski_harabasz : float or None
        Calinski-Harabasz index. ``None`` if not computed; ``NaN`` if
        undefined.
    wcss : float or None
        Within-cluster sum of squares (K-Means ``inertia_``). ``None``
        if not computed or not applicable to the algorithm family.
    stability : dict or None
        Placeholder for stability metrics (ARI, AMI, ...) computed in
        EPIC-08. ``None`` means not yet computed.
    runtime : dict or None
        Placeholder for runtime metrics (mean, std, min, max). ML-01
        already records ``execution_time`` as a top-level field; this
        is the place for richer statistics computed by EPIC-08.
    extra : dict
        Escape hatch for algorithm-specific metrics that do not fit
        the standard slots.
    """

    silhouette: float | None = None
    davies_bouldin: float | None = None
    calinski_harabasz: float | None = None
    wcss: float | None = None
    stability: dict[str, Any] | None = None
    runtime: dict[str, Any] | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-friendly dict.

        ``None`` fields are kept (not dropped) so the schema is stable
        across runs.
        """
        return asdict(self)


# ---------------------------------------------------------------------------
# Cluster result (per-algorithm)
# ---------------------------------------------------------------------------


@dataclass
class ClusterResult:
    """Result of fitting a single clustering algorithm.

    The schema supports all four algorithm families through optional
    fields. Subclasses / concrete adapters are responsible for
    populating only the fields that apply.

    Attributes
    ----------
    algorithm : str
        Algorithm name (must match the registered name in
        :class:`AlgorithmRegistry`).
    algorithm_version : str
        Implementation / library version string (e.g. ``"sklearn_1.5"``).
    algorithm_family : str
        Value of :class:`AlgorithmFamily` as a string.

    n_samples : int
        Number of samples the algorithm was fit on.
    n_features : int
        Number of features in the input matrix.

    cluster_labels : numpy.ndarray
        Integer cluster labels of shape ``(n_samples,)``. Convention:

        - Hard clustering: ``labels in [0, k-1]``.
        - DBSCAN: cluster IDs in ``[0, k-1]`` **plus** ``-1`` for noise.
          The noise label MUST be preserved verbatim.

    n_clusters : int or None
        Number of distinct clusters (excluding noise). ``None`` for
        algorithms that do not report this (e.g. DBSCAN may report 0
        clusters if everything is noise; the adapter should report
        whatever sklearn returns).

    soft_probabilities : numpy.ndarray or None
        GMM-style posterior probabilities of shape
        ``(n_samples, n_components)``. ``None`` for non-probabilistic
        algorithms.
    soft_membership : numpy.ndarray or None
        Fuzzy-style membership matrix of shape ``(n_samples, c)``.
        ``None`` for non-fuzzy algorithms.

    noise_label : int
        Sentinel value used to mark noise points. Defaults to ``-1``
        (sklearn convention). DBSCAN adapters MUST set this; other
        adapters leave the default.
    noise_count : int or None
        Number of noise samples. ``None`` for algorithms that have no
        notion of noise.
    noise_ratio : float or None
        ``noise_count / n_samples``. ``None`` for algorithms without
        noise.

    supports_random_state : bool
        Whether this algorithm respects ``random_state``. Recorded so
        the experiment log captures the truth even for deterministic
        algorithms.
    random_seed_used : int or None
        Seed that was actually passed to the algorithm. ``None`` for
        deterministic algorithms that do not consume a seed.

    model_artifact_path : str or None
        Path to a serialised model artifact if the runner was asked to
        save one. ``None`` if no model was persisted.

    extra : dict
        Escape hatch for algorithm-specific outputs that do not fit
        the standard slots (e.g. inertia, n_iter_, linkage_matrix).
    """

    algorithm: str
    algorithm_version: str
    algorithm_family: str

    n_samples: int
    n_features: int

    cluster_labels: np.ndarray
    n_clusters: int | None

    # ----- Optional algorithm-family-specific outputs -----
    soft_probabilities: np.ndarray | None = None
    soft_membership: np.ndarray | None = None

    # ----- Noise (DBSCAN-style) -----
    noise_label: int = -1
    noise_count: int | None = None
    noise_ratio: float | None = None

    # ----- Reproducibility metadata -----
    supports_random_state: bool = True
    random_seed_used: int | None = None

    # ----- Artifact paths -----
    model_artifact_path: str | None = None

    # ----- Escape hatch -----
    extra: dict[str, Any] = field(default_factory=dict)

    # ----- Metrics placeholder (EPIC-07/08 populate) -----
    metrics: MetricsResult = field(default_factory=MetricsResult)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-friendly dict.

        Numpy arrays are converted to nested lists with a metadata
        note. ``extra`` is passed through as-is if it is JSON-friendly.
        """
        out: dict[str, Any] = {
            "algorithm": self.algorithm,
            "algorithm_version": self.algorithm_version,
            "algorithm_family": self.algorithm_family,
            "n_samples": int(self.n_samples),
            "n_features": int(self.n_features),
            "n_clusters": (None if self.n_clusters is None else int(self.n_clusters)),
            "cluster_labels_shape": list(self.cluster_labels.shape),
            "cluster_labels_dtype": str(self.cluster_labels.dtype),
            "cluster_labels_first_5": (
                [int(x) for x in self.cluster_labels[:5].tolist()]
                if self.cluster_labels.size > 0
                else []
            ),
            "soft_probabilities_shape": (
                None if self.soft_probabilities is None else list(self.soft_probabilities.shape)
            ),
            "soft_membership_shape": (
                None if self.soft_membership is None else list(self.soft_membership.shape)
            ),
            "noise_label": int(self.noise_label),
            "noise_count": (None if self.noise_count is None else int(self.noise_count)),
            "noise_ratio": (None if self.noise_ratio is None else float(self.noise_ratio)),
            "supports_random_state": bool(self.supports_random_state),
            "random_seed_used": (
                None if self.random_seed_used is None else int(self.random_seed_used)
            ),
            "model_artifact_path": self.model_artifact_path,
            "extra": self.extra,
            "metrics": self.metrics.to_dict(),
        }
        return out


# ---------------------------------------------------------------------------
# Experiment-level result
# ---------------------------------------------------------------------------


class ExperimentStatus(StrEnum):
    """Status markers for a single ML-01 experiment run."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


@dataclass
class ExperimentResult:
    """End-to-end result of a single ML-01 experiment.

    Captures both the algorithm result (:class:`ClusterResult`) and the
    experiment-level metadata required for reproducibility, logging,
    and downstream evaluation.

    Attributes
    ----------
    experiment_id : str
        Stable identifier for this experiment run.
    status : str
        :class:`ExperimentStatus` value. ``SUCCESS`` if the runner
        produced a :class:`ClusterResult`; ``FAILED`` if the algorithm
        raised and the runner caught it.

    algorithm : str
        Algorithm name.
    algorithm_version : str
        Algorithm / library version string.

    dataset_version : str
        Version label of the input dataset (e.g. ``"FE06-v1.0"``).
    dataset_sha256 : str or None
        SHA-256 of the input matrix file, if available. ``None`` if the
        runner could not compute one.
    input_path : str or None
        Path to the input clustering matrix.
    metadata_path : str or None
        Path to the customer metadata parquet.

    feature_set : list of str
        Names of the feature columns used for clustering.
    feature_count : int
        ``len(feature_set)``.
    n_samples : int
        Number of customers.

    hyperparameters : dict
        ``adapter.get_params()`` snapshot at fit time.
    random_seed : int or None
        Seed requested by the experiment. ``None`` if no seed.
    random_seed_used : int or None
        Seed actually consumed by the algorithm (after any
        per-algorithm override).

    n_clusters : int or None
        Convenience copy from :attr:`ClusterResult.n_clusters`.
    cluster_labels : numpy.ndarray or None
        Convenience copy from :attr:`ClusterResult.cluster_labels`.
        ``None`` if ``status == FAILED``.

    execution_time : float
        Wall-clock time (seconds) spent in ``adapter.fit``.
    timestamp : str
        ISO-8601 UTC timestamp of the run.

    cluster_result : ClusterResult or None
        Full algorithm result. ``None`` if ``status == FAILED``.
    metrics : MetricsResult
        Convenience copy of ``cluster_result.metrics`` (or empty if
        the run failed).

    artifact_paths : dict
        Mapping of artifact name → path. At minimum: ``cluster_labels``
        (when ``save_labels`` is True), ``experiment_log``.

    error : dict or None
        Populated when ``status == FAILED``. Keys: ``type`` (exception
        class name), ``message``, ``traceback``.

    platform : dict
        Python version / OS snapshot, mirroring FE-06 run metadata.
    library_versions : dict
        Snapshot of relevant library versions.

    scope_boundaries : list of str
        Human-readable notes about what ML-01 did and did not do.

    pending_review_notes : list of str
        Decisions that are still WORKING_ASSUMPTION /
        MENTOR_REVIEW_PENDING.

    assumptions : list of str
        Methodology assumptions baked into the run.

    config_source : str or None
        Origin of the config (e.g. ``"yaml:/.../clustering.yaml"``).
    config_sha256 : str or None
        SHA-256 of the YAML config that drove this run.
    """

    experiment_id: str
    status: str

    algorithm: str
    algorithm_version: str

    dataset_version: str
    dataset_sha256: str | None
    input_path: str | None
    metadata_path: str | None

    feature_set: list[str]
    feature_count: int
    n_samples: int

    hyperparameters: dict[str, Any]
    random_seed: int | None
    random_seed_used: int | None

    n_clusters: int | None
    cluster_labels: np.ndarray | None

    execution_time: float
    timestamp: str

    cluster_result: ClusterResult | None
    metrics: MetricsResult

    artifact_paths: dict[str, str]

    error: dict[str, Any] | None = None

    platform: dict[str, str] = field(default_factory=dict)
    library_versions: dict[str, str] = field(default_factory=dict)

    scope_boundaries: list[str] = field(default_factory=list)
    pending_review_notes: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)

    config_source: str | None = None
    config_sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-friendly dict (numpy arrays → metadata)."""
        out: dict[str, Any] = {
            "experiment_id": self.experiment_id,
            "status": self.status,
            "algorithm": self.algorithm,
            "algorithm_version": self.algorithm_version,
            "dataset_version": self.dataset_version,
            "dataset_sha256": self.dataset_sha256,
            "input_path": self.input_path,
            "metadata_path": self.metadata_path,
            "feature_set": list(self.feature_set),
            "feature_count": int(self.feature_count),
            "n_samples": int(self.n_samples),
            "hyperparameters": self.hyperparameters,
            "random_seed": (None if self.random_seed is None else int(self.random_seed)),
            "random_seed_used": (
                None if self.random_seed_used is None else int(self.random_seed_used)
            ),
            "n_clusters": (None if self.n_clusters is None else int(self.n_clusters)),
            "cluster_labels_shape": (
                None if self.cluster_labels is None else list(self.cluster_labels.shape)
            ),
            "cluster_labels_dtype": (
                None if self.cluster_labels is None else str(self.cluster_labels.dtype)
            ),
            "execution_time": float(self.execution_time),
            "timestamp": self.timestamp,
            "cluster_result": (
                None if self.cluster_result is None else self.cluster_result.to_dict()
            ),
            "metrics": self.metrics.to_dict(),
            "artifact_paths": dict(self.artifact_paths),
            "error": self.error,
            "platform": self.platform,
            "library_versions": self.library_versions,
            "scope_boundaries": list(self.scope_boundaries),
            "pending_review_notes": list(self.pending_review_notes),
            "assumptions": list(self.assumptions),
            "config_source": self.config_source,
            "config_sha256": self.config_sha256,
        }
        return out


# ---------------------------------------------------------------------------
# JSON encoder (numpy-safe)
# ---------------------------------------------------------------------------


class ClusterResultEncoder(json.JSONEncoder):
    """JSON encoder that handles numpy scalars and arrays safely.

    Used by :func:`cluster_result_to_dict` callers that want a fully
    serialised JSON string in one call. For finer control, build the
    dict with the per-class ``to_dict()`` methods first.
    """

    def default(self, obj: Any) -> Any:
        if isinstance(obj, np.ndarray):
            return {
                "__numpy_array__": True,
                "shape": list(obj.shape),
                "dtype": str(obj.dtype),
            }
        if isinstance(obj, (np.integer, np.floating)):
            return obj.item()
        return super().default(obj)


def cluster_result_to_dict(obj: Any) -> dict[str, Any]:
    """Convert an :class:`ExperimentResult` or :class:`ClusterResult` to dict.

    Convenience wrapper around ``obj.to_dict()`` for callers that want
    a single entry point.
    """
    if obj is None:
        return {}
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    raise TypeError(
        f"Object of type {type(obj).__name__} does not have to_dict(); "
        "expected ClusterResult or ExperimentResult."
    )
