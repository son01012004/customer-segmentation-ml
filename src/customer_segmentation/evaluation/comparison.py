"""Cross-algorithm comparison tables.

TODO
----
- Implement `compare_algorithms(results_per_algorithm) -> pandas.DataFrame`
  that produces a single tidy table indexed by algorithm with columns for
  internal metrics, stability, and runtime.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

__all__: list[str] = []


def compare_algorithms(results_per_algorithm: dict[str, dict[str, Any]]) -> pd.DataFrame:
    """Build a comparison table across clustering algorithms.

    Parameters
    ----------
    results_per_algorithm : dict[str, dict[str, Any]]
        Mapping of algorithm name to its evaluation result dictionary.

    Returns
    -------
    pandas.DataFrame
        Tidy comparison table.

    Notes
    -----
    Placeholder. Implementation will be added in the evaluation stage.
    """
    # TODO: implement comparison table assembly.
    raise NotImplementedError("compare_algorithms is not implemented yet.")
