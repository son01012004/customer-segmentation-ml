"""Tests for final matrix validation.

Checks:
- Row count = 4371
- CustomerID NOT in matrix
- No NaN values
- No Inf values
- No constant features
- All numeric
- Metadata alignment
"""

from __future__ import annotations

import pandas as pd

from customer_segmentation.transformation.validators import (
    check_all_numeric,
    check_metadata_alignment,
    check_no_constant_features,
    check_no_identifier_in_matrix,
    check_no_inf,
    check_no_nan,
    check_row_count,
    validate_final_matrix,
)


class TestRowCount:
    """Tests for row count check."""

    def test_correct_row_count_passes(self) -> None:
        """Correct row count should PASS."""
        df = pd.DataFrame({"feat": [1.0] * 4371})
        check = check_row_count(df, expected=4371)
        assert check.status == "PASS"

    def test_wrong_row_count_fails(self) -> None:
        """Wrong row count should FAIL."""
        df = pd.DataFrame({"feat": [1.0] * 100})
        check = check_row_count(df, expected=4371)
        assert check.status == "FAIL"


class TestNoNaN:
    """Tests for NaN check."""

    def test_no_nan_passes(self) -> None:
        """DataFrame without NaN should PASS."""
        df = pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0]})
        check = check_no_nan(df)
        assert check.status == "PASS"

    def test_nan_fails(self) -> None:
        """DataFrame with NaN should FAIL."""
        df = pd.DataFrame({"a": [1.0, float("nan")], "b": [3.0, 4.0]})
        check = check_no_nan(df)
        assert check.status == "FAIL"
        assert "NaN" in check.message


class TestNoInf:
    """Tests for Inf check."""

    def test_no_inf_passes(self) -> None:
        """DataFrame without Inf should PASS."""
        df = pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0]})
        check = check_no_inf(df)
        assert check.status == "PASS"

    def test_inf_fails(self) -> None:
        """DataFrame with Inf should FAIL."""
        df = pd.DataFrame({"a": [1.0, float("inf")], "b": [3.0, 4.0]})
        check = check_no_inf(df)
        assert check.status == "FAIL"


class TestNoConstantFeature:
    """Tests for constant feature check."""

    def test_non_constant_passes(self) -> None:
        """Non-constant feature should PASS."""
        df = pd.DataFrame({"a": [1.0, 2.0, 3.0]})
        check = check_no_constant_features(df)
        assert check.status == "PASS"

    def test_constant_fails(self) -> None:
        """Constant feature should FAIL."""
        df = pd.DataFrame({"a": [5.0, 5.0, 5.0]})
        check = check_no_constant_features(df)
        assert check.status == "FAIL"


class TestAllNumeric:
    """Tests for all-numeric check."""

    def test_all_numeric_passes(self) -> None:
        """All-numeric DataFrame should PASS."""
        df = pd.DataFrame({"a": [1, 2], "b": [3.0, 4.0]})
        check = check_all_numeric(df)
        assert check.status == "PASS"

    def test_non_numeric_fails(self) -> None:
        """Non-numeric column should FAIL."""
        df = pd.DataFrame({"a": [1.0, 2.0], "b": ["x", "y"]})
        check = check_all_numeric(df)
        assert check.status == "FAIL"


class TestNoIdentifierInMatrix:
    """Tests for identifier leakage check."""

    def test_customerid_absent_passes(self) -> None:
        """CustomerID absent from matrix should PASS."""
        df = pd.DataFrame({"Recency": [1.0], "Frequency": [2.0]})
        check = check_no_identifier_in_matrix(df)
        assert check.status == "PASS"

    def test_customerid_present_fails(self) -> None:
        """CustomerID present in matrix should FAIL."""
        df = pd.DataFrame({"CustomerID": [1, 2], "Recency": [1.0, 2.0]})
        check = check_no_identifier_in_matrix(df)
        assert check.status == "FAIL"

    def test_invoiceno_present_fails(self) -> None:
        """InvoiceNo present in matrix should FAIL."""
        df = pd.DataFrame({"InvoiceNo": ["A001", "A002"], "Recency": [1.0, 2.0]})
        check = check_no_identifier_in_matrix(df)
        assert check.status == "FAIL"


class TestMetadataAlignment:
    """Tests for metadata/matrix alignment."""

    def test_matching_row_counts_passes(self) -> None:
        """Matching row counts should PASS."""
        matrix = pd.DataFrame({"a": [1.0, 2.0, 3.0]})
        metadata = pd.DataFrame({"CustomerID": [1, 2, 3]})
        check = check_metadata_alignment(metadata, matrix)
        assert check.status == "PASS"

    def test_mismatched_row_counts_fails(self) -> None:
        """Mismatched row counts should FAIL."""
        matrix = pd.DataFrame({"a": [1.0, 2.0]})
        metadata = pd.DataFrame({"CustomerID": [1, 2, 3]})
        check = check_metadata_alignment(metadata, matrix)
        assert check.status == "FAIL"

    def test_no_customerid_in_metadata_fails(self) -> None:
        """CustomerID absent from metadata should FAIL."""
        matrix = pd.DataFrame({"a": [1.0, 2.0, 3.0]})
        metadata = pd.DataFrame({"OtherID": [1, 2, 3]})
        check = check_metadata_alignment(metadata, matrix)
        assert check.status == "FAIL"


class TestValidateFinalMatrix:
    """Integration test for full validation."""

    def test_valid_matrix_passes(self) -> None:
        """Valid matrix passes all checks."""
        # Build matrix with 4371 rows and 14 columns
        data = {f"feat{i}": list(range(4371)) for i in range(14)}
        matrix = pd.DataFrame(data).astype(float)
        metadata = pd.DataFrame({"CustomerID": list(range(4371))})

        result = validate_final_matrix(matrix, metadata, expected_row_count=4371)
        assert result.all_passed, [c.message for c in result.checks if c.status == "FAIL"]
