"""Missing-value handling for FE-02.

Provides one primary entry point, :func:`handle_missing`, plus a
companion :func:`summarise_missing` that produces a per-column summary
before any decision is applied. Both functions are **read-only** with
respect to the input DataFrame: every transformation returns a new
DataFrame.

Strategies supported
--------------------

- ``"drop"`` — drop rows with missing values in any of the targeted
  columns.
- ``"impute_zero"`` — fill missing values with ``0`` (only safe for
  numeric columns where zero is a meaningful value).
- ``"impute_median"`` — fill missing values with the column median.
- ``"impute_mean"`` — fill missing values with the column mean.
- ``"keep"`` — leave the values unchanged (no rows removed, no
  imputation performed).

The strategies are deliberately conservative: the function never
silently fills identifier columns (e.g. ``CustomerID``) with a sentinel
value because doing so would break the customer-level join semantics.
Identifier imputation is not implemented here and is flagged as
``IDENTIFIER_COLUMN`` in the per-column summary.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

__all__ = [
    "MissingSummary",
    "MissingHandlingResult",
    "handle_missing",
    "summarise_missing",
    "is_identifier_column",
    "safe_fillna",
    "count_missing_cells",
    "IDENTIFIER_COLUMNS",
]


# Columns that must NEVER be imputed with a placeholder. Imputation here
# would silently break the customer-level join semantics. They can still
# be dropped under the ``"drop"`` strategy; the constant is used to
# guard against accidental imputation.
IDENTIFIER_COLUMNS: frozenset[str] = frozenset({"CustomerID", "InvoiceNo"})

# Type alias for the strategy argument of :func:`handle_missing`. Used as
# documentation only; the function still accepts any string and validates
# the value at runtime.
ValidStrategy = str


@dataclass(frozen=True)
class MissingSummary:
    """Per-column missing-value summary produced before any cleaning.

    Attributes
    ----------
    column : str
        Column name.
    missing_count : int
        Number of missing values in the input.
    missing_rate : float
        Missing rate as a percentage in [0, 100].
    n_unique_non_null : int
        Distinct non-null values.
    dtype : str
        Original dtype string.
    """

    column: str
    missing_count: int
    missing_rate: float
    n_unique_non_null: int
    dtype: str

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dict representation."""
        return {
            "column": self.column,
            "missing_count": int(self.missing_count),
            "missing_rate": round(float(self.missing_rate), 4),
            "n_unique_non_null": int(self.n_unique_non_null),
            "dtype": str(self.dtype),
        }


@dataclass
class MissingHandlingResult:
    """Outcome of a missing-value handling pass.

    Attributes
    ----------
    df : pandas.DataFrame
        DataFrame after the strategy has been applied.
    rows_before : int
        Number of rows in the input.
    rows_after : int
        Number of rows in the output.
    rows_dropped : int
        Number of rows removed.
    rows_imputed : int
        Number of cells filled (sum across all targeted columns).
    strategy : str
        Strategy that was actually applied (e.g. ``"drop"``,
        ``"impute_median"``).
    per_column : list[dict]
        One record per targeted column with ``column``, ``strategy``,
        ``missing_count_before``, ``missing_count_after``,
        ``imputed_count``.
    """

    df: pd.DataFrame
    rows_before: int
    rows_after: int
    rows_dropped: int
    rows_imputed: int
    strategy: str
    per_column: list[dict] = field(default_factory=list)


def summarise_missing(
    df: pd.DataFrame,
    columns: Iterable[str] | None = None,
) -> list[MissingSummary]:
    """Compute a missing-value summary for the given columns.

    Parameters
    ----------
    df : pandas.DataFrame
        Input DataFrame (not mutated).
    columns : iterable of str, optional
        Subset of columns to summarise. ``None`` uses every column.

    Returns
    -------
    list[MissingSummary]
        One summary per requested column, sorted by
        ``missing_count`` descending.
    """
    columns = list(df.columns) if columns is None else [c for c in columns if c in df.columns]
    total = max(int(df.shape[0]), 1)
    out: list[MissingSummary] = []
    for col in columns:
        s = df[col]
        miss = int(s.isna().sum())
        rate = miss / total * 100.0
        out.append(
            MissingSummary(
                column=col,
                missing_count=miss,
                missing_rate=round(rate, 4),
                n_unique_non_null=int(s.dropna().nunique()),
                dtype=str(s.dtype),
            )
        )
    out.sort(key=lambda r: (-r.missing_count, r.column))
    return out


def handle_missing(
    df: pd.DataFrame,
    columns: Iterable[str],
    strategy: ValidStrategy,
) -> MissingHandlingResult:
    """Apply a missing-value strategy to selected columns.

    Parameters
    ----------
    df : pandas.DataFrame
        Input DataFrame. **Not mutated** — a copy is returned.
    columns : iterable of str
        Columns the strategy applies to. Unknown columns raise
        ``KeyError``.
    strategy : {"drop", "impute_zero", "impute_median", "impute_mean", "keep"}
        Strategy to apply. See module docstring for semantics.

    Returns
    -------
    MissingHandlingResult
        Cleaned DataFrame plus a structured per-column report.

    Raises
    ------
    KeyError
        If any requested column is not present in `df`.
    ValueError
        If ``strategy`` is not recognised, or if a non-numeric
        imputation strategy is requested for a non-numeric column.
    """
    valid_strategies = {"drop", "impute_zero", "impute_median", "impute_mean", "keep"}
    if strategy not in valid_strategies:
        raise ValueError(
            f"Unknown missing-value strategy {strategy!r}. "
            f"Valid strategies: {sorted(valid_strategies)}"
        )

    columns = list(columns)
    missing_cols = [c for c in columns if c not in df.columns]
    if missing_cols:
        raise KeyError(f"Columns not in DataFrame: {missing_cols}")

    rows_before = int(df.shape[0])
    work = df.copy(deep=True)

    per_column: list[dict] = []
    rows_dropped = 0
    rows_imputed = 0

    if strategy == "keep":
        for col in columns:
            miss = int(work[col].isna().sum())
            per_column.append(
                {
                    "column": col,
                    "strategy": strategy,
                    "missing_count_before": miss,
                    "missing_count_after": miss,
                    "imputed_count": 0,
                }
            )
        return MissingHandlingResult(
            df=work,
            rows_before=rows_before,
            rows_after=rows_before,
            rows_dropped=0,
            rows_imputed=0,
            strategy=strategy,
            per_column=per_column,
        )

    if strategy == "drop":
        # Build a single mask so we drop the union, not column-by-column.
        mask = pd.Series(False, index=work.index)
        for col in columns:
            miss = int(work[col].isna().sum())
            mask = mask | work[col].isna()
            per_column.append(
                {
                    "column": col,
                    "strategy": strategy,
                    "missing_count_before": miss,
                    "missing_count_after": 0,
                    "imputed_count": 0,
                }
            )
        rows_dropped = int(mask.sum())
        work = work.loc[~mask].reset_index(drop=True)
    else:
        for col in columns:
            miss_before = int(work[col].isna().sum())
            if miss_before == 0:
                per_column.append(
                    {
                        "column": col,
                        "strategy": strategy,
                        "missing_count_before": 0,
                        "missing_count_after": 0,
                        "imputed_count": 0,
                    }
                )
                continue

            if strategy == "impute_zero":
                if not pd.api.types.is_numeric_dtype(work[col]) and not isinstance(
                    work[col].dtype, pd.CategoricalDtype
                ):
                    raise ValueError(
                        f"Column {col!r} has dtype {work[col].dtype!r}; "
                        "impute_zero is only valid for numeric columns."
                    )
                work[col] = work[col].fillna(0)
            elif strategy == "impute_median":
                if not pd.api.types.is_numeric_dtype(work[col]):
                    raise ValueError(
                        f"Column {col!r} has dtype {work[col].dtype!r}; "
                        "impute_median is only valid for numeric columns."
                    )
                median = float(work[col].median(skipna=True))
                work[col] = work[col].fillna(median)
            elif strategy == "impute_mean":
                if not pd.api.types.is_numeric_dtype(work[col]):
                    raise ValueError(
                        f"Column {col!r} has dtype {work[col].dtype!r}; "
                        "impute_mean is only valid for numeric columns."
                    )
                mean = float(work[col].mean(skipna=True))
                work[col] = work[col].fillna(mean)

            miss_after = int(work[col].isna().sum())
            rows_imputed += miss_before - miss_after
            per_column.append(
                {
                    "column": col,
                    "strategy": strategy,
                    "missing_count_before": miss_before,
                    "missing_count_after": miss_after,
                    "imputed_count": miss_before - miss_after,
                }
            )

    rows_after = int(work.shape[0])
    return MissingHandlingResult(
        df=work,
        rows_before=rows_before,
        rows_after=rows_after,
        rows_dropped=rows_dropped,
        rows_imputed=rows_imputed,
        strategy=strategy,
        per_column=per_column,
    )


def count_missing_cells(df: pd.DataFrame, columns: Iterable[str]) -> dict[str, int]:
    """Count missing cells per column in `columns` that exist in `df`.

    Parameters
    ----------
    df : pandas.DataFrame
        Input DataFrame.
    columns : iterable of str
        Columns to inspect.

    Returns
    -------
    dict[str, int]
        ``{column: missing_count}`` for every requested column that
        exists in `df`.
    """
    return {c: int(df[c].isna().sum()) for c in columns if c in df.columns}


def is_identifier_column(column: str) -> bool:
    """Return True if `column` is a known identifier that must not be imputed."""
    return column in IDENTIFIER_COLUMNS


def safe_fillna(series: pd.Series, value: object) -> pd.Series:
    """Fill missing values but raise for identifier columns.

    Parameters
    ----------
    series : pandas.Series
        Input Series.
    value : object
        Fill value.

    Returns
    -------
    pandas.Series
        Series with missing values filled.

    Raises
    ------
    ValueError
        If the column is a known identifier and `value` is not ``NaN``.
    """
    if is_identifier_column(str(series.name)) and not (
        isinstance(value, float) and np.isnan(value)
    ):
        raise ValueError(
            f"Refusing to fill identifier column {series.name!r} with value {value!r}. "
            "Identifiers must not be imputed."
        )
    return series.fillna(value)
