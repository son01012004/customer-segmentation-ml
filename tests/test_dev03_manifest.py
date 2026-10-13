"""Tests for the PreprocessedManifest dataclass + JSON I/O."""

from __future__ import annotations

import json
from pathlib import Path

from customer_segmentation.prototype.preprocessing.manifest import (
    PREPROCESSED_MANIFEST_SCHEMA_VERSION,
    CleaningRuleRecord,
    Dev03ManifestError,
    EnvironmentBlock,
    FeatureGenerationAggregationBlock,
    FeatureGenerationBehaviorBlock,
    FeatureGenerationBlock,
    FeatureGenerationCancellationBlock,
    FeatureGenerationDiversityBlock,
    FeatureGenerationQuantityBlock,
    FeatureGenerationRFMBlock,
    MLDatasetBlock,
    PreprocessedManifest,
    PreprocessingBlock,
    ResearchSafetyBlock,
    manifest_to_dict,
    read_preprocessed_manifest,
    runtime_field_names,
    stable_field_names,
    write_preprocessed_manifest,
)


def _make_manifest(preprocessed_id: str = "pp_0123456789abcdef01234567") -> PreprocessedManifest:
    return PreprocessedManifest(
        schema_version=PREPROCESSED_MANIFEST_SCHEMA_VERSION,
        preprocessed_id=preprocessed_id,
        preprocessed_scope="PREPROCESSED_PROTOTYPE",
        source_dataset_id="ds_0123456789abcdef01234567",
        source_dataset_sha256="0" * 64,
        config_hash="0" * 64,
        preprocessing_block=PreprocessingBlock(
            enabled=True,
            input_row_count=1000,
            input_column_count=8,
            output_row_count=900,
            rows_removed_total=100,
            rows_retained=900,
            cancellation_prefix="C",
            flag_cancellations=True,
            flag_returns=True,
            outlier_action="none",
            outlier_method="iqr",
            transformation="none",
            scaling="none",
            stage_outcomes={"A": "PASS", "B": "PASS", "C": "PASS"},
            rules=[
                CleaningRuleRecord(rule_id="CL-01", status="WORKING_ASSUMPTION"),
                CleaningRuleRecord(rule_id="CL-06", status="PENDING_MENTOR_REVIEW"),
                CleaningRuleRecord(rule_id="CL-08", status="PENDING_MENTOR_REVIEW"),
            ],
            config_snapshot={"a": 1},
            status="WORKING_ASSUMPTION",
        ),
        feature_generation_block=FeatureGenerationBlock(
            enabled=True,
            aggregation=FeatureGenerationAggregationBlock(
                enabled=True,
                customer_key="CustomerID",
                status="WORKING_ASSUMPTION",
            ),
            rfm=FeatureGenerationRFMBlock(
                monetary_strategy="signed",
                monetary_status="WORKING_ASSUMPTION",
                frequency_mode="by_invoice",
                frequency_status="WORKING_ASSUMPTION",
                reference_date_mode="from_data_max",
                reference_date_value="2011-12-10T00:00:00",
            ),
            quantity=FeatureGenerationQuantityBlock(
                default_variant="signed",
                status="WORKING_ASSUMPTION",
            ),
            behavior=FeatureGenerationBehaviorBlock(
                tenure_enabled=True,
                purchase_interval_ddof=1,
                active_days_enabled=True,
                average_invoice_value_enabled=True,
            ),
            diversity=FeatureGenerationDiversityBlock(
                strategy="products_per_invoice",
                category_count_not_materialized=True,
            ),
            cancellation=FeatureGenerationCancellationBlock(
                cancellation_enabled=True,
                return_enabled=True,
                status="WORKING_ASSUMPTION",
            ),
            optional_transform_transformation="none",
            optional_transform_scaling="none",
            optional_transform_imputation="median",
            status="PASS",
        ),
        ml_dataset_block=MLDatasetBlock(
            row_count=4371,
            column_count=15,
            columns=["CustomerID", "Recency", "Frequency", "Monetary"]
            + [f"f{i}" for i in range(11)],
            sha256="0" * 64,
            file_size_bytes=12345,
            artifact_path="ml_dataset_20261009_pp_0123456789abcdef01234567.parquet",
            status="WORKING_ASSUMPTION",
        ),
        environment=EnvironmentBlock(
            python="3.11.0",
            platform="Linux",
            release="5.0",
            machine="x86_64",
            key_libraries={"numpy": "1.26.0", "pandas": "2.2.0", "scikit-learn": "1.4.0"},
        ),
        research_safety=ResearchSafetyBlock(
            automatically_promoted_to_research=False,
            scope="PREPROCESSED_PROTOTYPE",
            appeared_in_research_evidence=False,
            read_only_paths_unmodified=[
                "data/raw/primary",
                "data/raw/backup",
                "data/processed",
                "reports",
            ],
        ),
        created_utc="2026-10-09T08:00:00Z",
        last_seen_utc="2026-10-09T08:00:00Z",
        log_file="pp_0123456789abcdef01234567.log",
        intermediate_artifact_path="preprocessed_20261009_pp_0123456789abcdef01234567.parquet",
    )


def test_schema_version_is_set() -> None:
    assert PREPROCESSED_MANIFEST_SCHEMA_VERSION == "1.0.0"


def test_stable_runtime_field_classification() -> None:
    stables = stable_field_names()
    runtimes = runtime_field_names()
    assert "preprocessed_id" in stables
    assert "preprocessing_block" in stables
    assert "research_safety" in stables
    assert "config_hash" in runtimes
    assert "environment" in runtimes
    assert "created_utc" in runtimes
    assert "last_seen_utc" in runtimes
    # Stables ∩ runtimes = ∅
    assert stables & runtimes == frozenset()


def test_manifest_to_dict_is_json_serialisable() -> None:
    m = _make_manifest()
    d = manifest_to_dict(m)
    text = json.dumps(d)
    assert isinstance(text, str)
    assert "preprocessed_id" in text


def test_round_trip_to_and_from_json(tmp_path: Path) -> None:
    m = _make_manifest()
    target = tmp_path / "manifest.json"
    write_preprocessed_manifest(m, target)
    assert target.exists()
    m2 = read_preprocessed_manifest(target)
    assert m2.preprocessed_id == m.preprocessed_id
    assert m2.source_dataset_id == m.source_dataset_id
    assert m2.preprocessing_block.rows_removed_total == 100
    assert m2.feature_generation_block.diversity.category_count_not_materialized is True
    assert m2.research_safety.automatically_promoted_to_research is False
    assert m2.environment.python == "3.11.0"


def test_write_manifest_atomic_no_temp_left(tmp_path: Path) -> None:
    m = _make_manifest()
    target = tmp_path / "m.json"
    write_preprocessed_manifest(m, target)
    # No .tmp leftover.
    leftover = list(tmp_path.glob("*.tmp"))
    assert leftover == []


def test_read_manifest_missing_file(tmp_path: Path) -> None:
    with_error_catch = False
    try:
        read_preprocessed_manifest(tmp_path / "nope.json")
    except Dev03ManifestError:
        with_error_catch = True
    assert with_error_catch


def test_read_manifest_malformed_json(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("{this is not json", encoding="utf-8")
    with_error_catch = False
    try:
        read_preprocessed_manifest(p)
    except Dev03ManifestError:
        with_error_catch = True
    assert with_error_catch


def test_research_safety_block_always_safe() -> None:
    """The three required safety markers MUST be set."""
    m = _make_manifest()
    rs = m.research_safety
    assert rs.automatically_promoted_to_research is False
    assert rs.appeared_in_research_evidence is False
    assert rs.scope == "PREPROCESSED_PROTOTYPE"


def test_cleaning_rules_status_inherited_verbatim() -> None:
    m = _make_manifest()
    rules_dict = {r.rule_id: r.status for r in m.preprocessing_block.rules}
    assert rules_dict["CL-01"] == "WORKING_ASSUMPTION"
    assert rules_dict["CL-06"] == "PENDING_MENTOR_REVIEW"
    assert rules_dict["CL-08"] == "PENDING_MENTOR_REVIEW"
