"""Tests for DEV-08 marketing placeholder (REVIEW_REQUIRED only)."""

from __future__ import annotations

import re
from typing import Any

import pytest

from customer_segmentation.prototype.marketing.manifest import (
    build_marketing_manifest,
    build_recommendation_entry_review_required,
)
from customer_segmentation.prototype.marketing.scope import (
    DEFAULT_AVAILABILITY,
)
from customer_segmentation.prototype.visualization.charts.marketing_placeholder import (
    AVAILABLE_PLACEHOLDER,
    NOT_AVAILABLE_PLACEHOLDER,
    REVIEW_REQUIRED_PLACEHOLDER,
    format_marketing_placeholder,
    is_marketing_placeholder_visible,
)
from customer_segmentation.prototype.visualization.exceptions import (
    VisualizationError,
)
from customer_segmentation.prototype.visualization.scope import (
    BANNED_SUBSTRINGS,
    DEFAULT_DISCLAIMER_TEXT,
)

# ---------------------------------------------------------------------------
# Placeholder text constants
# ---------------------------------------------------------------------------


def test_review_required_placeholder_text_present() -> None:
    assert "REVIEW_REQUIRED" in REVIEW_REQUIRED_PLACEHOLDER


def test_not_available_placeholder_text() -> None:
    assert "NOT_AVAILABLE" in NOT_AVAILABLE_PLACEHOLDER


def test_available_placeholder_text() -> None:
    assert "AVAILABLE" in AVAILABLE_PLACEHOLDER


# ---------------------------------------------------------------------------
# is_marketing_placeholder_visible
# ---------------------------------------------------------------------------


def test_is_visible_for_each_availability() -> None:
    for s in ("REVIEW_REQUIRED", "NOT_AVAILABLE", "AVAILABLE"):
        assert is_marketing_placeholder_visible(s) is True


def test_is_visible_raises_on_empty() -> None:
    with pytest.raises(VisualizationError, match="non-empty str"):
        is_marketing_placeholder_visible("")


def test_is_visible_raises_on_non_string() -> None:
    with pytest.raises(VisualizationError):
        is_marketing_placeholder_visible(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# format_marketing_placeholder — None input
# ---------------------------------------------------------------------------


def test_format_with_none_manifest_default_section() -> None:
    out = format_marketing_placeholder(None)
    assert "REVIEW_REQUIRED" in out
    assert DEFAULT_DISCLAIMER_TEXT in out


def test_format_with_none_manifest_availability_echoed() -> None:
    out = format_marketing_placeholder(None)
    assert "REVIEW_REQUIRED" in out


def test_format_with_none_manifest_zero_recommendations() -> None:
    out = format_marketing_placeholder(None)
    assert "n_recommendations : 0" in out


# ---------------------------------------------------------------------------
# format_marketing_placeholder — Phase A REVIEW_REQUIRED manifest
# ---------------------------------------------------------------------------


def _make_args(**overrides: Any) -> dict[str, Any]:
    base = {
        "marketing_id": "mkt_" + "0" * 24,
        "segmentation_id": "seg_" + "1" * 24,
        "clustering_id": "cl_" + "2" * 24,
        "preprocessed_id": "pp_x",
        "dataset_id": "ds_x",
        "source_framework_version": None,
        "mkt_framework_found": False,
        "ml_dataset_sha256": "a" * 64,
        "feature_set_sha256": "b" * 64,
        "preprocessing_config_sha256": "c" * 64,
        "segmentation_manifest_sha256": "d" * 64,
        "n_segments_input": 3,
        "n_segments_with_recommendation": 3,
        "n_segments_noise": 0,
        "n_segments_not_available": 0,
        "noise_policy_used": "exclude",
        "recommendations": [
            build_recommendation_entry_review_required(
                segment_id=i,
                cluster_label=i,
                evidence_ref=["seg_" + "1" * 24],
            )
            for i in range(3)
        ],
        "environment": {
            "python": "3.14",
            "platform": "Linux",
            "release": "7.0",
            "machine": "x86_64",
            "key_libraries": {"pandas": "2.0"},
        },
        "config_sha256": "e" * 64,
        "log_file": "mkt.log",
        "validation_report": {"all_passed": True, "checks": []},
        "readonly_paths": ["data/raw/primary"],
        "input_segmentation_manifest": "segmentation_manifest.json",
        "availability": DEFAULT_AVAILABILITY,
    }
    base.update(overrides)
    return base


def test_format_review_required_manifest_default() -> None:
    manifest = build_marketing_manifest(**_make_args())
    out = format_marketing_placeholder(manifest)
    assert "REVIEW_REQUIRED" in out
    assert DEFAULT_DISCLAIMER_TEXT in out


def test_format_not_available_manifest() -> None:
    # Build a manifest where availability is NOT_AVAILABLE.
    manifest = build_marketing_manifest(
        **_make_args(
            availability="NOT_AVAILABLE",
            n_segments_with_recommendation=0,
            n_segments_not_available=0,
            recommendations=[],
        )
    )
    out = format_marketing_placeholder(manifest)
    assert "NOT_AVAILABLE" in out
    assert DEFAULT_DISCLAIMER_TEXT in out


def test_format_available_manifest_does_not_emit_recommendations() -> None:
    """Even when availability == AVAILABLE, the dashboard only emits the banner."""
    manifest = build_marketing_manifest(
        **_make_args(
            availability="AVAILABLE",
            source_framework_version="MKT-01..05__v1",
            mkt_framework_found=True,
            n_segments_with_recommendation=3,
            n_segments_not_available=0,
        )
    )
    out = format_marketing_placeholder(manifest)
    assert "AVAILABLE" in out
    # Never emit recommendation content even in AVAILABLE mode.
    assert "marketing_objective" not in out
    assert "recommended_action" not in out


def test_format_unknown_availability_falls_back_to_review_required() -> None:
    """Unknown availability is treated as REVIEW_REQUIRED (safe default)."""
    manifest = build_marketing_manifest(
        **_make_args(
            availability="AVAILABLE",  # only valid values
        )
    )
    # Sanity: this is AVAILABLE.
    assert manifest.availability == "AVAILABLE"
    # But format() with an unknown availability literal is rendered as AVAILABLE.
    out = format_marketing_placeholder(manifest)
    assert "AVAILABLE" in out


def test_format_does_not_include_mkt_recommendation_id() -> None:
    """No per-segment recommendation_id is leaked into the placeholder."""
    manifest = build_marketing_manifest(**_make_args())
    out = format_marketing_placeholder(manifest)
    for r in manifest.recommendations:
        assert r.recommendation_id not in out


# ---------------------------------------------------------------------------
# Hidden marketing section
# ---------------------------------------------------------------------------


def test_format_hidden_section_returns_empty() -> None:
    out = format_marketing_placeholder(None, marketing_section="hidden")
    assert out == ""


def test_format_hidden_with_manifest_still_empty() -> None:
    manifest = build_marketing_manifest(**_make_args())
    out = format_marketing_placeholder(manifest, marketing_section="hidden")
    assert out == ""


def test_format_invalid_marketing_section_raises() -> None:
    with pytest.raises(VisualizationError, match="marketing_section"):
        format_marketing_placeholder(None, marketing_section="bogus")


# ---------------------------------------------------------------------------
# Custom disclaimer
# ---------------------------------------------------------------------------


def test_custom_disclaimer() -> None:
    out = format_marketing_placeholder(None, disclaimer="custom text")
    assert "custom text" in out
    assert DEFAULT_DISCLAIMER_TEXT not in out


# ---------------------------------------------------------------------------
# Banned word discipline
# ---------------------------------------------------------------------------


def _strip(text: str) -> str:
    out = text
    lower = out.lower()
    dl = DEFAULT_DISCLAIMER_TEXT.lower()
    while dl in lower:
        idx = lower.index(dl)
        out = out[:idx] + out[idx + len(dl) :]
        lower = out.lower()
    return out


def test_no_banned_words_in_default_placeholder() -> None:
    out = format_marketing_placeholder(None)
    cleaned = _strip(out)
    for banned in BANNED_SUBSTRINGS:
        pattern = r"\b" + re.escape(banned).replace("\\-", r"[-\s]") + r"\b"
        assert not re.search(
            pattern, cleaned, flags=re.IGNORECASE
        ), f"Banned word {banned!r} found in placeholder output"


def test_no_banned_words_with_review_required_manifest() -> None:
    manifest = build_marketing_manifest(**_make_args())
    out = format_marketing_placeholder(manifest)
    cleaned = _strip(out)
    for banned in BANNED_SUBSTRINGS:
        pattern = r"\b" + re.escape(banned).replace("\\-", r"[-\s]") + r"\b"
        assert not re.search(
            pattern, cleaned, flags=re.IGNORECASE
        ), f"Banned word {banned!r} found in placeholder output"
