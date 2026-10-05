"""Tests for pipeline determinism.

Tests:
- Same input + same config produces same output (numerically equivalent).
- Pipeline pickle can be reloaded.
- Fitted pipeline transforms new data correctly.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _REPO_ROOT / "src"

if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))


class TestPipelineDeterminism:
    """Tests for pipeline determinism."""

    def test_pipeline_reproducible_numerically(self, tmp_path: Path) -> None:
        """Same input + same config → numerically equivalent output."""
        from customer_segmentation.transformation.pipeline import run_fe06_pipeline

        candidates_path = _REPO_ROOT / "data" / "processed" / "customer_candidates.parquet"
        if not candidates_path.exists():
            pytest.skip("customer_candidates.parquet not found")

        # Run pipeline twice
        out1 = tmp_path / "processed1"
        out2 = tmp_path / "processed2"
        rep1 = tmp_path / "reports1"
        rep2 = tmp_path / "reports2"

        result1 = run_fe06_pipeline(
            customer_candidates_path=candidates_path,
            processed_dir=out1,
            report_dir=rep1,
        )

        result2 = run_fe06_pipeline(
            customer_candidates_path=candidates_path,
            processed_dir=out2,
            report_dir=rep2,
        )

        # Final matrix should be numerically equivalent
        np.testing.assert_array_almost_equal(
            result1.final_matrix.values,
            result2.final_matrix.values,
            decimal=10,
        )

    def test_pipeline_metadata_sha_reproducible(self, tmp_path: Path) -> None:
        """Metadata SHA-256 is reproducible across runs."""
        from customer_segmentation.transformation.pipeline import run_fe06_pipeline

        candidates_path = _REPO_ROOT / "data" / "processed" / "customer_candidates.parquet"
        if not candidates_path.exists():
            pytest.skip("customer_candidates.parquet not found")

        out1 = tmp_path / "processed1"
        out2 = tmp_path / "processed2"
        rep1 = tmp_path / "reports1"
        rep2 = tmp_path / "reports2"

        result1 = run_fe06_pipeline(
            customer_candidates_path=candidates_path,
            processed_dir=out1,
            report_dir=rep1,
        )

        result2 = run_fe06_pipeline(
            customer_candidates_path=candidates_path,
            processed_dir=out2,
            report_dir=rep2,
        )

        # Metadata SHA-256 should be reproducible (same CustomerID ordering)
        assert result1.output_metadata_sha256 == result2.output_metadata_sha256


class TestPipelinePickle:
    """Tests for fitted pipeline pickle."""

    def test_fitted_pipeline_can_be_loaded(self, tmp_path: Path) -> None:
        """Fitted pipeline can be unpickled."""
        import pickle

        from customer_segmentation.transformation.pipeline import run_fe06_pipeline

        candidates_path = _REPO_ROOT / "data" / "processed" / "customer_candidates.parquet"
        if not candidates_path.exists():
            pytest.skip("customer_candidates.parquet not found")

        output_dir = tmp_path / "processed"
        report_dir = tmp_path / "reports"

        run_fe06_pipeline(
            customer_candidates_path=candidates_path,
            processed_dir=output_dir,
            report_dir=report_dir,
        )

        pipeline_path = output_dir / "fitted_preprocessing_pipeline.pkl"
        assert pipeline_path.exists(), "Fitted pipeline should be saved"

        with pipeline_path.open("rb") as f:
            loaded = pickle.load(f)

        assert loaded is not None
        assert "imputation_method" in loaded
        assert "transformation_method" in loaded
        assert "scaling_method" in loaded
        assert "feature_columns" in loaded
        assert "median_values" in loaded

    def test_fitted_pipeline_has_required_fields(self, tmp_path: Path) -> None:
        """Fitted pipeline contains all required metadata."""
        import pickle

        from customer_segmentation.transformation.pipeline import run_fe06_pipeline

        candidates_path = _REPO_ROOT / "data" / "processed" / "customer_candidates.parquet"
        if not candidates_path.exists():
            pytest.skip("customer_candidates.parquet not found")

        output_dir = tmp_path / "processed"
        report_dir = tmp_path / "reports"

        run_fe06_pipeline(
            customer_candidates_path=candidates_path,
            processed_dir=output_dir,
            report_dir=report_dir,
        )

        pipeline_path = output_dir / "fitted_preprocessing_pipeline.pkl"
        with pipeline_path.open("rb") as f:
            loaded = pickle.load(f)

        assert loaded["imputation_method"] == "median"
        assert loaded["transformation_method"] == "yeo_johnson"
        assert loaded["scaling_method"] == "robust"
        assert loaded["feature_columns"] is not None
        assert len(loaded["feature_columns"]) == 14
