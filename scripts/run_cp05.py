"""CP-05 runner entrypoint script.

Usage::

    python3 scripts/run_cp05.py [--output-dir PATH] [--no-exp03]
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make src/ importable when run from repo root.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from customer_segmentation.profiling.cp05.runner import (  # noqa: E402
    DEFAULT_OUTPUT_DIR,
    run_cp05,
)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="CP-05 runner")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--no-exp03", action="store_true")
    args = parser.parse_args()

    result = run_cp05(
        output_dir=Path(args.output_dir),
        include_exp03=not args.no_exp03,
    )
    print(
        f"CP-05 complete.\n"
        f"  units:            {result.n_units}\n"
        f"  definitions:      {result.n_definitions}\n"
        f"  output_dir:       {result.output_dir}"
    )


if __name__ == "__main__":
    main()
