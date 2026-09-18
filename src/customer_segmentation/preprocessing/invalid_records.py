"""Invalid-record filtering (cancelled invoices, non-positive quantities, ...).

TODO
----
- Implement `drop_invalid(df, rules) -> pd.DataFrame`.
- Rules driven by `configs/preprocessing.yaml::invalid_records`.
"""

from __future__ import annotations

from typing import TypedDict

import pandas as pd

__all__: list[str] = []


class InvalidRecordRules(TypedDict, total=False):
    """Subset of preprocessing rules applied to individual transactions."""

    drop_cancelled_invoices: bool
    cancellation_prefix: str
    drop_non_positive_quantity: bool
    drop_non_positive_unit_price: bool
    drop_missing_customer_id: bool


def drop_invalid(df: pd.DataFrame, rules: InvalidRecordRules) -> pd.DataFrame:
    """Drop rows failing the configured invalid-record rules.

    Parameters
    ----------
    df : pandas.DataFrame
        Input DataFrame.
    rules : InvalidRecordRules
        Mapping of rule toggles.

    Returns
    -------
    pandas.DataFrame
        Filtered DataFrame.

    Notes
    -----
    Placeholder. Implementation will be added in the preprocessing stage.
    """
    # TODO: implement invalid-record filtering.
    raise NotImplementedError("drop_invalid is not implemented yet.")
