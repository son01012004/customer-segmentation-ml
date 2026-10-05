"""Load the EVA-01 standardised repository from disk.

EVA-02 only READS the EVA-01 outputs (parquet / CSV) and never mutates
them. The loading layer is intentionally tolerant: it accepts either
the parquet (preferred — preserves dtypes) or the CSV (fallback) and
returns a :class:`pandas.DataFrame` ready for comparison / analysis.

Hard constraints (AGENTS.md §2):

- No mutation of source EVA-01 artifacts.
- No synthetic rows; rows come exclusively from the loaded file.
- The DataFrame carries the EVA-01 standard schema as-is, including
  the literal ``MISSING`` sentinel for fields that are not applicable
  to a particular experiment.

Notes
-----

The loading functions DO NOT silently fill missing metric values.
Callers must filter the loaded DataFrame using
:func:`filter_metric_rows` (see :mod:`metrics`) before drawing any
quality conclusion.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from customer_segmentation.evaluation.experiment_results.schema import (
    MISSING,
    STANDARD_COLUMNS,
)

__all__ = [
    "DEFAULT_EVA01_DIR",
    "REPOSITORY_PARQUET_NAME",
    "REPOSITORY_CSV_NAME",
    "load_repository",
    "load_repository_parquet",
    "load_repository_csv",
    "list_experiment_ids",
    "list_algorithms",
]


# Default location of EVA-01 outputs (matches run_eva01.py default).
DEFAULT_EVA01_DIR: Path = Path("reports/evaluation/eva01")

# Filenames emitted by run_eva01.py (kept here as constants so callers
# don't have to memorise them).
REPOSITORY_PARQUET_NAME: str = "eva01_experiment_repository.parquet"
REPOSITORY_CSV_NAME: str = "eva01_experiment_repository.csv"


def _coerce_loaded_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Restore the ``MISSING`` literal for string columns lost in parquet round-trip.

    Parquet round-trip can rewrite the literal ``MISSING`` to
    ``None`` for some columns; this helper re-applies the sentinel
    where the standard schema expects a string column. Numeric
    columns stay as ``NaN`` because the schema's nullable dtypes
    already use ``pd.NA`` / ``NaN`` for missing numerics.
    """
    if df.empty:
        return df

    # Re-apply MISSING for object/string columns where the standard
    # schema expects a literal ``MISSING`` sentinel. We only rewrite
    # values that are currently ``None`` / NaN; real data is preserved.
    for col in df.columns:
        if col not in STANDARD_COLUMNS:
            continue
        if df[col].dtype == "object":
            df[col] = df[col].where(df[col].notna(), MISSING)
    return df


def load_repository_parquet(path: Path | str) -> pd.DataFrame:
    """Load the standardised repository from a parquet file.

    Parameters
    ----------
    path : path-like
        Absolute or relative path to ``eva01_experiment_repository.parquet``.

    Returns
    -------
    pandas.DataFrame
        Standardised repository with the EVA-01 schema.
    """
    path = Path(path)
    df = pd.read_parquet(path)
    return _coerce_loaded_frame(df)


def load_repository_csv(path: Path | str) -> pd.DataFrame:
    """Load the standardised repository from a CSV file.

    CSV round-trip preserves the literal ``MISSING`` string, so this
    helper does not need to rewrite anything.
    """
    path = Path(path)
    df = pd.read_csv(path)
    return _coerce_loaded_frame(df)


def load_repository(
    eva01_dir: Path | str = DEFAULT_EVA01_DIR,
    *,
    prefer_parquet: bool = True,
) -> pd.DataFrame:
    """Load the EVA-01 repository, preferring parquet when available.

    Parameters
    ----------
    eva01_dir : path-like
        Directory containing ``eva01_experiment_repository.parquet``
        (and optionally a CSV twin).
    prefer_parquet : bool, default True
        If True and the parquet file exists, return the parquet.
        If False, force CSV loading (useful for tests / debugging).

    Returns
    -------
    pandas.DataFrame
        Standardised repository.

    Raises
    ------
    FileNotFoundError
        Neither the parquet nor the CSV file exists under ``eva01_dir``.
    """
    eva01_dir = Path(eva01_dir)
    parquet_path = eva01_dir / REPOSITORY_PARQUET_NAME
    csv_path = eva01_dir / REPOSITORY_CSV_NAME

    if prefer_parquet and parquet_path.exists():
        return load_repository_parquet(parquet_path)
    if csv_path.exists():
        return load_repository_csv(csv_path)
    raise FileNotFoundError(
        f"EVA-01 repository not found under {eva01_dir}. "
        f"Expected one of: {parquet_path} or {csv_path}."
    )


# ---------------------------------------------------------------------------
# Convenience accessors
# ---------------------------------------------------------------------------


def list_experiment_ids(df: pd.DataFrame) -> list[str]:
    """Return the sorted list of unique source experiments in the repository."""
    return sorted(df["source_experiment"].dropna().unique().tolist())


def list_algorithms(df: pd.DataFrame) -> list[str]:
    """Return the sorted list of unique algorithm names in the repository."""
    return sorted(df["algorithm"].dropna().unique().tolist())


def iter_by_experiment(
    df: pd.DataFrame, experiments: Iterable[str] | None = None
) -> Iterable[tuple[str, pd.DataFrame]]:
    """Yield (source_experiment, subframe) pairs.

    Used to drive per-experiment comparison / analysis. If
    ``experiments`` is None, yields all source experiments present
    in ``df``.
    """
    wanted = set(experiments) if experiments is not None else None
    for exp, group in df.groupby("source_experiment", dropna=False):
        if wanted is not None and exp not in wanted:
            continue
        yield exp, group
