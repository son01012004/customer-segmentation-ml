"""EVA-01 — Experiment Result Repository.

Module-level docstrings follow the per-module AGENTS.md / EPIC-07
constraints. This package ONLY implements EVA-01 scope: collect,
normalize, validate, detect duplicates/missing/invalid/inconsistent
conditions, and emit standardized tables for downstream EVA-* phases.

Hard constraints (AGENTS.md §2):

- No ranking, no "best/winner/optimal/recommended/final" labels.
- No mutation of EPIC-07 artifacts under ``reports/exp0X/``.
- No new dependencies beyond the existing scientific Python stack.
- No "RFM-only" materialization (RFM-only is future work).
- No promotion of ``WORKING_ASSUMPTION`` to ``RESEARCH_APPROVED``.
- All output traceable to source experiment / run.

Submodules
----------
- :mod:`customer_segmentation.evaluation.experiment_results.schema`
    Standardized column schema, field types, ``MISSING`` semantics.
- :mod:`customer_segmentation.evaluation.experiment_results.collectors`
    Functions that read each EPIC-07 source artifact and emit
    rows in the standardized schema.
- :mod:`customer_segmentation.evaluation.experiment_results.repository`
    The :class:`ExperimentResultRepository` — top-level container
    with collection, validation, and serialization methods.
- :mod:`customer_segmentation.evaluation.experiment_results.validation`
    Anomaly / validation report (``MISSING``, ``INVALID``,
    ``DUPLICATE`` (``DUPLICATE_EXACT`` / ``DUPLICATE_BY_INTENT``),
    ``INCONSISTENT_CONDITIONS``).
- :mod:`customer_segmentation.evaluation.experiment_results.summary`
    Summary table builders (per-experiment, per-algorithm, etc.).
- :mod:`customer_segmentation.evaluation.experiment_results.io`
    I/O helpers (read CSV / JSON / manifest; write parquet + MD).
"""

from customer_segmentation.evaluation.experiment_results.repository import (
    ExperimentResultRepository,
    build_repository_from_reports,
)
from customer_segmentation.evaluation.experiment_results.schema import (
    FIELD_TYPES,
    MISSING_INT_REASON_FIELDS,
    REQUIRED_FIELDS,
    STANDARD_COLUMNS,
    SourceExperiment,
)

__all__ = [
    # Schema
    "STANDARD_COLUMNS",
    "REQUIRED_FIELDS",
    "FIELD_TYPES",
    "MISSING_INT_REASON_FIELDS",
    "SourceExperiment",
    # Repository
    "ExperimentResultRepository",
    "build_repository_from_reports",
]
