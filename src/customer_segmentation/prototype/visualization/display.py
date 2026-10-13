"""Display helpers for DEV-08 Prototype Visualization Dashboard.

Provides printable text and JSON output for the dashboard:

- :func:`format_dashboard_summary` — manifest-level summary
  (which charts were emitted, which manifests were consumed, lifecycle).
- :func:`format_dashboard_section_header` — single section header
  for a chart in the text report.
- :func:`format_dashboard_run_report` — concise per-dashboard run report
  for CLI output.
- :func:`dashboard_result_to_json` — JSON-serialisable representation
  of a :class:`DashboardResult`.
- :func:`check_no_banned_substrings` — defensive scan that mirrors the
  pattern established in
  :mod:`customer_segmentation.prototype.marketing.display`.

Hard rules
----------
- The mandatory disclaimer phrase is the single allowed occurrence of
  any banned substrings in dashboard text output (per AGENTS.md §2.5).
- The JSON output is for tooling consumption (no pretty-printed text).
- No internal clustering metric names appear anywhere (the metric
  comparison chart embeds them — but that is data, not text).
- All functions are pure: no manifest mutation, no filesystem side
  effects, no logging.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from customer_segmentation.prototype.visualization.exceptions import (
    VisualizationError,
)
from customer_segmentation.prototype.visualization.scope import (
    BANNED_SUBSTRINGS,
    DEFAULT_DISCLAIMER_TEXT,
)

__all__ = [
    "DEFAULT_DISCLAIMER_TEXT",
    "BANNED_SUBSTRINGS",
    "BANNED_SUBSTRINGS_OUTSIDE_DISCLAIMER",
    "check_no_banned_substrings",
    "DashboardResult",
    "DashboardChartRecord",
    "format_dashboard_section_header",
    "format_dashboard_summary",
    "format_dashboard_run_report",
    "dashboard_result_to_dict",
    "dashboard_result_to_json",
    "now_utc_iso",
]


DEFAULT_DISCLAIMER_TEXT: Final[str] = DEFAULT_DISCLAIMER_TEXT

# Mirror the visualization BANNED_SUBSTRINGS list. The dashboard text
# output is scanned with the same list.
BANNED_SUBSTRINGS: Final[tuple[str, ...]] = BANNED_SUBSTRINGS

BANNED_SUBSTRINGS_OUTSIDE_DISCLAIMER: Final[tuple[str, ...]] = BANNED_SUBSTRINGS


# ---------------------------------------------------------------------------
# Time helper
# ---------------------------------------------------------------------------


def now_utc_iso() -> str:
    """Return current UTC time as ISO-8601 string (suffix ``Z``)."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DashboardChartRecord:
    """One chart emitted by the dashboard."""

    name: str
    output_path: str
    status: str  # "EMITTED" | "SKIPPED" | "BLOCKED" | "ERROR"
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "output_path": self.output_path,
            "status": self.status,
            "note": self.note,
        }


@dataclass(frozen=True)
class DashboardResult:
    """Outcome of one dashboard generation run."""

    dashboard_id: str
    segmentation_id: str
    clustering_id: str
    preprocessed_id: str
    dataset_id: str
    run_dir: str
    lifecycle: str
    validation_passed: bool
    charts: list[DashboardChartRecord]
    input_segmentation_manifest_path: str | None
    input_evaluation_manifest_paths: list[str] = field(default_factory=list)
    input_marketing_manifest_path: str | None = None
    notes: list[str] = field(default_factory=list)
    created_utc: str = field(default_factory=now_utc_iso)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Convert list of dataclasses to list of dicts.
        d["charts"] = [c if isinstance(c, dict) else c.to_dict() for c in self.charts]
        return d


# ---------------------------------------------------------------------------
# Banned-substring scan
# ---------------------------------------------------------------------------


def _strip_disclaimer(text: str, disclaimer: str) -> str:
    """Remove all occurrences of ``disclaimer`` from ``text`` (case-insensitive)."""
    if not disclaimer:
        return text
    out = text
    lower = out.lower()
    dl_lower = disclaimer.lower()
    while dl_lower in lower:
        idx = lower.index(dl_lower)
        out = out[:idx] + out[idx + len(dl_lower) :]
        lower = out.lower()
    return out


def check_no_banned_substrings(
    text: str,
    *,
    disclaimer: str = DEFAULT_DISCLAIMER_TEXT,
) -> list[str]:
    """Return the list of banned substrings present in ``text``.

    The disclaimer phrase is excluded from the check. Any other
    occurrence of a banned word (case-insensitive, word-boundary) is
    reported.

    This is a defensive scan; the chart modules already enforce this
    rule on their own outputs. The dashboard text layer enforces it
    again on the assembled text.
    """
    found: list[str] = []
    check_text = _strip_disclaimer(text, disclaimer)
    for banned in BANNED_SUBSTRINGS:
        pattern = r"\b" + re.escape(banned).replace("\\-", r"[-\s]") + r"\b"
        if re.search(pattern, check_text, flags=re.IGNORECASE):
            found.append(banned)
    return found


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def _row(*cells: str) -> str:
    return "  ".join(cells)


def format_dashboard_section_header(
    *,
    section_name: str,
    source_label: str,
    status: str,
    note: str = "",
    separator: str = "=",
) -> str:
    """Return a printable header for one dashboard section."""
    lines: list[str] = []
    lines.append(separator * 78)
    lines.append(f"# {section_name}")
    lines.append(f"# source : {source_label}")
    lines.append(f"# status : {status}")
    if note:
        lines.append(f"# note   : {note}")
    lines.append(separator * 78)
    return "\n".join(lines)


def format_dashboard_summary(
    result: DashboardResult,
    *,
    disclaimer: str = DEFAULT_DISCLAIMER_TEXT,
    separator: str = "  ",
) -> str:
    """Format a manifest-level dashboard summary.

    The summary enumerates inputs (segmentation_id, evaluation runs,
    marketing availability), output lifecycle, charts emitted, and
    run dir. No banned substrings appear outside the disclaimer.
    """
    lines: list[str] = []
    lines.append(_row("field", "value"))
    lines.append(_row("-" * 24, "-" * 64))
    lines.append(_row("dashboard_id", result.dashboard_id))
    lines.append(_row("segmentation_id", result.segmentation_id))
    lines.append(_row("clustering_id", result.clustering_id))
    lines.append(_row("preprocessed_id", result.preprocessed_id))
    lines.append(_row("dataset_id", result.dataset_id))
    lines.append(_row("lifecycle", result.lifecycle))
    lines.append(_row("validation_passed", str(result.validation_passed)))
    lines.append(_row("run_dir", result.run_dir))
    lines.append(
        _row(
            "input_segmentation_manifest",
            str(result.input_segmentation_manifest_path or "(none)"),
        )
    )
    n_evals = len(result.input_evaluation_manifest_paths)
    lines.append(_row("n_evaluation_manifests", str(n_evals)))
    for i, p in enumerate(result.input_evaluation_manifest_paths):
        lines.append(_row(f"  evaluation_manifest[{i}]", p))
    lines.append(
        _row(
            "input_marketing_manifest",
            str(result.input_marketing_manifest_path or "(none)"),
        )
    )
    lines.append(_row("created_utc", result.created_utc))

    if result.charts:
        lines.append("")
        lines.append(_row("chart_name", "status", "output_path"))
        lines.append(_row("-" * 24, "-" * 12, "-" * 64))
        for c in result.charts:
            lines.append(_row(c.name, c.status, c.output_path))

    if result.notes:
        lines.append("")
        lines.append("# Notes:")
        for n in result.notes:
            lines.append(f"#   - {n}")

    lines.append("")
    lines.append(f"Disclaimer: {disclaimer}")
    text = "\n".join(lines)
    bad = check_no_banned_substrings(text, disclaimer=disclaimer)
    if bad:
        raise VisualizationError(
            f"DEV-08 dashboard summary contains banned substrings: {bad}. "
            f"This is a programming error; check display code for "
            f"forbidden-term leakage."
        )
    return text


def format_dashboard_run_report(
    result: DashboardResult,
    *,
    disclaimer: str = DEFAULT_DISCLAIMER_TEXT,
) -> str:
    """Return a concise one-block per-dashboard run report for CLI output.

    This is the "compact" view: chart names + statuses only, suitable
    for tail-style log inspection.
    """
    lines: list[str] = []
    lines.append(f"dashboard_id={result.dashboard_id}")
    lines.append(f"  segmentation_id  : {result.segmentation_id}")
    lines.append(f"  lifecycle        : {result.lifecycle}")
    lines.append(f"  validation_passed: {result.validation_passed}")
    lines.append(f"  run_dir          : {result.run_dir}")
    lines.append(f"  n_charts         : {len(result.charts)}")
    for c in result.charts:
        marker = "OK " if c.status == "EMITTED" else c.status[:4].rjust(4)
        note_part = f"  ({c.note})" if c.note else ""
        lines.append(f"    [{marker}] {c.name:<30s} {c.output_path}{note_part}")
    lines.append(f"Disclaimer: {disclaimer}")
    text = "\n".join(lines)
    bad = check_no_banned_substrings(text, disclaimer=disclaimer)
    if bad:
        raise VisualizationError(f"DEV-08 dashboard run report contains banned substrings: {bad}.")
    return text


# ---------------------------------------------------------------------------
# JSON serialization
# ---------------------------------------------------------------------------


def dashboard_result_to_dict(result: DashboardResult) -> dict[str, Any]:
    """Convert a :class:`DashboardResult` to a JSON-serialisable dict."""
    return result.to_dict()


def dashboard_result_to_json(
    result: DashboardResult,
    *,
    indent: int = 2,
) -> str:
    """Return a JSON-serialised string representation of the dashboard result.

    The output is suitable for tooling consumption: ``indent`` defaults
    to 2 for readability; the field set is identical to
    :func:`dashboard_result_to_dict`.
    """
    payload = dashboard_result_to_dict(result)
    try:
        return json.dumps(payload, indent=indent, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise VisualizationError(f"Failed to serialise DashboardResult to JSON: {exc}") from exc


# ---------------------------------------------------------------------------
# Path-to-string helper for the result records
# ---------------------------------------------------------------------------


def _path_str(p: Path | str | None) -> str:
    """Return the canonical string form of a Path (or empty for None)."""
    if p is None:
        return ""
    return str(p)
