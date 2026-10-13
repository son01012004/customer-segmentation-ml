"""Tests for list_datasets / get_dataset."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from customer_segmentation.dataset_management import (
    DatasetNotFound,
    list_datasets,
    get_dataset,
)
from customer_segmentation.dataset_management.importer import (
    ImportRequest,
    import_dataset,
)


def _make_config(storage_root: Path) -> dict:
    return {
        "storage_root": str(storage_root),
        "max_file_size_mb": 256,
        "supported_import_formats": ["csv", "parquet"],
        "default_csv_encoding": "utf-8",
        "source_path_policy": {"allow_external_source": True},
        "readonly_research_paths": [],
    }


def _import(tmp_path: Path, content: str, name: str) -> str:
    storage = tmp_path / "datasets"
    storage.mkdir(parents=True, exist_ok=True)
    src = tmp_path / f"{name}.csv"
    src.write_text(content, encoding="utf-8")
    res = import_dataset(
        ImportRequest(
            source_path=src,
            name=name,
            config=_make_config(storage),
            allow_external_source=True,
            cwd=tmp_path,
            repo_root=tmp_path,
        )
    )
    return res.dataset_id


def test_list_datasets_returns_empty_when_no_storage(tmp_path: Path) -> None:
    assert list_datasets(tmp_path / "nope") == []


def test_list_datasets_returns_all_after_imports(tmp_path: Path) -> None:
    a_id = _import(tmp_path, "x\n1\n2\n", "a")
    b_id = _import(tmp_path, "y\n3\n4\n", "b")
    items = list_datasets(tmp_path / "datasets")
    ids = {i.dataset_id for i in items}
    assert {a_id, b_id} <= ids


def test_list_datasets_sorted_by_id(tmp_path: Path) -> None:
    _import(tmp_path, "a\n1\n", "a")
    _import(tmp_path, "b\n1\n", "b")
    _import(tmp_path, "c\n1\n", "c")
    items = list_datasets(tmp_path / "datasets")
    ids = [i.dataset_id for i in items]
    assert ids == sorted(ids)


def test_list_datasets_filter_by_name_substring(tmp_path: Path) -> None:
    # Distinct content → distinct SHA256 → distinct dataset_ids (no
    # REUSED_EXISTING_DATASET collapsing on identical bytes).
    _import(tmp_path, "x\n1\n", "alpha")
    _import(tmp_path, "y\n1\n", "beta")
    _import(tmp_path, "z\n1\n", "alpha-prime")
    items = list_datasets(tmp_path / "datasets", name_substring="alpha")
    names = {i.name for i in items}
    assert names == {"alpha", "alpha-prime"}


def test_list_datasets_filter_by_status(tmp_path: Path) -> None:
    _import(tmp_path, "x\n1\n", "ok")
    items = list_datasets(tmp_path / "datasets", status="VALID")
    assert all(i.validation_status == "VALID" for i in items)
    items_failed = list_datasets(tmp_path / "datasets", status="FAILED")
    assert items_failed == []


def test_list_datasets_filter_by_scope(tmp_path: Path) -> None:
    _import(tmp_path, "x\n1\n", "ok")
    items = list_datasets(tmp_path / "datasets", scope="IMPORTED_PROTOTYPE")
    assert len(items) >= 1
    items_other = list_datasets(tmp_path / "datasets", scope="OTHER_SCOPE")
    assert items_other == []


def test_get_dataset_returns_manifest(tmp_path: Path) -> None:
    ds_id = _import(tmp_path, "a,b\n1,2\n3,4\n", "rows")
    m = get_dataset(tmp_path / "datasets", ds_id)
    assert m.dataset_id == ds_id
    assert m.row_count == 2
    assert m.column_count == 2


def test_get_dataset_raises_not_found(tmp_path: Path) -> None:
    with pytest.raises(DatasetNotFound):
        get_dataset(tmp_path / "datasets", "ds_does_not_exist")


def test_list_datasets_summary_fields(tmp_path: Path) -> None:
    ds_id = _import(tmp_path, "a,b\n1,2\n", "fields")
    items = list_datasets(tmp_path / "datasets")
    item = next(i for i in items if i.dataset_id == ds_id)
    assert item.name == "fields"
    assert item.scope == "IMPORTED_PROTOTYPE"
    assert item.validation_status == "VALID"
    assert item.row_count == 1
    assert item.column_count == 2
    assert item.sha256  # non-empty
