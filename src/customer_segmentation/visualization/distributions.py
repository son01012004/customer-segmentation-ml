"""Feature distribution plots.

TODO
----
- Implement `plot_feature_distribution(df, column, output_path)`.
- Use matplotlib + seaborn. Save to `reports/figures/`.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

__all__: list[str] = []


def plot_feature_distribution(
    df: pd.DataFrame,
    column: str,
    output_path: Path,
) -> None:
    """Plot the distribution of a single numeric column.

    Parameters
    ----------
    df : pandas.DataFrame
        Source data.
    column : str
        Numeric column to plot.
    output_path : pathlib.Path
        Destination file (e.g. PNG).

    Notes
    -----
    Placeholder. Implementation will be added in the visualization stage.
    """
    # TODO: implement distribution plot.
    raise NotImplementedError("plot_feature_distribution is not implemented yet.")
