"""Reusable raw-dataset audit functions for FE-01.

This module exposes **read-only** statistics that summarise the raw
primary (and, for comparison, backup) dataset. It never mutates the
input DataFrame.

The functions are deliberately generic so they can be reused both from
``scripts/run_fe01_audit.py`` and from
``notebooks/01_dataset_audit/01_audit.ipynb``.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd

__all__ = [
    "basic_overview",
    "missing_profile",
    "numerical_profile",
    "categorical_profile",
    "date_profile",
    "identifier_profile",
    "duplicate_profile",
    "frequency_table",
    "AuditSummary",
]


# ---------------------------------------------------------------------------
# Containers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuditSummary:
    """Top-level overview of one dataset (or one sheet)."""

    n_rows: int
    n_columns: int
    column_names: tuple[str, ...]
    dtypes: dict[str, str]
    memory_bytes: int


# ---------------------------------------------------------------------------
# Basic overview
# ---------------------------------------------------------------------------


def basic_overview(df: pd.DataFrame) -> AuditSummary:
    """Return a top-level structural summary of `df`.

    Parameters
    ----------
    df : pandas.DataFrame
        Raw DataFrame to summarise.

    Returns
    -------
    AuditSummary
        Row count, column count, column names, dtype strings, memory.
    """
    return AuditSummary(
        n_rows=int(df.shape[0]),
        n_columns=int(df.shape[1]),
        column_names=tuple(str(c) for c in df.columns),
        dtypes={str(c): str(df[c].dtype) for c in df.columns},
        memory_bytes=int(df.memory_usage(deep=True).sum()),
    )


# ---------------------------------------------------------------------------
# Missing-value profile
# ---------------------------------------------------------------------------


def missing_profile(df: pd.DataFrame) -> pd.DataFrame:
    """Per-column missing count and rate.

    Parameters
    ----------
    df : pandas.DataFrame
        Raw DataFrame.

    Returns
    -------
    pandas.DataFrame
        Columns: ``column``, ``missing_count``, ``missing_rate``,
        ``present_count``, ``total_rows``. Sorted by ``missing_count``
        descending so the worst columns appear first.
    """
    total = len(df)
    records = []
    for col in df.columns:
        miss = int(df[col].isna().sum())
        rate = (miss / total * 100.0) if total else 0.0
        records.append(
            {
                "column": str(col),
                "missing_count": miss,
                "missing_rate": round(rate, 4),
                "present_count": total - miss,
                "total_rows": total,
            }
        )
    out = pd.DataFrame.from_records(records)
    out = out.sort_values(["missing_count", "column"], ascending=[False, True]).reset_index(
        drop=True
    )
    return out


# ---------------------------------------------------------------------------
# Numerical profile
# ---------------------------------------------------------------------------


_NUMERIC_QUANTILES = (0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99)


def numerical_profile(df: pd.DataFrame, columns: Sequence[str] | None = None) -> pd.DataFrame:
    """Per-numeric-column descriptive statistics.

    Parameters
    ----------
    df : pandas.DataFrame
        Raw DataFrame.
    columns : sequence of str, optional
        Subset of columns to summarise. If ``None``, all numeric
        columns are used.

    Returns
    -------
    pandas.DataFrame
        One row per column with: ``column``, ``count``, ``missing_count``,
        ``min``, ``max``, ``mean``, ``median``, ``std``,
        ``q01``, ``q05``, ``q25``, ``q50``, ``q75``, ``q95``, ``q99``,
        ``zero_count``, ``negative_count``.
    """
    if columns is None:
        columns = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    records: list[dict] = []
    for col in columns:
        s = df[col]
        miss = int(s.isna().sum())
        non_na = s.dropna()
        if non_na.empty:
            row = {
                "column": str(col),
                "count": 0,
                "missing_count": miss,
                "min": np.nan,
                "max": np.nan,
                "mean": np.nan,
                "median": np.nan,
                "std": np.nan,
                "q01": np.nan,
                "q05": np.nan,
                "q25": np.nan,
                "q50": np.nan,
                "q75": np.nan,
                "q95": np.nan,
                "q99": np.nan,
                "zero_count": 0,
                "negative_count": 0,
            }
        else:
            qs = non_na.quantile(_NUMERIC_QUANTILES)
            row = {
                "column": str(col),
                "count": int(non_na.shape[0]),
                "missing_count": miss,
                "min": _to_float(non_na.min()),
                "max": _to_float(non_na.max()),
                "mean": _to_float(non_na.mean()),
                "median": _to_float(non_na.median()),
                "std": _to_float(non_na.std()),
                "q01": _to_float(qs.loc[0.01]) if 0.01 in qs.index else _to_float(non_na.min()),
                "q05": _to_float(qs.loc[0.05]) if 0.05 in qs.index else _to_float(non_na.min()),
                "q25": _to_float(qs.loc[0.25]) if 0.25 in qs.index else _to_float(non_na.min()),
                "q50": _to_float(qs.loc[0.50]) if 0.50 in qs.index else _to_float(non_na.median()),
                "q75": _to_float(qs.loc[0.75]) if 0.75 in qs.index else _to_float(non_na.max()),
                "q95": _to_float(qs.loc[0.95]) if 0.95 in qs.index else _to_float(non_na.max()),
                "q99": _to_float(qs.loc[0.99]) if 0.99 in qs.index else _to_float(non_na.max()),
                "zero_count": int((non_na == 0).sum()),
                "negative_count": int((non_na < 0).sum()),
            }
        records.append(row)
    return pd.DataFrame.from_records(records)


def _to_float(x) -> float:
    """Cast a numpy/python scalar to float; return NaN for non-finite."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return float("nan")
    return v


# ---------------------------------------------------------------------------
# Categorical / object profile
# ---------------------------------------------------------------------------


def categorical_profile(
    df: pd.DataFrame,
    columns: Sequence[str] | None = None,
    *,
    top_k: int = 10,
) -> pd.DataFrame:
    """Per-categorical-column uniqueness and top categories.

    Parameters
    ----------
    df : pandas.DataFrame
        Raw DataFrame.
    columns : sequence of str, optional
        Subset of columns to summarise. If ``None``, all object/string
        columns are used.
    top_k : int, default 10
        How many top values to include in the ``top_values`` column,
        encoded as ``"value:count;value:count;..."``.

    Returns
    -------
    pandas.DataFrame
        Columns: ``column``, ``count``, ``missing_count``, ``unique_count``,
        ``top_values``.
    """
    if columns is None:
        columns = [
            c
            for c in df.columns
            if pd.api.types.is_object_dtype(df[c]) or pd.api.types.is_string_dtype(df[c])
        ]
    records: list[dict] = []
    for col in columns:
        s = df[col]
        miss = int(s.isna().sum())
        non_na = s.dropna()
        if non_na.empty:
            top_str = ""
            uniq = 0
        else:
            counts = non_na.value_counts().head(top_k)
            uniq = int(non_na.nunique())
            top_str = ";".join(f"{str(k)}:{int(v)}" for k, v in counts.items())
        records.append(
            {
                "column": str(col),
                "count": int(non_na.shape[0]),
                "missing_count": miss,
                "unique_count": uniq,
                "top_values": top_str,
            }
        )
    return pd.DataFrame.from_records(records)


def frequency_table(s: pd.Series, top_k: int | None = None) -> pd.DataFrame:
    """Build a (value, count, rate) frequency table for one Series.

    Parameters
    ----------
    s : pandas.Series
        Series of categorical/string values.
    top_k : int, optional
        If given, keep only the top_k most frequent values.

    Returns
    -------
    pandas.DataFrame
        ``value``, ``count``, ``rate`` (percent).
    """
    s = s.dropna()
    total = int(s.shape[0])
    counts = s.value_counts()
    if top_k is not None:
        counts = counts.head(top_k)
    out = counts.rename("count").reset_index().rename(columns={"index": "value"})
    out["rate"] = (out["count"] / total * 100.0).round(4) if total else 0.0
    return out


# ---------------------------------------------------------------------------
# Date profile
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DateProfile:
    """Summary of a datetime column."""

    column: str
    parsed_count: int
    unparsed_count: int
    total: int
    min: datetime | None
    max: datetime | None
    duplicate_timestamps: int


def date_profile(df: pd.DataFrame, column: str) -> DateProfile:
    """Inspect a single datetime column.

    Parameters
    ----------
    df : pandas.DataFrame
        Raw DataFrame.
    column : str
        Column to inspect. The function attempts to coerce the column to
        datetime via ``pandas.to_datetime(..., errors='coerce')`` —
        non-parseable values become ``NaT`` and are counted as
        ``unparsed``.

    Returns
    -------
    DateProfile
        Parsed / unparsed counts, min/max dates, and the number of
        values that share their exact timestamp with another row.
    """
    if column not in df.columns:
        raise KeyError(f"Column {column!r} not in DataFrame.")
    parsed = pd.to_datetime(df[column], errors="coerce")
    parsed_count = int(parsed.notna().sum())
    unparsed_count = int(parsed.isna().sum() - int(df[column].isna().sum()))
    unparsed_count = max(unparsed_count, 0)
    if parsed_count:
        dups = int(parsed.duplicated(keep=False).sum())
        return DateProfile(
            column=column,
            parsed_count=parsed_count,
            unparsed_count=unparsed_count,
            total=int(df.shape[0]),
            min=parsed.min().to_pydatetime(),
            max=parsed.max().to_pydatetime(),
            duplicate_timestamps=dups,
        )
    return DateProfile(
        column=column,
        parsed_count=0,
        unparsed_count=unparsed_count,
        total=int(df.shape[0]),
        min=None,
        max=None,
        duplicate_timestamps=0,
    )


# ---------------------------------------------------------------------------
# Identifier profile
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IdentifierProfile:
    """Uniqueness summary for a column treated as an identifier."""

    column: str
    total: int
    missing_count: int
    unique_count: int
    duplicate_count: int
    unique_rate: float
    is_unique: bool
    sample_values: tuple[object, ...]


def identifier_profile(df: pd.DataFrame, column: str) -> IdentifierProfile:
    """Quantify uniqueness and missingness for one identifier-like column.

    Parameters
    ----------
    df : pandas.DataFrame
        Raw DataFrame.
    column : str
        Column to inspect.

    Returns
    -------
    IdentifierProfile
        ``unique_count``, ``duplicate_count``, ``unique_rate`` (percent),
        ``is_unique`` (unique_count == total - missing_count), and a
        small sample of values for inspection.
    """
    if column not in df.columns:
        raise KeyError(f"Column {column!r} not in DataFrame.")
    s = df[column]
    miss = int(s.isna().sum())
    non_na = s.dropna()
    uniq = int(non_na.nunique())
    total_non_na = int(non_na.shape[0])
    dup = total_non_na - uniq
    rate = (uniq / total_non_na * 100.0) if total_non_na else 0.0
    sample = tuple(non_na.head(3).tolist())
    return IdentifierProfile(
        column=column,
        total=int(df.shape[0]),
        missing_count=miss,
        unique_count=uniq,
        duplicate_count=dup,
        unique_rate=round(rate, 4),
        is_unique=(uniq == total_non_na and total_non_na > 0),
        sample_values=sample,
    )


# ---------------------------------------------------------------------------
# Duplicate profile
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DuplicateProfile:
    """Row-level and key-level duplicate summary."""

    exact_duplicate_rows: int
    exact_duplicate_row_rate: float
    key_subset: tuple[str, ...] | None
    key_duplicate_rows: int
    key_unique_combinations: int


def duplicate_profile(
    df: pd.DataFrame,
    subset: Sequence[str] | None = None,
) -> DuplicateProfile:
    """Count exact-row duplicates and (optionally) key-subset duplicates.

    Parameters
    ----------
    df : pandas.DataFrame
        Raw DataFrame.
    subset : sequence of str, optional
        Columns that define a "logical key". If provided, the function
        also reports how many rows share the same key combination.

    Returns
    -------
    DuplicateProfile
        Exact-row duplicate count + rate, and key-subset duplicate
        count + unique-key count.
    """
    total = int(df.shape[0])
    exact_dup = int(df.duplicated().sum())
    exact_rate = (exact_dup / total * 100.0) if total else 0.0
    if subset is None:
        return DuplicateProfile(
            exact_duplicate_rows=exact_dup,
            exact_duplicate_row_rate=round(exact_rate, 4),
            key_subset=None,
            key_duplicate_rows=0,
            key_unique_combinations=0,
        )
    sub = list(subset)
    n_uniq = int(df.drop_duplicates(subset=sub).shape[0])
    key_dup = total - n_uniq
    return DuplicateProfile(
        exact_duplicate_rows=exact_dup,
        exact_duplicate_row_rate=round(exact_rate, 4),
        key_subset=tuple(sub),
        key_duplicate_rows=key_dup,
        key_unique_combinations=n_uniq,
    )


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------


def coerce_object_dtype_strings(df: pd.DataFrame) -> pd.DataFrame:
    """Return a shallow copy of `df` with object columns cast to ``string``.

    Parameters
    ----------
    df : pandas.DataFrame
        Raw DataFrame.

    Returns
    -------
    pandas.DataFrame
        Copy whose object columns are ``pd.StringDtype()``. Used only
        for cleaner inspection in notebooks/reports; no other side
        effects.
    """
    out = df.copy(deep=False)
    for c in out.columns:
        if pd.api.types.is_object_dtype(out[c]):
            out[c] = out[c].astype("string")
    return out


def detect_string_pattern(s: pd.Series, n: int = 5) -> list[tuple[object, int]]:
    """Detect values that look like strings hidden inside a numeric column.

    Parameters
    ----------
    s : pandas.Series
        Numeric-looking column. The function looks at the original
        DataFrame values (before dtype coercion) and reports values
        whose Python type is not ``int``/``float``.
    n : int, default 5
        Max number of examples to return.

    Returns
    -------
    list[(value, count)]
        Up to ``n`` suspicious values with their counts.

    Notes
    -----
    Designed for use with ``InvoiceNo`` to detect cancellations written
    as ``"Cxxxxx"`` even when the rest of the column is numeric.
    """
    if not hasattr(s, "iloc"):
        raise TypeError("s must be a pandas Series.")
    raw = s.iloc[: min(len(s), 200000)]  # bound work for very large files
    suspicious = raw[~raw.apply(lambda v: isinstance(v, (int, float)))]
    if suspicious.empty:
        return []
    counts = suspicious.value_counts().head(n)
    return [(v, int(c)) for v, c in counts.items()]


def looks_like_cancellation_prefix(s: pd.Series, prefix: str = "C") -> dict:
    """Check whether any value starts with ``prefix`` (e.g. cancelled invoice).

    Parameters
    ----------
    s : pandas.Series
        Series to scan.
    prefix : str, default "C"
        Prefix that signals a cancellation in invoice numbers.

    Returns
    -------
    dict
        ``{"n_matching": int, "examples": list[str], "rate_percent": float}``.
    """
    raw = s.dropna()
    if raw.empty:
        return {"n_matching": 0, "examples": [], "rate_percent": 0.0}
    as_str = raw.astype(str)
    mask = as_str.str.startswith(prefix)
    n = int(mask.sum())
    examples = as_str[mask].head(5).tolist()
    return {
        "n_matching": n,
        "examples": examples,
        "rate_percent": round(n / len(as_str) * 100.0, 4),
    }


def safe_quantile(s: pd.Series, q: float) -> float:
    """Return the ``q``-quantile of ``s`` (NaN-safe) or NaN."""
    non_na = s.dropna()
    if non_na.empty:
        return float("nan")
    return float(non_na.quantile(q))


def select_columns_by_dtype(df: pd.DataFrame, kind: str) -> list[str]:
    """Return the list of columns whose dtype matches ``kind``.

    Parameters
    ----------
    df : pandas.DataFrame
        Raw DataFrame.
    kind : str
        One of: ``"numeric"``, ``"integer"``, ``"float"``, ``"object"``,
        ``"string"``, ``"datetime"``, ``"bool"``.

    Returns
    -------
    list[str]
        Column names whose dtype matches ``kind``.
    """
    checkers = {
        "numeric": pd.api.types.is_numeric_dtype,
        "integer": pd.api.types.is_integer_dtype,
        "float": pd.api.types.is_float_dtype,
        "object": pd.api.types.is_object_dtype,
        "string": pd.api.types.is_string_dtype,
        "datetime": pd.api.types.is_datetime64_any_dtype,
        "bool": pd.api.types.is_bool_dtype,
    }
    if kind not in checkers:
        raise ValueError(f"Unknown kind {kind!r}; valid: {sorted(checkers.keys())}")
    checker = checkers[kind]
    return [c for c in df.columns if checker(df[c])]


def ensure_iterable(x) -> Iterable:
    """Pass-through helper for column lists."""
    return x if isinstance(x, Iterable) and not isinstance(x, str) else [x]
