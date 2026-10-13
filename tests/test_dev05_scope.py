"""Tests for the DEV-05 scope, status, reason, and metric-name enums."""

from __future__ import annotations

import pytest

from customer_segmentation.prototype.evaluation.scope import (
    DEFAULT_METRIC_SET,
    DEFAULT_NOISE_POLICY,
    EVALUATED_SCOPES,
    EVALUATION_MANIFEST_SCHEMA_VERSION,
    METRIC_NAMES,
    METRIC_REASONS,
    METRIC_REASON_BY_STATUS,
    METRIC_STATUSES,
    NOISE_POLICIES,
    EvaluatedScope,
    MetricName,
    MetricReason,
    MetricStatus,
    NoisePolicy,
)


def test_evaluated_scope_has_only_one_value() -> None:
    assert [s.value for s in EvaluatedScope] == ["EVALUATED_PROTOTYPE"]


def test_evaluated_scope_is_str_subclass() -> None:
    s = EvaluatedScope.EVALUATED_PROTOTYPE
    assert isinstance(s, str)
    assert s == "EVALUATED_PROTOTYPE"


def test_evaluated_scopes_frozenset_matches_enum() -> None:
    assert frozenset({"EVALUATED_PROTOTYPE"}) == EVALUATED_SCOPES


def test_metric_name_has_three_values() -> None:
    assert {m.value for m in MetricName} == {
        "silhouette",
        "davies_bouldin",
        "calinski_harabasz",
    }


def test_metric_names_frozenset_matches_enum() -> None:
    assert (
        frozenset({"silhouette", "davies_bouldin", "calinski_harabasz"}) == METRIC_NAMES
    )


def test_default_metric_set_is_three_sorted() -> None:
    assert DEFAULT_METRIC_SET == ("silhouette", "davies_bouldin", "calinski_harabasz")


def test_metric_status_has_four_values() -> None:
    assert {s.value for s in MetricStatus} == {
        "VALID_VALUE",
        "NOT_APPLICABLE",
        "MISSING",
        "COMPUTATION_ERROR",
    }


def test_metric_statuses_frozenset_matches_enum() -> None:
    assert (
        frozenset({"VALID_VALUE", "NOT_APPLICABLE", "MISSING", "COMPUTATION_ERROR"})
        == METRIC_STATUSES
    )


def test_metric_reason_subgroups_match_status() -> None:
    """``METRIC_REASON_BY_STATUS`` must cover all ``MetricReason`` values."""
    all_reasons: set[str] = set()
    for reasons in METRIC_REASON_BY_STATUS.values():
        all_reasons |= set(reasons)
    enum_reasons = {r.value for r in MetricReason}
    assert enum_reasons == all_reasons, (
        f"Mismatch: enum-only={enum_reasons - all_reasons}, "
        f"mapping-only={all_reasons - enum_reasons}"
    )


def test_metric_reasons_frozenset_matches_enum() -> None:
    assert frozenset(r.value for r in MetricReason) == METRIC_REASONS


def test_valid_value_reasons_only() -> None:
    valid_value_reasons = METRIC_REASON_BY_STATUS[MetricStatus.VALID_VALUE.value]
    assert valid_value_reasons == frozenset(
        {"COMPUTED", "DBSCAN_NOISE_EXCLUDED"}
    )


def test_not_applicable_reasons() -> None:
    na_reasons = METRIC_REASON_BY_STATUS[MetricStatus.NOT_APPLICABLE.value]
    assert "ALL_NOISE" in na_reasons
    assert "SINGLE_CLUSTER" in na_reasons
    assert "INSUFFICIENT_CLUSTERS" in na_reasons
    assert "DEGENERATE_FEATURE_SPACE" in na_reasons


def test_missing_reasons() -> None:
    missing_reasons = METRIC_REASON_BY_STATUS[MetricStatus.MISSING.value]
    assert "ALGORITHM_FAMILY_NOT_SUPPORTED" in missing_reasons
    assert "MANIFEST_MISSING" in missing_reasons


def test_computation_error_reasons() -> None:
    ce_reasons = METRIC_REASON_BY_STATUS[MetricStatus.COMPUTATION_ERROR.value]
    assert "ALIGNMENT_ERROR" in ce_reasons
    assert "NAN_OR_INF_INPUT" in ce_reasons
    assert "SCHEMA_CORRUPT" in ce_reasons
    assert "SKLEARN_EXCEPTION" in ce_reasons
    assert "IO_ERROR" in ce_reasons


def test_noise_policy_literal_values() -> None:
    assert NOISE_POLICIES == frozenset({"include", "exclude"})


def test_default_noise_policy_is_exclude() -> None:
    """Per ADR-0006, prototype default is 'exclude'."""
    assert DEFAULT_NOISE_POLICY == "exclude"


def test_noise_policy_alias_supports_both_values() -> None:
    """NoisePolicy Literal type accepts both 'include' and 'exclude'."""
    # Type system check: assignment must succeed for both literal values.
    p1: NoisePolicy = "include"
    p2: NoisePolicy = "exclude"
    assert p1 in NOISE_POLICIES
    assert p2 in NOISE_POLICIES


def test_schema_version_is_pinned() -> None:
    assert EVALUATION_MANIFEST_SCHEMA_VERSION == "1.0.0"


def test_metric_status_closed_no_additions() -> None:
    """Adding a new MetricStatus would require updating test."""
    assert len(METRIC_STATUSES) == 4


def test_metric_reason_includes_dbscan_noise_excluded() -> None:
    """DBSCAN_NOISE_EXCLUDED is cross-status (audit annotation, not failure)."""
    assert MetricReason.DBSCAN_NOISE_EXCLUDED.value in METRIC_REASONS
    # It belongs to VALID_VALUE only.
    assert (
        MetricReason.DBSCAN_NOISE_EXCLUDED.value
        in METRIC_REASON_BY_STATUS[MetricStatus.VALID_VALUE.value]
    )


def test_metric_reason_no_fake_default_reasons() -> None:
    """No reason like 'DEFAULT' or 'ZERO' that would be a fake-default flag."""
    for reason in METRIC_REASONS:
        assert reason != "DEFAULT"
        assert reason != "ZERO"
        assert reason != "NAN"


def test_scope_enum_membership_closed() -> None:
    with pytest.raises(ValueError):
        EvaluatedScope("NOT_A_REAL_SCOPE")
