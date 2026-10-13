"""Tests for the DEV-04 configuration loader."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from customer_segmentation.prototype.clustering.config_loader import (
    DEV04_CONFIG_TOP_KEY,
    Dev04Config,
    Dev04ConfigError,
    find_default_dev04_config_path,
    load_dev04_config,
)


class TestFindDefaultDev04ConfigPath:
    def test_returns_canonical_path(self) -> None:
        path = find_default_dev04_config_path()
        assert isinstance(path, Path)
        assert path.name == "dev04_clustering.yaml"


class TestLoadDev04Config:
    def test_load_default_config(self) -> None:
        cfg, raw_text = load_dev04_config()
        assert isinstance(cfg, Dev04Config)
        assert isinstance(raw_text, str)
        assert DEV04_CONFIG_TOP_KEY in raw_text

    def test_all_five_algorithms_present(self) -> None:
        cfg, _ = load_dev04_config()
        names = set(cfg.algorithms.keys())
        assert names == {"kmeans", "agglomerative", "dbscan", "gmm", "fuzzy_cmeans"}

    def test_algorithm_enabled_by_default(self) -> None:
        cfg, _ = load_dev04_config()
        for name, algo in cfg.algorithms.items():
            assert algo.enabled is True, f"{name} should be enabled by default"

    def test_kmeans_has_n_clusters(self) -> None:
        cfg, _ = load_dev04_config()
        assert cfg.algorithms["kmeans"].n_clusters == 4
        assert cfg.algorithms["kmeans"].init == "k-means++"
        assert cfg.algorithms["kmeans"].n_init == 10

    def test_dbscan_has_eps_min_samples(self) -> None:
        cfg, _ = load_dev04_config()
        assert cfg.algorithms["dbscan"].eps == 0.5
        assert cfg.algorithms["dbscan"].min_samples == 5

    def test_gmm_has_n_components(self) -> None:
        cfg, _ = load_dev04_config()
        assert cfg.algorithms["gmm"].n_components == 4
        assert cfg.algorithms["gmm"].covariance_type == "full"

    def test_random_seed_default(self) -> None:
        cfg, _ = load_dev04_config()
        assert cfg.random_seed.default == 42
        assert cfg.random_seed.per_algorithm_override == {}

    def test_logging_level_info(self) -> None:
        cfg, _ = load_dev04_config()
        assert cfg.logging.level == "INFO"
        assert cfg.logging.emit_to_console is True

    def test_research_safety_never_promote(self) -> None:
        cfg, _ = load_dev04_config()
        assert cfg.research_safety.never_promote_to_research is True
        assert "data/raw/primary" in cfg.research_safety.readonly_paths

    def test_validation_require_no_nan(self) -> None:
        cfg, _ = load_dev04_config()
        assert cfg.validation.require_no_nan is True
        assert cfg.validation.min_samples == 2

    def test_load_custom_yaml(self, tmp_path: Path) -> None:
        custom = {
            "dev04_clustering": {
                "random_seed": {"default": 99},
                "algorithms": {
                    "kmeans": {"n_clusters": 7},
                },
            }
        }
        path = tmp_path / "custom.yaml"
        with path.open("w", encoding="utf-8") as fh:
            yaml.dump(custom, fh)
        cfg, _ = load_dev04_config(path)
        assert cfg.random_seed.default == 99
        assert cfg.algorithms["kmeans"].n_clusters == 7

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(Dev04ConfigError):
            load_dev04_config(tmp_path / "nonexistent.yaml")

    def test_invalid_yaml_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.yaml"
        path.write_text("  invalid: yaml: content", encoding="utf-8")
        with pytest.raises(Dev04ConfigError):
            load_dev04_config(path)

    def test_missing_top_key_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "notop.yaml"
        with path.open("w", encoding="utf-8") as fh:
            yaml.dump({"wrong_key": {}}, fh)
        with pytest.raises(Dev04ConfigError):
            load_dev04_config(path)

    def test_unknown_algorithm_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "unknown_algo.yaml"
        with path.open("w", encoding="utf-8") as fh:
            yaml.dump(
                {"dev04_clustering": {"algorithms": {"unknown_algo": {}}}},
                fh,
            )
        with pytest.raises(Dev04ConfigError):
            load_dev04_config(path)

    def test_invalid_log_level_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "badlevel.yaml"
        with path.open("w", encoding="utf-8") as fh:
            yaml.dump(
                {"dev04_clustering": {"logging": {"level": "INVALID"}}},
                fh,
            )
        with pytest.raises(Dev04ConfigError):
            load_dev04_config(path)
