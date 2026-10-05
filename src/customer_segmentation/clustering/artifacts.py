"""Artifact I/O for ML-01 experiments.

Three artifact classes:

- ``cluster_labels.parquet`` — pandas DataFrame with at least
  ``CustomerID`` and ``ClusterLabel`` columns, optionally augmented
  with algorithm-specific columns (``ClusterProbability`` for GMM,
  ``Membership`` for Fuzzy C-Means).
- ``algorithm_output.parquet`` — algorithm-specific outputs that do
  not fit into cluster_labels (e.g. full membership matrix,
  responsibilities).
- ``experiment_log.json`` — full :class:`ExperimentResult` payload.

All writers are **append-only with respect to the input**: the
framework never mutates the FE-06 final clustering matrix or the
customer metadata parquet.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from customer_segmentation.clustering.logging_utils import write_experiment_log
from customer_segmentation.clustering.result import ClusterResult, ExperimentResult

__all__ = [
    "write_cluster_labels",
    "write_algorithm_output",
    "write_experiment_artifacts",
]


def _resolve_cluster_labels_df(
    cluster_result: ClusterResult,
    customer_metadata_df: pd.DataFrame | None,
    customer_key: str,
) -> pd.DataFrame:
    """Build the cluster_labels DataFrame with CustomerID alignment.

    If metadata is provided, the label at row ``i`` is paired with the
    metadata's ``customer_key`` value at row ``i``. The metadata row
    order is preserved (ML-01 never reorders customers).

    If metadata is ``None``, only the integer labels are written
    (positionally indexed); the runner is responsible for downstream
    re-attachment of CustomerID by the caller.
    """
    labels = cluster_result.cluster_labels
    if customer_metadata_df is not None:
        if len(customer_metadata_df) != len(labels):
            raise ValueError(
                f"Customer metadata rows ({len(customer_metadata_df)}) "
                f"!= cluster_labels rows ({len(labels)})."
            )
        if customer_key not in customer_metadata_df.columns:
            raise ValueError(
                f"Customer key '{customer_key}' not in metadata columns "
                f"{list(customer_metadata_df.columns)}."
            )
        out = pd.DataFrame(
            {
                customer_key: customer_metadata_df[customer_key].to_numpy(),
                "ClusterLabel": labels.astype(np.int64, copy=False),
            }
        )
    else:
        out = pd.DataFrame(
            {
                "RowIndex": np.arange(len(labels), dtype=np.int64),
                "ClusterLabel": labels.astype(np.int64, copy=False),
            }
        )

    # Add noise indicator (sklearn convention: -1).
    out["IsNoise"] = (out["ClusterLabel"] == cluster_result.noise_label).astype(bool)

    # Algorithm-specific extras.
    if cluster_result.soft_probabilities is not None:
        n_components = cluster_result.soft_probabilities.shape[1]
        for j in range(n_components):
            out[f"Probability_{j}"] = cluster_result.soft_probabilities[:, j].astype(
                np.float64, copy=False
            )
    if cluster_result.soft_membership is not None:
        n_clusters = cluster_result.soft_membership.shape[1]
        for j in range(n_clusters):
            out[f"Membership_{j}"] = cluster_result.soft_membership[:, j].astype(
                np.float64, copy=False
            )
    return out


def write_cluster_labels(
    output_path: Path,
    cluster_result: ClusterResult,
    *,
    customer_metadata_df: pd.DataFrame | None,
    customer_key: str = "CustomerID",
) -> Path:
    """Write the cluster-labels artifact.

    Parameters
    ----------
    output_path : pathlib.Path
        Destination ``.parquet`` path.
    cluster_result : ClusterResult
        Algorithm result to serialise.
    customer_metadata_df : pandas.DataFrame or None
        Customer metadata carrying ``customer_key``. If ``None``, only
        positional labels are written.
    customer_key : str
        Name of the customer ID column in ``customer_metadata_df``.

    Returns
    -------
    pathlib.Path
        Path the artifact was written to.

    Raises
    ------
    ValueError
        If metadata is provided but its row count does not match the
        number of cluster labels, or if ``customer_key`` is missing.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df = _resolve_cluster_labels_df(cluster_result, customer_metadata_df, customer_key)
    df.to_parquet(output_path, index=False)
    return output_path


def write_algorithm_output(
    output_path: Path,
    cluster_result: ClusterResult,
    *,
    customer_metadata_df: pd.DataFrame | None,
    customer_key: str = "CustomerID",
) -> Path | None:
    """Write algorithm-specific outputs (soft probabilities, membership, ...).

    If neither soft probabilities nor soft membership is present, this
    returns ``None`` without writing anything (DBSCAN and hard
    clustering have no extra columns).

    Parameters
    ----------
    output_path : pathlib.Path
        Destination ``.parquet`` path.
    cluster_result : ClusterResult
        Algorithm result.
    customer_metadata_df : pandas.DataFrame or None
        Customer metadata (used only to attach ``CustomerID`` if
        available).
    customer_key : str
        Name of the customer ID column.

    Returns
    -------
    pathlib.Path or None
        Path the artifact was written to, or ``None`` if no
        algorithm-specific output was produced.
    """
    if cluster_result.soft_probabilities is None and cluster_result.soft_membership is None:
        return None

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if customer_metadata_df is not None:
        if len(customer_metadata_df) != len(cluster_result.cluster_labels):
            raise ValueError(
                f"Customer metadata rows ({len(customer_metadata_df)}) "
                f"!= cluster_labels rows ({len(cluster_result.cluster_labels)})."
            )
        out = pd.DataFrame({customer_key: customer_metadata_df[customer_key].to_numpy()})
    else:
        out = pd.DataFrame({"RowIndex": np.arange(len(cluster_result.cluster_labels))})

    if cluster_result.soft_probabilities is not None:
        n_components = cluster_result.soft_probabilities.shape[1]
        for j in range(n_components):
            out[f"Probability_{j}"] = cluster_result.soft_probabilities[:, j].astype(
                np.float64, copy=False
            )
    if cluster_result.soft_membership is not None:
        n_clusters = cluster_result.soft_membership.shape[1]
        for j in range(n_clusters):
            out[f"Membership_{j}"] = cluster_result.soft_membership[:, j].astype(
                np.float64, copy=False
            )
    out.to_parquet(output_path, index=False)
    return output_path


def write_experiment_artifacts(
    output_dir: Path,
    experiment_result: ExperimentResult,
    *,
    cluster_labels_filename: str,
    experiment_log_filename: str,
    algorithm_output_filename: str,
    customer_metadata_df: pd.DataFrame | None,
    customer_key: str,
    save_labels: bool,
    save_metadata: bool,  # currently unused; reserved for symmetry with config
    save_algorithm_specific: bool,
) -> dict[str, str]:
    """Write all experiment artifacts and return their paths.

    Parameters
    ----------
    output_dir : pathlib.Path
        Output directory (created if missing).
    experiment_result : ExperimentResult
        Experiment result to serialise.
    cluster_labels_filename : str
        Template filename. Supports ``{experiment_id}`` placeholder.
    experiment_log_filename : str
        Template filename for the JSON log.
    algorithm_output_filename : str
        Template filename for the algorithm-specific output parquet.
    customer_metadata_df : pandas.DataFrame or None
        Customer metadata for CustomerID alignment.
    customer_key : str
        Name of the customer ID column.
    save_labels : bool
        If ``True``, write cluster_labels parquet.
    save_metadata : bool
        Reserved. Currently unused (metadata is never overwritten by
        ML-01).
    save_algorithm_specific : bool
        If ``True`` AND algorithm produced soft probabilities or
        membership, write the algorithm_output parquet.

    Returns
    -------
    dict[str, str]
        Mapping of artifact name → written path (string form).
    """
    _ = save_metadata  # reserved
    output_dir.mkdir(parents=True, exist_ok=True)

    experiment_id = experiment_result.experiment_id
    paths: dict[str, str] = {}

    if save_labels and experiment_result.cluster_result is not None:
        labels_path = output_dir / cluster_labels_filename.format(experiment_id=experiment_id)
        write_cluster_labels(
            labels_path,
            experiment_result.cluster_result,
            customer_metadata_df=customer_metadata_df,
            customer_key=customer_key,
        )
        paths["cluster_labels"] = str(labels_path)

    log_path = output_dir / experiment_log_filename.format(experiment_id=experiment_id)
    write_experiment_log(experiment_result, log_path)
    paths["experiment_log"] = str(log_path)

    if (
        save_algorithm_specific
        and experiment_result.cluster_result is not None
        and (
            experiment_result.cluster_result.soft_probabilities is not None
            or experiment_result.cluster_result.soft_membership is not None
        )
    ):
        algo_path = output_dir / algorithm_output_filename.format(experiment_id=experiment_id)
        written = write_algorithm_output(
            algo_path,
            experiment_result.cluster_result,
            customer_metadata_df=customer_metadata_df,
            customer_key=customer_key,
        )
        if written is not None:
            paths["algorithm_output"] = str(written)

    return paths


# ---------------------------------------------------------------------------
# Low-level helpers used by tests
# ---------------------------------------------------------------------------


def build_cluster_labels_dataframe(
    cluster_result: ClusterResult,
    customer_metadata_df: pd.DataFrame | None,
    customer_key: str = "CustomerID",
) -> pd.DataFrame:
    """Public re-export of the internal DataFrame builder (used by tests)."""
    return _resolve_cluster_labels_df(cluster_result, customer_metadata_df, customer_key)


def summarise_artifact_paths(paths: dict[str, Any]) -> dict[str, str]:
    """Coerce artifact paths dict to str-only (for JSON serialisation)."""
    return {k: str(v) for k, v in paths.items()}
