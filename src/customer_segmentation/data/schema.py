"""Canonical schema definitions for raw and processed customer data.

TODO
----
- Define `RAW_TRANSACTION_COLUMNS` and `CUSTOMER_FEATURE_COLUMNS`.
- Define per-column dtypes and value ranges for validation.
- Add pydantic or dataclass models for strict schema checks (optional).
"""

from __future__ import annotations

from typing import Final

# Placeholder constant. Final list will be set after dataset audit (DS-05+FE-01).
RAW_TRANSACTION_COLUMNS: Final[tuple[str, ...]] = (
    # TODO: e.g. ("InvoiceNo", "StockCode", "Description", "Quantity",
    #            "InvoiceDate", "UnitPrice", "CustomerID", "Country")
)

# Placeholder constant. Final list will be set after FE-01.
CUSTOMER_FEATURE_COLUMNS: Final[tuple[str, ...]] = (
    # TODO: e.g. ("CustomerID", "Recency", "Frequency", "Monetary", ...)
)


def get_raw_transaction_columns() -> tuple[str, ...]:
    """Return the canonical raw transaction columns.

    Returns
    -------
    tuple[str, ...]
        Currently empty placeholder. Will be filled after dataset audit.
    """
    # TODO: replace with canonical raw column list.
    return RAW_TRANSACTION_COLUMNS


def get_customer_feature_columns() -> tuple[str, ...]:
    """Return the canonical customer-level feature columns.

    Returns
    -------
    tuple[str, ...]
        Currently empty placeholder. Will be filled after FE-01.
    """
    # TODO: replace with canonical customer feature column list.
    return CUSTOMER_FEATURE_COLUMNS
