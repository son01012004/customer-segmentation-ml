"""Tests for the DEV-04 scope, stage, and enum definitions."""

from __future__ import annotations

from customer_segmentation.prototype.clustering.scope import (
    CLUSTERED_SCOPES,
    CLUSTERING_STAGES,
    DETERMINISTIC_ALGORITHMS,
    STOCHASTIC_ALGORITHMS,
    SUPPORTED_ALGORITHMS,
    AlgorithmFamily,
    ClusteredScope,
    ClusteringStage,
)


def test_clustered_scope_has_only_one_value() -> None:
    assert [s.value for s in ClusteredScope] == ["CLUSTERED_PROTOTYPE"]


def test_clustered_scope_is_str_subclass() -> None:
    s = ClusteredScope.CLUSTERED_PROTOTYPE
    assert isinstance(s, str)
    assert s == "CLUSTERED_PROTOTYPE"


def test_clustered_scopes_frozenset_matches_enum() -> None:
    assert frozenset({"CLUSTERED_PROTOTYPE"}) == CLUSTERED_SCOPES


def test_clustering_stage_has_eight_values() -> None:
    expected = {"0", "1", "2", "3", "4", "5", "5b", "6"}
    assert {s.value for s in ClusteringStage} == expected


def test_clustering_stages_frozenset_matches_enum() -> None:
    assert frozenset({"0", "1", "2", "3", "4", "5", "5b", "6"}) == CLUSTERING_STAGES


def test_deterministic_algorithms() -> None:
    assert frozenset({"agglomerative", "dbscan"}) == DETERMINISTIC_ALGORITHMS


def test_stochastic_algorithms() -> None:
    assert frozenset({"kmeans", "gmm", "fuzzy_cmeans"}) == STOCHASTIC_ALGORITHMS


def test_supported_algorithms_is_union() -> None:
    assert SUPPORTED_ALGORITHMS == DETERMINISTIC_ALGORITHMS | STOCHASTIC_ALGORITHMS
    assert len(SUPPORTED_ALGORITHMS) == 5


def test_algorithm_families_re_exported() -> None:
    assert AlgorithmFamily.HARD.value == "hard"
    assert AlgorithmFamily.DENSITY_BASED.value == "density_based"
    assert AlgorithmFamily.MODEL_BASED.value == "model_based"
    assert AlgorithmFamily.FUZZY.value == "fuzzy"
