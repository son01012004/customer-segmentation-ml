"""Outlier detection and treatment.

TODO
----
- Implement `treat_outliers(df, columns, method, action) -> pd.DataFrame`.
- Methods: iqr | zscore | winsorize.
- Actions: clip | remove | flag (add boolean column).
"""

from __future__ import annotations

from typing import Literal

import pandas as pd

__all__: list[str] = []

OutlierMethod = Literal["iqr", "zscore", "winsorize"]
OutlierAction = Literal["clip", "remove", "flag"]


def treat_outliers(
    df: pd.DataFrame,
    columns: list[str],
    method: OutlierMethod = "iqr",
    action: OutlierAction = "clip",
    iqr_multiplier: float = 1.5,
    zscore_threshold: float = 3.0,
) -> pd.DataFrame:
    """Detect and treat outliers on the selected numeric columns.

    Parameters
    ----------
    df : pandas.DataFrame
        Input DataFrame.
    columns : list[str]
        Numeric columns to inspect.
    method : {"iqr", "zscore", "winsorize"}
        Detection method.
    action : {"clip", "remove", "flag"}
        Treatment strategy.
    iqr_multiplier : float
        Multiplier for the IQR fences (only used when ``method == "iqr"``).
    zscore_threshold : float
        Absolute z-score threshold (only used when ``method == "zscore"``).

    Returns
    -------
    pandas.DataFrame
        DataFrame with outliers treated.

    Notes
    -----
    Placeholder. Implementation will be added in the preprocessing stage.
    """
    # TODO: implement outlier detection and treatment.
    raise NotImplementedError("treat_outliers is not implemented yet.")
