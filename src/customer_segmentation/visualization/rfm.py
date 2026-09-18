"""RFM-specific plots (recency histogram, frequency histogram, monetary histogram, ...).

TODO
----
- Implement `plot_rfm_distributions(df_rfm, output_dir)`.
- Save individual plots and an optional combined panel.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

__all__: list[str] = []


def plot_rfm_distributions(df_rfm: pd.DataFrame, output_dir: Path) -> None:
    """Plot Recency, Frequency, and Monetary distributions.

    Parameters
    ----------
    df_rfm : pandas.DataFrame
        Customer-level RFM table.
    output_dir : pathlib.Path
        Directory to save plots into.

    Notes
    -----
    Placeholder. Implementation will be added in the visualization stage.
    """
    # TODO: implement RFM distribution plots.
    raise NotImplementedError("plot_rfm_distributions is not implemented yet.")
