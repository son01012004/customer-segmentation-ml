"""Tests for the YAML → ``PipelineConfig`` loader.

These tests use **synthetic in-memory YAML** strings written to a
temporary directory. They do **not** read the real
``configs/preprocessing.yaml`` so they pass on CI without that file
being present in the checked-out tree.

The tests verify:

- Happy path: a well-formed YAML yields the same ``PipelineConfig``
  as :func:`customer_segmentation.preprocessing.cleaning.default_pipeline_config`.
- Strict mode raises :class:`PreprocessingConfigError` on missing keys.
- Strict mode raises on malformed values (e.g. ``keep: "bogus"``).
- Annotations map the YAML keys to cleaning-rule IDs.
- The canonical file ``configs/preprocessing.yaml`` (when present
  locally) loads with the strict loader without error.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from customer_segmentation.config.loader import (
    DEFAULT_PREPROCESSING_CONFIG_PATH,
    KEY_ANNOTATIONS,
    STATUS_PENDING_MENTOR_REVIEW,
    STATUS_WORKING_ASSUMPTION,
    PreprocessingConfigError,
    find_default_preprocessing_config_path,
    load_preprocessing_config,
    preprocessing_config_to_dict,
    resolve_preprocessing_config_path,
)
from customer_segmentation.preprocessing.cleaning import (
    PipelineConfig,
    default_pipeline_config,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


_MINIMAL_VALID_YAML = """\
preprocessing:
  duplicate_subset: null
  duplicate_keep: "first"
  missing_strategy: "keep"
  missing_columns: []
  outlier_action: "none"
  outlier_method: "iqr"
  outlier_columns: []
  outlier_iqr_multiplier: 1.5
  outlier_zscore_threshold: 3.0
  invalid_records:
    drop_missing_invoice_no: true
    drop_missing_customer_id: true
    drop_missing_description: true
    drop_unparseable_invoice_date: true
    drop_zero_quantity: true
    drop_non_positive_unit_price: true
    flag_cancellations: true
    flag_returns: true
    cancellation_prefix: "C"
"""


@pytest.fixture()
def minimal_yaml_path(tmp_path: Path) -> Path:
    """Write the minimal valid YAML and return its path."""
    p = tmp_path / "preprocessing.yaml"
    p.write_text(_MINIMAL_VALID_YAML, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_load_minimal_yaml(self, minimal_yaml_path: Path) -> None:
        cfg = load_preprocessing_config(minimal_yaml_path, strict=True)
        assert isinstance(cfg, PipelineConfig)

    def test_matches_default_pipeline_config(self, minimal_yaml_path: Path) -> None:
        """The minimal YAML must produce a config byte-equal to the defaults."""
        yaml_cfg = load_preprocessing_config(minimal_yaml_path, strict=True)
        default_cfg = default_pipeline_config()
        assert preprocessing_config_to_dict(yaml_cfg) == preprocessing_config_to_dict(default_cfg)

    def test_default_file_exists_or_not(self) -> None:
        """`find_default_preprocessing_config_path` returns the canonical path."""
        p = find_default_preprocessing_config_path()
        assert p == DEFAULT_PREPROCESSING_CONFIG_PATH
        assert isinstance(p, Path)

    def test_canonical_yaml_loads_when_present(self) -> None:
        """If the canonical YAML is checked out, the strict loader succeeds."""
        if not DEFAULT_PREPROCESSING_CONFIG_PATH.exists():
            pytest.skip("Canonical preprocessing.yaml not present in this checkout.")
        cfg = load_preprocessing_config(DEFAULT_PREPROCESSING_CONFIG_PATH, strict=True)
        d = preprocessing_config_to_dict(cfg)
        assert d["missing_strategy"] == "keep"
        assert d["duplicate_keep"] == "first"
        assert d["outlier_action"] == "none"
        # Cancel/return are flagged (not dropped) — PENDING_MENTOR_REVIEW.
        assert d["invalid_rules"]["flag_cancellations"] is True
        assert d["invalid_rules"]["flag_returns"] is True


# ---------------------------------------------------------------------------
# Strict-mode failures
# ---------------------------------------------------------------------------


class TestStrictFailures:
    def test_missing_top_level_key(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text(
            "preprocessing:\n"
            "  duplicate_subset: null\n"
            "  duplicate_keep: 'first'\n"
            "  missing_strategy: 'keep'\n"
            "  missing_columns: []\n"
            "  # outlier_action and remaining keys intentionally absent\n"
            "  invalid_records:\n"
            "    cancellation_prefix: 'C'\n",
            encoding="utf-8",
        )
        with pytest.raises(PreprocessingConfigError) as exc_info:
            load_preprocessing_config(bad, strict=True)
        # In strict mode, the loader raises on the first missing key it
        # finds. The error message must mention the "Missing required key"
        # pattern; the specific key depends on the loader's check order.
        msg = str(exc_info.value)
        assert "Missing required key" in msg

    def test_missing_invalid_record_key(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text(
            "preprocessing:\n"
            "  duplicate_subset: null\n"
            "  duplicate_keep: 'first'\n"
            "  missing_strategy: 'keep'\n"
            "  missing_columns: []\n"
            "  outlier_action: 'none'\n"
            "  outlier_method: 'iqr'\n"
            "  outlier_columns: []\n"
            "  outlier_iqr_multiplier: 1.5\n"
            "  outlier_zscore_threshold: 3.0\n"
            "  invalid_records:\n"
            "    drop_missing_customer_id: true\n"
            "    cancellation_prefix: 'C'\n"
            "    # the other 7 keys are missing\n",
            encoding="utf-8",
        )
        with pytest.raises(PreprocessingConfigError):
            load_preprocessing_config(bad, strict=True)

    def test_invalid_keep_mode(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text(
            _MINIMAL_VALID_YAML.replace('duplicate_keep: "first"', 'duplicate_keep: "all"'),
            encoding="utf-8",
        )
        with pytest.raises(PreprocessingConfigError) as exc_info:
            load_preprocessing_config(bad, strict=True)
        assert "duplicate_keep" in str(exc_info.value)

    def test_invalid_strategy(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text(
            _MINIMAL_VALID_YAML.replace('missing_strategy: "keep"', 'missing_strategy: "magic"'),
            encoding="utf-8",
        )
        with pytest.raises(PreprocessingConfigError):
            load_preprocessing_config(bad, strict=True)

    def test_invalid_outlier_action(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text(
            _MINIMAL_VALID_YAML.replace('outlier_action: "none"', 'outlier_action: "delete"'),
            encoding="utf-8",
        )
        with pytest.raises(PreprocessingConfigError):
            load_preprocessing_config(bad, strict=True)

    def test_invalid_outlier_method(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text(
            _MINIMAL_VALID_YAML.replace('outlier_method: "iqr"', 'outlier_method: "fancy"'),
            encoding="utf-8",
        )
        with pytest.raises(PreprocessingConfigError):
            load_preprocessing_config(bad, strict=True)

    def test_non_bool_invalid_record_field(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text(
            _MINIMAL_VALID_YAML.replace(
                "drop_missing_customer_id: true",
                'drop_missing_customer_id: "yes"',
            ),
            encoding="utf-8",
        )
        with pytest.raises(PreprocessingConfigError) as exc_info:
            load_preprocessing_config(bad, strict=True)
        assert "drop_missing_customer_id" in str(exc_info.value)

    def test_empty_yaml_fails(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text("", encoding="utf-8")
        with pytest.raises(PreprocessingConfigError):
            load_preprocessing_config(bad, strict=True)

    def test_missing_preprocessing_section_fails(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text("not_preprocessing:\n  foo: bar\n", encoding="utf-8")
        with pytest.raises(PreprocessingConfigError):
            load_preprocessing_config(bad, strict=True)

    def test_missing_file_fails(self, tmp_path: Path) -> None:
        with pytest.raises(PreprocessingConfigError):
            load_preprocessing_config(tmp_path / "does_not_exist.yaml", strict=True)


# ---------------------------------------------------------------------------
# Partial-mode behaviour
# ---------------------------------------------------------------------------


class TestPartialMode:
    def test_partial_mode_drops_back_to_defaults_for_missing_keys(self, tmp_path: Path) -> None:
        """In ``strict=False`` mode, missing keys fall back to dataclass defaults."""
        p = tmp_path / "partial.yaml"
        p.write_text(
            "preprocessing:\n"
            "  duplicate_keep: 'last'\n"
            "  invalid_records:\n"
            "    cancellation_prefix: 'X'\n",
            encoding="utf-8",
        )
        cfg = load_preprocessing_config(p, strict=False)
        assert cfg.duplicate_keep == "last"
        # Untouched fields fall back to dataclass defaults
        assert cfg.missing_strategy == "keep"
        assert cfg.outlier_action == "none"
        # cancellation_prefix was explicitly set
        assert cfg.invalid_rules.cancellation_prefix == "X"
        # The other invalid-rule flags stay at their dataclass default
        assert cfg.invalid_rules.drop_missing_customer_id is True


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


class TestPathResolution:
    def test_explicit_path_wins(self, minimal_yaml_path: Path) -> None:
        out = resolve_preprocessing_config_path(explicit=minimal_yaml_path)
        assert out == minimal_yaml_path

    def test_search_paths_first_match_wins(self, tmp_path: Path, minimal_yaml_path: Path) -> None:
        non_existent = tmp_path / "nope.yaml"
        out = resolve_preprocessing_config_path(
            explicit=None,
            search_paths=(non_existent, minimal_yaml_path),
        )
        assert out == minimal_yaml_path

    def test_no_existing_path_returns_none(self, tmp_path: Path) -> None:
        out = resolve_preprocessing_config_path(
            explicit=None,
            search_paths=(tmp_path / "a.yaml", tmp_path / "b.yaml"),
        )
        assert out is None


# ---------------------------------------------------------------------------
# Annotations and status markers
# ---------------------------------------------------------------------------


class TestAnnotations:
    def test_cancellation_is_pending(self) -> None:
        ann = KEY_ANNOTATIONS["invalid_records.flag_cancellations"]
        assert ann.status == STATUS_PENDING_MENTOR_REVIEW
        assert ann.rule_id == "CL-08"

    def test_return_is_pending(self) -> None:
        ann = KEY_ANNOTATIONS["invalid_records.flag_returns"]
        assert ann.status == STATUS_PENDING_MENTOR_REVIEW
        assert ann.rule_id == "CL-06"

    def test_known_drops_are_working_assumption(self) -> None:
        for key in (
            "invalid_records.drop_missing_customer_id",
            "invalid_records.drop_zero_quantity",
            "invalid_records.drop_non_positive_unit_price",
        ):
            ann = KEY_ANNOTATIONS[key]
            assert ann.status == STATUS_WORKING_ASSUMPTION
            assert ann.rule_id.startswith("CL-")

    def test_annotation_unknown_key_raises(self) -> None:
        from customer_segmentation.config.loader import ConfigAnnotation

        with pytest.raises(ValueError):
            # Status must be one of the recognised markers.
            ConfigAnnotation(
                status="UNKNOWN",
                source="x",
                rule_id=None,
                rationale="",
            )


# ---------------------------------------------------------------------------
# Serialisation round-trip
# ---------------------------------------------------------------------------


class TestSerialisation:
    def test_to_dict_is_json_serialisable(self, minimal_yaml_path: Path) -> None:
        cfg = load_preprocessing_config(minimal_yaml_path, strict=True)
        d = preprocessing_config_to_dict(cfg)
        # Must not raise.
        json.dumps(d, default=str)
        # Spot-check a few keys.
        assert d["missing_strategy"] == "keep"
        assert d["duplicate_subset"] is None
        assert d["invalid_rules"]["cancellation_prefix"] == "C"
