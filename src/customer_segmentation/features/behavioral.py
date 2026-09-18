"""Extended behavioral features beyond RFM.

TODO
----
- Implement `build_behavioral_features(df_transactions) -> pd.DataFrame`.
- Examples: AvgBasketValue, UniqueProducts, TotalQuantity, ActiveDays,
  PurchaseSpan, AvgDaysBetweenPurchases, country diversity, etc.
- Return one row per ``CustomerID``.
"""

from __future__ import annotations

import pandas as pd

__all__: list[str] = []


def build_behavioral_features(df_transactions: pd.DataFrame) -> pd.DataFrame:
    """Compute extended behavioral features at the customer level.

    Parameters
    ----------
    df_transactions : pandas.DataFrame
        Cleaned transactional data.

    Returns
    -------
    pandas.DataFrame
        Customer-level behavioral features (one row per ``CustomerID``).

    Notes
    -----
    Placeholder. The exact set of features will be finalized in FE-01 and
    driven by ``configs/features.yaml``.
    """
    # TODO: implement behavioral feature engineering.
    raise NotImplementedError("build_behavioral_features is not implemented yet.")
