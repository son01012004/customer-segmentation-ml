"""Loading raw datasets into pandas DataFrames.

FE-01 (Raw Dataset Audit): real loading for `.xlsx` files via openpyxl.

Notes
-----
- The loader never mutates the raw file.
- It returns a `pandas.DataFrame` whose columns follow the casing and
  naming that the raw file actually uses. Canonical renaming belongs to
  the **preprocessing** stage (PR-XX), not to FE-01.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

__all__ = ["load_raw_transactions", "list_raw_files", "list_sheet_names"]


def load_raw_transactions(
    path: Path | str,
    sheet_name: str | int = 0,
    *,
    engine: str = "openpyxl",
) -> pd.DataFrame:
    """Load a raw transactional Excel file into a pandas DataFrame.

    Parameters
    ----------
    path : pathlib.Path or str
        Path to the raw file. Only ``.xlsx`` is supported in FE-01.
    sheet_name : str or int, default 0
        Sheet to read. For the Primary dataset there is a single sheet
        ``"Online Retail"``. For the Backup dataset there are two sheets
        (``"Year 2009-2010"`` and ``"Year 2010-2011"``); the caller must
        decide which one (or both) to read.
    engine : str, default "openpyxl"
        Excel engine passed through to ``pandas.read_excel``.

    Returns
    -------
    pandas.DataFrame
        Raw transactions in their original column casing and order.

    Raises
    ------
    FileNotFoundError
        If `path` does not exist.
    ValueError
        If the file extension is not ``.xlsx``.

    Notes
    -----
    This loader performs **no transformation**: no rename, no dtype
    coercion beyond what ``read_excel`` does by default, no aggregation,
    no filtering. Anything beyond that belongs to the preprocessing
    stage.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Raw dataset not found: {p}")
    if p.suffix.lower() != ".xlsx":
        raise ValueError(
            f"Unsupported raw file extension {p.suffix!r}; only .xlsx is supported in FE-01."
        )
    return pd.read_excel(p, sheet_name=sheet_name, engine=engine)


def list_sheet_names(path: Path | str, *, engine: str = "openpyxl") -> list[str]:
    """Return the list of sheet names in an Excel file.

    Parameters
    ----------
    path : pathlib.Path or str
        Path to the raw file.
    engine : str, default "openpyxl"
        Excel engine passed through to ``pandas.ExcelFile``.

    Returns
    -------
    list[str]
        Sheet names in workbook order.

    Raises
    ------
    FileNotFoundError
        If `path` does not exist.
    ValueError
        If the file extension is not ``.xlsx``.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Raw dataset not found: {p}")
    if p.suffix.lower() != ".xlsx":
        raise ValueError(
            f"Unsupported raw file extension {p.suffix!r}; only .xlsx is supported in FE-01."
        )
    with pd.ExcelFile(p, engine=engine) as xl:
        return list(xl.sheet_names)


def list_raw_files(raw_dir: Path | str) -> list[Path]:
    """List raw dataset files present in `raw_dir`.

    Parameters
    ----------
    raw_dir : pathlib.Path or str
        Directory to scan (typically ``data/raw/primary`` or
        ``data/raw/backup``).

    Returns
    -------
    list[pathlib.Path]
        Sorted list of file paths. Hidden files and ``.gitkeep`` are
        excluded. Empty list if directory is missing.
    """
    d = Path(raw_dir)
    if not d.exists():
        return []
    return sorted(p for p in d.iterdir() if p.is_file() and not p.name.startswith("."))
