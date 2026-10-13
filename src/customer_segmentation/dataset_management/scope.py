"""Scope and lifecycle enums for DEV-02 Dataset Management.

Three independent enums:

- :class:`DatasetScope`  — the *scope* of a dataset in the prototype
  storage layer. Currently only ``IMPORTED_PROTOTYPE`` is in use; the
  enum is defined to keep room for future values without changing the
  manifest schema.

- :class:`ValidationStatus` — the *lifecycle status* of a single
  dataset over time. Distinct from :class:`ValidationResult`: a
  ``ValidationStatus`` is what the manifest stores; a
  ``ValidationResult`` is what a single validation pass returns.

- :class:`ValidationResult` — the *per-pass outcome* of one
  validation pass. ``PASS`` / ``WARNING`` / ``FAIL``.

Why an enum (and not just a string)
-----------------------------------
Using a string-valued :class:`Enum` (the ``str, Enum`` mixin) gives
us both the `==` semantics of strings and the type-checkable
membership in a closed set. It also mirrors the
:class:`frozenset`-based convention used by
:mod:`customer_segmentation.config.loader`.

Hard rules (per docs/system/DEV-02_dataset_management.md §6.1)
-------------------------------------------------------------
- The CLI does **not** expose any way for a user to change
  ``DatasetScope`` of a manifest. The value is always
  ``IMPORTED_PROTOTYPE``.
- ``ValidationStatus`` is a property of a dataset, not a property
  of the dataset's contents. The same DataFrame content re-imported
  twice has the same ``ValidationStatus`` (post-validation).
"""

from __future__ import annotations

from enum import Enum
from typing import Final

__all__ = [
    "DatasetScope",
    "ValidationStatus",
    "ValidationResult",
    "DATASET_SCOPES",
    "VALIDATION_STATUSES",
    "VALIDATION_RESULTS",
]


class DatasetScope(str, Enum):
    """Scope of a dataset in the prototype storage layer.

    Attributes
    ----------
    IMPORTED_PROTOTYPE : str
        The only value currently in use. Implies that the dataset was
        added by the DEV-02 CLI from a user-supplied CSV or Parquet
        file. It is **not** a research dataset; it has not been
        promoted by the research methodology.
    """

    IMPORTED_PROTOTYPE = "IMPORTED_PROTOTYPE"


DATASET_SCOPES: Final[frozenset[str]] = frozenset(s.value for s in DatasetScope)


class ValidationStatus(str, Enum):
    """Lifecycle status of a single dataset over time.

    The state machine is::

        NOT_VALIDATED  ->  VALIDATING  ->  VALID
                                  |
                                  +----------->  FAILED

    Attributes
    ----------
    NOT_VALIDATED : str
        Manifest written; no validation run has occurred yet. Not
        reachable from the public import API (Stage D always runs);
        only reachable if a manifest is hand-edited (not part of
        DEV-02's behaviour).
    VALIDATING : str
        A validation pass is in flight. Set in memory at the start
        of :func:`customer_segmentation.dataset_management.validation
        .run_validation` and cleared on completion.
    VALID : str
        At least one validation pass ran; the latest aggregate
        result is ``PASS`` or ``WARNING`` (a WARNING is still VALID
        with ``validation.warnings[]`` populated).
    FAILED : str
        The latest aggregate result is ``FAIL``.
    """

    NOT_VALIDATED = "NOT_VALIDATED"
    VALIDATING = "VALIDATING"
    VALID = "VALID"
    FAILED = "FAILED"


VALIDATION_STATUSES: Final[frozenset[str]] = frozenset(s.value for s in ValidationStatus)


class ValidationResult(str, Enum):
    """Per-pass outcome of one validation pass.

    Attributes
    ----------
    PASS : str
        No issues in the relevant category.
    WARNING : str
        At least one non-fatal issue; overall pass is still VALID.
    FAIL : str
        At least one fatal issue; overall pass is FAILED.
    """

    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"


VALIDATION_RESULTS: Final[frozenset[str]] = frozenset(s.value for s in ValidationResult)
