"""Scope, stage, and enum definitions for DEV-04 Prototype Clustering.

DEV-04 defines:
- :class:`ClusteredScope`: the scope of a clustering artefact
  (always ``CLUSTERED_PROTOTYPE``).
- :class:`ClusteringStage`: the per-run stage enumeration
  (mirrors ML-01 / DEV-03 pipeline stages).

Why an enum (and not a string)
--------------------------------
A string-valued :class:`Enum` (the ``str, Enum`` mixin) gives both
``==`` semantics of strings and the type-checkable membership in a
closed set. This mirrors the convention used by
:mod:`customer_segmentation.config.loader`,
:mod:`customer_segmentation.dataset_management.scope`, and
:mod:`customer_segmentation.prototype.preprocessing.scope`.

Hard rules
----------
- :class:`ClusteredScope` has exactly ONE value:
  ``CLUSTERED_PROTOTYPE``. The pipeline never exposes a way to change it.
- :class:`ClusteringStage` enumerates the 7 pipeline stages
  (Stage 0→6 per DEV-04 plan §5.3 sequence diagram).
- The ``seed_policy`` canonical values (``"stochastic"`` /
  ``"deterministic"``) match ML-01's ``supports_random_state()``
  truth table: kmeans/gmm/fuzzy_cmeans → stochastic;
  agglomerative/dbscan → deterministic.
- ``DETERMINISTIC_ALGORITHMS`` is the frozenset of algorithm names
  that are deterministic (no random state). It mirrors
  ``BaseClusterAlgorithm.supports_random_state() == False`` for those
  adapters.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

__all__ = [
    "ClusteredScope",
    "ClusteringStage",
    "CLUSTERED_SCOPES",
    "CLUSTERING_STAGES",
    "DETERMINISTIC_ALGORITHMS",
    "STOCHASTIC_ALGORITHMS",
    "SUPPORTED_ALGORITHMS",
    "AlgorithmFamily",
    "run_clustering_experiment",
]


# ---------------------------------------------------------------------------
# Scope
# ---------------------------------------------------------------------------


class ClusteredScope(StrEnum):
    """Scope of a clustering artefact in the prototype storage layer.

    Attributes
    ----------
    CLUSTERED_PROTOTYPE : str
        The only value currently in use. Implies that the artefact
        was produced by the DEV-04 pipeline on a DEV-03 preprocessed
        ML Dataset. It is **not** a research artefact; it has not been
        promoted by the research methodology.
    """

    CLUSTERED_PROTOTYPE = "CLUSTERED_PROTOTYPE"


CLUSTERED_SCOPES: Final[frozenset[str]] = frozenset(s.value for s in ClusteredScope)


# ---------------------------------------------------------------------------
# Pipeline stages (Stage 0 → 6)
# ---------------------------------------------------------------------------


class ClusteringStage(StrEnum):
    """The 7-stage DEV-04 pipeline.

    Stages are listed in execution order. Each stage corresponds to one
    step in the DEV-04 sequence diagram (§5.3).

    The mapping is::

        0: preflight          — CLI args + config load
        1: lookup             — DEV-03 manifest + ML Dataset lookup
        2: split              — matrix / metadata split
        3: build              — ExperimentSpec + ExperimentRunner + staging prep
        4: fit                — runner.run() into staging_dir
        5: manifest           — write clustering_manifest (atomic, in staging)
        5b: publish          — atomic rename staging → final
        6: finalize_log      — finalize per-stage log
    """

    STAGE_0 = "0"  # preflight
    STAGE_1 = "1"  # DEV-03 lookup
    STAGE_2 = "2"  # matrix/metadata split
    STAGE_3 = "3"  # build ExperimentSpec + staging prep
    STAGE_4 = "4"  # runner.run() into staging
    STAGE_5 = "5"  # write clustering_manifest
    STAGE_5B = "5b"  # atomic publish
    STAGE_6 = "6"  # finalize log


CLUSTERING_STAGES: Final[frozenset[str]] = frozenset(s.value for s in ClusteringStage)


# ---------------------------------------------------------------------------
# Algorithm classification
# ---------------------------------------------------------------------------

# Algorithms whose adapters set supports_random_state() == True
# (stochastic; runner passes seed_to_pass = resolved seed).
STOCHASTIC_ALGORITHMS: Final[frozenset[str]] = frozenset({"kmeans", "gmm", "fuzzy_cmeans"})

# Algorithms whose adapters set supports_random_state() == False
# (deterministic; runner sets seed_to_pass = None regardless of CLI/YAML).
DETERMINISTIC_ALGORITHMS: Final[frozenset[str]] = frozenset({"agglomerative", "dbscan"})

# All 5 supported algorithms (mirror AlgorithmRegistry.list_registered()).
SUPPORTED_ALGORITHMS: Final[frozenset[str]] = STOCHASTIC_ALGORITHMS | DETERMINISTIC_ALGORITHMS


# ---------------------------------------------------------------------------
# Re-export AlgorithmFamily from research core for convenience
# ---------------------------------------------------------------------------
from customer_segmentation.clustering.result import AlgorithmFamily

_ = AlgorithmFamily  # noqa: F401


# ---------------------------------------------------------------------------
# Public top-level driver
# ---------------------------------------------------------------------------


def run_clustering_experiment(
    dataset_id: str,
    preprocessed_id: str,
    algorithm: str,
    *,
    config_path: str | None = None,
    hyperparameters: dict | None = None,
    seed: int | None = None,
    experiment_id: str | None = None,
    force_rerun: bool = False,
) -> dict:
    """Top-level public entry point for DEV-04 clustering execution.

    Re-export of :func:`pipeline.run_clustering_pipeline` for ergonomic
    imports. Returns a JSON-serialisable summary dict.

    See :func:`pipeline.run_clustering_pipeline` for full documentation.

    Parameters
    ----------
    dataset_id : str
        DEV-02 dataset id (e.g. ``"ds_ba54033e45525bf5123c2d9d"``).
    preprocessed_id : str
        DEV-03 preprocessed id (e.g. ``"pp_abc123..."``).
    algorithm : str
        Algorithm name: one of ``kmeans``, ``agglomerative``, ``dbscan``,
        ``gmm``, ``fuzzy_cmeans``.
    config_path : str, optional
        Path to ``configs/dev04_clustering.yaml``. ``None`` uses the
        canonical default.
    hyperparameters : dict, optional
        Per-algorithm hyperparameter overrides (merged onto YAML defaults).
    seed : int, optional
        Per-experiment seed override (3-level resolution: CLI > YAML).
    experiment_id : str, optional
        Custom experiment identifier. ``None`` auto-derives from
        ``algorithm + hyperparameters`` (mirror ``run_ml02_kmeans``).
    force_rerun : bool
        If ``True``, re-run even if an artefact with the same
        ``clustering_id`` already exists (using staging + atomic publish
        to preserve the old result until publish succeeds).

    Returns
    -------
    dict
        Run summary (clustering_id, experiment_id, artifact paths, ...).
    """
    from customer_segmentation.prototype.clustering.pipeline import (  # local import to avoid cycles
        run_clustering_pipeline,
    )

    result = run_clustering_pipeline(
        dataset_id=dataset_id,
        preprocessed_id=preprocessed_id,
        algorithm=algorithm,
        config_path=config_path,
        hyperparameters=hyperparameters,
        seed=seed,
        experiment_id=experiment_id,
        force_rerun=force_rerun,
    )
    return result.as_summary()
