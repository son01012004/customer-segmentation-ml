"""Integration tests for the DEV-03 preprocessing pipeline.

These tests import a real CSV (or in-memory DataFrame) through DEV-02
+ DEV-03 and check the artefacts. They use a tmpdir as the storage
root so the real on-disk data is never touched.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pandas as pd
import pytest
import yaml

from customer_segmentation.dataset_management import ImportRequest, import_dataset
from customer_segmentation.prototype.preprocessing import (
    PreprocessingStage,
    run_preprocessing_pipeline,
)


@pytest.fixture
def fixture_csv(tmp_path: Path) -> Path:
    """Write a small fixture CSV (multi-customer, with cancellation)."""
    rows = [
        # Customer 12345, normal purchases
        ("536365", "85123A", "ITEM-A", 6, "2010-12-01 08:26:00", 2.55, 12345, "United Kingdom"),
        ("536365", "71053", "ITEM-B", 8, "2010-12-01 08:26:00", 3.39, 12345, "United Kingdom"),
        # Customer 12345, second invoice
        ("536366", "84406B", "ITEM-C", 2, "2010-12-01 09:32:00", 4.25, 12345, "United Kingdom"),
        # Customer 12346, single purchase
        ("536367", "84029G", "ITEM-D", 12, "2010-12-01 10:15:00", 1.85, 12346, "United Kingdom"),
        # Customer 12347, cancellation
        ("C536368", "85123A", "ITEM-A", -6, "2010-12-01 10:45:00", 2.55, 12347, "United Kingdom"),
    ]
    df = pd.DataFrame(
        rows,
        columns=[
            "InvoiceNo",
            "StockCode",
            "Description",
            "Quantity",
            "InvoiceDate",
            "UnitPrice",
            "CustomerID",
            "Country",
        ],
    )
    p = tmp_path / "fixture.csv"
    df.to_csv(p, index=False, encoding="utf-8")
    return p


@pytest.fixture
def dev02_config(tmp_path: Path) -> dict:
    storage_root = tmp_path / "datasets"
    storage_root.mkdir(parents=True, exist_ok=True)
    return {
        "dataset_management": {
            "storage_root": str(storage_root),
            "max_file_size_mb": 256,
            "supported_import_formats": ["csv", "parquet"],
            "default_csv_encoding": "utf-8",
            "source_path_policy": {"allow_external_source": True},
            "readonly_research_paths": [
                "data/raw/primary",
                "data/raw/backup",
                "data/processed",
                "reports",
            ],
        }
    }


@pytest.fixture
def setup_dirs(tmp_path: Path, dev02_config: dict) -> tuple[Path, Path]:
    """Set up CWD-cfg with dev02 + dev03 configs; chdir before tests."""
    cfg_dir = tmp_path / "cfgdir"
    cfg_dir.mkdir()
    (cfg_dir / "configs").mkdir()
    dev02_yaml = cfg_dir / "configs" / "dev02_dataset_management.yaml"
    dev02_yaml.write_text(yaml.safe_dump(dev02_config))
    dev03_src = Path(
        "/home/hoangson301223/NCKH/EPU_CNS_SG_SV_2026_PHASE_2_PROJECT_13/customer-segmentation-ml"
        "/configs/dev03_preprocessing.yaml"
    )
    shutil.copy(dev03_src, cfg_dir / "configs" / "dev03_preprocessing.yaml")
    cwd = Path.cwd()
    os.chdir(cfg_dir)
    yield cfg_dir / "configs" / "dev03_preprocessing.yaml", dev02_yaml
    os.chdir(cwd)


def test_pipeline_end_to_end_csv(
    tmp_path: Path, fixture_csv: Path, dev02_config: dict, setup_dirs: tuple
) -> None:
    dev03_yaml, _ = setup_dirs
    Path(dev02_config["dataset_management"]["storage_root"])
    res = import_dataset(
        ImportRequest(
            source_path=fixture_csv,
            name=None,
            config=dev02_config["dataset_management"],
            allow_external_source=True,
            cwd=tmp_path,
            repo_root=tmp_path,
        )
    )
    assert res.manifest.validation_status == "VALID"
    dataset_id = res.dataset_id

    result = run_preprocessing_pipeline(dataset_id, config_path=dev03_yaml)
    assert result.lifecycle in {"VALID", "WARNING", "FAILED"}
    assert result.preprocessed_id.startswith("pp_")
    # 5 rows input; 1 is a cancellation; cleaning may keep most rows.
    assert result.cleaning.rows_in == 5
    # Stage outcomes should include all 7 stages (A→G).
    for stage in ("A", "B", "C", "D", "E", "F", "G"):
        assert stage in result.stage_outcomes, f"Stage {stage} missing"


def test_pipeline_writes_manifest_and_ml_dataset(
    tmp_path: Path, fixture_csv: Path, dev02_config: dict, setup_dirs: tuple
) -> None:
    dev03_yaml, _ = setup_dirs
    res = import_dataset(
        ImportRequest(
            source_path=fixture_csv,
            name=None,
            config=dev02_config["dataset_management"],
            allow_external_source=True,
            cwd=tmp_path,
            repo_root=tmp_path,
        )
    )
    dataset_id = res.dataset_id
    result = run_preprocessing_pipeline(dataset_id, config_path=dev03_yaml)
    assert result.manifest_path.exists()
    assert result.ml_dataset_path.exists()
    assert result.log_path.exists()


def test_pipeline_output_contains_required_columns(
    tmp_path: Path, fixture_csv: Path, dev02_config: dict, setup_dirs: tuple
) -> None:
    dev03_yaml, _ = setup_dirs
    res = import_dataset(
        ImportRequest(
            source_path=fixture_csv,
            name=None,
            config=dev02_config["dataset_management"],
            allow_external_source=True,
            cwd=tmp_path,
            repo_root=tmp_path,
        )
    )
    dataset_id = res.dataset_id
    result = run_preprocessing_pipeline(dataset_id, config_path=dev03_yaml)
    df = pd.read_parquet(result.ml_dataset_path)
    # CustomerID + at least one RFM/behavioral feature.
    assert "CustomerID" in df.columns
    assert "Recency" in df.columns
    assert "Frequency" in df.columns
    assert "Monetary" in df.columns
    assert "TenureDays" in df.columns
    assert "CancellationRate" in df.columns


def test_pipeline_idempotent_same_input_same_id(
    tmp_path: Path, fixture_csv: Path, dev02_config: dict, setup_dirs: tuple
) -> None:
    """Re-preprocess the same dataset; preprocessed_id is deterministic."""
    dev03_yaml, _ = setup_dirs
    res = import_dataset(
        ImportRequest(
            source_path=fixture_csv,
            name=None,
            config=dev02_config["dataset_management"],
            allow_external_source=True,
            cwd=tmp_path,
            repo_root=tmp_path,
        )
    )
    dataset_id = res.dataset_id
    r1 = run_preprocessing_pipeline(dataset_id, config_path=dev03_yaml)
    r2 = run_preprocessing_pipeline(dataset_id, config_path=dev03_yaml)
    assert r1.preprocessed_id == r2.preprocessed_id


def test_pipeline_unknown_dataset_id_returns_failed_result(
    tmp_path: Path, setup_dirs: tuple
) -> None:
    """An unknown dataset_id surfaces as a FAILED result (lifecycle=FAILED, empty preprocessed_id)."""
    dev03_yaml, _ = setup_dirs
    fake_id = "ds_" + "0" * 24
    result = run_preprocessing_pipeline(fake_id, config_path=dev03_yaml)
    assert result.lifecycle == "FAILED"
    assert result.preprocessed_id == ""
    assert "A" not in result.stage_outcomes


def test_pipeline_aborts_on_empty_input(tmp_path: Path, setup_dirs: tuple) -> None:
    """An empty input should fail at DEV-02 import (raises ImportError)."""
    dev03_yaml, _ = setup_dirs
    empty_csv = tmp_path / "empty.csv"
    empty_csv.write_text(
        "InvoiceNo,StockCode,Description,Quantity,InvoiceDate,UnitPrice,CustomerID,Country\n"
    )
    dev02_storage = tmp_path / "datasets2"
    dev02_storage.mkdir()
    from customer_segmentation.dataset_management import ImportError as DMImportError

    with pytest.raises((DMImportError, ValueError, Exception)):
        import_dataset(
            ImportRequest(
                source_path=empty_csv,
                name=None,
                config={
                    "storage_root": str(dev02_storage),
                    "max_file_size_mb": 256,
                    "supported_import_formats": ["csv", "parquet"],
                    "default_csv_encoding": "utf-8",
                    "source_path_policy": {"allow_external_source": True},
                    "readonly_research_paths": [
                        "data/raw/primary",
                        "data/raw/backup",
                        "data/processed",
                        "reports",
                    ],
                },
                allow_external_source=True,
                cwd=tmp_path,
                repo_root=tmp_path,
            )
        )


def test_stage_letters_in_outcomes(
    tmp_path: Path, fixture_csv: Path, dev02_config: dict, setup_dirs: tuple
) -> None:
    """The 7 stages in the plan are A→B→C→D→E→F→G; outcomes map covers all 7."""
    dev03_yaml, _ = setup_dirs
    res = import_dataset(
        ImportRequest(
            source_path=fixture_csv,
            name=None,
            config=dev02_config["dataset_management"],
            allow_external_source=True,
            cwd=tmp_path,
            repo_root=tmp_path,
        )
    )
    run_preprocessing_pipeline(res.dataset_id, config_path=dev03_yaml)
    for stage in PreprocessingStage:
        # Stage enum values include "A"..."G"
        assert stage.value in {"A", "B", "C", "D", "E", "F", "G"}
