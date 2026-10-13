"""Tests for DEV-09 show / reload helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from customer_segmentation.prototype.end_to_end import (
    E2E_STAGE_SUCCESS,
    E2E_SUCCESS,
    E2ERunSummary,
    E2EStageOutcome,
)
from customer_segmentation.prototype.end_to_end.exceptions import (
    Dev09Error,
    Dev09InputError,
    Dev09StoragePathError,
)
from customer_segmentation.prototype.end_to_end.show import (
    REQUIRED_TOP_KEYS,
    format_run_summary,
    load_run_summary,
    validate_run_summary_payload,
)
from customer_segmentation.prototype.end_to_end.storage import (
    E2E_RUN_ID_REGEX,
    derive_e2e_run_id,
)


def _make_payload(**overrides) -> dict:
    base = {
        "schema_version": "1.0.0",
        "e2e_run_id": "e2e_" + "0" * 24,
        "dataset_id": "ds_x",
        "dataset_sha256": "a" * 64,
        "storage_root": "/tmp/datasets",
        "run_dir": "/tmp/datasets/ds_x/end_to_end/e2e_" + "0" * 24,
        "overall_status": "SUCCESS",
        "lifecycle": "SUCCESS",
        "algorithm": "kmeans",
        "seed": 42,
        "preprocessed_id": "pp_x",
        "clustering_id": "cl_" + "1" * 24,
        "evaluation_id": "ev_" + "2" * 24,
        "segmentation_id": "seg_" + "3" * 24,
        "marketing_id": "mkt_" + "4" * 24,
        "dashboard_id": "viz_" + "5" * 24,
        "stages": [
            {
                "stage": "UPLOAD",
                "status": "SUCCESS",
                "note": "ok",
                "started_utc": "2026-10-10T00:00:00Z",
                "ended_utc": "2026-10-10T00:00:01Z",
                "error_type": "",
                "error_message": "",
                "artifacts": {"manifest_path": "/x/manifest.json"},
            }
        ],
        "inputs": {"source_file": "/x/file.csv"},
        "config": {"dev09_algorithm": "kmeans"},
        "environment": {
            "python": "3.14",
            "platform": "Linux",
            "release": "7.0",
            "machine": "x86_64",
            "key_libraries": {"pandas": "2.0"},
        },
        "notes": [],
        "created_utc": "2026-10-10T00:00:00Z",
    }
    base.update(overrides)
    return base


def _write_summary(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_load_run_summary_happy_path(tmp_path: Path) -> None:
    payload = _make_payload()
    p = _write_summary(tmp_path / "e2e_run.json", payload)
    s = load_run_summary(p)
    assert isinstance(s, E2ERunSummary)
    assert s.schema_version == "1.0.0"
    assert s.dataset_id == "ds_x"
    assert s.algorithm == "kmeans"
    assert s.seed == 42
    assert s.preprocessed_id == "pp_x"
    assert len(s.stages) == 1
    assert s.stages[0].stage == "UPLOAD"


def test_load_run_summary_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(Dev09InputError, match="not found"):
        load_run_summary(tmp_path / "missing.json")


def test_load_run_summary_directory_raises(tmp_path: Path) -> None:
    d = tmp_path / "dir"
    d.mkdir()
    with pytest.raises(Dev09InputError, match="not a file"):
        load_run_summary(d)


def test_load_run_summary_malformed_json_raises(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(Dev09Error, match="Malformed"):
        load_run_summary(p)


def test_load_run_summary_missing_required_keys_raises(tmp_path: Path) -> None:
    payload = _make_payload()
    del payload["e2e_run_id"]
    p = _write_summary(tmp_path / "e2e_run.json", payload)
    with pytest.raises(Dev09Error, match="missing required keys"):
        load_run_summary(p)


def test_load_run_summary_wrong_schema_version_raises(tmp_path: Path) -> None:
    payload = _make_payload(schema_version="0.9.0")
    p = _write_summary(tmp_path / "e2e_run.json", payload)
    with pytest.raises(Dev09Error, match="schema_version"):
        load_run_summary(p)


def test_load_run_summary_invalid_id_format_raises(tmp_path: Path) -> None:
    payload = _make_payload(e2e_run_id="bad_id")
    p = _write_summary(tmp_path / "e2e_run.json", payload)
    with pytest.raises(Dev09StoragePathError, match="e2e_run_id"):
        load_run_summary(p)


def test_load_run_summary_none_optional_ids_preserved(tmp_path: Path) -> None:
    payload = _make_payload(
        preprocessed_id=None,
        clustering_id=None,
        evaluation_id=None,
        segmentation_id=None,
        marketing_id=None,
        dashboard_id=None,
    )
    p = _write_summary(tmp_path / "e2e_run.json", payload)
    s = load_run_summary(p)
    assert s.preprocessed_id is None
    assert s.clustering_id is None
    assert s.evaluation_id is None
    assert s.segmentation_id is None
    assert s.marketing_id is None
    assert s.dashboard_id is None


def test_load_run_summary_empty_string_optional_ids_become_none(tmp_path: Path) -> None:
    payload = _make_payload(
        preprocessed_id="",
        clustering_id="",
        segmentation_id="",
    )
    p = _write_summary(tmp_path / "e2e_run.json", payload)
    s = load_run_summary(p)
    assert s.preprocessed_id is None
    assert s.clustering_id is None
    assert s.segmentation_id is None


def test_load_run_summary_malformed_stage_does_not_raise(tmp_path: Path) -> None:
    payload = _make_payload(stages=[{"stage": "X"}])
    p = _write_summary(tmp_path / "e2e_run.json", payload)
    from customer_segmentation.prototype.end_to_end import E2EStageOutcome

    s = load_run_summary(p)
    assert s.stages[0].stage == "X"
    assert s.stages[0].status == ""
    assert isinstance(s.stages[0], E2EStageOutcome)


def test_load_run_summary_top_level_not_object_raises(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(Dev09Error, match="JSON object"):
        load_run_summary(p)


def test_validate_payload_happy_path() -> None:
    payload = _make_payload()
    validate_run_summary_payload(payload)


def test_validate_payload_not_dict_raises() -> None:
    with pytest.raises(Dev09Error, match="JSON object"):
        validate_run_summary_payload([1, 2, 3])


def test_required_keys_has_all_canonical() -> None:
    assert "e2e_run_id" in REQUIRED_TOP_KEYS
    assert "dataset_id" in REQUIRED_TOP_KEYS
    assert "stages" in REQUIRED_TOP_KEYS


def test_format_run_summary_from_summary_object() -> None:
    payload = _make_payload()
    s = load_run_summary(_write_summary(Path("/tmp/fake.json"), payload))
    text = format_run_summary(s)
    assert "End-to-End Run Summary" in text
    assert payload["e2e_run_id"] in text
    assert "kmeans" in text
    assert "SUCCESS" in text
    assert "UPLOAD" in text


def test_format_run_summary_from_path(tmp_path: Path) -> None:
    payload = _make_payload()
    p = _write_summary(tmp_path / "e2e_run.json", payload)
    text = format_run_summary(p)
    assert "End-to-End Run Summary" in text
    assert payload["e2e_run_id"] in text


def test_format_run_summary_includes_stage_details() -> None:
    payload = _make_payload(
        stages=[
            {
                "stage": "CLUSTERING",
                "status": "FAILED",
                "note": "raised ValueError",
                "started_utc": "2026-10-10T00:00:00Z",
                "ended_utc": "2026-10-10T00:00:01Z",
                "error_type": "ValueError",
                "error_message": "bad k",
                "artifacts": {"manifest_path": "/x/m.json"},
            }
        ]
    )
    p = _write_summary(Path("/tmp/fake.json"), payload)
    text = format_run_summary(p)
    assert "CLUSTERING" in text
    assert "FAILED" in text
    assert "ValueError" in text
    assert "bad k" in text
    assert "/x/m.json" in text


def test_format_run_summary_includes_notes(tmp_path: Path) -> None:
    payload = _make_payload(notes=["manifest copy failed"])
    p = _write_summary(tmp_path / "e2e_run.json", payload)
    text = format_run_summary(p)
    assert "manifest copy failed" in text


def test_format_run_summary_includes_environment(tmp_path: Path) -> None:
    payload = _make_payload()
    p = _write_summary(tmp_path / "e2e_run.json", payload)
    text = format_run_summary(p)
    assert "python" in text
    assert "pandas" in text


def test_format_run_summary_includes_cross_stage_ids(tmp_path: Path) -> None:
    payload = _make_payload()
    p = _write_summary(tmp_path / "e2e_run.json", payload)
    text = format_run_summary(p)
    assert "preprocessed_id" in text
    assert "clustering_id" in text
    assert "segmentation_id" in text


def test_format_run_summary_includes_optional_id_placeholders(tmp_path: Path) -> None:
    payload = _make_payload(
        preprocessed_id=None,
        clustering_id=None,
        segmentation_id=None,
    )
    p = _write_summary(tmp_path / "e2e_run.json", payload)
    text = format_run_summary(p)
    assert "(none)" in text


def test_format_run_summary_returns_string() -> None:
    payload = _make_payload()
    s = load_run_summary(_write_summary(Path("/tmp/fake.json"), payload))
    text = format_run_summary(s)
    assert isinstance(text, str)
    assert len(text) > 0


def test_format_run_summary_no_raw_customer_data() -> None:
    payload = _make_payload(
        stages=[
            {
                "stage": "CUSTOMER_PROFILE",
                "status": "SUCCESS",
                "note": "n_profiles=5",
                "started_utc": "",
                "ended_utc": "",
                "error_type": "",
                "error_message": "",
                "artifacts": {},
            }
        ]
    )
    s = load_run_summary(_write_summary(Path("/tmp/fake.json"), payload))
    text = format_run_summary(s)
    disclaimer = "no ranking, recommendation, or winner annotation is emitted"
    body = text.replace(disclaimer, "")
    for banned in ("best", "winner", "optimal", "recommended", "champion", "vip"):
        assert banned not in body.lower(), f"banned '{banned}' found in {body!r}"


def test_e2e_run_id_regex_format() -> None:
    assert E2E_RUN_ID_REGEX.match("e2e_" + "0" * 24)
    assert not E2E_RUN_ID_REGEX.match("bad")
    assert not E2E_RUN_ID_REGEX.match("e2e_short")


def test_derive_e2e_run_id_for_format() -> None:
    rid = derive_e2e_run_id(
        dataset_id="ds_x",
        dataset_sha256="a" * 64,
        preprocessed_id="pp_x",
        clustering_id="cl_" + "1" * 24,
        segmentation_id="seg_" + "0" * 24,
        algorithm="kmeans",
        seed=42,
        dev04_config_sha256="c" * 64,
        dev06_config_sha256="d" * 64,
    )
    assert E2E_RUN_ID_REGEX.match(rid)


def test_e2erun_summary_can_be_constructed() -> None:
    summary = E2ERunSummary(
        e2e_run_id="e2e_" + "0" * 24,
        schema_version="1.0.0",
        dataset_id="ds_x",
        dataset_sha256="a" * 64,
        storage_root="/tmp",
        run_dir="/tmp/x",
        overall_status=E2E_SUCCESS,
        lifecycle=E2E_SUCCESS,
        algorithm="kmeans",
        seed=42,
        preprocessed_id="pp_x",
        clustering_id="cl_x",
        evaluation_id="ev_x",
        segmentation_id="seg_x",
        marketing_id="mkt_x",
        dashboard_id="viz_x",
        stages=[
            E2EStageOutcome(
                stage="UPLOAD",
                status=E2E_STAGE_SUCCESS,
            )
        ],
        inputs={},
        config={},
        environment={},
        notes=[],
        created_utc="2026-10-10T00:00:00Z",
    )
    d = summary.as_dict()
    assert d["e2e_run_id"] == "e2e_" + "0" * 24
    assert d["overall_status"] == E2E_SUCCESS
    assert len(d["stages"]) == 1
