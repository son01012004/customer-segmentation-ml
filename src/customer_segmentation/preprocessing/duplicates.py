"""Duplicate-record handling.

TODO
----
- Implement `drop_duplicates(df, subset, keep) -> pd.DataFrame`.
- Track the number of removed rows.
"""

from __future__ import annotations

import pandas as pd

__all__: list[str] = []


def drop_duplicates(
    df: pd.DataFrame,
    subset: list[str] | None = None,
    keep: str = "none",
) -> pd.DataFrame:
    """Drop duplicate rows.

    Parameters
    ----------
    df : pandas.DataFrame
        Input DataFrame.
    subset : list[str] or None
        Columns considered for uniqueness. ``None`` uses all columns.
    keep : str
        ``"first"``, ``"last"``, or ``"none"``.

    Returns
    -------
    pandas.DataFrame
        DataFrame without duplicates.

    Notes
    -----
    Placeholder. Implementation will be added in the preprocessing stage.
    """
    # TODO: implement duplicate removal with row tracking.
    raise NotImplementedError("drop_duplicates is not implemented yet.")
