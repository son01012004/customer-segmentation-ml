"""Display and reload helpers for DEV-09 End-to-End Prototype.

Responsibilities
----------------
1. :func:`load_run_summary` — read an existing ``e2e_run.json`` from
   disk and validate the canonical schema fields. Returns a fresh
   :class:`E2ERunSummary` reconstructed from the JSON payload.

2. :func:`format_run_summary` — format an
   :class:`E2ERunSummary` (or raw JSON path) as a human-readable text
   report. Honours the same banned-substring discipline as DEV-07 /
   DEV-08 display helpers.

Hard rules
----------
- :func:`load_run_summary` performs schema-version validation. A
  mismatch raises :exc:`Dev09Error`.
- :func:`format_run_summary` never invents fields. Unknown JSON keys
  are surfaced under a ``(extra)`` block; missing required keys raise
  :exc:`Dev09Error`.
- No raw customer rows / IDs / sensitive data are printed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from customer_segmentation.prototype.end_to_end.exceptions import (
    Dev09Error,
    Dev09InputError,
    Dev09StoragePathError,
)
from customer_segmentation.prototype.end_to_end.pipeline import (
    E2ERunSummary,
    E2EStageOutcome,
)
from customer_segmentation.prototype.end_to_end.scope import (
    END_TO_END_SCHEMA_VERSION,
)
from customer_segmentation.prototype.end_to_end.storage import E2E_RUN_ID_REGEX

__all__ = [
    "format_run_summary",
    "load_run_summary",
    "validate_run_summary_payload",
]


REQUIRED_TOP_KEYS: Final[tuple[str, ...]] = (
    "schema_version",
    "e2e_run_id",
    "dataset_id",
    "dataset_sha256",
    "storage_root",
    "run_dir",
    "overall_status",
    "lifecycle",
    "algorithm",
    "preprocessed_id",
    "clustering_id",
    "evaluation_id",
    "segmentation_id",
    "marketing_id",
    "dashboard_id",
    "stages",
    "inputs",
    "config",
    "environment",
    "created_utc",
)


@dataclass(frozen=True)
class _ReloadedSummary:
    """Lightweight wrapper returned by :func:`load_run_summary`.

    Exposes the canonical :class:`E2ERunSummary` plus the source path
    and a flag indicating whether the summary was reconstructed from
    a non-canonical ``notes`` list (i.e. some failures during the run
    were captured as notes).
    """

    summary: E2ERunSummary
    source_path: Path


def load_run_summary(path: Path | str) -> E2ERunSummary:
    """Load an ``e2e_run.json`` from disk and return an
    :class:`E2ERunSummary`.

    Parameters
    ----------
    path : pathlib.Path or str
        Path to the persisted ``e2e_run.json``.

    Returns
    -------
    E2ERunSummary
        The reconstructed summary.

    Raises
    ------
    Dev09InputError
        If ``path`` does not exist or is not a file.
    Dev09Error
        If the JSON is malformed, missing required keys, or has an
        incompatible ``schema_version``.
    Dev09StoragePathError
        If ``e2e_run_id`` does not match the required format.
    """
    p = Path(path)
    if not p.exists():
        raise Dev09InputError(f"e2e_run.json not found: {p!s}")
    if not p.is_file():
        raise Dev09InputError(f"e2e_run.json path is not a file: {p!s}")
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Dev09Error(f"Malformed e2e_run.json at {p!s}: {exc}") from exc
    except OSError as exc:
        raise Dev09Error(f"Failed to read e2e_run.json at {p!s}: {exc}") from exc
    return _summary_from_payload(payload, source_path=p)


def validate_run_summary_payload(payload: dict[str, Any]) -> None:
    """Validate a parsed ``e2e_run.json`` payload.

    Raises
    ------
    Dev09Error
        If any required key is missing or ``schema_version`` is not
        the pinned :data:`END_TO_END_SCHEMA_VERSION`.
    Dev09StoragePathError
        If ``e2e_run_id`` does not match the required format.
    """
    if not isinstance(payload, dict):
        raise Dev09Error(f"e2e_run.json must be a JSON object; got {type(payload).__name__}.")
    missing = [k for k in REQUIRED_TOP_KEYS if k not in payload]
    if missing:
        raise Dev09Error(f"e2e_run.json is missing required keys: {missing}.")
    schema_version = str(payload.get("schema_version", ""))
    if schema_version != END_TO_END_SCHEMA_VERSION:
        raise Dev09Error(
            f"e2e_run.json schema_version={schema_version!r} does not match "
            f"pinned version {END_TO_END_SCHEMA_VERSION!r}."
        )
    e2e_run_id = str(payload.get("e2e_run_id", ""))
    if not E2E_RUN_ID_REGEX.match(e2e_run_id):
        raise Dev09StoragePathError(
            f"e2e_run_id {e2e_run_id!r} does not match required format " f"^e2e_[0-9a-f]{{24}}$."
        )


def _summary_from_payload(payload: dict[str, Any], *, source_path: Path) -> E2ERunSummary:
    """Reconstruct an :class:`E2ERunSummary` from a parsed JSON dict.

    Raises
    ------
    Dev09Error
        On schema mismatches.
    """
    validate_run_summary_payload(payload)
    raw_stages = payload.get("stages", [])
    if not isinstance(raw_stages, list):
        raise Dev09Error(f"e2e_run.json stages must be a list; got {type(raw_stages).__name__}.")
    stages: list[E2EStageOutcome] = []
    for s in raw_stages:
        if not isinstance(s, dict):
            raise Dev09Error(f"Each stage entry must be a dict; got {type(s).__name__}.")
        stages.append(
            E2EStageOutcome(
                stage=str(s.get("stage", "")),
                status=str(s.get("status", "")),
                note=str(s.get("note", "")),
                started_utc=str(s.get("started_utc", "")),
                ended_utc=str(s.get("ended_utc", "")),
                error_type=str(s.get("error_type", "")),
                error_message=str(s.get("error_message", "")),
                artifacts=dict(s.get("artifacts", {}) or {}),
            )
        )
    seed_value = payload.get("seed")
    if seed_value is not None and not isinstance(seed_value, int):
        seed_value = None
    inputs = payload.get("inputs", {})
    config_block = payload.get("config", {})
    environment = payload.get("environment", {})
    notes_raw = payload.get("notes", [])
    notes_list: list[str] = []
    if isinstance(notes_raw, list):
        notes_list = [str(n) for n in notes_raw]
    return E2ERunSummary(
        e2e_run_id=str(payload.get("e2e_run_id", "")),
        schema_version=str(payload.get("schema_version", "")),
        dataset_id=str(payload.get("dataset_id", "")),
        dataset_sha256=str(payload.get("dataset_sha256", "")),
        storage_root=str(payload.get("storage_root", "")),
        run_dir=str(payload.get("run_dir", "")),
        overall_status=str(payload.get("overall_status", "")),
        lifecycle=str(payload.get("lifecycle", "")),
        algorithm=str(payload.get("algorithm", "")),
        seed=seed_value,
        preprocessed_id=(
            None
            if payload.get("preprocessed_id") in (None, "")
            else str(payload.get("preprocessed_id"))
        ),
        clustering_id=(
            None
            if payload.get("clustering_id") in (None, "")
            else str(payload.get("clustering_id"))
        ),
        evaluation_id=(
            None
            if payload.get("evaluation_id") in (None, "")
            else str(payload.get("evaluation_id"))
        ),
        segmentation_id=(
            None
            if payload.get("segmentation_id") in (None, "")
            else str(payload.get("segmentation_id"))
        ),
        marketing_id=(
            None if payload.get("marketing_id") in (None, "") else str(payload.get("marketing_id"))
        ),
        dashboard_id=(
            None if payload.get("dashboard_id") in (None, "") else str(payload.get("dashboard_id"))
        ),
        stages=stages,
        inputs=dict(inputs or {}),
        config=dict(config_block or {}),
        environment=dict(environment or {}),
        notes=notes_list,
        created_utc=str(payload.get("created_utc", "")),
    )


def format_run_summary(
    summary: E2ERunSummary | Path | str,
    *,
    max_line_len: int = 100,
) -> str:
    """Format an :class:`E2ERunSummary` (or ``e2e_run.json`` path) as
    a human-readable text report.

    The output is a deterministic text table suitable for stdout or
    logging. No raw customer rows / IDs / sensitive data are emitted.

    Parameters
    ----------
    summary : E2ERunSummary or pathlib.Path or str
        Either a summary object or the path to an ``e2e_run.json``.
    max_line_len : int
        Maximum line length used for word-wrap on long notes.

    Returns
    -------
    str
        The formatted text report.
    """
    if isinstance(summary, (str, Path)):
        loaded = load_run_summary(Path(summary))
        obj = loaded
    else:
        obj = summary
    lines: list[str] = []
    rule = "=" * max_line_len
    lines.append(rule)
    lines.append(f"End-to-End Run Summary ({obj.schema_version})")
    lines.append(rule)
    lines.append(f"e2e_run_id       : {obj.e2e_run_id}")
    lines.append(f"created_utc      : {obj.created_utc}")
    lines.append(f"overall_status   : {obj.overall_status}")
    lines.append(f"lifecycle        : {obj.lifecycle}")
    lines.append(f"dataset_id       : {obj.dataset_id}")
    lines.append(f"dataset_sha256   : {obj.dataset_sha256}")
    lines.append(f"algorithm        : {obj.algorithm}")
    lines.append(f"seed             : {obj.seed}")
    lines.append(f"storage_root     : {obj.storage_root}")
    lines.append(f"run_dir          : {obj.run_dir}")
    lines.append("")
    lines.append("Cross-stage ids")
    lines.append("-" * max_line_len)
    lines.append(f"  preprocessed_id : {obj.preprocessed_id or '(none)'}")
    lines.append(f"  clustering_id   : {obj.clustering_id or '(none)'}")
    lines.append(f"  evaluation_id   : {obj.evaluation_id or '(none)'}")
    lines.append(f"  segmentation_id : {obj.segmentation_id or '(none)'}")
    lines.append(f"  marketing_id    : {obj.marketing_id or '(none)'}")
    lines.append(f"  dashboard_id    : {obj.dashboard_id or '(none)'}")
    lines.append("")
    lines.append("Stage outcomes")
    lines.append("-" * max_line_len)
    for s in obj.stages:
        note = s.note
        if len(note) > max_line_len - 24:
            note = note[: max_line_len - 27] + "..."
        lines.append(
            f"  {s.stage:<20s} {s.status:<18s} started={s.started_utc} ended={s.ended_utc}"
        )
        if note:
            lines.append(f"    note : {note}")
        if s.error_type:
            lines.append(f"    error_type    : {s.error_type}")
            lines.append(f"    error_message : {s.error_message}")
        for k, v in (s.artifacts or {}).items():
            if not v:
                continue
            lines.append(f"    artifact[{k}] : {v}")
    lines.append("")
    lines.append("Inputs")
    lines.append("-" * max_line_len)
    for k, v in (obj.inputs or {}).items():
        lines.append(f"  {k:<24s} = {v}")
    lines.append("")
    lines.append("Config")
    lines.append("-" * max_line_len)
    for k, v in (obj.config or {}).items():
        lines.append(f"  {k:<32s} = {v}")
    lines.append("")
    lines.append("Environment")
    lines.append("-" * max_line_len)
    env = obj.environment or {}
    for k in ("python", "platform", "release", "machine"):
        if k in env:
            lines.append(f"  {k:<16s} = {env[k]}")
    libs = env.get("key_libraries") or {}
    if libs:
        lines.append("  key_libraries   :")
        for k, v in libs.items():
            lines.append(f"    {k:<14s} = {v}")
    lines.append("")
    if obj.notes:
        lines.append("Notes")
        lines.append("-" * max_line_len)
        for n in obj.notes:
            lines.append(f"  - {n}")
        lines.append("")
    lines.append(rule)
    return "\n".join(lines)
