"""Tests for input integrity verification.

Tests:
- Input SHA-256 unchanged after pipeline
- No mutation of customer_candidates.parquet
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _REPO_ROOT / "src"

if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from customer_segmentation.transformation.versioning import (  # noqa: E402
    compute_df_sha256,
    compute_file_sha256,
)


class TestInputIntegrity:
    """Tests for input integrity verification."""

    def test_input_file_sha_unchanged(self, tmp_path: Path) -> None:
        """Input file SHA-256 is unchanged after pipeline."""
        from customer_segmentation.transformation.pipeline import run_fe06_pipeline

        candidates_path = _REPO_ROOT / "data" / "processed" / "customer_candidates.parquet"
        if not candidates_path.exists():
            pytest.skip("customer_candidates.parquet not found")

        sha_before = compute_file_sha256(candidates_path)

        output_dir = tmp_path / "processed"
        report_dir = tmp_path / "reports"

        run_fe06_pipeline(
            customer_candidates_path=candidates_path,
            processed_dir=output_dir,
            report_dir=report_dir,
        )

        sha_after = compute_file_sha256(candidates_path)
        assert sha_before == sha_after

    def test_input_content_unchanged(self, tmp_path: Path) -> None:
        """Input DataFrame content is unchanged after pipeline."""
        from customer_segmentation.transformation.pipeline import run_fe06_pipeline

        candidates_path = _REPO_ROOT / "data" / "processed" / "customer_candidates.parquet"
        if not candidates_path.exists():
            pytest.skip("customer_candidates.parquet not found")

        df_before = pd.read_parquet(candidates_path)
        sha_before = compute_df_sha256(df_before)

        output_dir = tmp_path / "processed"
        report_dir = tmp_path / "reports"

        run_fe06_pipeline(
            customer_candidates_path=candidates_path,
            processed_dir=output_dir,
            report_dir=report_dir,
        )

        df_after = pd.read_parquet(candidates_path)
        sha_after = compute_df_sha256(df_after)
        assert sha_before == sha_after

    def test_input_file_exists(self) -> None:
        """Input file exists."""
        candidates_path = _REPO_ROOT / "data" / "processed" / "customer_candidates.parquet"
        if not candidates_path.exists():
            pytest.skip("customer_candidates.parquet not found")
        assert candidates_path.exists()


class TestExpectedInputSHA:
    """Tests for expected input SHA-256."""

    def test_expected_input_sha(self) -> None:
        """Expected input SHA-256 matches FE-05 record."""
        expected_sha = "df5333fba95a48d4fe92b1136b3654d06c631f5e65313d6a34a1c15557225649"
        candidates_path = _REPO_ROOT / "data" / "processed" / "customer_candidates.parquet"
        if not candidates_path.exists():
            pytest.skip("customer_candidates.parquet not found")
        actual_sha = compute_file_sha256(candidates_path)
        assert actual_sha == expected_sha, f"Expected SHA {expected_sha}, got {actual_sha}"
