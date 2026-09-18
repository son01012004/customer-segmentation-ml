"""Clustering-result plots (scatter, elbow, silhouette, dendrogram).

TODO
----
- Implement `plot_cluster_scatter(X_2d, labels, output_path)`.
- Implement `plot_elbow(inertias, k_range, output_path)`.
- Implement `plot_silhouette(silhouettes, k_range, output_path)`.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

__all__: list[str] = []


def plot_cluster_scatter(
    X_2d: np.ndarray,
    labels: np.ndarray,
    output_path: Path,
) -> None:
    """Plot a 2D scatter of clusters (typically from PCA or UMAP)."""
    # TODO: implement cluster scatter.
    raise NotImplementedError("plot_cluster_scatter is not implemented yet.")


def plot_elbow(inertias: list[float], k_range: range, output_path: Path) -> None:
    """Plot the elbow curve for K-Means."""
    # TODO: implement elbow plot.
    raise NotImplementedError("plot_elbow is not implemented yet.")


def plot_silhouette(silhouettes: list[float], k_range: range, output_path: Path) -> None:
    """Plot silhouette scores vs k."""
    # TODO: implement silhouette plot.
    raise NotImplementedError("plot_silhouette is not implemented yet.")
