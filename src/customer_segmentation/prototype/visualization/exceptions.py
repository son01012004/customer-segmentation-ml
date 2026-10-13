"""DEV-08 visualization package exceptions.

This module re-exports the DEV-08 visualization error types from
:mod:`customer_segmentation.prototype.visualization.scope` to keep
a dedicated exceptions surface consistent with the package structure
used by other prototype modules (errors are defined near their
domain; re-exported here for discoverability).

The four error types map to four failure modes:

- :exc:`VisualizationError` — generic construction / I/O / invariant
  failure (e.g. chart rendering on empty manifest, missing metric
  entries).
- :exc:`VisualizationStoragePathError` — path / storage resolution
  failure (id format, path containment, storage-root missing).
- :exc:`VisualizationInputError` — invalid CLI / user input
  (mutually exclusive args, missing required path).
- :exc:`VisualizationConfigError` — invalid or missing config
  payloads (malformed YAML, missing keys, out-of-range values).
"""

from __future__ import annotations

from customer_segmentation.prototype.visualization.scope import (
    VisualizationConfigError,
    VisualizationError,
    VisualizationInputError,
    VisualizationStoragePathError,
)

__all__ = [
    "VisualizationError",
    "VisualizationStoragePathError",
    "VisualizationInputError",
    "VisualizationConfigError",
]
