"""Customer-profile plots (cluster heatmap, radar chart, segment sizes).

TODO
----
- Implement `plot_cluster_heatmap(df_profile, output_path)`.
- Implement `plot_cluster_sizes(sizes, output_path)`.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

__all__: list[str] = []


def plot_cluster_heatmap(df_profile: pd.DataFrame, output_path: Path) -> None:
    """Plot a heatmap of standardized cluster means per feature."""
    # TODO: implement cluster heatmap.
    raise NotImplementedError("plot_cluster_heatmap is not implemented yet.")


def plot_cluster_sizes(sizes: pd.Series, output_path: Path) -> None:
    """Plot cluster size distribution as a bar chart."""
    # TODO: implement cluster sizes plot.
    raise NotImplementedError("plot_cluster_sizes is not implemented yet.")
