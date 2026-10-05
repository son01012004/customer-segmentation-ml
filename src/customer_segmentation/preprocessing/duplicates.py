"""Duplicate-record handling for FE-02.

The cleaning pipeline distinguishes three notions of "duplicate":

- **Exact-row duplicates**: every column matches. These are always a
  data-quality issue (the same row was emitted twice).
- **Key-subset duplicates**: a chosen key (e.g.
  ``(InvoiceNo, StockCode)``) repeats. Multiple lines per invoice are
  expected, so the *interpretation* of subset duplicates is data-driven
  and reported by :func:`analyse_subset_duplicates`.
- **Full-line-key duplicates**: every business column except CustomerID
  and Country matches (a complete invoice line repeats). These are
  reported but rarely dropped without inspection.

Only :func:`drop_duplicates` is destructive. It returns the cleaned
DataFrame plus a structured :class:`DuplicateResult` so the pipeline
can record exactly what was removed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

__all__ = [
    "DuplicateAnalysis",
    "DuplicateResult",
    "analyse_subset_duplicates",
    "drop_duplicates",
]


KeepMode = Literal["first", "last", "none"]


@dataclass(frozen=True)
class DuplicateAnalysis:
    """Descriptive analysis of subset-key duplicates.

    Attributes
    ----------
    subset : tuple[str, ...]
        Key columns.
    total_rows : int
        Total rows inspected.
    unique_combinations : int
        Distinct values of the key.
    duplicate_rows : int
        Rows that share their key with at least one other row.
    duplicate_groups : int
        Number of distinct groups that contain at least one duplicate.
    max_group_size : int
        Largest number of rows sharing one key.
    """

    subset: tuple[str, ...]
    total_rows: int
    unique_combinations: int
    duplicate_rows: int
    duplicate_groups: int
    max_group_size: int

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dict representation."""
        return {
            "subset": list(self.subset),
            "total_rows": int(self.total_rows),
            "unique_combinations": int(self.unique_combinations),
            "duplicate_rows": int(self.duplicate_rows),
            "duplicate_groups": int(self.duplicate_groups),
            "max_group_size": int(self.max_group_size),
        }


@dataclass
class DuplicateResult:
    """Outcome of a duplicate-removal pass.

    Attributes
    ----------
    df : pandas.DataFrame
        DataFrame after deduplication.
    rows_before : int
        Rows in the input.
    rows_after : int
        Rows in the output.
    rows_removed : int
        Number of rows removed.
    keep : str
        Keep mode that was used (``"first"``, ``"last"``, ``"none"``).
    subset : tuple[str, ...] or None
        Subset of columns used for uniqueness (``None`` means all).
    rule_id : str
        Identifier of the cleaning rule that triggered the removal.
    """

    df: pd.DataFrame
    rows_before: int
    rows_after: int
    rows_removed: int
    keep: str
    subset: tuple[str, ...] | None
    rule_id: str = "CL-09"

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dict representation."""
        return {
            "df": self.df,
            "rows_before": self.rows_before,
            "rows_after": self.rows_after,
            "rows_removed": self.rows_removed,
            "keep": self.keep,
            "subset": list(self.subset) if self.subset is not None else None,
            "rule_id": self.rule_id,
        }


def analyse_subset_duplicates(
    df: pd.DataFrame,
    subset: list[str],
) -> DuplicateAnalysis:
    """Quantify subset-key duplicates without removing anything.

    The semantics mirror :func:`customer_segmentation.data.audit.duplicate_profile`
    (i.e. ``total - df.drop_duplicates(subset=subset).shape[0]``): only
    the rows that duplicate an earlier key are counted, not every row
    in a multi-row group.

    Parameters
    ----------
    df : pandas.DataFrame
        Input DataFrame.
    subset : list[str]
        Columns that define the key.

    Returns
    -------
    DuplicateAnalysis
        Counts of unique combinations, duplicate rows and groups.

    Raises
    ------
    KeyError
        If any column in `subset` is missing from `df`.
    """
    missing = [c for c in subset if c not in df.columns]
    if missing:
        raise KeyError(f"Columns not in DataFrame: {missing}")

    total = int(df.shape[0])
    grouped = df.groupby(subset, dropna=False, sort=False)
    counts = grouped.size()
    n_unique = int(counts.shape[0])
    # Number of rows that are "extra" duplicates (i.e. every row beyond
    # the first one in a multi-row group). Matches FE-01's
    # ``total - n_unique`` semantics.
    n_duplicate_rows = total - n_unique
    dup_mask = counts > 1
    duplicate_groups = int(dup_mask.sum())
    return DuplicateAnalysis(
        subset=tuple(subset),
        total_rows=total,
        unique_combinations=n_unique,
        duplicate_rows=n_duplicate_rows,
        duplicate_groups=duplicate_groups,
        max_group_size=int(counts.max()) if not counts.empty else 0,
    )


def drop_duplicates(
    df: pd.DataFrame,
    subset: list[str] | None = None,
    keep: KeepMode = "first",
    *,
    rule_id: str = "CL-09",
) -> DuplicateResult:
    """Remove duplicate rows.

    Parameters
    ----------
    df : pandas.DataFrame
        Input DataFrame (not mutated).
    subset : list[str], optional
        Columns to consider for uniqueness. ``None`` means all columns.
    keep : {"first", "last", "none"}
        Which occurrence to keep. ``"none"`` drops every duplicated row
        (i.e. rows whose key occurs more than once are all removed).
    rule_id : str, default "CL-09"
        Identifier of the cleaning rule that triggered the removal.
        Used for traceability in the cleaning report.

    Returns
    -------
    DuplicateResult
        Cleaned DataFrame plus a structured report.

    Raises
    ------
    KeyError
        If any column in `subset` is missing from `df`.
    ValueError
        If ``keep`` is not recognised.
    """
    if keep not in {"first", "last", "none"}:
        raise ValueError(f"Unknown keep mode {keep!r}. Valid: 'first', 'last', 'none'.")
    if subset is not None:
        missing = [c for c in subset if c not in df.columns]
        if missing:
            raise KeyError(f"Columns not in DataFrame: {missing}")

    rows_before = int(df.shape[0])

    if keep == "none":
        # Pandas does not support ``keep=False`` directly in drop_duplicates
        # for the rows we want to *keep*. Strategy: mark duplicated rows
        # (every occurrence) and drop them all.
        mask = df.duplicated(subset=subset, keep=False)
        work = df.loc[~mask].reset_index(drop=True)
        rows_removed = int(mask.sum())
    else:
        work = df.drop_duplicates(subset=subset, keep=keep).reset_index(drop=True)
        rows_removed = rows_before - int(work.shape[0])

    return DuplicateResult(
        df=work,
        rows_before=rows_before,
        rows_after=int(work.shape[0]),
        rows_removed=rows_removed,
        keep=keep,
        subset=tuple(subset) if subset is not None else None,
        rule_id=rule_id,
    )


def count_exact_duplicates(df: pd.DataFrame) -> int:
    """Return the number of rows that are exact duplicates of another row.

    The semantics mirror :func:`customer_segmentation.data.audit.duplicate_profile`
    (i.e. ``df.duplicated(keep='first').sum()``): only the rows that
    duplicate an earlier row are counted, **not** the first occurrence.
    """
    return int(df.duplicated(keep="first").sum())


def exact_duplicate_analysis(df: pd.DataFrame) -> dict:
    """Return a small descriptive analysis of exact-row duplicates.

    The semantics mirror :func:`customer_segmentation.data.audit.duplicate_profile`
    (i.e. ``df.duplicated(keep='first').sum()``): only the rows that
    duplicate an earlier row are counted, **not** the first occurrence.

    Returns
    -------
    dict
        ``{"total_rows": int, "duplicate_rows": int,
        "duplicate_groups": int, "max_group_size": int,
        "duplicate_rate_percent": float}``.
    """
    total = int(df.shape[0])
    if total == 0:
        return {
            "total_rows": 0,
            "duplicate_rows": 0,
            "duplicate_groups": 0,
            "max_group_size": 0,
            "duplicate_rate_percent": 0.0,
        }
    # `df.duplicated(keep='first')` returns True for every row that
    # has at least one earlier identical row. This matches the FE-01
    # audit's `duplicate_profile()` exactly.
    dup_mask = df.duplicated(keep="first")
    duplicate_rows = int(dup_mask.sum())
    # Number of distinct groups whose size is > 1.
    if duplicate_rows == 0:
        duplicate_groups = 0
    else:
        duplicate_groups = int(
            df.loc[dup_mask].groupby(list(df.columns), dropna=False, sort=False).ngroups
        )
    return {
        "total_rows": total,
        "duplicate_rows": duplicate_rows,
        "duplicate_groups": duplicate_groups,
        "max_group_size": int(df.groupby(list(df.columns), dropna=False, sort=False).size().max()),
        "duplicate_rate_percent": round(duplicate_rows / total * 100.0, 4),
    }
