"""Tests for the DEV-05 configuration loader."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from customer_segmentation.prototype.evaluation.config_loader import (
    DEFAULT_DEV05_CONFIG_PATH,
    DEV05_CONFIG_TOP_KEY,
    Dev05Config,
    Dev05ConfigError,
    VALID_LOG_LEVELS,
    find_default_dev05_config_path,
    load_dev05_config,
)


class TestFindDefaultDev05ConfigPath:
    def test_returns_canonical_path(self) -> None:
        path = find_default_dev05_config_path()
        assert isinstance(path, Path)
        assert path.name == "dev05_evaluation.yaml"
        assert path == DEFAULT_DEV05_CONFIG_PATH

    def test_path_inside_configs_dir(self) -> None:
        path = find_default_dev05_config_path()
        assert path.parent.name == "configs"


class TestLoadDev05Config:
    def test_load_default_config(self) -> None:
        cfg, raw_text = load_dev05_config()
        assert isinstance(cfg, Dev05Config)
        assert isinstance(raw_text, str)
        assert DEV05_CONFIG_TOP_KEY in raw_text

    def test_all_three_metrics_present(self) -> None:
        cfg, _ = load_dev05_config()
        assert set(cfg.metrics.enabled) == {
            "silhouette",
            "davies_bouldin",
            "calinski_harabasz",
        }
        # Order must be preserved (canonical row order).
        assert cfg.metrics.enabled == (
            "silhouette",
            "davies_bouldin",
            "calinski_harabasz",
        )

    def test_noise_policy_default_is_exclude(self) -> None:
        cfg, _ = load_dev05_config()
        assert cfg.noise_policy.default == "exclude"

    def test_display_placeholders(self) -> None:
        cfg, _ = load_dev05_config()
        assert cfg.display.missing_value_placeholder == "--"
        assert cfg.display.csv_missing_value == ""

    def test_logging_level_info(self) -> None:
        cfg, _ = load_dev05_config()
        assert cfg.logging.level == "INFO"
        assert cfg.logging.emit_to_console is True
        assert "%(stage)s" in cfg.logging.format

    def test_storage_settings(self) -> None:
        cfg, _ = load_dev05_config()
        assert cfg.storage.output_dir_relative == "evaluation"
        assert cfg.storage.emit_metrics_csv is True

    def test_research_safety_never_promote(self) -> None:
        cfg, _ = load_dev05_config()
        assert cfg.research_safety.never_promote_to_research is True
        assert "data/raw/primary" in cfg.research_safety.readonly_paths
        assert cfg.research_safety.evaluation_scope == "EVALUATED_PROTOTYPE"

    def test_validation_require_no_nan(self) -> None:
        cfg, _ = load_dev05_config()
        assert cfg.validation.require_no_nan is True
        assert cfg.validation.min_samples == 2
        assert cfg.validation.exclude_customer_id_from_features is True

    def test_compare_settings(self) -> None:
        cfg, _ = load_dev05_config()
        assert cfg.compare.emit_singleton_group is True
        assert cfg.compare.show_provenance_per_row is True
        assert "ranking" in cfg.compare.disclaimer_text
        assert "recommendation" in cfg.compare.disclaimer_text
        assert "winner" in cfg.compare.disclaimer_text

    def test_load_custom_yaml(self, tmp_path: Path) -> None:
        custom = {
            "dev05_evaluation": {
                "noise_policy": {"default": "include"},
                "display": {"missing_value_placeholder": "n/a"},
            }
        }
        path = tmp_path / "custom.yaml"
        with path.open("w", encoding="utf-8") as fh:
            yaml.dump(custom, fh)
        cfg, _ = load_dev05_config(path)
        assert cfg.noise_policy.default == "include"
        assert cfg.display.missing_value_placeholder == "n/a"

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(Dev05ConfigError):
            load_dev05_config(tmp_path / "nonexistent.yaml")

    def test_invalid_yaml_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.yaml"
        path.write_text("not: valid: yaml: [unclosed", encoding="utf-8")
        with pytest.raises(Dev05ConfigError):
            load_dev05_config(path)

    def test_top_level_must_be_dict(self, tmp_path: Path) -> None:
        path = tmp_path / "list.yaml"
        path.write_text("- a\n- b\n", encoding="utf-8")
        with pytest.raises(Dev05ConfigError):
            load_dev05_config(path)

    def test_missing_top_key_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "wrong_top.yaml"
        path.write_text("other_top: {}\n", encoding="utf-8")
        with pytest.raises(Dev05ConfigError):
            load_dev05_config(path)


class TestMetricsConfig:
    def test_rejects_empty_enabled(self) -> None:
        from customer_segmentation.prototype.evaluation.config_loader import (
            Dev05MetricsConfig,
        )

        with pytest.raises(Dev05ConfigError):
            Dev05MetricsConfig(enabled=())

    def test_rejects_unknown_metric_name(self) -> None:
        from customer_segmentation.prototype.evaluation.config_loader import (
            Dev05MetricsConfig,
        )

        with pytest.raises(Dev05ConfigError):
            Dev05MetricsConfig(enabled=("silhouette", "wcss"))

    def test_rejects_duplicates(self) -> None:
        from customer_segmentation.prototype.evaluation.config_loader import (
            Dev05MetricsConfig,
        )

        with pytest.raises(Dev05ConfigError):
            Dev05MetricsConfig(enabled=("silhouette", "silhouette"))

    def test_rejects_non_string_entries(self) -> None:
        from customer_segmentation.prototype.evaluation.config_loader import (
            Dev05MetricsConfig,
        )

        with pytest.raises(Dev05ConfigError):
            Dev05MetricsConfig(enabled=("silhouette", 42))  # type: ignore[arg-type]


class TestNoisePolicyConfig:
    def test_rejects_invalid_policy(self) -> None:
        from customer_segmentation.prototype.evaluation.config_loader import (
            Dev05NoisePolicyConfig,
        )

        with pytest.raises(Dev05ConfigError):
            Dev05NoisePolicyConfig(default="invalid")


class TestLoggingConfig:
    def test_rejects_invalid_log_level(self) -> None:
        from customer_segmentation.prototype.evaluation.config_loader import (
            Dev05LoggingConfig,
        )

        with pytest.raises(Dev05ConfigError):
            Dev05LoggingConfig(level="VERBOSE")

    def test_all_valid_log_levels_accepted(self) -> None:
        from customer_segmentation.prototype.evaluation.config_loader import (
            Dev05LoggingConfig,
        )

        for level in VALID_LOG_LEVELS:
            cfg = Dev05LoggingConfig(level=level)
            assert cfg.level == level


class TestResearchSafetyConfig:
    def test_rejects_non_evaluated_prototype_scope(self) -> None:
        from customer_segmentation.prototype.evaluation.config_loader import (
            Dev05ResearchSafetyConfig,
        )

        with pytest.raises(Dev05ConfigError):
            Dev05ResearchSafetyConfig(evaluation_scope="RESEARCH_APPROVED")

    def test_readonly_paths_default(self) -> None:
        from customer_segmentation.prototype.evaluation.config_loader import (
            Dev05ResearchSafetyConfig,
        )

        cfg = Dev05ResearchSafetyConfig()
        assert "data/raw/primary" in cfg.readonly_paths
        assert "data/processed" in cfg.readonly_paths


class TestValidationConfig:
    def test_defaults(self) -> None:
        from customer_segmentation.prototype.evaluation.config_loader import (
            Dev05ValidationConfig,
        )

        cfg = Dev05ValidationConfig()
        assert cfg.min_samples == 2
        assert cfg.min_features == 1
        assert cfg.require_no_nan is True
        assert cfg.exclude_customer_id_from_features is True


class TestDisplayConfig:
    def test_defaults(self) -> None:
        from customer_segmentation.prototype.evaluation.config_loader import (
            Dev05DisplayConfig,
        )

        cfg = Dev05DisplayConfig()
        assert cfg.missing_value_placeholder == "--"
        assert cfg.csv_missing_value == ""


class TestCompareConfig:
    def test_defaults(self) -> None:
        from customer_segmentation.prototype.evaluation.config_loader import (
            Dev05CompareConfig,
        )

        cfg = Dev05CompareConfig()
        assert cfg.emit_singleton_group is True
        assert "ranking" in cfg.disclaimer_text
