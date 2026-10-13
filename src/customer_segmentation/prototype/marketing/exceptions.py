"""Exception hierarchy for DEV-07 Prototype Marketing.

Mirror the typed-error convention used by DEV-04/05/06 packages.

All exceptions inherit from :class:`MarketingError` so callers can
catch the entire DEV-07 surface with a single ``except`` clause if
they wish.
"""

from __future__ import annotations

__all__ = [
    "MarketingError",
    "MarketingInputError",
    "MarketingManifestError",
    "MarketingValidationError",
    "MarketingScopeError",
    "MarketingStoragePathError",
    "MarketingCollisionError",
    "MarketingManifestCorrupt",
    "MarketingConfigError",
]


class MarketingError(Exception):
    """Base class for all DEV-07 errors."""


class MarketingInputError(MarketingError, ValueError):
    """Raised when CLI args or input file paths are invalid."""


class MarketingManifestError(MarketingError, ValueError):
    """Raised on manifest construction / I/O / invariant failures."""


class MarketingValidationError(MarketingError, ValueError):
    """Raised on input validation gate (Stage C) failure."""


class MarketingScopeError(MarketingError, ValueError):
    """Raised when ``research_safety.scope`` is not in the closed set
    or when the prototype layer is asked to expose non-prototype
    status values."""


class MarketingStoragePathError(MarketingError, ValueError):
    """Raised on storage path resolution or path-traversal defence."""


class MarketingCollisionError(MarketingError, ValueError):
    """Raised when a ``marketing_id`` collision is detected."""


class MarketingManifestCorrupt(MarketingError, ValueError):
    """Raised when a stored marketing manifest exists but cannot be
    parsed (fail-closed)."""


class MarketingConfigError(MarketingError, ValueError):
    """Raised when ``configs/dev07_marketing.yaml`` is malformed."""
