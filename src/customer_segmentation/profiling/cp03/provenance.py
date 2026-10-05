"""CP-03 input provenance.

CP-03 reuses CP-02 analysis units directly to guarantee consistency
between CP-02 and CP-03 (no recomputation of cluster statistics, no
parallel labelling pipeline).

Hard constraints (AGENTS.md §2):
- Read-only against EXP-01 / EXP-03 / FE-05 / FE-06 / CP-01 / CP-02
  artifacts.
- No new cluster labels are produced; CP-03 only consumes existing
  analysis units and computes derived indicators.
- K-Medoids is OUT OF SCOPE (per ADR-0003) — same as CP-01/CP-02.
- DBSCAN noise is excluded from cluster statistics; CP-03 inherits
  the CP-02 treatment of noise.
- EXP-03 working-selected labels remain ``NOT_AVAILABLE`` — CP-03
  reports them as such and produces no cluster-level indicators for
  those units.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from customer_segmentation.profiling.cp02.provenance import (
    Cp02AnalysisUnit,
    build_cp02_analysis_units,
)

# CP-03 analysis unit = CP-02 analysis unit. CP-03 adds no
# additional provenance fields; it consumes the same set of analysis
# units (algorithm × condition) as CP-01 and CP-02.
Cp03AnalysisUnit = Cp02AnalysisUnit


def build_cp03_analysis_units(repo_root: Path) -> Sequence[Cp03AnalysisUnit]:
    """Build the CP-03 analysis units (identical to CP-02).

    Returns a list of :class:`Cp02AnalysisUnit` (alias
    :class:`Cp03AnalysisUnit`) with one entry per algorithm × condition.
    The list includes both EXP-01 working-default units (with persisted
    labels) and EXP-03 working-selected units (metadata-only).

    CP-03 does not filter or modify the CP-02 list — the runner applies
    ``include_exp03`` flag downstream to skip the EXP-03 units when
    desired.
    """
    return build_cp02_analysis_units(repo_root)


__all__ = [
    "Cp03AnalysisUnit",
    "build_cp03_analysis_units",
]
