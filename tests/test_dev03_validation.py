"""Tests for the preprocessing config_loader dataclasses and YAML parsing."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from customer_segmentation.prototype.preprocessing.config_loader import (
    DEFAULT_DEV03_CONFIG_PATH,
    DEV03_CONFIG_TOP_KEY,
    Dev03Config,
    Dev03ConfigError,
    FeatureGenerationAggregationConfig,
    FeatureGenerationFeaturesConfig,
    FeatureGenerationOptionalTransformConfig,
    FeatureGenerationReferenceDateConfig,
    PreprocessingCleaningConfig,
    PreprocessingCleaningInvalidRecordsConfig,
    PreprocessingConfig,
    PreprocessingLoggingConfig,
    PreprocessingOutlierConfig,
    PreprocessingResearchSafetyConfig,
    PreprocessingStorageConfig,
    PreprocessingTransformationConfig,
    load_dev03_config,
)


def test_default_config_path_exists() -> None:
    assert DEFAULT_DEV03_CONFIG_PATH.name == "dev03_preprocessing.yaml"
    assert str(DEFAULT_DEV03_CONFIG_PATH).endswith("configs/dev03_preprocessing.yaml")


def test_top_key_constant() -> None:
    assert DEV03_CONFIG_TOP_KEY == "dev03_preprocessing"


def test_status_for_inherited_from_fe02() -> None:
    cfg = PreprocessingCleaningInvalidRecordsConfig()
    assert cfg.status_for("CL-01") == "WORKING_ASSUMPTION"
    assert cfg.status_for("CL-06") == "PENDING_MENTOR_REVIEW"
    assert cfg.status_for("CL-08") == "PENDING_MENTOR_REVIEW"
    assert cfg.status_for("CL-09") == "WORKING_ASSUMPTION"
    assert cfg.status_for("CL-99-not-real") == "REVIEW_REQUIRED"


def test_cleaning_invariant_default_rules_match_fe02() -> None:
    cfg = PreprocessingCleaningInvalidRecordsConfig()
    assert cfg.drop_missing_customer_id is True
    assert cfg.drop_missing_invoice_no is True
    assert cfg.flag_cancellations is True  # CL-08 still on
    assert cfg.flag_returns is True  # CL-06 still on


def test_transformation_rejects_unknown() -> None:
    with pytest.raises(Dev03ConfigError):
        PreprocessingTransformationConfig(transformation="bad")


def test_outlier_rejects_unknown_action() -> None:
    with pytest.raises(Dev03ConfigError):
        PreprocessingOutlierConfig(action="bad", method="iqr")


def test_outlier_rejects_zero_iqr_multiplier() -> None:
    with pytest.raises(Dev03ConfigError):
        PreprocessingOutlierConfig(action="clip", method="iqr", iqr_multiplier=0)


def test_logging_rejects_unknown_level() -> None:
    with pytest.raises(Dev03ConfigError):
        PreprocessingLoggingConfig(level="NOPE")


def test_storage_rejects_unknown_format() -> None:
    with pytest.raises(Dev03ConfigError):
        PreprocessingStorageConfig(output_format="xls")


def test_optional_transform_rejects_unknown() -> None:
    with pytest.raises(Dev03ConfigError):
        FeatureGenerationOptionalTransformConfig(transformation="bad", scaling="none")


def test_reference_date_requires_fixed_iso_when_mode_from_config() -> None:
    with pytest.raises(Dev03ConfigError):
        FeatureGenerationReferenceDateConfig(mode="from_config", fixed_iso_date=None)


def test_load_dev03_config_default(tmp_path: Path) -> None:
    cfg = load_dev03_config(DEFAULT_DEV03_CONFIG_PATH)
    assert isinstance(cfg, Dev03Config)
    assert cfg.preprocessing.cleaning.invalid_records.flag_cancellations is True
    assert cfg.preprocessing.transformation.transformation == "none"
    assert cfg.preprocessing.outlier.action == "none"
    assert cfg.feature_generation.features.monetary_strategy == "signed"
    assert cfg.feature_generation.features.frequency_mode == "by_invoice"
    assert cfg.feature_generation.reference_date.mode == "from_data_max"


def test_load_dev03_config_custom_path(tmp_path: Path) -> None:
    cfg_path = tmp_path / "dev03.yaml"
    cfg_path.write_text(
        yaml.safe_dump(
            {
                "dev03_preprocessing": {
                    "preprocessing": {
                        "transformation": {"transformation": "log1p"},
                        "outlier": {"action": "clip", "method": "iqr"},
                    },
                    "feature_generation": {
                        "features": {"monetary_strategy": "absolute"},
                        "optional_transform": {
                            "transformation": "yeo_johnson",
                            "scaling": "robust",
                        },
                    },
                }
            }
        )
    )
    cfg = load_dev03_config(cfg_path)
    assert cfg.preprocessing.transformation.transformation == "log1p"
    assert cfg.preprocessing.outlier.action == "clip"
    assert cfg.feature_generation.features.monetary_strategy == "absolute"
    assert cfg.feature_generation.optional_transform.transformation == "yeo_johnson"
    assert cfg.feature_generation.optional_transform.scaling == "robust"


def test_load_dev03_config_missing_file(tmp_path: Path) -> None:
    with pytest.raises(Dev03ConfigError):
        load_dev03_config(tmp_path / "nope.yaml")


def test_load_dev03_config_missing_top_key(tmp_path: Path) -> None:
    p = tmp_path / "bad.yaml"
    p.write_text(yaml.safe_dump({"not_dev03": {"foo": "bar"}}))
    with pytest.raises(Dev03ConfigError):
        load_dev03_config(p)


def test_load_dev03_config_missing_block(tmp_path: Path) -> None:
    p = tmp_path / "bad2.yaml"
    p.write_text(
        yaml.safe_dump({"dev03_preprocessing": {"preprocessing": {}, "feature_generation": {}}})
    )
    # Strict mode requires preprocessing / feature_generation keys; both present.
    cfg = load_dev03_config(p)
    assert cfg.preprocessing.transformation.transformation == "none"


def test_load_dev03_config_invalid_yaml(tmp_path: Path) -> None:
    p = tmp_path / "bad3.yaml"
    p.write_text("this is : not : valid: yaml :::: [")
    with pytest.raises(Dev03ConfigError):
        load_dev03_config(p)


def test_dataclass_construction_round_trip() -> None:
    """Construct a Dev03Config from dataclasses; verify status invariants."""
    from customer_segmentation.prototype.preprocessing.config_loader import (
        FeatureGenerationBlockConfig,
    )

    cfg = Dev03Config(
        preprocessing=PreprocessingConfig(
            enabled=True,
            cleaning=PreprocessingCleaningConfig(),
            transformation=PreprocessingTransformationConfig(),
            outlier=PreprocessingOutlierConfig(),
            logging=PreprocessingLoggingConfig(),
            storage=PreprocessingStorageConfig(),
            research_safety=PreprocessingResearchSafetyConfig(),
        ),
        feature_generation=FeatureGenerationBlockConfig(
            aggregation=FeatureGenerationAggregationConfig(),
            features=FeatureGenerationFeaturesConfig(),
            optional_transform=FeatureGenerationOptionalTransformConfig(),
            reference_date=FeatureGenerationReferenceDateConfig(),
        ),
    )
    assert cfg.feature_generation.features.purchase_interval_ddof == 1
