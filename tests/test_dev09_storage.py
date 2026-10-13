"""Tests for DEV-09 storage layer (storage.py)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from customer_segmentation.prototype.end_to_end.storage import (
    CANONICAL_PAYLOAD_KEYS,
    Dev09StoragePathError,
    compute_config_sha256,
    derive_e2e_run_id,
    end_to_end_run_dir,
    list_e2e_runs,
    resolve_e2e_storage_root,
)


def test_compute_config_sha256_deterministic() -> None:
    h1 = compute_config_sha256("dev09: {x: 1}")
    h2 = compute_config_sha256("dev09: {x: 1}")
    assert h1 == h2


def test_compute_config_sha256_is_64_hex() -> None:
    h = compute_config_sha256("anything")
    assert re.match(r"^[0-9a-f]{64}$", h)


def test_compute_config_sha256_different_content_different_hash() -> None:
    h1 = compute_config_sha256("aaa")
    h2 = compute_config_sha256("bbb")
    assert h1 != h2


def test_compute_config_sha256_non_string_raises() -> None:
    with pytest.raises(Dev09StoragePathError, match="must be a str"):
        compute_config_sha256(123)  # type: ignore[arg-type]


def _valid_kwargs(**overrides) -> dict:
    base = {
        "dataset_id": "ds_x",
        "dataset_sha256": "a" * 64,
        "preprocessed_id": "pp_x",
        "clustering_id": "cl_" + "1" * 24,
        "segmentation_id": "seg_" + "0" * 24,
        "algorithm": "kmeans",
        "seed": 42,
        "dev04_config_sha256": "c" * 64,
        "dev06_config_sha256": "d" * 64,
    }
    base.update(overrides)
    return base


def test_derive_e2e_run_id_prefix_and_length() -> None:
    rid = derive_e2e_run_id(**_valid_kwargs())
    assert rid.startswith("e2e_")
    assert len(rid) == 4 + 24


def test_derive_e2e_run_id_deterministic() -> None:
    assert derive_e2e_run_id(**_valid_kwargs()) == derive_e2e_run_id(**_valid_kwargs())


def test_derive_e2e_run_id_different_inputs_different_id() -> None:
    rid1 = derive_e2e_run_id(**_valid_kwargs(seed=42))
    rid2 = derive_e2e_run_id(**_valid_kwargs(seed=43))
    assert rid1 != rid2


def test_derive_e2e_run_id_algorithm_affects_id() -> None:
    rid1 = derive_e2e_run_id(**_valid_kwargs(algorithm="kmeans"))
    rid2 = derive_e2e_run_id(**_valid_kwargs(algorithm="agglomerative"))
    assert rid1 != rid2


def test_derive_e2e_run_id_dataset_affects_id() -> None:
    rid1 = derive_e2e_run_id(**_valid_kwargs(dataset_id="ds_a"))
    rid2 = derive_e2e_run_id(**_valid_kwargs(dataset_id="ds_b"))
    assert rid1 != rid2


def test_derive_e2e_run_id_allows_none_ids() -> None:
    rid = derive_e2e_run_id(
        **_valid_kwargs(preprocessed_id=None, clustering_id=None, segmentation_id=None)
    )
    assert rid.startswith("e2e_")
    assert len(rid) == 4 + 24


def test_derive_e2e_run_id_allows_none_seed() -> None:
    rid = derive_e2e_run_id(**_valid_kwargs(seed=None))
    assert rid.startswith("e2e_")


@pytest.mark.parametrize("field_name", ["dataset_id", "dataset_sha256", "algorithm"])
def test_derive_e2e_run_id_empty_required_raises(field_name: str) -> None:
    kwargs = _valid_kwargs(**{field_name: ""})
    with pytest.raises(Dev09StoragePathError):
        derive_e2e_run_id(**kwargs)


def test_derive_e2e_run_id_invalid_preprocessed_id_type() -> None:
    kwargs = _valid_kwargs(preprocessed_id=123)
    with pytest.raises(Dev09StoragePathError):
        derive_e2e_run_id(**kwargs)


def test_derive_e2e_run_id_invalid_clustering_id_type() -> None:
    kwargs = _valid_kwargs(clustering_id=123)
    with pytest.raises(Dev09StoragePathError):
        derive_e2e_run_id(**kwargs)


def test_derive_e2e_run_id_invalid_segmentation_id_type() -> None:
    kwargs = _valid_kwargs(segmentation_id=123)
    with pytest.raises(Dev09StoragePathError):
        derive_e2e_run_id(**kwargs)


def test_derive_e2e_run_id_empty_config_sha_raises() -> None:
    kwargs = _valid_kwargs(dev04_config_sha256="")
    with pytest.raises(Dev09StoragePathError):
        derive_e2e_run_id(**kwargs)


def test_resolve_e2e_storage_root_path_layout(tmp_path: Path) -> None:
    p = resolve_e2e_storage_root(tmp_path, dataset_id="ds_x")
    expected = (tmp_path.resolve() / "ds_x" / "end_to_end").resolve()
    assert p == expected


def test_resolve_e2e_storage_root_empty_dataset_id_raises(tmp_path: Path) -> None:
    with pytest.raises(Dev09StoragePathError):
        resolve_e2e_storage_root(tmp_path, dataset_id="")


def test_end_to_end_run_dir_format(tmp_path: Path) -> None:
    rid = derive_e2e_run_id(**_valid_kwargs())
    p = end_to_end_run_dir(tmp_path, dataset_id="ds_x", e2e_run_id=rid)
    assert p.name == rid
    assert "end_to_end" in p.parts
    assert "ds_x" in p.parts


def test_end_to_end_run_dir_invalid_id_raises(tmp_path: Path) -> None:
    with pytest.raises(Dev09StoragePathError, match="does not match"):
        end_to_end_run_dir(tmp_path, dataset_id="ds_x", e2e_run_id="bad")


def test_end_to_end_run_dir_path_inside_storage(tmp_path: Path) -> None:
    rid = derive_e2e_run_id(**_valid_kwargs())
    p = end_to_end_run_dir(tmp_path, dataset_id="ds_x", e2e_run_id=rid)
    assert str(p).startswith(str(tmp_path.resolve()))


def test_list_e2e_runs_empty_dir(tmp_path: Path) -> None:
    recs = list_e2e_runs(tmp_path)
    assert recs == []


def test_list_e2e_runs_missing_storage_root(tmp_path: Path) -> None:
    recs = list_e2e_runs(tmp_path / "nope")
    assert recs == []


def _make_run_record(
    run_dir: Path,
    e2e_run_id: str,
    dataset_id: str = "ds_x",
    overall_status: str = "SUCCESS",
    lifecycle: str = "SUCCESS",
    created_utc: str = "2026-10-10T00:00:00Z",
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0.0",
        "e2e_run_id": e2e_run_id,
        "dataset_id": dataset_id,
        "dataset_sha256": "a" * 64,
        "storage_root": str(run_dir.parents[3]),
        "run_dir": str(run_dir),
        "overall_status": overall_status,
        "lifecycle": lifecycle,
        "algorithm": "kmeans",
        "seed": 42,
        "preprocessed_id": "pp_x",
        "clustering_id": "cl_" + "1" * 24,
        "evaluation_id": None,
        "segmentation_id": "seg_" + "0" * 24,
        "marketing_id": None,
        "dashboard_id": "viz_x",
        "stages": [],
        "inputs": {},
        "config": {},
        "environment": {},
        "notes": [],
        "created_utc": created_utc,
    }
    (run_dir / "e2e_run.json").write_text(json.dumps(payload), encoding="utf-8")


def test_list_e2e_runs_finds_existing_run(tmp_path: Path) -> None:
    rid = derive_e2e_run_id(**_valid_kwargs())
    run_dir = tmp_path / "ds_x" / "end_to_end" / rid
    _make_run_record(run_dir, rid)
    recs = list_e2e_runs(tmp_path)
    assert len(recs) == 1
    assert recs[0].e2e_run_id == rid
    assert recs[0].dataset_id == "ds_x"
    assert recs[0].overall_status == "SUCCESS"


def test_list_e2e_runs_filter_by_dataset_id(tmp_path: Path) -> None:
    rid1 = derive_e2e_run_id(**_valid_kwargs(dataset_id="ds_a"))
    rid2 = derive_e2e_run_id(**_valid_kwargs(dataset_id="ds_b"))
    _make_run_record(tmp_path / "ds_a" / "end_to_end" / rid1, rid1, dataset_id="ds_a")
    _make_run_record(tmp_path / "ds_b" / "end_to_end" / rid2, rid2, dataset_id="ds_b")
    recs = list_e2e_runs(tmp_path, dataset_id="ds_a")
    assert len(recs) == 1
    assert recs[0].dataset_id == "ds_a"


def test_list_e2e_runs_skeleton_dir_returns_unknown_status(tmp_path: Path) -> None:
    e2e_dir = tmp_path / "ds_x" / "end_to_end" / ("e2e_" + "0" * 24)
    e2e_dir.mkdir(parents=True, exist_ok=True)
    recs = list_e2e_runs(tmp_path)
    assert len(recs) == 1
    assert recs[0].overall_status == "UNKNOWN"


def test_list_e2e_runs_skips_malformed_summary(tmp_path: Path) -> None:
    e2e_dir = tmp_path / "ds_x" / "end_to_end" / ("e2e_" + "0" * 24)
    e2e_dir.mkdir(parents=True, exist_ok=True)
    (e2e_dir / "e2e_run.json").write_text("not json {{{", encoding="utf-8")
    recs = list_e2e_runs(tmp_path)
    assert recs == []


def test_list_e2e_runs_skips_unknown_directory_names(tmp_path: Path) -> None:
    bogus_dir = tmp_path / "ds_x" / "end_to_end" / "not_e2e_id"
    bogus_dir.mkdir(parents=True, exist_ok=True)
    recs = list_e2e_runs(tmp_path)
    assert recs == []


def test_canonical_payload_keys_is_tuple() -> None:
    assert isinstance(CANONICAL_PAYLOAD_KEYS, tuple)


def test_canonical_payload_keys_required_fields() -> None:
    keys = set(CANONICAL_PAYLOAD_KEYS)
    assert "schema_version" in keys
    assert "dataset_id" in keys
    assert "dataset_sha256" in keys
    assert "preprocessed_id" in keys
    assert "clustering_id" in keys
    assert "segmentation_id" in keys
    assert "algorithm" in keys
    assert "seed" in keys
    assert "dev04_config_sha256" in keys
    assert "dev06_config_sha256" in keys
