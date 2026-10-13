"""Tests for the importer Parquet path."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from customer_segmentation.dataset_management.importer import (
    ImportError,
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


def _write_parquet(path: Path, df: pd.DataFrame) -> None:
    pq.write_table(pa.Table.from_pandas(df), path)


def test_parquet_with_all_dtypes(tmp_path: Path) -> None:
    storage = tmp_path / "datasets"
    storage.mkdir()
    src = tmp_path / "d.parquet"
    df = pd.DataFrame(
        {
            "i": pd.array([1, 2, 3], dtype="int64"),
            "f": pd.array([1.0, 2.5, 3.5], dtype="float64"),
            "s": pd.array(["a", "b", "c"], dtype="object"),
            "b": pd.array([True, False, True], dtype="bool"),
            "d": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
        }
    )
    _write_parquet(src, df)
    res = import_dataset(
        ImportRequest(
            source_path=src,
            name=None,
            config=_make_config(storage),
            allow_external_source=True,
            cwd=tmp_path,
            repo_root=tmp_path,
        )
    )
    types = {c.name: c.inferred_type for c in res.manifest.columns}
    assert types["i"] == "numeric"
    assert types["f"] == "numeric"
    assert types["s"] == "string"
    assert types["b"] == "boolean"
    assert types["d"] == "datetime"


def test_parquet_corrupt_file_rejected(tmp_path: Path) -> None:
    storage = tmp_path / "datasets"
    storage.mkdir()
    src = tmp_path / "bad.parquet"
    src.write_bytes(b"not a parquet file at all")
    with pytest.raises(ImportError):
        import_dataset(
            ImportRequest(
                source_path=src,
                name=None,
                config=_make_config(storage),
                allow_external_source=True,
                cwd=tmp_path,
                repo_root=tmp_path,
            )
        )


def test_parquet_with_null_column(tmp_path: Path) -> None:
    storage = tmp_path / "datasets"
    storage.mkdir()
    src = tmp_path / "null.parquet"
    df = pd.DataFrame({"a": [1, None, 3]})
    _write_parquet(src, df)
    res = import_dataset(
        ImportRequest(
            source_path=src,
            name=None,
            config=_make_config(storage),
            allow_external_source=True,
            cwd=tmp_path,
            repo_root=tmp_path,
        )
    )
    assert res.manifest.columns[0].missing_count == 1


def test_parquet_idempotency(tmp_path: Path) -> None:
    storage = tmp_path / "datasets"
    storage.mkdir()
    src = tmp_path / "d.parquet"
    _write_parquet(src, pd.DataFrame({"a": [1, 2, 3]}))
    req = ImportRequest(
        source_path=src,
        name=None,
        config=_make_config(storage),
        allow_external_source=True,
        cwd=tmp_path,
        repo_root=tmp_path,
    )
    r1 = import_dataset(req)
    r2 = import_dataset(req)
    assert not r1.reused
    assert r2.reused
    assert r1.dataset_id == r2.dataset_id
