"""Tests for DEV-07 scope, stage, and closed-set constants."""

from __future__ import annotations

import pytest

from customer_segmentation.prototype.marketing.scope import (
    AVAILABILITY_STATUSES,
    DEFAULT_AVAILABILITY,
    FORBIDDEN_MARKETING_TERMS,
    KPI_BLOCKLIST,
    KPI_BLOCKLIST_DISPLAY,
    MARKETING_LIMITATION_TEXT,
    MARKETING_MANIFEST_SCHEMA_VERSION,
    MARKETING_PENDING_PLACEHOLDER,
    MARKETING_SCOPES,
    MARKETING_STAGES,
    NOISE_POLICIES,
    MarketingScope,
    MarketingStage,
)

# ---------------------------------------------------------------------------
# MarketingScope
# ---------------------------------------------------------------------------


def test_marketing_scope_has_one_value() -> None:
    assert len(list(MarketingScope)) == 1
    assert MarketingScope.MARKETING_PROTOTYPE.value == "MARKETING_PROTOTYPE"


def test_marketing_scopes_contains_canonical() -> None:
    assert "MARKETING_PROTOTYPE" in MARKETING_SCOPES
    assert len(MARKETING_SCOPES) == 1


# ---------------------------------------------------------------------------
# MarketingStage
# ---------------------------------------------------------------------------


def test_marketing_stage_canonical_order() -> None:
    stages = [s.value for s in MarketingStage]
    assert stages == ["A", "B", "C", "D", "E", "F", "G"]


def test_marketing_stages_set_matches_enum() -> None:
    assert frozenset(s.value for s in MarketingStage) == MARKETING_STAGES


# ---------------------------------------------------------------------------
# AvailabilityStatus
# ---------------------------------------------------------------------------


def test_availability_statuses_closed_set() -> None:
    assert frozenset({"AVAILABLE", "NOT_AVAILABLE", "REVIEW_REQUIRED"}) == AVAILABILITY_STATUSES


def test_default_availability_is_review_required() -> None:
    assert DEFAULT_AVAILABILITY == "REVIEW_REQUIRED"


# ---------------------------------------------------------------------------
# Noise policies
# ---------------------------------------------------------------------------


def test_noise_policies_closed_set() -> None:
    assert frozenset({"include", "exclude", "n/a"}) == NOISE_POLICIES


# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------


def test_schema_version_pinned() -> None:
    assert MARKETING_MANIFEST_SCHEMA_VERSION == "1.0.0"


# ---------------------------------------------------------------------------
# KPI blocklist
# ---------------------------------------------------------------------------


def test_kpi_blocklist_contains_silhouette() -> None:
    assert "silhouette" in KPI_BLOCKLIST
    assert "silhouette_score" in KPI_BLOCKLIST


def test_kpi_blocklist_contains_dbi() -> None:
    assert "davies_bouldin_index" in KPI_BLOCKLIST
    assert "davies_bouldin" in KPI_BLOCKLIST


def test_kpi_blocklist_contains_ch() -> None:
    assert "calinski_harabasz_index" in KPI_BLOCKLIST
    assert "ch" in KPI_BLOCKLIST


def test_kpi_blocklist_contains_wcss() -> None:
    assert "wcss" in KPI_BLOCKLIST
    assert "inertia" in KPI_BLOCKLIST


def test_kpi_blocklist_contains_ari_ami() -> None:
    assert "ari" in KPI_BLOCKLIST
    assert "ami" in KPI_BLOCKLIST


def test_kpi_blocklist_contains_runtime() -> None:
    assert "runtime" in KPI_BLOCKLIST
    assert "fit_time" in KPI_BLOCKLIST


def test_kpi_blocklist_display_nonempty_string() -> None:
    assert isinstance(KPI_BLOCKLIST_DISPLAY, str)
    assert "silhouette" in KPI_BLOCKLIST_DISPLAY


# ---------------------------------------------------------------------------
# Forbidden marketing terms
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "term",
    ["champion", "loyal", "vip", "at-risk", "churn", "ltv", "clv"],
)
def test_forbidden_marketing_terms_contains_core(term: str) -> None:
    assert term in FORBIDDEN_MARKETING_TERMS


# ---------------------------------------------------------------------------
# Placeholders
# ---------------------------------------------------------------------------


def test_marketing_pending_placeholder() -> None:
    assert MARKETING_PENDING_PLACEHOLDER == "PENDING_MKT_FRAMEWORK"


def test_marketing_limitation_text_mentions_mkt() -> None:
    assert "MKT" in MARKETING_LIMITATION_TEXT
    assert "prototype" in MARKETING_LIMITATION_TEXT.lower()
