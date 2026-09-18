"""Build the RFM feature table.

Stage: 04_rfm_features

Reads cleaned transactions and writes a customer-level RFM table.

TODO
----
- Wire up `features.rfm.build_rfm`.
- Save to ``data/processed/rfm.parquet``.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = REPO_ROOT / "data" / "interim" / "transactions_clean.parquet"
DEFAULT_OUTPUT = REPO_ROOT / "data" / "processed" / "rfm.parquet"


def main(input_path: Path = DEFAULT_INPUT, output_path: Path = DEFAULT_OUTPUT) -> None:
    """Build the RFM feature table.

    Parameters
    ----------
    input_path : pathlib.Path
        Cleaned transactional data.
    output_path : pathlib.Path
        Destination RFM table.

    Notes
    -----
    Placeholder. Implementation is part of the FE-01+ pipeline.
    """
    # TODO: implement RFM table construction.
    raise NotImplementedError("build_rfm_features.main is not implemented yet.")


if __name__ == "__main__":
    main()
