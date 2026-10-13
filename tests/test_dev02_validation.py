"""Tests for the validation module (3-category, lifecycle mapping)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from customer_segmentation.dataset_management.scope import (
    ValidationResult as _VR,
    ValidationStatus as _VS,
)
from customer_segmentation.dataset_management.validation import (
    CategoryResult,
    ValidationBlock,
    aggregate,
    make_file_level_result,
    map_to_lifecycle,
    run_validation,
)


# ---------------------------------------------------------------------------
# aggregate / map_to_lifecycle
# ---------------------------------------------------------------------------


def test_aggregate_all_pass() -> None:
    block = ValidationBlock(
        file_level=CategoryResult(result="PASS"),
        structural=CategoryResult(result="PASS"),
        data_quality=CategoryResult(result="PASS"),
    )
    assert aggregate(block) == _VR.PASS.value
    assert map_to_lifecycle(aggregate(block)) == _VS.VALID.value


def test_aggregate_warning_in_data_quality() -> None:
    block = ValidationBlock(
        file_level=CategoryResult(result="PASS"),
        structural=CategoryResult(result="PASS"),
        data_quality=CategoryResult(
            result="WARNING", warnings=["NaN in 1 column."]
        ),
    )
    assert aggregate(block) == _VR.WARNING.value
    assert map_to_lifecycle(aggregate(block)) == _VS.VALID.value


def test_aggregate_warning_in_structural() -> None:
    block = ValidationBlock(
        file_level=CategoryResult(result="PASS"),
        structural=CategoryResult(
            result="WARNING", warnings=["Column 'x' is all-NULL."]
        ),
        data_quality=CategoryResult(result="PASS"),
    )
    assert aggregate(block) == _VR.WARNING.value


def test_aggregate_fail_dominates_warning() -> None:
    block = ValidationBlock(
        file_level=CategoryResult(result="PASS"),
        structural=CategoryResult(
            result="FAIL", errors=["row_count == 0."]
        ),
        data_quality=CategoryResult(
            result="WARNING", warnings=["NaN in 1 column."]
        ),
    )
    assert aggregate(block) == _VR.FAIL.value
    assert map_to_lifecycle(aggregate(block)) == _VS.FAILED.value


def test_aggregate_file_level_fail() -> None:
    block = ValidationBlock(
        file_level=CategoryResult(
            result="FAIL", errors=["file not found"]
        ),
        structural=CategoryResult(result="PASS"),
        data_quality=CategoryResult(result="PASS"),
    )
    assert aggregate(block) == _VR.FAIL.value


def test_aggregate_rejects_invalid_category() -> None:
    block = ValidationBlock(
        file_level=CategoryResult(result="PASS"),
        structural=CategoryResult(result="BOGUS"),
        data_quality=CategoryResult(result="PASS"),
    )
    with pytest.raises(ValueError):
        aggregate(block)


def test_map_to_lifecycle_rejects_invalid() -> None:
    with pytest.raises(ValueError):
        map_to_lifecycle("BOGUS")


def test_make_file_level_result_pass() -> None:
    cat = make_file_level_result(passed=True)
    assert cat.result == "PASS"
    assert cat.errors == []


def test_make_file_level_result_fail_records_errors() -> None:
    cat = make_file_level_result(passed=False, errors=["e1", "e2"])
    assert cat.result == "FAIL"
    assert cat.errors == ["e1", "e2"]


# ---------------------------------------------------------------------------
# run_validation — structural rules
# ---------------------------------------------------------------------------


def test_structural_empty_rows() -> None:
    df = pd.DataFrame({"a": [], "b": []})
    block = run_validation(df, make_file_level_result(passed=True))
    assert block.structural.result == "FAIL"
    assert any("row_count == 0" in e for e in block.structural.errors)


def test_structural_empty_columns() -> None:
    df = pd.DataFrame(index=range(3))
    block = run_validation(df, make_file_level_result(passed=True))
    assert block.structural.result == "FAIL"
    assert any("column_count == 0" in e for e in block.structural.errors)


def test_structural_duplicate_columns() -> None:
    df = pd.DataFrame([[1, 2]], columns=["a", "a"])
    block = run_validation(df, make_file_level_result(passed=True))
    assert block.structural.result == "FAIL"
    assert any("Duplicate column" in e for e in block.structural.errors)


def test_structural_empty_column_name() -> None:
    df = pd.DataFrame([[1, 2]], columns=["a", ""])
    block = run_validation(df, make_file_level_result(passed=True))
    assert any("Empty column" in e for e in block.structural.errors)


def test_structural_shell_unsafe_character() -> None:
    df = pd.DataFrame([[1]], columns=["a b"])
    block = run_validation(df, make_file_level_result(passed=True))
    assert any("shell-unsafe" in e for e in block.structural.errors)


def test_structural_all_null_column_is_warning() -> None:
    df = pd.DataFrame({"a": [1, 2, 3], "b": [None, None, None]})
    block = run_validation(df, make_file_level_result(passed=True))
    assert block.structural.result == "WARNING"
    assert any("all-NULL" in w for w in block.structural.warnings)


# ---------------------------------------------------------------------------
# run_validation — data-quality rules
# ---------------------------------------------------------------------------


def test_data_quality_passes_for_clean_df() -> None:
    df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    block = run_validation(df, make_file_level_result(passed=True))
    assert block.data_quality.result == "PASS"


def test_data_quality_warns_on_nan() -> None:
    df = pd.DataFrame({"a": [1, None, 3]})
    block = run_validation(df, make_file_level_result(passed=True))
    assert block.data_quality.result == "WARNING"
    assert block.data_quality.stats["nan_columns"] == 1


def test_data_quality_warns_on_inf() -> None:
    df = pd.DataFrame({"a": [1.0, np.inf, 3.0]})
    block = run_validation(df, make_file_level_result(passed=True))
    assert block.data_quality.result == "WARNING"
    assert block.data_quality.stats["inf_columns"] == 1


def test_data_quality_warns_on_constant_column() -> None:
    df = pd.DataFrame({"a": [5, 5, 5, 5]})
    block = run_validation(df, make_file_level_result(passed=True))
    assert block.data_quality.result == "WARNING"
    assert block.data_quality.stats["constant_columns"] == 1


def test_data_quality_warns_on_duplicate_rows() -> None:
    df = pd.DataFrame({"a": [1, 1, 2]})
    block = run_validation(df, make_file_level_result(passed=True))
    assert block.data_quality.result == "WARNING"
    assert block.data_quality.stats["duplicate_rows"] == 1


def test_data_quality_warns_on_mixed_column() -> None:
    df = pd.DataFrame({"a": [1, "two", 3.0]})
    block = run_validation(df, make_file_level_result(passed=True))
    assert block.data_quality.result == "WARNING"
    assert block.data_quality.stats["mixed_columns"] == 1


def test_run_validation_does_not_mutate_input() -> None:
    df = pd.DataFrame({"a": [1, 2, 3]})
    snapshot = df.copy(deep=True)
    run_validation(df, make_file_level_result(passed=True))
    pd.testing.assert_frame_equal(df, snapshot)


# ---------------------------------------------------------------------------
# End-to-end aggregation behaviour
# ---------------------------------------------------------------------------


def test_validation_pipeline_clean_dataset_is_valid() -> None:
    df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    block = run_validation(df, make_file_level_result(passed=True))
    assert aggregate(block) == "PASS"
    assert map_to_lifecycle(aggregate(block)) == "VALID"


def test_validation_pipeline_dataset_with_warnings_is_valid() -> None:
    df = pd.DataFrame({"a": [1, 1, 1]})  # constant column -> WARNING
    block = run_validation(df, make_file_level_result(passed=True))
    assert aggregate(block) == "WARNING"
    assert map_to_lifecycle(aggregate(block)) == "VALID"


def test_validation_pipeline_empty_dataset_fails() -> None:
    df = pd.DataFrame({"a": []})
    block = run_validation(df, make_file_level_result(passed=True))
    assert aggregate(block) == "FAIL"
    assert map_to_lifecycle(aggregate(block)) == "FAILED"
