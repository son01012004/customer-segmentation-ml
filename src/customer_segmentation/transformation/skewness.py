"""Skewness correction for numeric features.

TODO
----
- Implement `correct_skewness(df, method) -> pd.DataFrame`.
- Methods: none | log1p | yeojohnson.
"""

from __future__ import annotations

from typing import Literal

import pandas as pd

__all__: list[str] = []

SkewMethod = Literal["none", "log1p", "yeojohnson"]


def correct_skewness(df: pd.DataFrame, method: SkewMethod = "yeojohnson") -> pd.DataFrame:
    """Apply a skewness-correction transform to numeric columns.

    Parameters
    ----------
    df : pandas.DataFrame
        Customer-level feature matrix (numeric columns only).
    method : {"none", "log1p", "yeojohnson"}
        Transform to apply.

    Returns
    -------
    pandas.DataFrame
        Transformed feature matrix.

    Notes
    -----
    Placeholder. Implementation will be added in the transformation stage.
    """
    # TODO: implement skewness correction.
    raise NotImplementedError("correct_skewness is not implemented yet.")
