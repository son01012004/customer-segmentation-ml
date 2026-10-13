"""Tests for the manifest module — schema, JSON I/O, stable/runtime fields."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from customer_segmentation.dataset_management.manifest import (
    MANIFEST_SCHEMA_VERSION,
    CategoricalStats,
    ColumnInfo,
    Manifest,
    ManifestError,
    NumericStats,
    Provenance,
    ResearchSafety,
    StatisticsSummary,
    StorageInfo,
    ValidationBlock,
    ValidationCategory,
    now_iso,
    read_manifest,
    runtime_field_names,
    stable_field_names,
    update_last_seen,
    write_manifest,
)


def _make_manifest(tmp_path: Path, *, sha: str = "a" * 64) -> Manifest:
    storage = StorageInfo(
        directory=str(tmp_path / "ds_aaa" / "datasets" / "ds_aaa"),
        artifact_path="ds_aaa/data.csv",
        file_size_bytes=12345,
    )
    return Manifest(
        schema_version=MANIFEST_SCHEMA_VERSION,
        dataset_id="ds_" + sha[:24],
        dataset_scope="IMPORTED_PROTOTYPE",
        name="data",
        original_filename="data.csv",
        format="csv",
        storage=storage,
        sha256=sha,
        row_count=10,
        column_count=3,
        columns=[
            ColumnInfo(name="a", inferred_type="numeric", nullable=False, missing_count=0),
            ColumnInfo(name="b", inferred_type="string", nullable=True, missing_count=2),
            ColumnInfo(name="c", inferred_type="numeric", nullable=False, missing_count=0),
        ],
        missing_summary={"a": 0.0, "b": 20.0, "c": 0.0},
        statistics_summary=StatisticsSummary(
            numeric={
                "a": NumericStats(count=10, mean=1.0, std=0.5, min=0, median=1, max=2),
                "c": NumericStats(count=10, mean=3.0, std=0.7, min=2, median=3, max=4),
            },
            categorical={
                "b": CategoricalStats(count=8, unique_count=4),
            },
        ),
        validation=ValidationBlock(
            file_level=ValidationCategory(
                result="PASS", errors=[], warnings=[], stats={}
            ),
            structural=ValidationCategory(
                result="PASS", errors=[], warnings=[], stats={"row_count": 10}
            ),
            data_quality=ValidationCategory(
                result="WARNING",
                errors=[],
                warnings=["NaN values present in 1 column(s)."],
                stats={"nan_columns": 1},
            ),
        ),
        validation_status="VALID",
        created_utc="2026-10-08T12:00:00Z",
        last_seen_utc="2026-10-08T12:00:00Z",
        provenance=Provenance(
            import_method="cli",
            source_filename="data.csv",
            source_relative_path="data.csv",
            license=None,
            notes="Imported for prototype validation.",
        ),
        research_safety=ResearchSafety(
            automatically_promoted_to_research=False,
            scope="IMPORTED_PROTOTYPE",
            appeared_in_research_evidence=False,
            read_only_paths_unmodified=[
                "data/raw/primary",
                "data/raw/backup",
                "data/processed",
                "reports",
            ],
        ),
    )


def test_now_iso_returns_utc_z_suffix() -> None:
    s = now_iso()
    assert s.endswith("Z")
    assert s[10] == "T"


def test_write_then_read_round_trip(tmp_path: Path) -> None:
    m = _make_manifest(tmp_path)
    target = tmp_path / "manifest.json"
    write_manifest(m, target)
    assert target.exists()
    # Original is gone, only the final file remains.
    assert not (tmp_path / "manifest.json.tmp").exists()
    m2 = read_manifest(target)
    assert m2.dataset_id == m.dataset_id
    assert m2.sha256 == m.sha256
    assert m2.row_count == m.row_count
    assert m2.validation_status == m.validation_status
    assert m2.provenance.source_filename == m.provenance.source_filename
    assert m2.statistics_summary.numeric["a"].mean == 1.0


def test_write_atomic_no_partial_on_failure(tmp_path: Path) -> None:
    m = _make_manifest(tmp_path)
    target = tmp_path / "manifest.json"

    class _BrokenManifest:
        def __getattr__(self, name: str) -> None:
            raise RuntimeError("nope")

    # Patch a tmp suffix and inject an exception path: we monkey-patch
    # json.dump to raise, then write. Temp should be cleaned up.
    import customer_segmentation.dataset_management.manifest as m_mod

    orig = m_mod.json.dump
    try:
        def boom(*args, **kwargs):
            raise RuntimeError("disk full")
        m_mod.json.dump = boom  # type: ignore[assignment]
        with pytest.raises(RuntimeError):
            write_manifest(m, target)
        # No partial target, no leftover temp.
        assert not target.exists()
        temps = list(tmp_path.glob("*.tmp"))
        assert temps == []
    finally:
        m_mod.json.dump = orig  # type: ignore[assignment]


def test_read_manifest_raises_on_missing(tmp_path: Path) -> None:
    with pytest.raises(ManifestError):
        read_manifest(tmp_path / "missing.json")


def test_read_manifest_raises_on_invalid_json(tmp_path: Path) -> None:
    target = tmp_path / "m.json"
    target.write_text("not json", encoding="utf-8")
    with pytest.raises(ManifestError):
        read_manifest(target)


def test_read_manifest_raises_on_missing_required_field(tmp_path: Path) -> None:
    target = tmp_path / "m.json"
    target.write_text('{"dataset_id": "ds_xxx"}', encoding="utf-8")
    with pytest.raises(ManifestError):
        read_manifest(target)


def test_stable_field_names_present() -> None:
    expected = {
        "schema_version",
        "dataset_id",
        "dataset_scope",
        "name",
        "original_filename",
        "format",
        "storage",
        "sha256",
        "row_count",
        "column_count",
        "columns",
        "missing_summary",
        "statistics_summary",
        "validation",
        "validation_status",
        "provenance",
        "research_safety",
    }
    assert stable_field_names() == expected


def test_runtime_field_names_present() -> None:
    expected = {"created_utc", "last_seen_utc", "environment", "config_hash"}
    assert runtime_field_names() == expected


def test_stable_and_runtime_are_disjoint() -> None:
    assert stable_field_names() & runtime_field_names() == set()


def test_update_last_seen_changes_only_last_seen(tmp_path: Path) -> None:
    m = _make_manifest(tmp_path)
    before = m.last_seen_utc
    m2 = update_last_seen(m, now="2099-01-01T00:00:00Z")
    assert m2.last_seen_utc == "2099-01-01T00:00:00Z"
    assert m.last_seen_utc == before
    # All stable fields preserved.
    assert m2.dataset_id == m.dataset_id
    assert m2.sha256 == m.sha256
    assert m2.created_utc == m.created_utc


def test_manifest_to_dict_is_json_serialisable(tmp_path: Path) -> None:
    import customer_segmentation.dataset_management.manifest as m_mod

    m = _make_manifest(tmp_path)
    d = m_mod.manifest_to_dict(m)
    text = json.dumps(d)
    parsed = json.loads(text)
    assert parsed["dataset_id"] == m.dataset_id
    assert parsed["storage"]["file_size_bytes"] == 12345
    assert parsed["validation"]["data_quality"]["warnings"] == [
        "NaN values present in 1 column(s)."
    ]
