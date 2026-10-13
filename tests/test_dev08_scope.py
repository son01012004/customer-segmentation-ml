"""Tests for DEV-08 scope, constants, colour palette, and exceptions (Task 1.1)."""

from __future__ import annotations

import re

import pytest

from customer_segmentation.prototype.visualization.exceptions import (
    VisualizationError,
)
from customer_segmentation.prototype.visualization.scope import (
    BANNED_SUBSTRINGS,
    BANNED_SUBSTRINGS_OUTSIDE_DISCLAIMER,
    DEFAULT_COLOR_PALETTE,
    DEFAULT_DISCLAIMER_TEXT,
    NOISE_COLOR,
    VISUALIZATION_SCHEMA_VERSION,
)

# ---------------------------------------------------------------------------
# Package import (re-exports)
# ---------------------------------------------------------------------------


def test_package_imports_visualization_schema_version() -> None:
    # The top-level __init__.py re-exports everything.
    from customer_segmentation.prototype.visualization import (
        VISUALIZATION_SCHEMA_VERSION,
    )

    assert VISUALIZATION_SCHEMA_VERSION == "1.0.0"


def test_package_imports_color_palette() -> None:
    from customer_segmentation.prototype.visualization import (
        DEFAULT_COLOR_PALETTE,
    )

    assert isinstance(DEFAULT_COLOR_PALETTE, tuple)
    assert len(DEFAULT_COLOR_PALETTE) >= 3


def test_package_imports_banned_substrings() -> None:
    from customer_segmentation.prototype.visualization import (
        BANNED_SUBSTRINGS,
    )

    assert isinstance(BANNED_SUBSTRINGS, tuple)
    assert len(BANNED_SUBSTRINGS) >= 3


def test_package_imports_visualization_error() -> None:
    from customer_segmentation.prototype.visualization import (
        VisualizationError,
    )

    assert issubclass(VisualizationError, ValueError)


# ---------------------------------------------------------------------------
# VISUALIZATION_SCHEMA_VERSION
# ---------------------------------------------------------------------------


def test_schema_version_is_pinned() -> None:
    """Schema version is pinned to '1.0.0' for Task 1.1."""
    assert VISUALIZATION_SCHEMA_VERSION == "1.0.0"


def test_schema_version_is_string() -> None:
    assert isinstance(VISUALIZATION_SCHEMA_VERSION, str)


# ---------------------------------------------------------------------------
# DEFAULT_COLOR_PALETTE
# ---------------------------------------------------------------------------


def test_palette_is_tuple() -> None:
    assert isinstance(DEFAULT_COLOR_PALETTE, tuple)


def test_palette_has_at_least_10_entries() -> None:
    """DEV-08 must support up to 10 clusters; palette must cover them."""
    assert len(DEFAULT_COLOR_PALETTE) >= 10


def test_palette_entries_are_valid_hex() -> None:
    """Each palette entry must be a valid CSS hex colour."""
    hex_re = re.compile(r"^#[0-9A-Fa-f]{6}$")
    for entry in DEFAULT_COLOR_PALETTE:
        assert hex_re.match(entry), f"Invalid hex colour: {entry!r}"


def test_palette_entries_are_distinct() -> None:
    """All palette entries must be distinct (no duplicate hex values)."""
    assert len(DEFAULT_COLOR_PALETTE) == len(set(DEFAULT_COLOR_PALETTE))


def test_palette_is_not_empty() -> None:
    assert len(DEFAULT_COLOR_PALETTE) > 0


def test_noise_color_is_valid_hex() -> None:
    """Noise overlay colour must be a valid CSS hex colour."""
    hex_re = re.compile(r"^#[0-9A-Fa-f]{6}$")
    assert hex_re.match(NOISE_COLOR), f"Invalid hex colour for NOISE_COLOR: {NOISE_COLOR!r}"


def test_noise_color_distinct_from_palette() -> None:
    """Noise colour must not be in the cluster palette (avoids confusion)."""
    assert NOISE_COLOR not in DEFAULT_COLOR_PALETTE


# ---------------------------------------------------------------------------
# Display-discipline constants
# ---------------------------------------------------------------------------


def test_banned_substrings_is_nonempty_tuple() -> None:
    assert isinstance(BANNED_SUBSTRINGS, tuple)
    assert len(BANNED_SUBSTRINGS) >= 5


def test_banned_substrings_contains_research_decision_language() -> None:
    """'best', 'optimal', 'winner', 'ranking', 'recommended' are forbidden."""
    for term in ("best", "optimal", "winner", "ranking", "recommended"):
        assert term in BANNED_SUBSTRINGS, f"{term!r} must be in BANNED_SUBSTRINGS"


def test_banned_substrings_contains_business_naming() -> None:
    """Business segment names are forbidden without an ADR."""
    for term in ("champion", "loyal", "vip", "at-risk"):
        assert term in BANNED_SUBSTRINGS, f"{term!r} must be in BANNED_SUBSTRINGS"


def test_banned_substrings_alias_matches() -> None:
    """The alias must be identical to the primary constant."""
    assert BANNED_SUBSTRINGS_OUTSIDE_DISCLAIMER == BANNED_SUBSTRINGS


def test_disclaimer_is_nonempty_string() -> None:
    assert isinstance(DEFAULT_DISCLAIMER_TEXT, str)
    assert len(DEFAULT_DISCLAIMER_TEXT) > 0


def test_disclaimer_contains_post_preprocessing_warning() -> None:
    """The disclaimer must mention post-preprocessing values."""
    assert "post-preprocessing" in DEFAULT_DISCLAIMER_TEXT.lower()


def test_disclaimer_contains_no_ranking_claim() -> None:
    """Disclaimer itself must not claim anything ranking-related."""
    lower = DEFAULT_DISCLAIMER_TEXT.lower()
    assert "ranking" in lower
    assert "recommendation" in lower
    assert "winner" in lower


# ---------------------------------------------------------------------------
# VisualizationError
# ---------------------------------------------------------------------------


def test_visualization_error_is_valueerror_subclass() -> None:
    """VisualizationError must inherit from ValueError."""
    assert issubclass(VisualizationError, ValueError)


def test_visualization_error_can_be_raised_with_message() -> None:
    """Error must accept a string message."""
    with pytest.raises(VisualizationError) as exc_info:
        raise VisualizationError("test message")
    assert "test message" in str(exc_info.value)


def test_visualization_error_can_be_raised_from_valueerror() -> None:
    """Error raised from ValueError context must be catchable as ValueError."""
    with pytest.raises(ValueError) as exc_info:
        raise VisualizationError("from valueerror")
    assert isinstance(exc_info.value, VisualizationError)


def test_visualization_error_exceptions_module_re_exports() -> None:
    """The exceptions module must re-export VisualizationError."""
    from customer_segmentation.prototype.visualization.exceptions import (
        VisualizationError as ReExported,
    )

    assert ReExported is VisualizationError


# ---------------------------------------------------------------------------
# Sub-package chart placeholder
# ---------------------------------------------------------------------------


def test_charts_submodule_exists() -> None:
    """The charts/ sub-package must exist (even if empty in Task 1.1)."""
    from customer_segmentation.prototype.visualization import charts

    assert hasattr(charts, "__all__")
    # __all__ is defined and is an empty list in the placeholder.
    assert isinstance(charts.__all__, list)
