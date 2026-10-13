"""Shared pytest fixtures for DEV-04 tests.

Fixtures defined here are available to every test module under
``tests/`` without explicit import. This lets cross-cutting safety
tests (e.g. ``test_dev04_safety.py``) reuse the same synthetic
DEV-03 artefact as the integration tests in
``test_dev04_pipeline.py``.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pandas as pd
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_PATH = str(_REPO_ROOT / "src")
if _SRC_PATH not in sys.path:
    sys.path.insert(0, _SRC_PATH)


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
def synthetic_ml_dataset(tmp_path: Path) -> pd.DataFrame:
    """Create a small synthetic ML Dataset (20 customers × 4 features)."""
    import numpy as np

    np.random.seed(42)
    df = pd.DataFrame(
        {
            "CustomerID": list(range(1, 21)),
            "Recency": list(range(20)),
            "Frequency": [10 + i for i in range(20)],
            "Monetary": [100.0 + i * 5 for i in range(20)],
            "Tenure": [12 + i for i in range(20)],
        }
    )
    return df


@pytest.fixture
def synthetic_dev03_artefact(
    tmp_path: Path, dev02_config: dict, synthetic_ml_dataset: pd.DataFrame
) -> tuple[Path, Path, Path]:
    """Set up a synthetic DEV-03 artefact: ml_dataset parquet + manifest.

    Returns (ml_dataset_path, manifest_path, storage_root).
    """
    import yaml

    storage_root = tmp_path / "datasets"
    dataset_id = "ds_dev04test01"
    preprocessed_id = "pp_dev04test01"

    # Write the DEV-02 config to the canonical location.
    cfg_path = _REPO_ROOT / "configs" / "dev02_dataset_management.yaml"
    if cfg_path.exists():
        canonical_cfg = yaml.safe_load(cfg_path.read_text())
        canonical_cfg["dataset_management"]["storage_root"] = str(storage_root)
        canonical_cfg_path = storage_root / "dev02_dataset_management.yaml"
        canonical_cfg_path.parent.mkdir(parents=True, exist_ok=True)
        with canonical_cfg_path.open("w", encoding="utf-8") as fh:
            yaml.dump(canonical_cfg, fh)
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
    else:
        original_cwd = None

    try:
        # Create the preprocessed directory structure (post-A-1: DEV-03
        # writes artefacts FLAT under ``<storage_root>/<dataset_id>/preprocessed/``
        # — no ``<preprocessed_id>`` subdirectory).
        preprocessed_dir = storage_root / dataset_id / "preprocessed"
        preprocessed_dir.mkdir(parents=True, exist_ok=True)

        # Write the ML Dataset parquet.
        ml_dataset_name = f"ml_dataset_dev04test01_{preprocessed_id}.parquet"
        ml_dataset_path = preprocessed_dir / ml_dataset_name
        synthetic_ml_dataset.to_parquet(ml_dataset_path, index=False)

        # Write the DEV-03 manifest.
        import hashlib

        sha = hashlib.sha256(ml_dataset_path.read_bytes()).hexdigest()
        manifest = {
            "schema_version": "1.0.0",
            "preprocessed_id": preprocessed_id,
            "preprocessed_scope": "PREPROCESSED_PROTOTYPE",
            "source_dataset_id": dataset_id,
            "source_dataset_sha256": "b" * 64,
            "config_hash": "c" * 64,
            "preprocessing_block": {
                "enabled": True,
                "input_row_count": 1000,
                "input_column_count": 8,
                "output_row_count": 1000,
                "rows_removed_total": 0,
                "rows_retained": 1000,
                "cancellation_prefix": "C",
                "flag_cancellations": True,
                "flag_returns": True,
                "outlier_action": "flag",
                "outlier_method": "iqr",
                "transformation": "none",
                "scaling": "none",
                "stage_outcomes": {"A": "PASS", "B": "PASS", "C": "PASS"},
                "rules": [],
                "config_snapshot": {},
                "status": "WORKING_ASSUMPTION",
            },
            "feature_generation_block": {
                "reference_date": "2011-12-09",
                "customer_count": 20,
                "candidate_feature_count": 4,
                "outcome": "PASS",
                "validation_passed": True,
                "f1_input_row_count": 1000,
                "f2_base_row_count": 20,
                "errors": [],
                "warnings": [],
                "status": "WORKING_ASSUMPTION",
            },
            "ml_dataset_block": {
                "row_count": 20,
                "column_count": 5,
                "columns": ["CustomerID", "Recency", "Frequency", "Monetary", "Tenure"],
                "sha256": sha,
                "file_size_bytes": int(ml_dataset_path.stat().st_size),
                "artifact_path": ml_dataset_name,
                "status": "WORKING_ASSUMPTION",
            },
            "environment": {
                "python": "3.14",
                "platform": "Linux",
                "release": "7.0",
                "machine": "x86_64",
                "key_libraries": {"pandas": "2.0"},
            },
            "research_safety": {
                "automatically_promoted_to_research": False,
                "scope": "PREPROCESSED_PROTOTYPE",
                "appeared_in_research_evidence": False,
                "read_only_paths_unmodified": [],
            },
            "created_utc": "2026-10-09T00:00:00Z",
            "last_seen_utc": "2026-10-09T00:00:00Z",
            "log_file": "preprocessing.log",
            "intermediate_artifact_path": None,
        }
        manifest_path = preprocessed_dir / "preprocessed_manifest.json"
        with manifest_path.open("w", encoding="utf-8") as fh:
            json.dump(manifest, fh)

        return ml_dataset_path, manifest_path, storage_root
    finally:
        if original_cwd is not None:
            os.chdir(original_cwd)
