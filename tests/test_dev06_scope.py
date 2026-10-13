"""Tests for the DEV-06 scope, status, and statistic-name enums."""

from __future__ import annotations

import pytest

from customer_segmentation.prototype.segmentation.scope import (
    DEFAULT_NOISE_POLICY,
    DEFAULT_STATISTICS_SET,
    NOISE_POLICIES,
    PROFILED_SCOPES,
    PROFILING_STATISTIC_NAMES,
    PROFILING_STATISTICS_SET,
    SEGMENTATION_MANIFEST_SCHEMA_VERSION,
    SEGMENTATION_STAGES,
    NoisePolicy,
    ProfiledScope,
    SegmentationStage,
)


def test_profiled_scope_has_only_one_value() -> None:
    """ProfiledScope is a 1-value enum (mirror EvaluatedScope)."""
    assert [s.value for s in ProfiledScope] == ["PROFILED_PROTOTYPE"]


def test_profiled_scope_is_str_subclass() -> None:
    s = ProfiledScope.PROFILED_PROTOTYPE
    assert isinstance(s, str)
    assert s == "PROFILED_PROTOTYPE"


def test_profiled_scopes_frozenset_matches_enum() -> None:
    assert frozenset({"PROFILED_PROTOTYPE"}) == PROFILED_SCOPES


def test_profiled_scope_enum_rejects_arbitrary_string() -> None:
    with pytest.raises(ValueError):
        ProfiledScope("NOT_A_REAL_SCOPE")


def test_profiled_scope_value_used_in_manifest_block() -> None:
    """The 1-value ProfiledScope is the canonical scope used in
    segmentation_manifest.json research_safety block."""
    assert ProfiledScope.PROFILED_PROTOTYPE.value == "PROFILED_PROTOTYPE"


def test_segmentation_stage_has_eight_values() -> None:
    """SegmentationStage enumerates 8 stages A..H."""
    assert {s.value for s in SegmentationStage} == {
        "A",
        "B",
        "C",
        "D",
        "E",
        "F",
        "G",
        "H",
    }


def test_segmentation_stages_frozenset_matches_enum() -> None:
    assert frozenset({"A", "B", "C", "D", "E", "F", "G", "H"}) == SEGMENTATION_STAGES


def test_segmentation_stage_is_str_subclass() -> None:
    s = SegmentationStage.A
    assert isinstance(s, str)
    assert s == "A"


def test_segmentation_stage_enum_rejects_arbitrary_string() -> None:
    with pytest.raises(ValueError):
        SegmentationStage("Z")


def test_segmentation_stage_order_preserved() -> None:
    """The 8 stages must enumerate A→H in canonical order."""
    values = [s.value for s in SegmentationStage]
    assert values == ["A", "B", "C", "D", "E", "F", "G", "H"]


def test_noise_policy_literal_values() -> None:
    assert frozenset({"include", "exclude", "n/a"}) == NOISE_POLICIES


def test_default_noise_policy_is_exclude() -> None:
    """Per ADR-0006 prototype-scope decision, default = 'exclude'."""
    assert DEFAULT_NOISE_POLICY == "exclude"


def test_noise_policy_alias_supports_both_values() -> None:
    """NoisePolicy Literal type accepts all canonical values."""
    p1: NoisePolicy = "include"
    p2: NoisePolicy = "exclude"
    assert p1 in NOISE_POLICIES
    assert p2 in NOISE_POLICIES


def test_profiling_statistics_set_is_closed() -> None:
    """PROFILING_STATISTICS_SET is the closed set of statistic names DEV-06
    may emit. No ARI / AMI / silhouette / Davies-Bouldin allowed."""
    assert (
        frozenset(
            {
                "mean",
                "median",
                "std",
                "q1",
                "q3",
                "min",
                "max",
                "topk_categories",
                "value_counts",
                "other_count",
                "missing_count",
            }
        )
        == PROFILING_STATISTICS_SET
    )


def test_profiling_statistic_names_matches_set() -> None:
    assert frozenset(PROFILING_STATISTICS_SET) == PROFILING_STATISTIC_NAMES


def test_default_statistics_set_is_sublist_of_closed_set() -> None:
    """DEFAULT_STATISTICS_SET must be a subset of PROFILING_STATISTICS_SET
    (so the default never references a statistic that is forbidden by the
    closed set)."""
    assert frozenset(DEFAULT_STATISTICS_SET).issubset(PROFILING_STATISTICS_SET)


def test_default_statistics_set_is_non_empty() -> None:
    assert len(DEFAULT_STATISTICS_SET) >= 1


def test_profiling_statistics_set_excludes_research_metrics() -> None:
    """DEV-06 must NOT emit research-only metrics (silhouette, DBI, CH,
    ARI, AMI, runtime)."""
    for forbidden in (
        "silhouette",
        "davies_bouldin",
        "calinski_harabasz",
        "ari",
        "ami",
        "runtime_seconds",
        "n_iter",
        "inertia",
    ):
        assert forbidden not in PROFILING_STATISTICS_SET


def test_schema_version_is_pinned() -> None:
    """Bumping schema_version invalidates all old segmentation_ids."""
    assert SEGMENTATION_MANIFEST_SCHEMA_VERSION == "1.0.0"


def test_no_metric_names_starts_with_research_term() -> None:
    """Defence-in-depth: no statistic name begins with 'silhouette',
    'ari', 'ami', 'davies', 'calinski'."""
    for name in PROFILING_STATISTICS_SET:
        low = name.lower()
        assert not low.startswith("silhouette")
        assert not low.startswith("davies")
        assert not low.startswith("calinski")
        assert not low.startswith("ari_")
        assert not low.startswith("ami_")
