"""End-to-end cleaning pipeline.

TODO
----
- Compose `missing_values`, `duplicates`, `invalid_records`, and `outliers`
  into a single `clean_transactions(df, config) -> pd.DataFrame` entry point.
- Return both the cleaned DataFrame and a report of dropped rows per stage.
"""

from __future__ import annotations

from typing import NamedTuple

import pandas as pd

__all__ = ["CleaningResult", "clean_transactions"]


class CleaningResult(NamedTuple):
    """Result of the cleaning pipeline.

    Attributes
    ----------
    df : pandas.DataFrame
        Cleaned DataFrame.
    report : dict[str, int]
        Per-stage row-drop counters.
    """

    df: pd.DataFrame
    report: dict[str, int]


def clean_transactions(df: pd.DataFrame, config: dict | None = None) -> CleaningResult:
    """Run the full cleaning pipeline on raw transactions.

    Parameters
    ----------
    df : pandas.DataFrame
        Raw transactions.
    config : dict or None
        Preprocessing configuration. ``None`` uses documented defaults.

    Returns
    -------
    CleaningResult
        Cleaned DataFrame and per-stage drop report.

    Notes
    -----
    Placeholder. Composition order will be set after FE-01.
    """
    # TODO: implement ordered composition.
    raise NotImplementedError("clean_transactions is not implemented yet.")
