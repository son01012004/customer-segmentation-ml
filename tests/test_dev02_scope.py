"""Tests for the dataset_management scope enums."""

from __future__ import annotations

import pytest

from customer_segmentation.dataset_management.scope import (
    DATASET_SCOPES,
    VALIDATION_RESULTS,
    VALIDATION_STATUSES,
    DatasetScope,
    ValidationResult,
    ValidationStatus,
)


def test_dataset_scope_has_only_imported_prototype() -> None:
    assert [s.value for s in DatasetScope] == ["IMPORTED_PROTOTYPE"]


def test_dataset_scope_is_str_subclass() -> None:
    s = DatasetScope.IMPORTED_PROTOTYPE
    assert isinstance(s, str)
    assert s == "IMPORTED_PROTOTYPE"
    assert s.value == "IMPORTED_PROTOTYPE"


def test_dataset_scope_frozenset_matches_enum() -> None:
    assert DATASET_SCOPES == frozenset({"IMPORTED_PROTOTYPE"})


def test_validation_status_has_four_values() -> None:
    assert {s.value for s in ValidationStatus} == {
        "NOT_VALIDATED",
        "VALIDATING",
        "VALID",
        "FAILED",
    }


def test_validation_status_frozenset_matches_enum() -> None:
    assert VALIDATION_STATUSES == frozenset(
        {s.value for s in ValidationStatus}
    )


def test_validation_result_has_three_values() -> None:
    assert {s.value for s in ValidationResult} == {"PASS", "WARNING", "FAIL"}


def test_validation_result_frozenset_matches_enum() -> None:
    assert VALIDATION_RESULTS == frozenset({"PASS", "WARNING", "FAIL"})


def test_dataset_scope_string_equality() -> None:
    """DatasetScope members compare equal to their string value."""
    assert DatasetScope.IMPORTED_PROTOTYPE == "IMPORTED_PROTOTYPE"
    assert ValidationStatus.VALID == "VALID"
    assert ValidationResult.PASS == "PASS"


def test_enums_are_distinct_from_plain_strings() -> None:
    assert DatasetScope.IMPORTED_PROTOTYPE != "some_other_value"
    assert ValidationStatus.FAILED != "VALID"


def test_validation_status_for_full_lifecycle() -> None:
    # All four states reachable per plan §9.1.
    states = {s.value for s in ValidationStatus}
    assert "NOT_VALIDATED" in states
    assert "VALIDATING" in states
    assert "VALID" in states
    assert "FAILED" in states
