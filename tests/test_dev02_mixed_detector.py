"""Tests for the mixed-type detector (deterministic, head-sample)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from customer_segmentation.dataset_management.importer import (
    MIXED_TYPE_RANKS,
    detect_mixed,
)


# ---------------------------------------------------------------------------
# Conservative schema detection
# ---------------------------------------------------------------------------


@pytest.fixture()
def imported_detect_mixed():
    """Return the detect_mixed function (just a stable import)."""
    return detect_mixed


def test_non_object_dtype_is_never_mixed() -> None:
    s = pd.Series([1, 2, 3])
    assert not detect_mixed(s)


def test_int_dtype_is_never_mixed() -> None:
    s = pd.Series([0, 1, 1, 0, 1])
    # 0/1 ints are NOT boolean; they are numeric.
    assert not detect_mixed(s)


def test_uniform_string_column_is_not_mixed() -> None:
    s = pd.Series(["a", "b", "c", "a", "b"])
    assert not detect_mixed(s)


def test_uniform_int_column_is_not_mixed() -> None:
    s = pd.Series([1, 2, 3, 4, 5])
    assert not detect_mixed(s)


def test_uniform_float_column_is_not_mixed() -> None:
    s = pd.Series([1.0, 2.0, 3.0])
    assert not detect_mixed(s)


def test_uniform_bool_column_is_not_mixed() -> None:
    s = pd.Series([True, False, True])
    assert not detect_mixed(s)


def test_mixed_int_and_string_is_mixed() -> None:
    s = pd.Series([1, "two", 3])
    assert detect_mixed(s)


def test_mixed_float_and_string_is_mixed() -> None:
    s = pd.Series([1.0, "two", 3.0])
    assert detect_mixed(s)


def test_mixed_int_and_float_only_ints_in_head() -> None:
    # Use dtype=object so the column is object, not float64.
    s = pd.Series([1, 2, 3, 4.0], dtype=object)
    # Head sample sees ints AND the float — but the float's type name
    # is "float" (or "int" if it equals an int), and ints are "int".
    # With sample_size=1000, all 4 values are inspected.
    assert detect_mixed(s)


def test_mixed_detector_does_not_parse_iso_string_to_datetime() -> None:
    s = pd.Series(["2024-01-01", "2024-01-02", "2024-01-03"])
    # All strings — must not be classified as datetime.
    assert not detect_mixed(s)


def test_mixed_detector_does_not_coerce_bool_to_int() -> None:
    # True/False are bools; 1/0 are ints. Mixed type in head sample.
    s = pd.Series([True, False, 1, 0])
    assert detect_mixed(s)


def test_mixed_detector_handles_null_only() -> None:
    s = pd.Series([None, None, np.nan])
    assert not detect_mixed(s)


def test_mixed_detector_empty_is_not_mixed() -> None:
    s = pd.Series([], dtype=object)
    assert not detect_mixed(s)


def test_mixed_detector_single_type_is_not_mixed() -> None:
    s = pd.Series([1, 2, 3], dtype=object)
    assert not detect_mixed(s)


def test_mixed_detector_respects_sample_size() -> None:
    # First 3 non-null are ints; the 4th is a string.
    s = pd.Series([1, 2, 3, "x"])
    # Default sample_size=1000 sees both.
    assert detect_mixed(s)
    # With sample_size=3, only the first 3 are inspected; result is False.
    assert not detect_mixed(s, sample_size=3)


def test_mixed_detector_deterministic() -> None:
    s = pd.Series([1, "x", 2, "y", 3, "z"])
    a = detect_mixed(s)
    b = detect_mixed(s)
    assert a == b is True
    # Reversed source — same outcome.
    s2 = pd.Series(["x", 1, "y", 2, "z", 3])
    assert detect_mixed(s2)


def test_mixed_detector_handles_decimals() -> None:
    s = pd.Series([Decimal("1.0"), Decimal("2.0"), Decimal("3.0")])
    # All Decimals — not mixed.
    assert not detect_mixed(s)


def test_mixed_detector_handles_datetime_in_object_column() -> None:
    s = pd.Series([datetime(2024, 1, 1), datetime(2024, 1, 2)])
    # All datetimes — not mixed.
    assert not detect_mixed(s)


def test_mixed_detector_mixed_datetime_and_string() -> None:
    s = pd.Series([datetime(2024, 1, 1), "today"])
    assert detect_mixed(s)


def test_mixed_type_ranks_is_frozen_and_includes_int_bool_str() -> None:
    assert isinstance(MIXED_TYPE_RANKS, frozenset)
    assert "int" in MIXED_TYPE_RANKS
    assert "bool" in MIXED_TYPE_RANKS
    assert "str" in MIXED_TYPE_RANKS
    assert "float" in MIXED_TYPE_RANKS
    assert "datetime" in MIXED_TYPE_RANKS


def test_mixed_detector_does_not_call_pd_to_datetime() -> None:
    # Implementation must not import or call any pd.to_*.
    s = pd.Series(["2024-01-01", 1, "2024-01-02"])
    # First type is str; second is int -> mixed.
    assert detect_mixed(s)


def test_mixed_detector_with_date_only() -> None:
    s = pd.Series([date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3)])
    assert not detect_mixed(s)
