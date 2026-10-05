"""EVA-02 — Cluster Quality Evaluation.

Module-level docstrings follow the per-module AGENTS.md / EPIC-07
constraints. This package ONLY implements EVA-02 scope: load the
EVA-01 standardised repository, build comparison tables per
(algorithm, K, hyperparameters, preprocessing, feature set), emit
descriptive quality analysis, and produce a narrative Markdown
report plus visualisations.

Hard constraints (AGENTS.md §2):

- Read-only against EVA-01 outputs (no mutation of source artifacts).
- No ranking, no "best/winner/optimal/recommended/final" labels.
- No composite score.
- No promotion of ``WORKING_SELECTED`` to ``RESEARCH_APPROVED``.
- All comparisons traceable to source experiment / run.

Submodules
----------
- :mod:`customer_segmentation.evaluation.eva02.load`
    Functions to load the EVA-01 standardised dataset from disk.
- :mod:`customer_segmentation.evaluation.eva02.metrics`
    Internal metric helpers and metric row extraction.
- :mod:`customer_segmentation.evaluation.eva02.comparison`
    Per-algorithm / per-K / per-hyperparameter / per-preprocessing
    comparison tables.
- :mod:`customer_segmentation.evaluation.eva02.quality`
    Quality analysis (metric distributions, conflicts, anomalies).
- :mod:`customer_segmentation.evaluation.eva02.visualization`
    Matplotlib-based figures; single source of cluster colors / labels.
- :mod:`customer_segmentation.evaluation.eva02.report`
    Markdown report builder.
- :mod:`customer_segmentation.evaluation.eva02.runner`
    Top-level orchestration: load → compare → analyse → render →
    write outputs.
"""

from customer_segmentation.evaluation.eva02.runner import (
    Eva02Runner,
    run_eva02,
)

__all__ = [
    "Eva02Runner",
    "run_eva02",
]
