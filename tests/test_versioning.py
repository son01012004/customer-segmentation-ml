"""Tests for versioning utilities.

Tests:
- SHA-256 computation
- Dataset version
- Reproducibility
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from customer_segmentation.transformation.versioning import (
    FE06_VERSION,
    compute_df_sha256,
    compute_file_sha256,
    compute_sha256,
)


class TestSHA256:
    """Tests for SHA-256 computation."""

    def test_compute_sha256_bytes(self) -> None:
        """compute_sha256 returns hex digest."""
        result = compute_sha256(b"hello world")
        assert isinstance(result, str)
        assert len(result) == 64  # SHA-256 produces 64 hex chars

    def test_deterministic(self) -> None:
        """Same bytes produce same SHA-256."""
        result1 = compute_sha256(b"hello world")
        result2 = compute_sha256(b"hello world")
        assert result1 == result2

    def test_different_bytes_different_hash(self) -> None:
        """Different bytes produce different SHA-256."""
        h1 = compute_sha256(b"hello")
        h2 = compute_sha256(b"world")
        assert h1 != h2


class TestFileSHA256:
    """Tests for file SHA-256 computation."""

    def test_file_sha256_deterministic(self, tmp_path: Path) -> None:
        """Same file produces same SHA-256."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"hello world")
        h1 = compute_file_sha256(test_file)
        h2 = compute_file_sha256(test_file)
        assert h1 == h2

    def test_file_sha256_matches_bytes(self, tmp_path: Path) -> None:
        """File SHA-256 matches bytes SHA-256."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"hello world")
        h_file = compute_file_sha256(test_file)
        h_bytes = compute_sha256(b"hello world")
        assert h_file == h_bytes


class TestDataFrameSHA256:
    """Tests for DataFrame SHA-256 computation."""

    def test_df_sha256_deterministic(self) -> None:
        """Same DataFrame produces same SHA-256."""
        df = pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [4.0, 5.0, 6.0]})
        h1 = compute_df_sha256(df)
        h2 = compute_df_sha256(df)
        assert h1 == h2

    def test_different_df_different_sha(self) -> None:
        """Different DataFrames produce different SHA-256."""
        df1 = pd.DataFrame({"a": [1.0, 2.0]})
        df2 = pd.DataFrame({"a": [1.0, 3.0]})
        h1 = compute_df_sha256(df1)
        h2 = compute_df_sha256(df2)
        assert h1 != h2


class TestFE06Version:
    """Tests for FE-06 version constant."""

    def test_version_format(self) -> None:
        """FE06_VERSION follows FE06-vMAJOR.MINOR format."""
        assert FE06_VERSION.startswith(
            "FE06-"
        ), f"Version should start with FE06-, got {FE06_VERSION}"
        assert "-v" in FE06_VERSION, f"Version should contain -v, got {FE06_VERSION}"

    def test_version_is_string(self) -> None:
        """FE06_VERSION is a string."""
        assert isinstance(FE06_VERSION, str)
