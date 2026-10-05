"""EVA-03 — Stability & Reproducibility Evaluation.

Module-level docstrings follow the per-module AGENTS.md / EPIC-08
constraints. This package implements the RQ3 analysis: ARI / AMI /
NMI / Hungarian label-alignment over the EXP-05 raw stability
evidence (Block R, Block S, Block N), plus a descriptive
comparison of EXP-01 baseline metrics vs EXP-03 working-selected
metadata.

Hard constraints (AGENTS.md §2 / EPIC-08 boundary in
``configs/exp05_stability_reproducibility.yaml``):

- Read-only against EXP-05 / EXP-01 / EXP-03 artifacts.
- No ranking, no "best/winner/optimal/recommended/final" labels.
- No composite stability score.
- No promotion of ``WORKING_SELECTED`` to ``RESEARCH_APPROVED``.
- ARI / AMI / NMI are permutation-invariant by construction;
  Hungarian matching is DESCRIPTIVE only — provides per-cluster
  correspondence, NOT a stability metric.
- All comparisons traceable to a source experiment / run_id.

Submodules
----------
- :mod:`customer_segmentation.evaluation.eva03.load`
    Loaders for EXP-05 labels and per-block aggregates, EXP-01
    cluster labels, EXP-03 working-selected metadata.
- :mod:`customer_segmentation.evaluation.eva03.label_compare`
    ARI / AMI / NMI / Hungarian matching primitives.
- :mod:`customer_segmentation.evaluation.eva03.reproducibility`
    Block R reproducibility evidence.
- :mod:`customer_segmentation.evaluation.eva03.seed_stability`
    Block S seed stability evidence.
- :mod:`customer_segmentation.evaluation.eva03.perturbation`
    Block N perturbation robustness evidence.
- :mod:`customer_segmentation.evaluation.eva03.hyperparameter_stability`
    EXP-01 default vs EXP-03 working-selected metadata comparison.
- :mod:`customer_segmentation.evaluation.eva03.report`
    Markdown report builders for stability / reproducibility /
    comparison.
- :mod:`customer_segmentation.evaluation.eva03.runner`
    Top-level orchestration.
"""

from customer_segmentation.evaluation.eva03.runner import (
    Eva03Config,
    Eva03Runner,
    run_eva03,
)

__all__ = [
    "Eva03Config",
    "Eva03Runner",
    "run_eva03",
]
