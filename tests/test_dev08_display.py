"""Tests for DEV-08 display helpers (display.py)."""

from __future__ import annotations

import json
import re
from typing import Any

import pytest

from customer_segmentation.prototype.visualization.display import (
    BANNED_SUBSTRINGS,
    DEFAULT_DISCLAIMER_TEXT,
    DashboardChartRecord,
    DashboardResult,
    dashboard_result_to_dict,
    dashboard_result_to_json,
    format_dashboard_run_report,
    format_dashboard_section_header,
    format_dashboard_summary,
    now_utc_iso,
)
from customer_segmentation.prototype.visualization.display import (
    check_no_banned_substrings as display_check_no_banned_substrings,
)
from customer_segmentation.prototype.visualization.exceptions import (
    VisualizationError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _strip_disclaimer(text: str, disclaimer: str = DEFAULT_DISCLAIMER_TEXT) -> str:
    if not disclaimer:
        return text
    out = text
    lower = out.lower()
    dl = disclaimer.lower()
    while dl in lower:
        idx = lower.index(dl)
        out = out[:idx] + out[idx + len(dl) :]
        lower = out.lower()
    return out


def _has_banned(text: str) -> list[str]:
    cleaned = _strip_disclaimer(text)
    found: list[str] = []
    for b in BANNED_SUBSTRINGS:
        pattern = r"\b" + re.escape(b).replace("\\-", r"[-\s]") + r"\b"
        if re.search(pattern, cleaned, flags=re.IGNORECASE):
            found.append(b)
    return found


def _make_result(**overrides: Any) -> DashboardResult:
    base = {
        "dashboard_id": "viz_" + "0" * 24,
        "segmentation_id": "seg_" + "1" * 24,
        "clustering_id": "cl_" + "2" * 24,
        "preprocessed_id": "pp_x",
        "dataset_id": "ds_x",
        "run_dir": "/tmp/run",
        "lifecycle": "SUCCESS",
        "validation_passed": True,
        "charts": [
            DashboardChartRecord(
                name="cluster_distribution",
                output_path="/tmp/run/cluster_distribution.png",
                status="EMITTED",
                note="",
            ),
            DashboardChartRecord(
                name="metric_comparison",
                output_path="",
                status="SKIPPED",
                note="no EvaluationManifest provided",
            ),
            DashboardChartRecord(
                name="cluster_visualization_2d",
                output_path="",
                status="BLOCKED",
                note="no projection methodology approved",
            ),
        ],
        "input_segmentation_manifest_path": "/tmp/seg.json",
        "input_evaluation_manifest_paths": ["/tmp/ev1.json", "/tmp/ev2.json"],
        "input_marketing_manifest_path": None,
        "notes": ["test note"],
        "created_utc": "2026-10-10T00:00:00Z",
    }
    base.update(overrides)
    return DashboardResult(**base)


# ---------------------------------------------------------------------------
# check_no_banned_substrings
# ---------------------------------------------------------------------------


def test_check_no_banned_substrings_clean_text() -> None:
    assert display_check_no_banned_substrings("hello world") == []


def test_check_no_banned_substrings_detects_banned() -> None:
    assert "best" in display_check_no_banned_substrings("the best cluster")


def test_check_no_banned_substrings_excludes_disclaimer() -> None:
    # DEFAULT_DISCLAIMER_TEXT contains "ranking", "recommendation", "winner".
    assert display_check_no_banned_substrings(DEFAULT_DISCLAIMER_TEXT) == []


def test_check_no_banned_substrings_word_boundary() -> None:
    # "champion" should match; "championing" should also match (substr check).
    found = display_check_no_banned_substrings("champion of segment")
    assert "champion" in found


# ---------------------------------------------------------------------------
# format_dashboard_section_header
# ---------------------------------------------------------------------------


def test_format_dashboard_section_header_basic() -> None:
    h = format_dashboard_section_header(
        section_name="Cluster Distribution",
        source_label="SegmentationManifest seg_xxx",
        status="EMITTED",
        note="",
    )
    assert "Cluster Distribution" in h
    assert "SegmentationManifest seg_xxx" in h
    assert "EMITTED" in h


def test_format_dashboard_section_header_with_note() -> None:
    h = format_dashboard_section_header(
        section_name="Marketing",
        source_label="(no manifest)",
        status="EMITTED",
        note="availability=REVIEW_REQUIRED",
    )
    assert "REVIEW_REQUIRED" in h


# ---------------------------------------------------------------------------
# format_dashboard_summary
# ---------------------------------------------------------------------------


def test_format_dashboard_summary_basic() -> None:
    r = _make_result()
    s = format_dashboard_summary(r)
    assert "dashboard_id" in s
    assert "segmentation_id" in s
    assert "viz_" + "0" * 24 in s


def test_format_dashboard_summary_includes_chart_table() -> None:
    r = _make_result()
    s = format_dashboard_summary(r)
    assert "cluster_distribution" in s
    assert "EMITTED" in s
    assert "SKIPPED" in s
    assert "BLOCKED" in s


def test_format_dashboard_summary_includes_notes() -> None:
    r = _make_result()
    s = format_dashboard_summary(r)
    assert "Notes" in s
    assert "test note" in s


def test_format_dashboard_summary_disclaimer_appended() -> None:
    r = _make_result()
    s = format_dashboard_summary(r)
    assert "Disclaimer" in s
    assert DEFAULT_DISCLAIMER_TEXT in s


def test_format_dashboard_summary_no_banned_words() -> None:
    r = _make_result()
    s = format_dashboard_summary(r)
    assert _has_banned(s) == []


def test_format_dashboard_summary_custom_disclaimer() -> None:
    r = _make_result()
    s = format_dashboard_summary(r, disclaimer="custom")
    assert "custom" in s
    assert DEFAULT_DISCLAIMER_TEXT not in s


def test_format_dashboard_summary_raises_on_banned() -> None:
    """If the user-provided input somehow leaks a banned word, raise."""
    r = _make_result(notes=["This is the best segment"])
    with pytest.raises(VisualizationError, match="banned substrings"):
        format_dashboard_summary(r)


# ---------------------------------------------------------------------------
# format_dashboard_run_report
# ---------------------------------------------------------------------------


def test_format_dashboard_run_report_basic() -> None:
    r = _make_result()
    s = format_dashboard_run_report(r)
    assert r.dashboard_id in s
    assert "SUCCESS" in s


def test_format_dashboard_run_report_chart_markers() -> None:
    r = _make_result()
    s = format_dashboard_run_report(r)
    assert "[OK " in s  # EMITTED
    assert "[SKIP" in s or "[BLO" in s  # SKIPPED / BLOCKED


def test_format_dashboard_run_report_disclaimer() -> None:
    r = _make_result()
    s = format_dashboard_run_report(r)
    assert "Disclaimer" in s
    assert DEFAULT_DISCLAIMER_TEXT in s


def test_format_dashboard_run_report_no_banned() -> None:
    r = _make_result()
    s = format_dashboard_run_report(r)
    assert _has_banned(s) == []


# ---------------------------------------------------------------------------
# dashboard_result_to_dict / dashboard_result_to_json
# ---------------------------------------------------------------------------


def test_dashboard_result_to_dict_basic() -> None:
    r = _make_result()
    d = dashboard_result_to_dict(r)
    assert d["dashboard_id"] == r.dashboard_id
    assert "charts" in d
    assert isinstance(d["charts"], list)
    assert d["charts"][0]["name"] == "cluster_distribution"


def test_dashboard_result_to_json_round_trip() -> None:
    r = _make_result()
    j = dashboard_result_to_json(r)
    parsed = json.loads(j)
    assert parsed["dashboard_id"] == r.dashboard_id
    assert isinstance(parsed["charts"], list)


def test_dashboard_result_to_json_indent() -> None:
    r = _make_result()
    j = dashboard_result_to_json(r, indent=4)
    # Indented JSON contains \n at the top-level.
    assert "\n" in j


def test_now_utc_iso_format() -> None:
    s = now_utc_iso()
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", s)


# ---------------------------------------------------------------------------
# DashboardChartRecord
# ---------------------------------------------------------------------------


def test_chart_record_to_dict() -> None:
    c = DashboardChartRecord(name="x", output_path="/p", status="EMITTED", note="hello")
    d = c.to_dict()
    assert d["name"] == "x"
    assert d["status"] == "EMITTED"
    assert d["note"] == "hello"


# ---------------------------------------------------------------------------
# DashboardResult
# ---------------------------------------------------------------------------


def test_dashboard_result_to_dict_includes_charts() -> None:
    r = _make_result()
    d = r.to_dict()
    assert isinstance(d["charts"], list)
    assert all("name" in c for c in d["charts"])
