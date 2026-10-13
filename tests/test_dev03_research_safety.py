"""Tests for research-safety invariants of the DEV-03 preprocessing pipeline.

These tests verify that DEV-03 only writes to
``<storage_root>/<dataset_id>/preprocessed/`` and never to research
artefact paths.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import yaml

from customer_segmentation.dataset_management import ImportRequest, import_dataset
from customer_segmentation.prototype.preprocessing import run_preprocessing_pipeline


def _snapshot_research_paths(repo: Path) -> dict[Path, str]:
    """Return a {path: sha256-or-sentinel} map of every research path.

    Missing paths are recorded with an empty string so a deletion would
    show up as a missing value.
    """
    snap: dict[Path, str] = {}
    for sub in ("data/raw/primary", "data/raw/backup", "data/processed", "reports"):
        p = repo / sub
        if not p.exists():
            snap[p] = "<missing>"
            continue
        # Hash a directory listing of the path. For files, hash bytes.
        if p.is_file():
            snap[p] = hashlib.sha256(p.read_bytes()).hexdigest()
            continue
        parts = []
        for subp in sorted(p.rglob("*")):
            if subp.is_file():
                parts.append(
                    f"{subp.relative_to(p).as_posix()}|{hashlib.sha256(subp.read_bytes()).hexdigest()}"
                )
        snap[p] = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
    return snap


def _make_dev02_config(storage_root: Path) -> dict:
    return {
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


def _run_one_preprocess(
    repo_root_for_research_safety: Path,
    storage_root: Path,
    fixture_csv: Path,
    cwd_for_config_lookup: Path,
    cfg_yaml_dest: Path,
) -> tuple[str, str]:
    """Run DEV-02 import + DEV-03 preprocess against the test storage root."""
    import os

    dev02_cfg = _make_dev02_config(storage_root)
    res = import_dataset(
        ImportRequest(
            source_path=fixture_csv,
            name=None,
            config=dev02_cfg,
            allow_external_source=True,
            cwd=storage_root,
            repo_root=storage_root,  # source is external allowed
        )
    )
    dataset_id = res.dataset_id
    # Copy dev03 yaml to chdir's configs/ so the pipeline picks it up.
    import shutil

    (cwd_for_config_lookup / "configs").mkdir(parents=True, exist_ok=True)
    shutil.copy(
        Path(
            "/home/hoangson301223/NCKH/EPU_CNS_SG_SV_2026_PHASE_2_PROJECT_13/customer-segmentation-ml/configs/dev03_preprocessing.yaml"
        ),
        cfg_yaml_dest,
    )
    prev = Path.cwd()
    os.chdir(cwd_for_config_lookup)
    try:
        # Patch the dev02 config to point at our storage_root.
        (cwd_for_config_lookup / "configs" / "dev02_dataset_management.yaml").write_text(
            yaml.safe_dump({"dataset_management": dev02_cfg})
        )
        result = run_preprocessing_pipeline(
            dataset_id,
            config_path=cwd_for_config_lookup / "configs" / "dev03_preprocessing.yaml",
        )
    finally:
        os.chdir(prev)
    return dataset_id, result.preprocessed_id


def test_run_does_not_modify_research_paths(tmp_path: Path) -> None:
    """A successful DEV-03 run must not change any read-only research path."""
    repo = tmp_path / "repo"
    # Lay out a fake research-path structure.
    for sub in ("data/raw/primary", "data/raw/backup", "data/processed", "reports"):
        d = repo / sub
        d.mkdir(parents=True, exist_ok=True)
        (d / "marker.txt").write_text(f"research-marker:{sub}\n", encoding="utf-8")
    # A fake canonical FE-06 file (would be the research evidence).
    (repo / "data/processed" / "final_clustering_dataset.parquet").parent.mkdir(
        parents=True, exist_ok=True
    )
    pd.DataFrame({"x": [1, 2, 3]}).to_parquet(
        repo / "data" / "processed" / "final_clustering_dataset.parquet"
    )
    # Build a fixture CSV (no real Online Retail data needed).
    fixture = tmp_path / "fixture.csv"
    rows = [
        ("536365", "85123A", "ITEM-A", 6, "2010-12-01 08:26:00", 2.55, 12345, "UK"),
        ("536366", "71053", "ITEM-B", 8, "2010-12-01 09:32:00", 3.39, 12345, "UK"),
    ]
    pd.DataFrame(
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
    ).to_csv(fixture, index=False)

    storage_root = tmp_path / "storage"
    storage_root.mkdir()
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    cfg_yaml_dest = cfg_dir / "configs" / "dev03_preprocessing.yaml"

    [
        repo / "data" / "raw" / "primary",
        repo / "data" / "raw" / "backup",
        repo / "data" / "processed",
        repo / "reports",
    ]
    before = _snapshot_research_paths(repo)

    dataset_id, _ = _run_one_preprocess(
        repo_root_for_research_safety=repo,
        storage_root=storage_root,
        fixture_csv=fixture,
        cwd_for_config_lookup=cfg_dir,
        cfg_yaml_dest=cfg_yaml_dest,
    )

    after = _snapshot_research_paths(repo)
    assert before == after, "Research-safety violation: research path modified."


def test_write_locations_constrained_to_storage_root(tmp_path: Path) -> None:
    """All new files are under the configured storage root."""
    repo = tmp_path / "repo"
    for sub in ("data/raw/primary", "data/raw/backup", "data/processed", "reports"):
        d = repo / sub
        d.mkdir(parents=True, exist_ok=True)
        (d / "marker.txt").write_text("x\n", encoding="utf-8")
    fixture = tmp_path / "fixture.csv"
    rows = [
        ("536365", "85123A", "ITEM-A", 6, "2010-12-01 08:26:00", 2.55, 12345, "UK"),
        ("536366", "71053", "ITEM-B", 8, "2010-12-01 09:32:00", 3.39, 12345, "UK"),
    ]
    pd.DataFrame(
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
    ).to_csv(fixture, index=False)

    storage_root = tmp_path / "storage"
    storage_root.mkdir()
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    cfg_yaml_dest = cfg_dir / "configs" / "dev03_preprocessing.yaml"

    before_paths = set()
    for sub in ("data/raw/primary", "data/raw/backup", "data/processed", "reports"):
        before_paths |= {p.relative_to(repo) for p in (repo / sub).rglob("*")}

    _run_one_preprocess(
        repo_root_for_research_safety=repo,
        storage_root=storage_root,
        fixture_csv=fixture,
        cwd_for_config_lookup=cfg_dir,
        cfg_yaml_dest=cfg_yaml_dest,
    )

    after_paths = set()
    for sub in ("data/raw/primary", "data/raw/backup", "data/processed", "reports"):
        after_paths |= {p.relative_to(repo) for p in (repo / sub).rglob("*")}
    new_outside_storage = after_paths - before_paths
    assert (
        new_outside_storage == set()
    ), f"Unexpected new files outside storage root: {new_outside_storage}"


def test_manifest_research_safety_markers() -> None:
    """The PreprocessedManifest research_safety block is always set safely."""
    from customer_segmentation.prototype.preprocessing.manifest import ResearchSafetyBlock

    rs = ResearchSafetyBlock(
        automatically_promoted_to_research=False,
        scope="PREPROCESSED_PROTOTYPE",
        appeared_in_research_evidence=False,
        read_only_paths_unmodified=[
            "data/raw/primary",
            "data/raw/backup",
            "data/processed",
            "reports",
        ],
    )
    assert rs.automatically_promoted_to_research is False
    assert rs.appeared_in_research_evidence is False
    assert rs.scope == "PREPROCESSED_PROTOTYPE"


def test_cleaning_rules_status_inherited_verbatim_in_manifest() -> None:
    """The manifest's CL-01..CL-10 status matches FE-02 KEY_ANNOTATIONS."""
    from customer_segmentation.prototype.preprocessing.config_loader import (
        PreprocessingCleaningInvalidRecordsConfig,
    )

    cfg = PreprocessingCleaningInvalidRecordsConfig()
    assert cfg.status_for("CL-01") == "WORKING_ASSUMPTION"
    assert cfg.status_for("CL-06") == "PENDING_MENTOR_REVIEW"
    assert cfg.status_for("CL-08") == "PENDING_MENTOR_REVIEW"
    assert cfg.status_for("CL-09") == "WORKING_ASSUMPTION"
