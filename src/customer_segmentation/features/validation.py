"""Validation helpers for the customer-level feature matrix.

TODO
----
- Implement uniqueness checks on ``CustomerID``.
- Implement non-negativity / NA checks per configured column.
- Return a structured ``ValidationResult`` (defined in ``data.validator``).
"""

from __future__ import annotations

import pandas as pd

from customer_segmentation.data.validator import ValidationResult

__all__ = ["validate_customer_features"]


def validate_customer_features(df: pd.DataFrame) -> ValidationResult:
    """Validate the customer-level feature matrix.

    Parameters
    ----------
    df : pandas.DataFrame
        Customer-level feature matrix.

    Returns
    -------
    ValidationResult
        Aggregated validation outcome.

    Notes
    -----
    Placeholder. Real checks will be added once FE-01 columns are defined.
    """
    # TODO: implement per-column checks driven by configs/features.yaml.
    return ValidationResult()
