"""Tests for the DEV-06 YAML configuration loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from customer_segmentation.prototype.segmentation.config_loader import (
    DEFAULT_DEV06_CONFIG_PATH,
    DEV06_CONFIG_TOP_KEY,
    VALID_LOG_LEVELS,
    Dev06CharacteristicRulesConfig,
    Dev06CompareConfig,
    Dev06Config,
    Dev06ConfigError,
    Dev06DisplayConfig,
    Dev06LoggingConfig,
    Dev06NoisePolicyConfig,
    Dev06ResearchSafetyConfig,
    Dev06StatisticsConfig,
    Dev06StorageConfig,
    Dev06ValidationConfig,
    find_default_dev06_config_path,
    load_dev06_config,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _write_yaml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "dev06_segmentation.yaml"
    p.write_text(content, encoding="utf-8")
    return p


def _minimal_yaml() -> str:
    return """\
dev06_segmentation:
  noise_policy:
    default: "exclude"
"""


def _full_yaml() -> str:
    return """\
dev06_segmentation:
  noise_policy:
    default: "exclude"
  statistics:
    numerical: [mean, median, std, q1, q3, min, max]
    categorical_topk: 10
    categorical_uniqueness_threshold: 50
  characteristic_rules:
    enabled:
      - "mean_high_<feature>"
      - "mean_low_<feature>"
      - "median_above_dataset_median_<feature>"
      - "top_category_<feature>_<value>"
    z_threshold: 1.0
  display:
    percentage_decimals: 2
    missing_value_placeholder: "--"
    csv_missing_value: ""
    disclaimer_text: "no ranking, recommendation, or winner annotation is emitted"
  storage:
    output_dir_relative: "segmentation"
    emit_profiles_csv: true
    emit_profiles_json: true
    emit_characteristics_json: true
    emit_sizes_long_csv: true
  logging:
    level: "INFO"
    format: "%(asctime)s | %(levelname)-8s | %(name)s | %(stage)s | %(message)s"
    log_dir_relative: "data/prototype/datasets"
    emit_to_console: true
  research_safety:
    readonly_paths:
      - "data/raw/primary"
      - "data/raw/backup"
      - "data/processed"
      - "reports"
    never_promote_to_research: true
    segmentation_scope: "PROFILED_PROTOTYPE"
  validation:
    min_samples: 2
    min_features: 1
    require_no_nan: false
    exclude_customer_id_from_features: true
  compare:
    emit_singleton_group: true
    show_provenance_per_row: true
    disclaimer_text: "no ranking, recommendation, or winner annotation is emitted"
"""


# ---------------------------------------------------------------------------
# Paths / module surface
# ---------------------------------------------------------------------------


def test_default_dev06_config_path() -> None:
    """Default config path is `configs/dev06_segmentation.yaml`."""
    assert DEFAULT_DEV06_CONFIG_PATH.name == "dev06_segmentation.yaml"
    assert DEFAULT_DEV06_CONFIG_PATH.parent.name == "configs"


def test_dev06_config_top_key_constant() -> None:
    assert DEV06_CONFIG_TOP_KEY == "dev06_segmentation"


def test_find_default_dev06_config_path() -> None:
    p = find_default_dev06_config_path()
    assert p == DEFAULT_DEV06_CONFIG_PATH


def test_valid_log_levels_includes_standard_python_levels() -> None:
    assert frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}) == VALID_LOG_LEVELS


# ---------------------------------------------------------------------------
# Default dataclass values
# ---------------------------------------------------------------------------


def test_noise_policy_default() -> None:
    cfg = Dev06NoisePolicyConfig()
    assert cfg.default == "exclude"


def test_statistics_default_includes_seven_numerical() -> None:
    cfg = Dev06StatisticsConfig()
    assert "mean" in cfg.numerical
    assert "median" in cfg.numerical
    assert "std" in cfg.numerical
    assert "q1" in cfg.numerical
    assert "q3" in cfg.numerical
    assert "min" in cfg.numerical
    assert "max" in cfg.numerical


def test_statistics_default_categorical_topk_is_10() -> None:
    """Per OQ-SEG-DISPLAY-01, default top-K is 10."""
    cfg = Dev06StatisticsConfig()
    assert cfg.categorical_topk == 10


def test_characteristic_rules_default_set_of_four() -> None:
    """Per OQ-SEG-CHAR-01, the reduced set has exactly 4 rules."""
    cfg = Dev06CharacteristicRulesConfig()
    assert len(cfg.enabled) == 4
    assert "mean_high_<feature>" in cfg.enabled
    assert "mean_low_<feature>" in cfg.enabled
    assert "median_above_dataset_median_<feature>" in cfg.enabled
    assert "top_category_<feature>_<value>" in cfg.enabled


def test_characteristic_rules_drops_quality_indicators() -> None:
    """Per OQ-SEG-CHAR-01, ``category_diversity_low_<feature>`` and
    ``missing_share_high_<feature>`` are REMOVED (they are profile
    stats, not characteristics)."""
    cfg = Dev06CharacteristicRulesConfig()
    for rule in cfg.enabled:
        assert not rule.startswith("category_diversity_low_")
        assert not rule.startswith("missing_share_high_")


def test_display_default_missing_value_placeholder() -> None:
    cfg = Dev06DisplayConfig()
    assert cfg.missing_value_placeholder == "--"


def test_logging_default_level_is_info() -> None:
    cfg = Dev06LoggingConfig()
    assert cfg.level == "INFO"


def test_storage_default_output_dir_relative() -> None:
    cfg = Dev06StorageConfig()
    assert cfg.output_dir_relative == "segmentation"


def test_research_safety_default_scope_is_profiled_prototype() -> None:
    cfg = Dev06ResearchSafetyConfig()
    assert cfg.segmentation_scope == "PROFILED_PROTOTYPE"


def test_validation_default_min_samples() -> None:
    cfg = Dev06ValidationConfig()
    assert cfg.min_samples == 2
    assert cfg.min_features == 1
    assert cfg.exclude_customer_id_from_features is True


def test_compare_default_disclaimer_text() -> None:
    cfg = Dev06CompareConfig()
    assert "no ranking" in cfg.disclaimer_text
    assert "recommendation" in cfg.disclaimer_text
    assert "winner" in cfg.disclaimer_text


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------


def test_noise_policy_rejects_invalid_value() -> None:
    with pytest.raises(Dev06ConfigError):
        Dev06NoisePolicyConfig(default="maybe")


def test_logging_rejects_invalid_level() -> None:
    with pytest.raises(Dev06ConfigError):
        Dev06LoggingConfig(level="TRACE")


def test_research_safety_rejects_wrong_scope() -> None:
    with pytest.raises(Dev06ConfigError, match="PROFILED_PROTOTYPE"):
        Dev06ResearchSafetyConfig(segmentation_scope="RESEARCH_APPROVED")


def test_characteristic_rules_rejects_empty() -> None:
    with pytest.raises(Dev06ConfigError):
        Dev06CharacteristicRulesConfig(enabled=())


def test_characteristic_rules_rejects_non_string() -> None:
    with pytest.raises(Dev06ConfigError):
        Dev06CharacteristicRulesConfig(enabled=("mean_high_<feature>", 123))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# YAML loader — minimal
# ---------------------------------------------------------------------------


def test_load_minimal_config(tmp_path: Path) -> None:
    p = _write_yaml(tmp_path, _minimal_yaml())
    cfg, raw = load_dev06_config(p)
    assert isinstance(cfg, Dev06Config)
    assert cfg.noise_policy.default == "exclude"
    assert "noise_policy" in raw


def test_load_full_config(tmp_path: Path) -> None:
    p = _write_yaml(tmp_path, _full_yaml())
    cfg, _ = load_dev06_config(p)
    assert cfg.noise_policy.default == "exclude"
    assert cfg.statistics.categorical_topk == 10
    assert len(cfg.characteristic_rules.enabled) == 4
    assert cfg.display.csv_missing_value == ""
    assert cfg.storage.output_dir_relative == "segmentation"
    assert cfg.logging.level == "INFO"
    assert cfg.research_safety.segmentation_scope == "PROFILED_PROTOTYPE"
    assert cfg.validation.exclude_customer_id_from_features is True
    assert cfg.compare.emit_singleton_group is True


def test_load_config_returns_raw_text_for_sha256(tmp_path: Path) -> None:
    p = _write_yaml(tmp_path, _minimal_yaml())
    cfg, raw_text = load_dev06_config(p)
    # Same raw text on each call.
    cfg2, raw_text2 = load_dev06_config(p)
    assert raw_text == raw_text2


# ---------------------------------------------------------------------------
# YAML loader — error cases
# ---------------------------------------------------------------------------


def test_load_config_missing_file(tmp_path: Path) -> None:
    with pytest.raises(Dev06ConfigError, match="not found"):
        load_dev06_config(tmp_path / "nonexistent.yaml")


def test_load_config_missing_top_key(tmp_path: Path) -> None:
    bad = """\
some_other_key:
  noise_policy:
    default: "exclude"
"""
    p = _write_yaml(tmp_path, bad)
    with pytest.raises(Dev06ConfigError, match="dev06_segmentation"):
        load_dev06_config(p)


def test_load_config_invalid_yaml(tmp_path: Path) -> None:
    p = _write_yaml(tmp_path, "dev06_segmentation: [unclosed")
    with pytest.raises(Dev06ConfigError, match="YAML"):
        load_dev06_config(p)


def test_load_config_invalid_noise_policy_value(tmp_path: Path) -> None:
    bad = """\
dev06_segmentation:
  noise_policy:
    default: "maybe"
"""
    p = _write_yaml(tmp_path, bad)
    with pytest.raises(Dev06ConfigError):
        load_dev06_config(p)


def test_load_config_top_key_not_mapping(tmp_path: Path) -> None:
    bad = """\
dev06_segmentation: "should_be_a_mapping"
"""
    p = _write_yaml(tmp_path, bad)
    with pytest.raises(Dev06ConfigError):
        load_dev06_config(p)


def test_load_config_empty_file(tmp_path: Path) -> None:
    p = _write_yaml(tmp_path, "")
    with pytest.raises(Dev06ConfigError, match="dev06_segmentation"):
        load_dev06_config(p)


# ---------------------------------------------------------------------------
# Default path exists
# ---------------------------------------------------------------------------


def test_default_config_file_exists() -> None:
    """The canonical `configs/dev06_segmentation.yaml` must exist after Phase 2A."""
    assert DEFAULT_DEV06_CONFIG_PATH.exists(), (
        f"Default config not found at {DEFAULT_DEV06_CONFIG_PATH}. "
        "Phase 2A must create configs/dev06_segmentation.yaml."
    )


def test_default_config_file_loads() -> None:
    """The canonical config must parse to a valid Dev06Config."""
    cfg, _ = load_dev06_config(DEFAULT_DEV06_CONFIG_PATH)
    assert isinstance(cfg, Dev06Config)
    assert cfg.noise_policy.default == "exclude"
    assert cfg.research_safety.segmentation_scope == "PROFILED_PROTOTYPE"
