"""Tests for DEV-09 config loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from customer_segmentation.prototype.end_to_end.config_loader import (
    DEFAULT_DEV09_CONFIG_PATH,
    DEV09_CONFIG_TOP_KEY,
    VALID_ALGORITHMS,
    VALID_LOG_LEVELS,
    Dev09Config,
    Dev09ConfigError,
    load_dev09_config,
)


def test_default_config_path_is_string() -> None:
    assert isinstance(DEFAULT_DEV09_CONFIG_PATH, Path)
    assert DEFAULT_DEV09_CONFIG_PATH.name == "dev09_end_to_end.yaml"


def test_top_key_is_dev09_end_to_end() -> None:
    assert DEV09_CONFIG_TOP_KEY == "dev09_end_to_end"


def test_load_default_config() -> None:
    cfg = load_dev09_config()
    assert isinstance(cfg, Dev09Config)
    assert cfg.schema_version == "1.0.0"


def test_default_algorithm_is_kmeans() -> None:
    cfg = load_dev09_config()
    assert cfg.stage_selection.algorithm == "kmeans"


def test_default_skip_flags_false() -> None:
    cfg = load_dev09_config()
    assert cfg.stage_selection.skip_visualization is False
    assert cfg.stage_selection.skip_marketing is False


def test_default_research_safety() -> None:
    cfg = load_dev09_config()
    assert cfg.research_safety.never_promote_to_research is True
    assert cfg.research_safety.end_to_end_scope == "END_TO_END_PROTOTYPE"


def test_default_storage_layout() -> None:
    cfg = load_dev09_config()
    assert cfg.storage.output_dir_relative == "end_to_end"


def test_default_logging() -> None:
    cfg = load_dev09_config()
    assert cfg.logging.level in VALID_LOG_LEVELS
    assert cfg.logging.emit_to_console is True


def test_default_persistence() -> None:
    cfg = load_dev09_config()
    assert cfg.persistence.copy_manifests is True


def test_valid_algorithms_contains_required() -> None:
    assert "kmeans" in VALID_ALGORITHMS
    assert "agglomerative" in VALID_ALGORITHMS
    assert "dbscan" in VALID_ALGORITHMS
    assert "gmm" in VALID_ALGORITHMS
    assert "fuzzy_cmeans" in VALID_ALGORITHMS


def test_valid_algorithms_excludes_kmedoids() -> None:
    assert "kmedoids" not in VALID_ALGORITHMS


def test_valid_log_levels() -> None:
    assert "INFO" in VALID_LOG_LEVELS
    assert "DEBUG" in VALID_LOG_LEVELS
    assert "WARNING" in VALID_LOG_LEVELS
    assert "ERROR" in VALID_LOG_LEVELS


def _write_tmp_yaml(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "dev09.yaml"
    p.write_text(body, encoding="utf-8")
    return p


def test_load_custom_algorithm(tmp_path: Path) -> None:
    body = """
dev09_end_to_end:
  schema_version: "1.0.0"
  stage_selection:
    algorithm: "dbscan"
    skip_visualization: false
    skip_marketing: false
  storage:
    output_dir_relative: "end_to_end"
  logging:
    level: "INFO"
    format: "%(message)s"
    emit_to_console: true
  persistence:
    copy_manifests: false
  research_safety:
    never_promote_to_research: true
    end_to_end_scope: "END_TO_END_PROTOTYPE"
"""
    cfg = load_dev09_config(_write_tmp_yaml(tmp_path, body))
    assert cfg.stage_selection.algorithm == "dbscan"
    assert cfg.persistence.copy_manifests is False


def test_load_missing_top_key_raises(tmp_path: Path) -> None:
    body = """
some_other_key:
  schema_version: "1.0.0"
"""
    with pytest.raises(Dev09ConfigError, match="missing top-level key"):
        load_dev09_config(_write_tmp_yaml(tmp_path, body))


def test_load_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(Dev09ConfigError, match="not found"):
        load_dev09_config(tmp_path / "missing.yaml")


def test_load_malformed_yaml_raises(tmp_path: Path) -> None:
    p = tmp_path / "bad.yaml"
    p.write_text("not: valid: yaml: :::", encoding="utf-8")
    with pytest.raises(Dev09ConfigError, match="Failed to parse"):
        load_dev09_config(p)


def test_load_top_level_not_mapping_raises(tmp_path: Path) -> None:
    p = tmp_path / "wrong.yaml"
    p.write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(Dev09ConfigError, match="must be a YAML mapping"):
        load_dev09_config(p)


def test_load_schema_version_mismatch_raises(tmp_path: Path) -> None:
    body = """
dev09_end_to_end:
  schema_version: "99.0.0"
  stage_selection:
    algorithm: "kmeans"
    skip_visualization: false
    skip_marketing: false
  storage:
    output_dir_relative: "end_to_end"
  logging:
    level: "INFO"
    format: "%(message)s"
    emit_to_console: true
  persistence:
    copy_manifests: true
  research_safety:
    never_promote_to_research: true
    end_to_end_scope: "END_TO_END_PROTOTYPE"
"""
    with pytest.raises(Dev09ConfigError, match="schema_version"):
        load_dev09_config(_write_tmp_yaml(tmp_path, body))


def test_load_invalid_algorithm_raises(tmp_path: Path) -> None:
    body = """
dev09_end_to_end:
  schema_version: "1.0.0"
  stage_selection:
    algorithm: "kmedoids"
    skip_visualization: false
    skip_marketing: false
  storage:
    output_dir_relative: "end_to_end"
  logging:
    level: "INFO"
    format: "%(message)s"
    emit_to_console: true
  persistence:
    copy_manifests: true
  research_safety:
    never_promote_to_research: true
    end_to_end_scope: "END_TO_END_PROTOTYPE"
"""
    with pytest.raises(Dev09ConfigError, match="algorithm"):
        load_dev09_config(_write_tmp_yaml(tmp_path, body))


def test_load_invalid_log_level_raises(tmp_path: Path) -> None:
    body = """
dev09_end_to_end:
  schema_version: "1.0.0"
  stage_selection:
    algorithm: "kmeans"
    skip_visualization: false
    skip_marketing: false
  storage:
    output_dir_relative: "end_to_end"
  logging:
    level: "FATAL"
    format: "%(message)s"
    emit_to_console: true
  persistence:
    copy_manifests: true
  research_safety:
    never_promote_to_research: true
    end_to_end_scope: "END_TO_END_PROTOTYPE"
"""
    with pytest.raises(Dev09ConfigError, match="logging.level"):
        load_dev09_config(_write_tmp_yaml(tmp_path, body))


def test_load_invalid_research_safety_raises(tmp_path: Path) -> None:
    body = """
dev09_end_to_end:
  schema_version: "1.0.0"
  stage_selection:
    algorithm: "kmeans"
    skip_visualization: false
    skip_marketing: false
  storage:
    output_dir_relative: "end_to_end"
  logging:
    level: "INFO"
    format: "%(message)s"
    emit_to_console: true
  persistence:
    copy_manifests: true
  research_safety:
    never_promote_to_research: false
    end_to_end_scope: "END_TO_END_PROTOTYPE"
"""
    with pytest.raises(Dev09ConfigError, match="never_promote_to_research"):
        load_dev09_config(_write_tmp_yaml(tmp_path, body))


def test_display_separator_default(tmp_path: Path) -> None:
    body = """
dev09_end_to_end:
  schema_version: "1.0.0"
  stage_selection:
    algorithm: "kmeans"
    skip_visualization: false
    skip_marketing: false
  storage:
    output_dir_relative: "end_to_end"
  logging:
    level: "INFO"
    format: "%(message)s"
    emit_to_console: true
  persistence:
    copy_manifests: true
  research_safety:
    never_promote_to_research: true
    end_to_end_scope: "END_TO_END_PROTOTYPE"
"""
    cfg = load_dev09_config(_write_tmp_yaml(tmp_path, body))
    assert cfg.display.separator == "  "
    assert len(cfg.display.disclaimer_text) > 0


def test_config_is_frozen() -> None:
    cfg = load_dev09_config()
    with pytest.raises((AttributeError, Exception)):
        cfg.schema_version = "2.0.0"  # type: ignore[misc]
