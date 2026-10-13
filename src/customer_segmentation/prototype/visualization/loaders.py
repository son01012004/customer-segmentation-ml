"""Manifest loaders for DEV-08 Prototype Visualization.

DEV-08 charts operate on existing manifest schemas:

- :class:`SegmentationManifest` (DEV-06)
- :class:`EvaluationManifest` (DEV-05)
- :class:`MarketingRecommendationManifest` (DEV-07)

This module is a thin wrapper layer over the existing manifest
readers — it does not duplicate I/O logic, does not re-validate the
manifests, and does not modify the on-disk bytes. It exists so the
:class:`~customer_segmentation.prototype.visualization.dashboard.DashboardGenerator`
and CLI have a single import surface and so that ``load_*_manifest``
errors can be raised as :exc:`VisualizationError` (the dashboard
error convention) without changing the underlying readers.

Hard rules
----------
- No manifest re-implementation. All reads delegate to the existing
  ``read_*_manifest`` functions in
  :mod:`customer_segmentation.prototype.evaluation.manifest`,
  :mod:`customer_segmentation.prototype.segmentation.manifest`, and
  :mod:`customer_segmentation.prototype.marketing.manifest`.
- All errors raised by the underlying readers are re-raised as
  :exc:`VisualizationError` so the dashboard never has to import
  the prototype-layer exception namespaces.
- Manifest content is NEVER mutated; this module returns the
  reconstructed object as-is.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any

from customer_segmentation.prototype.visualization.exceptions import (
    VisualizationError,
)

__all__ = [
    "load_segmentation_manifest",
    "load_evaluation_manifest",
    "load_marketing_manifest",
]


def _coerce_visualization_error(
    path: Path,
    exc: BaseException,
    manifest_type: str,
) -> Any:
    """Re-raise ``exc`` as a :exc:`VisualizationError`.

    Preserves the original exception as ``__cause__`` for debugging.
    Never silently swallows the underlying error.
    """
    raise VisualizationError(f"Failed to load {manifest_type} manifest at {path!s}: {exc}") from exc


def load_segmentation_manifest(path: Path) -> Any:
    """Load a :class:`SegmentationManifest` from JSON.

    Parameters
    ----------
    path : pathlib.Path
        Path to ``segmentation_manifest.json``.

    Returns
    -------
    SegmentationManifest
        Reconstructed manifest, untouched.

    Raises
    ------
    VisualizationError
        If the file is missing, malformed, or fails invariant
        validation. The original exception is preserved via
        ``__cause__``.
    """
    path = Path(path)
    # Imports inside the function to avoid circular imports with the
    # visualization package init.
    from customer_segmentation.prototype.segmentation.manifest import (
        read_segmentation_manifest,
    )

    try:
        return read_segmentation_manifest(path)
    except Exception as exc:
        _coerce_visualization_error(path, exc, "segmentation")


def load_evaluation_manifest(path: Path) -> Any:
    """Load an :class:`EvaluationManifest` from JSON.

    Parameters
    ----------
    path : pathlib.Path
        Path to ``evaluation_manifest.json``.

    Returns
    -------
    EvaluationManifest
        Reconstructed manifest, untouched.

    Raises
    ------
    VisualizationError
        If the file is missing, malformed, or fails invariant
        validation.
    """
    path = Path(path)
    from customer_segmentation.prototype.evaluation.manifest import (
        read_evaluation_manifest,
    )

    try:
        return read_evaluation_manifest(path)
    except Exception as exc:
        _coerce_visualization_error(path, exc, "evaluation")


def load_marketing_manifest(path: Path) -> Any:
    """Load a :class:`MarketingRecommendationManifest` from JSON.

    Parameters
    ----------
    path : pathlib.Path
        Path to ``marketing_manifest.json``.

    Returns
    -------
    MarketingRecommendationManifest
        Reconstructed manifest, untouched.

    Raises
    ------
    VisualizationError
        If the file is missing, malformed, or fails invariant
        validation.
    """
    path = Path(path)
    from customer_segmentation.prototype.marketing.manifest import (
        read_marketing_manifest,
    )

    try:
        return read_marketing_manifest(path)
    except Exception as exc:
        _coerce_visualization_error(path, exc, "marketing")


# Suppress unused import warning for contextlib (kept for future
# context-manager-based loader patterns; not currently used).
_ = contextlib.suppress
