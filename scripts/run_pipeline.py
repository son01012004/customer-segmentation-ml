"""Run the full research pipeline end-to-end.

Drives preprocessing -> feature engineering -> transformation -> clustering
-> evaluation -> profiling -> visualization, using the YAML configurations
under ``configs/``.

TODO
----
- Wire each stage to its module in ``src/customer_segmentation``.
- Honor ``experiment.yaml`` toggles.
- Write logs to ``docs/experiment_logs/``.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIGS_DIR = REPO_ROOT / "configs"


def main(configs_dir: Path = CONFIGS_DIR) -> None:
    """Run the full pipeline.

    Parameters
    ----------
    configs_dir : pathlib.Path
        Directory containing the YAML configuration files.

    Notes
    -----
    Placeholder. Implementation is part of the FE-01+ pipeline.
    """
    # TODO: implement pipeline orchestration.
    raise NotImplementedError("run_pipeline.main is not implemented yet.")


if __name__ == "__main__":
    main()
