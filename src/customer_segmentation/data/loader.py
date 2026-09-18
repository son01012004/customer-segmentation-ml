"""Loading raw datasets into pandas DataFrames.

TODO
----
- Implement `load_raw_transactions(path: Path) -> pd.DataFrame` for both
  primary and backup datasets (Excel via openpyxl).
- Support both `.xlsx` and `.csv` if needed.
- Never hard-code dataset statistics. Only structural loading.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

__all__: list[str] = []


def load_raw_transactions(path: Path) -> pd.DataFrame:
    """Load raw transactional data into a pandas DataFrame.

    Parameters
    ----------
    path : pathlib.Path
        Absolute or relative path to the raw file (xlsx or csv).

    Returns
    -------
    pandas.DataFrame
        Raw transactions in their original form, untouched.

    Raises
    ------
    FileNotFoundError
        If `path` does not exist.
    ValueError
        If the file extension is unsupported.

    Notes
    -----
    This is a placeholder. No I/O is performed yet. Implementation will
    resolve to either openpyxl (xlsx) or pandas csv reader based on suffix.
    """
    # TODO: implement real loading.
    raise NotImplementedError("load_raw_transactions is not implemented yet (FE-01+).")


def list_raw_files(raw_dir: Path) -> list[Path]:
    """List raw dataset files present in `raw_dir`.

    Parameters
    ----------
    raw_dir : pathlib.Path
        Directory to scan (typically ``data/raw/primary`` or ``data/raw/backup``).

    Returns
    -------
    list[pathlib.Path]
        Sorted list of file paths. Empty list if directory is missing.

    Notes
    -----
    Placeholder implementation. Excludes hidden files and `.gitkeep`.
    """
    # TODO: implement directory scan.
    raise NotImplementedError("list_raw_files is not implemented yet.")
