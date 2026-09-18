"""Schema and value-range validation for raw and processed data.

TODO
----
- Implement column-presence checks against `data.schema`.
- Implement dtype and basic value-range checks (non-negative quantities,
  parseable dates, non-empty CustomerID).
- Return structured `ValidationResult` instead of raising.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

import pandas as pd

__all__ = ["ValidationResult"]


@dataclass
class ValidationResult:
    """Outcome of a validation pass.

    Attributes
    ----------
    is_valid : bool
        True if all checks passed.
    errors : list[str]
        List of human-readable error messages.
    warnings : list[str]
        List of human-readable warnings (non-fatal).
    stats : dict[str, int]
        Optional per-check counters (e.g. ``{"missing_customer_id": 133}``).
    """

    is_valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)


def validate_raw_transactions(df: pd.DataFrame) -> ValidationResult:
    """Validate a raw transactions DataFrame.

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame produced by ``data.loader.load_raw_transactions``.

    Returns
    -------
    ValidationResult
        Placeholder result. Currently always empty/valid.

    Notes
    -----
    Placeholder. Real checks will be added after FE-01 once the canonical
    schema is fixed.
    """
    # TODO: implement column-presence, dtype, and value-range checks.
    return ValidationResult()


def validate_customer_features(df: pd.DataFrame) -> ValidationResult:
    """Validate a customer-level feature DataFrame.

    Parameters
    ----------
    df : pandas.DataFrame
        Customer-level feature matrix produced by ``features.*``.

    Returns
    -------
    ValidationResult
        Placeholder result. Currently always empty/valid.

    Notes
    -----
    Placeholder. Real checks will be added once FE-01 columns are defined.
    """
    # TODO: implement per-column checks (non-negative Monetary, no NA, unique ids).
    return ValidationResult()


def assert_columns_exist(df: pd.DataFrame, required: Iterable[str]) -> None:
    """Raise if any required column is missing.

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame to inspect.
    required : Iterable[str]
        Column names that must be present.

    Raises
    ------
    KeyError
        If any required column is missing.

    Notes
    -----
    Generic helper. Implemented early to be reused across stages.
    """
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(f"Missing required columns: {missing}")
