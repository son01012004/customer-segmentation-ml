"""Missing-value handling.

TODO
----
- Implement `handle_missing(df, columns, strategy) -> pd.DataFrame`.
- Strategies: drop | impute_zero | impute_median | keep.
- Track and return the number of dropped/imputed rows.
"""

from __future__ import annotations

import pandas as pd

__all__: list[str] = []


def handle_missing(df: pd.DataFrame, columns: list[str], strategy: str) -> pd.DataFrame:
    """Apply a missing-value strategy to selected columns.

    Parameters
    ----------
    df : pandas.DataFrame
        Input DataFrame (not mutated).
    columns : list[str]
        Columns to consider.
    strategy : str
        One of ``"drop"``, ``"impute_zero"``, ``"impute_median"``, ``"keep"``.

    Returns
    -------
    pandas.DataFrame
        DataFrame with the strategy applied.

    Raises
    ------
    ValueError
        If `strategy` is not recognized.

    Notes
    -----
    Placeholder. Implementation will be added in the preprocessing stage.
    """
    # TODO: implement strategies.
    raise NotImplementedError("handle_missing is not implemented yet.")
