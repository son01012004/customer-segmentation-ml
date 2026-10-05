"""Unit tests for the FE-03 outlier config loader.

These tests use **synthetic** YAML strings. They do not depend on the
real ``configs/outlier.yaml`` so they are robust to local edits.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from customer_segmentation.config.outlier_loader import (
    DEFAULT_OUTLIER_CONFIG_PATH,
    OUTLIER_STATUS_PENDING_MENTOR_REVIEW,
    OUTLIER_STATUS_WORKING_ASSUMPTION,
    OUTLIER_VALID_FILTER_MODES,
    CustomerDiagnosticConfig,
    FeatureOutlierConfig,
    OutlierAnalysisConfig,
    OutlierConfigError,
    find_default_outlier_config_path,
    load_outlier_config,
    outlier_config_to_dict,
    resolve_outlier_config_path,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


VALID_YAML = """
outlier_analysis:
  enabled: true
  random_seed: 42
  source:
    role: "primary"
    cleaned_dataset_path: "./data/processed/transactions_clean.parquet"
    raw_dataset_path: "./data/raw/primary/Online Retail.xlsx"
  transaction_features:
    - column: "Quantity"
      detection: "iqr"
      iqr_multiplier: 1.5
      percentile_thresholds: [99.0, 99.5, 99.9]
      zscore_threshold: 3.0
      treatment: "none"
      status: "PENDING_MENTOR_REVIEW"
    - column: "UnitPrice"
      detection: "iqr"
      iqr_multiplier: 3.0
      percentile_thresholds: [99.5]
      zscore_threshold: 3.0
      treatment: "none"
      status: "PENDING_MENTOR_REVIEW"
    - column: "LineRevenue"
      detection: "zscore"
      iqr_multiplier: 1.5
      percentile_thresholds: [99.0, 99.5]
      zscore_threshold: 3.5
      treatment: "none"
      status: "WORKING_ASSUMPTION"
  customer_diagnostic:
    enabled: true
    customer_key: "CustomerID"
    aggregations:
      total_spend:       { source: "LineRevenue",  fn: "sum" }
      total_quantity:    { source: "Quantity",     fn: "sum" }
      distinct_invoices: { source: "InvoiceNo",    fn: "nunique" }
      distinct_products: { source: "StockCode",    fn: "nunique" }
      active_days:       { source: "InvoiceDate",  fn: "nunique_date" }
    detection:
      iqr_multiplier: 1.5
      percentile_thresholds: [95.0, 99.0, 99.5]
    treatment: "none"
    status: "PENDING_MENTOR_REVIEW"
  filter_modes:
    - { name: "all_rows",         where: "" }
    - { name: "clean_purchase",   where: "IsCancellation == False and IsReturn == False" }
    - { name: "non_cancellation", where: "IsCancellation == False" }
    - { name: "non_return",       where: "IsReturn == False" }
  sensitivity:
    enabled: true
    thresholds: [1.5, 3.0]
    percentiles: [99.0, 99.5, 99.9]
  output:
    processed_dir: "./data/processed"
    report_dir: "./reports/fe03"
    treated_filename: "transactions_outlier_treated.parquet"
    write_treated_dataset: false
    plots_dir: "./reports/fe03/plots"
    write_plots: true
"""


@pytest.fixture()
def valid_yaml_path(tmp_path: Path) -> Path:
    p = tmp_path / "outlier.yaml"
    p.write_text(VALID_YAML, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


class TestPathResolution:
    def test_default_path_is_repo_relative(self) -> None:
        p = find_default_outlier_config_path()
        assert isinstance(p, Path)
        assert p.name == "outlier.yaml"
        assert p.parent.name == "configs"

    def test_resolve_explicit_returns_explicit(self, valid_yaml_path: Path) -> None:
        out = resolve_outlier_config_path(explicit=valid_yaml_path)
        assert out == valid_yaml_path

    def test_resolve_search_finds_existing(self, valid_yaml_path: Path) -> None:
        out = resolve_outlier_config_path(search_paths=(valid_yaml_path,))
        assert out == valid_yaml_path

    def test_resolve_returns_none_when_no_file(self, tmp_path: Path) -> None:
        out = resolve_outlier_config_path(search_paths=(tmp_path / "missing.yaml",))
        assert out is None


# ---------------------------------------------------------------------------
# Loading the real default YAML
# ---------------------------------------------------------------------------


class TestDefaultYAML:
    def test_real_yaml_loads_strict(self) -> None:
        cfg = load_outlier_config(DEFAULT_OUTLIER_CONFIG_PATH, strict=True)
        assert isinstance(cfg, OutlierAnalysisConfig)
        assert cfg.enabled is True
        assert cfg.random_seed == 42
        assert cfg.source.role == "primary"
        assert cfg.source.cleaned_dataset_path.endswith("transactions_clean.parquet")
        assert cfg.source.raw_dataset_path.endswith("Online Retail.xlsx")

    def test_real_yaml_has_three_transaction_features(self) -> None:
        cfg = load_outlier_config(DEFAULT_OUTLIER_CONFIG_PATH, strict=True)
        cols = [f.column for f in cfg.transaction_features]
        assert cols == ["Quantity", "UnitPrice", "LineRevenue"]
        for f in cfg.transaction_features:
            assert f.treatment == "none"
            assert f.status == OUTLIER_STATUS_PENDING_MENTOR_REVIEW

    def test_real_yaml_customer_diagnostic(self) -> None:
        cfg = load_outlier_config(DEFAULT_OUTLIER_CONFIG_PATH, strict=True)
        diag = cfg.customer_diagnostic
        assert diag.enabled is True
        assert diag.customer_key == "CustomerID"
        assert set(diag.aggregations) == {
            "total_spend",
            "total_quantity",
            "distinct_invoices",
            "distinct_products",
            "active_days",
        }
        assert diag.aggregations["total_spend"].fn == "sum"
        assert diag.aggregations["active_days"].fn == "nunique_date"

    def test_real_yaml_filter_modes(self) -> None:
        cfg = load_outlier_config(DEFAULT_OUTLIER_CONFIG_PATH, strict=True)
        names = [m.name for m in cfg.filter_modes]
        assert set(names) == set(OUTLIER_VALID_FILTER_MODES)

    def test_real_yaml_sensitivity(self) -> None:
        cfg = load_outlier_config(DEFAULT_OUTLIER_CONFIG_PATH, strict=True)
        assert cfg.sensitivity.enabled is True
        assert 1.5 in cfg.sensitivity.thresholds
        assert 3.0 in cfg.sensitivity.thresholds
        assert 99.9 in cfg.sensitivity.percentiles

    def test_real_yaml_output_defaults(self) -> None:
        cfg = load_outlier_config(DEFAULT_OUTLIER_CONFIG_PATH, strict=True)
        assert cfg.output.write_treated_dataset is False
        assert cfg.output.write_plots is True
        assert cfg.output.treated_filename == "transactions_outlier_treated.parquet"


# ---------------------------------------------------------------------------
# Strict-mode failure modes
# ---------------------------------------------------------------------------


class TestStrictValidation:
    def test_missing_top_level_key(self, tmp_path: Path) -> None:
        bad = "outlier_analysis:\n  enabled: true\n"
        p = tmp_path / "outlier.yaml"
        p.write_text(bad, encoding="utf-8")
        with pytest.raises(OutlierConfigError, match="Missing required key"):
            load_outlier_config(p, strict=True)

    def test_missing_outlier_analysis_key(self, tmp_path: Path) -> None:
        p = tmp_path / "outlier.yaml"
        p.write_text("not_outlier_analysis: {}\n", encoding="utf-8")
        with pytest.raises(OutlierConfigError, match="'outlier_analysis'"):
            load_outlier_config(p, strict=True)

    def test_unknown_detection(self, valid_yaml_path: Path) -> None:
        data = yaml.safe_load(VALID_YAML)
        data["outlier_analysis"]["transaction_features"][0]["detection"] = "bogus"
        valid_yaml_path.write_text(yaml.safe_dump(data), encoding="utf-8")
        with pytest.raises(OutlierConfigError, match="unknown detection"):
            load_outlier_config(valid_yaml_path, strict=True)

    def test_unknown_treatment(self, valid_yaml_path: Path) -> None:
        data = yaml.safe_load(VALID_YAML)
        data["outlier_analysis"]["transaction_features"][0]["treatment"] = "wipe"
        valid_yaml_path.write_text(yaml.safe_dump(data), encoding="utf-8")
        with pytest.raises(OutlierConfigError, match="unknown treatment"):
            load_outlier_config(valid_yaml_path, strict=True)

    def test_unknown_status(self, valid_yaml_path: Path) -> None:
        data = yaml.safe_load(VALID_YAML)
        data["outlier_analysis"]["transaction_features"][0]["status"] = "CONFIRMED"
        valid_yaml_path.write_text(yaml.safe_dump(data), encoding="utf-8")
        with pytest.raises(OutlierConfigError, match="unknown status"):
            load_outlier_config(valid_yaml_path, strict=True)

    def test_negative_iqr_multiplier(self, valid_yaml_path: Path) -> None:
        data = yaml.safe_load(VALID_YAML)
        data["outlier_analysis"]["transaction_features"][0]["iqr_multiplier"] = -1.0
        valid_yaml_path.write_text(yaml.safe_dump(data), encoding="utf-8")
        with pytest.raises(OutlierConfigError, match="iqr_multiplier must be > 0"):
            load_outlier_config(valid_yaml_path, strict=True)

    def test_unknown_aggregation_fn(self, valid_yaml_path: Path) -> None:
        data = yaml.safe_load(VALID_YAML)
        data["outlier_analysis"]["customer_diagnostic"]["aggregations"]["total_spend"][
            "fn"
        ] = "wonderful"
        valid_yaml_path.write_text(yaml.safe_dump(data), encoding="utf-8")
        with pytest.raises(OutlierConfigError, match="fn"):
            load_outlier_config(valid_yaml_path, strict=True)

    def test_unknown_filter_mode_name(self, valid_yaml_path: Path) -> None:
        data = yaml.safe_load(VALID_YAML)
        data["outlier_analysis"]["filter_modes"].append({"name": "fantasy_mode", "where": ""})
        valid_yaml_path.write_text(yaml.safe_dump(data), encoding="utf-8")
        with pytest.raises(OutlierConfigError, match="not recognised"):
            load_outlier_config(valid_yaml_path, strict=True)

    def test_empty_yaml_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.yaml"
        p.write_text("", encoding="utf-8")
        with pytest.raises(OutlierConfigError, match="empty"):
            load_outlier_config(p, strict=True)

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(OutlierConfigError, match="not found"):
            load_outlier_config(tmp_path / "absent.yaml", strict=True)


# ---------------------------------------------------------------------------
# Strict vs non-strict
# ---------------------------------------------------------------------------


class TestStrictModes:
    def test_strict_false_returns_defaults(self, tmp_path: Path) -> None:
        # A YAML with only the required keys under non-strict mode still
        # produces a valid config.
        minimal = """
outlier_analysis:
  enabled: true
  random_seed: 7
"""
        p = tmp_path / "minimal.yaml"
        p.write_text(minimal, encoding="utf-8")
        cfg = load_outlier_config(p, strict=False)
        assert cfg.enabled is True
        assert cfg.random_seed == 7
        assert isinstance(cfg.transaction_features, list)
        assert isinstance(cfg.customer_diagnostic, CustomerDiagnosticConfig)
        assert isinstance(cfg.filter_modes, list)


# ---------------------------------------------------------------------------
# Serialisation round-trip
# ---------------------------------------------------------------------------


class TestSerialisation:
    def test_round_trip(self) -> None:
        cfg = load_outlier_config(DEFAULT_OUTLIER_CONFIG_PATH, strict=True)
        d = outlier_config_to_dict(cfg)
        # Sanity checks on the dict shape.
        assert d["enabled"] is True
        assert d["random_seed"] == 42
        assert isinstance(d["transaction_features"], list)
        assert len(d["transaction_features"]) == 3
        for f in d["transaction_features"]:
            assert "column" in f
            assert "detection" in f
            assert "treatment" in f
            assert "status" in f
        assert d["customer_diagnostic"]["enabled"] is True
        assert "total_spend" in d["customer_diagnostic"]["aggregations"]
        assert d["output"]["write_treated_dataset"] is False


# ---------------------------------------------------------------------------
# Default dataclass values
# ---------------------------------------------------------------------------


class TestDefaults:
    def test_default_outlier_config(self) -> None:
        cfg = OutlierAnalysisConfig()
        assert cfg.enabled is True
        assert cfg.random_seed == 42
        assert cfg.transaction_features == []
        assert cfg.customer_diagnostic.enabled is False
        assert cfg.sensitivity.thresholds == (1.5, 3.0)
        assert cfg.sensitivity.percentiles == (99.0, 99.5, 99.9)
        assert cfg.output.write_treated_dataset is False

    def test_feature_outlier_config_defaults(self) -> None:
        f = FeatureOutlierConfig(column="Quantity", detection="iqr")
        assert f.iqr_multiplier == 1.5
        assert f.zscore_threshold == 3.0
        assert f.percentile_thresholds == (99.0, 99.5, 99.9)
        assert f.treatment == "none"
        assert f.status == OUTLIER_STATUS_PENDING_MENTOR_REVIEW


# ---------------------------------------------------------------------------
# Status preservation
# ---------------------------------------------------------------------------


class TestStatusPreservation:
    def test_pending_status_preserved(self, valid_yaml_path: Path) -> None:
        cfg = load_outlier_config(valid_yaml_path, strict=True)
        for f in cfg.transaction_features[:2]:
            assert f.status == OUTLIER_STATUS_PENDING_MENTOR_REVIEW

    def test_working_status_preserved(self, valid_yaml_path: Path) -> None:
        cfg = load_outlier_config(valid_yaml_path, strict=True)
        assert cfg.transaction_features[2].status == OUTLIER_STATUS_WORKING_ASSUMPTION

    def test_customer_diagnostic_pending(self, valid_yaml_path: Path) -> None:
        cfg = load_outlier_config(valid_yaml_path, strict=True)
        assert cfg.customer_diagnostic.status == OUTLIER_STATUS_PENDING_MENTOR_REVIEW
