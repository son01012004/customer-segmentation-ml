"""Audit the raw datasets.

Stage: 01_dataset_audit

This script inspects the raw primary (and optionally backup) datasets and
produces a structured audit report under ``reports/dataset_audit/``.

TODO
----
- Wire up `data.loader.load_raw_transactions`.
- Emit CSV/JSON summaries (row counts, missing-value table, date range, ...).
- Do NOT compute or store any fake statistics.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_DIR = REPO_ROOT / "data" / "raw" / "primary"
DEFAULT_REPORT_DIR = REPO_ROOT / "reports" / "dataset_audit"


def main(raw_dir: Path = DEFAULT_RAW_DIR, report_dir: Path = DEFAULT_REPORT_DIR) -> None:
    """Run the dataset audit.

    Parameters
    ----------
    raw_dir : pathlib.Path
        Directory holding the raw files.
    report_dir : pathlib.Path
        Directory where audit reports are written.

    Notes
    -----
    Placeholder. Implementation is part of the FE-01+ pipeline.
    """
    # TODO: implement dataset audit.
    raise NotImplementedError("audit_dataset.main is not implemented yet.")


if __name__ == "__main__":
    main()
