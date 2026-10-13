"""Tests for DEV-08 config loader."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from customer_segmentation.prototype.visualization.config_loader import (
    DEFAULT_DEV08_CONFIG_PATH,
    DEV08_CONFIG_TOP_KEY,
    VALID_LOG_LEVELS,
    VALID_MARKETING_SECTIONS,
    VALID_OUTPUT_FORMATS,
    Dev08Config,
    find_default_dev08_config_path,
    load_dev08_config,
)
from customer_segmentation.prototype.visualization.exceptions import (
    VisualizationConfigError,
)


def test_default_config_path_exists() -> None:
    p = find_default_dev08_config_path()
    assert p.exists()
    assert p.name == "dev08_visualization.yaml"


def test_load_default_config() -> None:
    cfg = load_dev08_config()
    assert isinstance(cfg, Dev08Config)
    assert cfg.schema_version == "1.0.0"
    assert cfg.output_format == "png"
    assert cfg.marketing_section == "placeholder"
    assert cfg.logging.level == "INFO"


def test_load_config_with_custom_path(tmp_path: Path) -> None:
    custom = tmp_path / "custom.yaml"
    custom.write_text(
        textwrap.dedent("""\
            dev08_visualization:
              schema_version: "1.0.0"
              output_format: "svg"
              dpi: 200
              max_runs_per_chart: 10
              max_features_per_heatmap: 5
              include_noise_in_charts: true
              include_noise_in_text: false
              marketing_section: "hidden"
              display:
                missing_value_placeholder: "N/A"
                disclaimer_text: "custom disclaimer"
                separator: "|"
              storage:
                output_dir_relative: "visualization"
              logging:
                level: "DEBUG"
                format: "%(message)s"
                emit_to_console: false
              research_safety:
                never_promote_to_research: true
                visualization_scope: "DASHBOARD_PROTOTYPE"
            """),
        encoding="utf-8",
    )
    cfg = load_dev08_config(custom)
    assert cfg.output_format == "svg"
    assert cfg.dpi == 200
    assert cfg.max_runs_per_chart == 10
    assert cfg.max_features_per_heatmap == 5
    assert cfg.include_noise_in_charts is True
    assert cfg.include_noise_in_text is False
    assert cfg.marketing_section == "hidden"
    assert cfg.display.missing_value_placeholder == "N/A"
    assert cfg.display.disclaimer_text == "custom disclaimer"
    assert cfg.display.separator == "|"
    assert cfg.logging.level == "DEBUG"
    assert cfg.logging.emit_to_console is False


def test_load_config_missing_top_key(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("foo: 1\n", encoding="utf-8")
    with pytest.raises(VisualizationConfigError, match=DEV08_CONFIG_TOP_KEY):
        load_dev08_config(bad)


def test_load_config_invalid_output_format(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        textwrap.dedent("""\
            dev08_visualization:
              schema_version: "1.0.0"
              output_format: "jpg"
            """),
        encoding="utf-8",
    )
    with pytest.raises(VisualizationConfigError, match="output_format"):
        load_dev08_config(bad)


def test_load_config_invalid_log_level(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        textwrap.dedent("""\
            dev08_visualization:
              schema_version: "1.0.0"
              logging:
                level: "TRACE"
            """),
        encoding="utf-8",
    )
    with pytest.raises(VisualizationConfigError, match="logging.level"):
        load_dev08_config(bad)


def test_load_config_invalid_marketing_section(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        textwrap.dedent("""\
            dev08_visualization:
              schema_version: "1.0.0"
              marketing_section: "full"
            """),
        encoding="utf-8",
    )
    with pytest.raises(VisualizationConfigError, match="marketing_section"):
        load_dev08_config(bad)


def test_load_config_invalid_schema_version(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        textwrap.dedent("""\
            dev08_visualization:
              schema_version: "0.9.0"
            """),
        encoding="utf-8",
    )
    with pytest.raises(VisualizationConfigError, match="schema_version"):
        load_dev08_config(bad)


def test_load_config_invalid_dpi(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        textwrap.dedent("""\
            dev08_visualization:
              schema_version: "1.0.0"
              dpi: -1
            """),
        encoding="utf-8",
    )
    with pytest.raises(VisualizationConfigError, match="dpi"):
        load_dev08_config(bad)


def test_load_config_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.yaml"
    with pytest.raises(VisualizationConfigError, match="not found"):
        load_dev08_config(missing)


def test_load_config_invalid_yaml(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("this is: not: valid: yaml: [", encoding="utf-8")
    with pytest.raises(VisualizationConfigError, match="Failed to parse"):
        load_dev08_config(bad)


def test_load_config_top_key_not_mapping(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(f"{DEV08_CONFIG_TOP_KEY}: 'a string'\n", encoding="utf-8")
    with pytest.raises(VisualizationConfigError, match="mapping"):
        load_dev08_config(bad)


def test_config_closed_sets() -> None:
    assert "png" in VALID_OUTPUT_FORMATS
    assert "svg" in VALID_OUTPUT_FORMATS
    assert "placeholder" in VALID_MARKETING_SECTIONS
    assert "hidden" in VALID_MARKETING_SECTIONS
    assert "INFO" in VALID_LOG_LEVELS
    assert "DEBUG" in VALID_LOG_LEVELS


def test_default_path_constant() -> None:
    assert isinstance(DEFAULT_DEV08_CONFIG_PATH, Path)
    assert DEFAULT_DEV08_CONFIG_PATH.name == "dev08_visualization.yaml"


def test_never_promote_to_research_must_be_true(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        textwrap.dedent("""\
            dev08_visualization:
              schema_version: "1.0.0"
              research_safety:
                never_promote_to_research: false
                visualization_scope: "DASHBOARD_PROTOTYPE"
            """),
        encoding="utf-8",
    )
    with pytest.raises(VisualizationConfigError, match="never_promote_to_research"):
        load_dev08_config(bad)


def test_load_config_top_level_not_mapping(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("- 1\n- 2\n", encoding="utf-8")
    with pytest.raises(VisualizationConfigError, match="mapping"):
        load_dev08_config(bad)
