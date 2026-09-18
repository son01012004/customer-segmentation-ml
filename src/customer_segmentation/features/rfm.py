"""RFM (Recency, Frequency, Monetary) feature construction.

TODO
----
- Implement `build_rfm(df_transactions, reference_date) -> pd.DataFrame`.
- Use `CustomerID` as the index key.
- Return columns ``Recency`` (days), ``Frequency`` (unique invoices),
  ``Monetary`` (sum of line revenue).
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

__all__: list[str] = []


def build_rfm(
    df_transactions: pd.DataFrame,
    reference_date: datetime | str | None = None,
) -> pd.DataFrame:
    """Compute customer-level RFM features.

    Parameters
    ----------
    df_transactions : pandas.DataFrame
        Cleaned transactional data. Must contain the canonical columns.
    reference_date : datetime, str, or None
        Anchor for the Recency calculation. If ``None``, use the
        ``reference_date_mode`` from the active experiment configuration.

    Returns
    -------
    pandas.DataFrame
        Customer-level RFM table with index ``CustomerID`` and columns
        ``Recency``, ``Frequency``, ``Monetary``.

    Notes
    -----
    Placeholder. Implementation will be added in FE-01.
    """
    # TODO: implement RFM aggregation.
    raise NotImplementedError("build_rfm is not implemented yet.")
