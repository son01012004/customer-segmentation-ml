"""DEV-09 end-to-end package exceptions.

Re-exports the four error types from
:mod:`customer_segmentation.prototype.end_to_end.scope`. This module
exists for parity with the other prototype packages and to keep a
dedicated exceptions surface for discoverability.

Error → failure-mode mapping
----------------------------
- :exc:`Dev09Error` — generic orchestration failure (stage
  composition, lifecycle computation, summary serialization).
- :exc:`Dev09InputError` — invalid CLI args / user-supplied paths
  / mutually exclusive flags / id-format violations.
- :exc:`Dev09ConfigError` — invalid or missing DEV-09 config
  payloads (malformed YAML, missing keys, out-of-range values).
- :exc:`Dev09StoragePathError` — path resolution / id-format /
  path-containment failures during storage interaction.
"""

from __future__ import annotations

from customer_segmentation.prototype.end_to_end.scope import (
    Dev09ConfigError,
    Dev09Error,
    Dev09InputError,
    Dev09StoragePathError,
)

__all__ = [
    "Dev09Error",
    "Dev09InputError",
    "Dev09ConfigError",
    "Dev09StoragePathError",
]
