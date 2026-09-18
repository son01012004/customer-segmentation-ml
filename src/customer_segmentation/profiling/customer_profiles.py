"""Customer-level segment profile generation.

TODO
----
- Implement `build_customer_profiles(df_features, labels) -> pd.DataFrame`
  that summarizes each cluster: size, mean/median of each feature,
  qualitative label (e.g. "Champions", "At Risk").
"""

from __future__ import annotations

import pandas as pd

__all__: list[str] = []


def build_customer_profiles(
    df_features: pd.DataFrame,
    labels: pd.Series | None,
) -> pd.DataFrame:
    """Build per-cluster descriptive profiles.

    Parameters
    ----------
    df_features : pandas.DataFrame
        Customer-level feature matrix (one row per ``CustomerID``).
    labels : pandas.Series or None
        Cluster label per row, aligned with `df_features`. ``None`` skips
        profile generation.

    Returns
    -------
    pandas.DataFrame
        Per-cluster profile summary (size, mean, median per feature, ...).

    Notes
    -----
    Placeholder. Implementation will be added in the profiling stage.
    """
    # TODO: implement profile generation.
    raise NotImplementedError("build_customer_profiles is not implemented yet.")
