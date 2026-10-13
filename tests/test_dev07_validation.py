"""Tests for DEV-07 Stage C input validation gate.

Covers the per-check functions and the aggregate :func:`validate_inputs`
gate. Only synthetic manifest data is used (no real research data).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from customer_segmentation.prototype.marketing.config_loader import (
    DEFAULT_DEV07_CONFIG_PATH,
    Dev07Config,
    Dev07DisplayConfig,
    Dev07LoggingConfig,
    Dev07MktFrameworkConfig,
    Dev07ResearchSafetyConfig,
    Dev07StorageConfig,
    Dev07ValidationConfig,
    load_dev07_config,
)
from customer_segmentation.prototype.marketing.exceptions import (
    MarketingConfigError,
)
from customer_segmentation.prototype.marketing.scope import (
    FORBIDDEN_MARKETING_TERMS,
    KPI_BLOCKLIST,
)
from customer_segmentation.prototype.marketing.validation import (
    DBSCAN_NOISE_SEGMENT_ID,
    MarketingInputValidationError,
    compute_file_sha256,
    validate_inputs,
    validate_kpi_blocklist,
    validate_no_duplicate_segment_id,
    validate_noise_segments_isolated,
    validate_research_safety_block,
    validate_segmentation_manifest_shape,
    validate_text_no_forbidden_terms,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_manifest_data(**overrides) -> dict:
    """Build a minimal-but-valid DEV-06 segmentation manifest payload.

    All string values are chosen to be free of FORBIDDEN_MARKETING_TERMS
    so the gate passes by default.
    """
    base = {
        "schema_version": "1.0.0",
        "segmentation_id": "seg_" + "0" * 24,
        "scope": "PROFILED_PROTOTYPE",
        "clustering_id": "cl_" + "1" * 24,
        "preprocessed_id": "pp_test",
        "dataset_id": "ds_test",
        "algorithm": "kmeans",
        "algorithm_family": "hard",
        "ml_dataset_sha256": "a" * 64,
        "feature_set_sha256": "b" * 64,
        "preprocessing_config_sha256": "c" * 64,
        "noise_policy_used": "n/a",
        "segment_sizes": [
            {"segment_id": 0, "count": 100, "percentage": 0.5, "is_noise": False},
            {"segment_id": 1, "count": 100, "percentage": 0.5, "is_noise": False},
        ],
        "research_safety": {
            "automatically_promoted_to_research": False,
            "scope": "PROFILED_PROTOTYPE",
            "appeared_in_research_evidence": False,
            "read_only_paths_unmodified": [],
        },
        "input_segmentation_manifest": "segmentation_manifest.json",
        "input_cluster_labels": "cluster_labels.parquet",
        "input_ml_dataset": "ml_dataset.parquet",
        "input_evaluation_manifest": None,
    }
    base.update(overrides)
    return base


def _make_validation_config(**overrides) -> Dev07ValidationConfig:
    base = {
        "forbid_internal_metrics_as_kpi": True,
        "forbid_marketing_terminology": True,
        "require_no_duplicate_segment_id": True,
        "exclude_dbscan_noise": True,
    }
    base.update(overrides)
    return Dev07ValidationConfig(**base)


def _make_full_config(**validation_overrides) -> Dev07Config:
    """Build a minimal Dev07Config with a configurable validation block."""
    validation = _make_validation_config(**validation_overrides)
    return Dev07Config(
        schema_version="1.0.0",
        availability_default="REVIEW_REQUIRED",
        mkt_framework=Dev07MktFrameworkConfig(
            path_relative="docs/marketing",
            # Canonical aggregate form per ADR-0008 (Option A).
            version_pattern=r"^MKT-01\.\.05__v\d+(?:\.\d+)*$",
        ),
        display=Dev07DisplayConfig(
            percentage_decimals=2,
            missing_value_placeholder="--",
            csv_missing_value="",
            disclaimer_text="no marketing recommendation, ranking, or winner annotation is emitted; descriptive view only",
        ),
        storage=Dev07StorageConfig(
            output_dir_relative="marketing",
            emit_manifest_json=True,
            emit_recommendations_csv=False,
            emit_recommendations_jsonl=False,
        ),
        logging=Dev07LoggingConfig(
            level="INFO",
            format="%(asctime)s | %(levelname)-8s | %(name)s | %(stage)s | %(message)s",
            log_dir_relative="data/prototype/datasets",
            emit_to_console=True,
        ),
        research_safety=Dev07ResearchSafetyConfig(
            readonly_paths=["data/raw/primary"],
            never_promote_to_research=True,
            marketing_scope="MARKETING_PROTOTYPE",
        ),
        validation=validation,
    )


# ---------------------------------------------------------------------------
# Constants / DBSCAN sentinel
# ---------------------------------------------------------------------------


def test_dbscan_noise_segment_id_constant() -> None:
    assert DBSCAN_NOISE_SEGMENT_ID == -1


def test_kpi_blocklist_nonempty() -> None:
    assert len(KPI_BLOCKLIST) > 0
    assert "silhouette_score" in KPI_BLOCKLIST


def test_forbidden_marketing_terms_nonempty() -> None:
    assert len(FORBIDDEN_MARKETING_TERMS) > 0


# ---------------------------------------------------------------------------
# validate_segmentation_manifest_shape
# ---------------------------------------------------------------------------


class TestValidateSegmentationManifestShape:
    def test_full_manifest_all_present(self) -> None:
        data = _make_manifest_data()
        checks = validate_segmentation_manifest_shape(data)
        # All required-field checks must pass.
        passed_checks = [c for c in checks if c.passed]
        assert len(passed_checks) == len(checks)
        # Every check_id has the expected prefix.
        for c in checks:
            assert c.check_id.startswith("dev07_seg_manifest_")
            assert c.detail != ""

    def test_missing_required_field(self) -> None:
        data = _make_manifest_data()
        del data["research_safety"]
        checks = validate_segmentation_manifest_shape(data)
        missing = [c for c in checks if not c.passed and "research_safety" in c.check_id]
        assert len(missing) == 1
        assert "missing" in missing[0].detail

    def test_multiple_missing_fields(self) -> None:
        data = _make_manifest_data()
        del data["segment_sizes"]
        del data["noise_policy_used"]
        checks = validate_segmentation_manifest_shape(data)
        failed = [c for c in checks if not c.passed]
        assert len(failed) >= 2


# ---------------------------------------------------------------------------
# validate_research_safety_block
# ---------------------------------------------------------------------------


class TestValidateResearchSafetyBlock:
    def test_valid_block(self) -> None:
        data = _make_manifest_data()
        checks = validate_research_safety_block(data)
        assert all(c.passed for c in checks)
        # Both check_ids present.
        ids = {c.check_id for c in checks}
        assert "dev07_seg_scope_profiled_prototype" in ids
        assert "dev07_seg_not_promoted_to_research" in ids

    def test_wrong_scope(self) -> None:
        data = _make_manifest_data()
        data["research_safety"]["scope"] = "MARKETING_PROTOTYPE"
        checks = validate_research_safety_block(data)
        scope_checks = [c for c in checks if c.check_id == "dev07_seg_scope_profiled_prototype"]
        assert len(scope_checks) == 1
        assert scope_checks[0].passed is False

    def test_promoted_true(self) -> None:
        data = _make_manifest_data()
        data["research_safety"]["automatically_promoted_to_research"] = True
        checks = validate_research_safety_block(data)
        bad = [c for c in checks if c.check_id == "dev07_seg_not_promoted_to_research"]
        assert len(bad) == 1
        assert bad[0].passed is False


# ---------------------------------------------------------------------------
# validate_noise_segments_isolated
# ---------------------------------------------------------------------------


class TestValidateNoiseSegmentsIsolated:
    def test_gate_enabled(self) -> None:
        sizes = [{"segment_id": 0, "is_noise": False}]
        checks = validate_noise_segments_isolated(sizes, exclude_dbscan_noise=True)
        assert all(c.passed for c in checks)

    def test_noise_count_recorded(self) -> None:
        sizes = [
            {"segment_id": 0, "is_noise": False},
            {"segment_id": -1, "is_noise": True},
            {"segment_id": -1, "is_noise": True},
        ]
        checks = validate_noise_segments_isolated(sizes, exclude_dbscan_noise=True)
        assert len(checks) == 1
        assert "2 noise entries" in checks[0].detail

    def test_gate_disabled_fails(self) -> None:
        sizes = [{"segment_id": 0, "is_noise": False}]
        checks = validate_noise_segments_isolated(sizes, exclude_dbscan_noise=False)
        assert len(checks) == 1
        assert checks[0].passed is False
        assert "DISABLED" in checks[0].detail


# ---------------------------------------------------------------------------
# validate_no_duplicate_segment_id
# ---------------------------------------------------------------------------


class TestValidateNoDuplicateSegmentId:
    def test_unique_segment_ids(self) -> None:
        sizes = [
            {"segment_id": 0, "is_noise": False},
            {"segment_id": 1, "is_noise": False},
            {"segment_id": 2, "is_noise": False},
        ]
        checks = validate_no_duplicate_segment_id(sizes)
        assert all(c.passed for c in checks)

    def test_duplicate_segment_ids_fail(self) -> None:
        sizes = [
            {"segment_id": 0, "is_noise": False},
            {"segment_id": 1, "is_noise": False},
            {"segment_id": 1, "is_noise": False},
        ]
        checks = validate_no_duplicate_segment_id(sizes)
        failed = [c for c in checks if not c.passed]
        assert len(failed) == 1
        assert "1" in failed[0].detail

    def test_noise_segment_id_excluded_from_uniqueness(self) -> None:
        sizes = [
            {"segment_id": -1, "is_noise": True},
            {"segment_id": -1, "is_noise": True},  # Multiple noise rows are OK in raw input
        ]
        checks = validate_no_duplicate_segment_id(sizes)
        assert all(c.passed for c in checks)

    def test_check_skipped(self) -> None:
        sizes = [
            {"segment_id": 0, "is_noise": False},
            {"segment_id": 0, "is_noise": False},  # duplicate
        ]
        checks = validate_no_duplicate_segment_id(sizes, require=False)
        assert all(c.passed for c in checks)


# ---------------------------------------------------------------------------
# validate_kpi_blocklist
# ---------------------------------------------------------------------------


class TestValidateKpiBlocklist:
    def test_none_kpi_passes(self) -> None:
        checks = validate_kpi_blocklist(None)
        assert all(c.passed for c in checks)

    def test_empty_kpi_passes(self) -> None:
        checks = validate_kpi_blocklist([])
        assert all(c.passed for c in checks)

    def test_safe_kpi_passes(self) -> None:
        checks = validate_kpi_blocklist(["repeat_purchase_rate", "average_order_value"])
        assert all(c.passed for c in checks)

    def test_silhouette_blocked(self) -> None:
        checks = validate_kpi_blocklist(["silhouette_score"])
        failed = [c for c in checks if not c.passed]
        assert len(failed) == 1
        assert "silhouette_score" in failed[0].detail

    def test_wcss_blocked(self) -> None:
        checks = validate_kpi_blocklist(["wcss"])
        failed = [c for c in checks if not c.passed]
        assert len(failed) == 1

    def test_case_insensitive(self) -> None:
        """Blocklist is case-insensitive (KPI_BLOCKLIST lower-cased at match)."""
        checks = validate_kpi_blocklist(["SILHOUETTE_SCORE"])
        failed = [c for c in checks if not c.passed]
        assert len(failed) == 1

    def test_mixed_safe_and_blocked(self) -> None:
        checks = validate_kpi_blocklist(["repeat_purchase_rate", "ari", "average_order_value"])
        failed = [c for c in checks if not c.passed]
        assert len(failed) == 1
        assert "ari" in failed[0].detail

    def test_check_skipped(self) -> None:
        checks = validate_kpi_blocklist(["silhouette"], enforce=False)
        assert all(c.passed for c in checks)


# ---------------------------------------------------------------------------
# validate_text_no_forbidden_terms
# ---------------------------------------------------------------------------


class TestValidateTextNoForbiddenTerms:
    def test_clean_text_passes(self) -> None:
        checks = validate_text_no_forbidden_terms("A perfectly clean description.")
        assert all(c.passed for c in checks)

    def test_champion_blocked(self) -> None:
        checks = validate_text_no_forbidden_terms("champion segment description")
        failed = [c for c in checks if not c.passed]
        assert len(failed) == 1
        assert "champion" in failed[0].detail

    def test_loyal_blocked(self) -> None:
        checks = validate_text_no_forbidden_terms("loyal customer cohort")
        failed = [c for c in checks if not c.passed]
        assert len(failed) == 1

    def test_vip_blocked(self) -> None:
        checks = validate_text_no_forbidden_terms("VIP tier")
        failed = [c for c in checks if not c.passed]
        assert len(failed) == 1

    def test_churn_blocked(self) -> None:
        checks = validate_text_no_forbidden_terms("churn risk")
        failed = [c for c in checks if not c.passed]
        assert len(failed) == 1

    def test_ltv_blocked(self) -> None:
        checks = validate_text_no_forbidden_terms("ltv projection")
        failed = [c for c in checks if not c.passed]
        assert len(failed) == 1

    def test_check_skipped(self) -> None:
        checks = validate_text_no_forbidden_terms("champion segment", enforce=False)
        assert all(c.passed for c in checks)


# ---------------------------------------------------------------------------
# validate_inputs (aggregate gate)
# ---------------------------------------------------------------------------


class TestValidateInputs:
    def test_valid_manifest_passes(self) -> None:
        cfg = _make_full_config()
        data = _make_manifest_data()
        report = validate_inputs(manifest_data=data, config=cfg)
        assert report.all_passed
        assert len(report.checks) > 0

    def test_invalid_scope_fails(self) -> None:
        cfg = _make_full_config()
        data = _make_manifest_data()
        data["research_safety"]["scope"] = "MARKETING_PROTOTYPE"
        with pytest.raises(MarketingInputValidationError):
            validate_inputs(manifest_data=data, config=cfg)

    def test_duplicate_segment_id_fails(self) -> None:
        cfg = _make_full_config()
        data = _make_manifest_data()
        data["segment_sizes"] = [
            {"segment_id": 0, "count": 100, "percentage": 0.5, "is_noise": False},
            {"segment_id": 0, "count": 100, "percentage": 0.5, "is_noise": False},
        ]
        with pytest.raises(MarketingInputValidationError, match="segment_id"):
            validate_inputs(manifest_data=data, config=cfg)

    def test_promoted_to_research_fails(self) -> None:
        cfg = _make_full_config()
        data = _make_manifest_data()
        data["research_safety"]["automatically_promoted_to_research"] = True
        with pytest.raises(MarketingInputValidationError):
            validate_inputs(manifest_data=data, config=cfg)

    def test_segment_sizes_must_be_list(self) -> None:
        cfg = _make_full_config()
        data = _make_manifest_data()
        data["segment_sizes"] = "not a list"
        with pytest.raises(MarketingInputValidationError, match="segment_sizes"):
            validate_inputs(manifest_data=data, config=cfg)

    def test_dbscan_noise_in_segment_sizes_ok(self) -> None:
        """Noise entries are expected and counted, not rejected."""
        cfg = _make_full_config()
        data = _make_manifest_data()
        data["segment_sizes"] = [
            {"segment_id": 0, "count": 100, "percentage": 0.5, "is_noise": False},
            {"segment_id": -1, "count": 50, "percentage": 0.25, "is_noise": True},
        ]
        report = validate_inputs(manifest_data=data, config=cfg)
        assert report.all_passed

    def test_kpi_blocklist_disabled_passes(self) -> None:
        cfg = _make_full_config(forbid_internal_metrics_as_kpi=False)
        data = _make_manifest_data()
        report = validate_inputs(manifest_data=data, config=cfg)
        assert report.all_passed

    def test_forbidden_terms_disabled_passes(self) -> None:
        cfg = _make_full_config(forbid_marketing_terminology=False)
        data = _make_manifest_data()
        # Embed a term in a string field; validation should not flag it.
        data["input_cluster_labels"] = "champion_cluster_labels.parquet"
        report = validate_inputs(manifest_data=data, config=cfg)
        assert report.all_passed


# ---------------------------------------------------------------------------
# compute_file_sha256
# ---------------------------------------------------------------------------


class TestComputeFileSha256:
    def test_returns_64_hex(self, tmp_path: Path) -> None:
        p = tmp_path / "data.bin"
        p.write_bytes(b"hello world")
        sha = compute_file_sha256(p)
        assert len(sha) == 64
        assert all(c in "0123456789abcdef" for c in sha)

    def test_deterministic(self, tmp_path: Path) -> None:
        p = tmp_path / "data.bin"
        p.write_bytes(b"hello world")
        assert compute_file_sha256(p) == compute_file_sha256(p)

    def test_changes_with_content(self, tmp_path: Path) -> None:
        p1 = tmp_path / "a.bin"
        p2 = tmp_path / "b.bin"
        p1.write_bytes(b"alpha")
        p2.write_bytes(b"beta")
        assert compute_file_sha256(p1) != compute_file_sha256(p2)


# ---------------------------------------------------------------------------
# Default config loader integration
# ---------------------------------------------------------------------------


def test_default_dev07_config_has_validation_block() -> None:
    cfg = load_dev07_config()
    assert isinstance(cfg, Dev07Config)
    assert isinstance(cfg.validation, Dev07ValidationConfig)
    assert cfg.validation.forbid_internal_metrics_as_kpi is True
    assert cfg.validation.forbid_marketing_terminology is True
    assert cfg.validation.require_no_duplicate_segment_id is True
    assert cfg.validation.exclude_dbscan_noise is True


def test_default_dev07_config_path_exists() -> None:
    assert DEFAULT_DEV07_CONFIG_PATH.exists()


def test_load_dev07_config_missing_file(tmp_path: Path) -> None:
    with pytest.raises(MarketingConfigError, match="not found"):
        load_dev07_config(path=tmp_path / "missing.yaml")
