"""Build the customer-level dataset from raw transactions.

Stage: 03_customer_aggregation

Aggregates raw transactions to one row per ``CustomerID``. This is the
intermediate dataset consumed by the feature engineering stage.

TODO
----
- Read cleaned transactions from ``data/interim/``.
- Aggregate to one row per ``CustomerID``.
- Save to ``data/processed/customer_level.parquet``.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = REPO_ROOT / "data" / "interim" / "transactions_clean.parquet"
DEFAULT_OUTPUT = REPO_ROOT / "data" / "processed" / "customer_level.parquet"


def main(input_path: Path = DEFAULT_INPUT, output_path: Path = DEFAULT_OUTPUT) -> None:
    """Aggregate transactions to the customer level.

    Parameters
    ----------
    input_path : pathlib.Path
        Cleaned transactional data.
    output_path : pathlib.Path
        Destination customer-level dataset.

    Notes
    -----
    Placeholder. Implementation is part of the FE-01+ pipeline.
    """
    # TODO: implement customer-level aggregation.
    raise NotImplementedError("build_customer_dataset.main is not implemented yet.")


if __name__ == "__main__":
    main()
