"""Per-stage logging configuration for DEV-04 Prototype Clustering.

DEV-04 emits one log file per ``clustering_id`` under
``<clustering_base_dir>/<clustering_id>.log``.
Each stage (0→6) writes a structured log entry with timestamp,
level, stage name, and key metrics.

The module wraps the stdlib :mod:`logging` to:

- configure a project-scoped logger name
  ``"customer_segmentation.prototype.clustering"``
  (and a sub-logger for each Stage when run by
  :func:`customer_segmentation.prototype.clustering.pipeline.run_clustering_pipeline`);
- attach a per-clustering_id file handler in addition to a
  console handler (level controlled by the YAML config);
- expose a small :class:`PerStageLogger` façade so callers can
  emit ``stage_X.start / .end / .failure`` without handler management.

Hard rules
----------
- Log files MUST live under
  ``<clustering_base_dir>/`` (the per-preprocessed-id container).
  See :func:`configure_logging`.
- The project root logger name is reserved: do not propagate to the
  root logger.
- Failures MUST emit ERROR log; log file is preserved on failure
  (handlers are flushed + closed in :func:`finalize_logging`).
- ``%(stage)s`` is a custom LogRecord attribute added by
  :class:`_StageAdapter`.
"""

from __future__ import annotations

import contextlib
import logging
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from customer_segmentation.prototype.clustering.config_loader import (
    Dev04LoggingConfig,
)

__all__ = [
    "DEV04_LOGGER_NAME",
    "DEV04_LOG_FORMAT",
    "PerStageLogHandler",
    "PerStageLogger",
    "configure_logging",
    "finalize_logging",
    "now_iso",
]


DEV04_LOGGER_NAME: str = "customer_segmentation.prototype.clustering"
DEV04_LOG_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(stage)s | %(message)s"


# ---------------------------------------------------------------------------
# Custom stage adapter (adds %(stage)s to every LogRecord)
# ---------------------------------------------------------------------------


class _StageAdapter(logging.LoggerAdapter):
    """Inject ``stage`` key into every LogRecord extra dict."""

    def process(self, msg: str, kwargs: Any) -> tuple[str, Any]:
        extra = kwargs.get("extra", {})
        if not isinstance(extra, dict):
            extra = {}
        # Always stamp the current stage
        extra["stage"] = getattr(self, "_current_stage", "")
        kwargs["extra"] = extra
        return msg, kwargs


# ---------------------------------------------------------------------------
# Time helper
# ---------------------------------------------------------------------------


def now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string with 'Z' suffix."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Handler tracking
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PerStageLogHandler:
    """Track a file handler attached to one clustering run.

    Attributes
    ----------
    logger : _StageAdapter
        The adapter logger that owns the file handler.
    handler : logging.FileHandler
        The file handler (for close/flush in finalize_logging).
    path : pathlib.Path
        Path to the log file.
    """

    logger: _StageAdapter
    handler: logging.FileHandler
    path: Path


# ---------------------------------------------------------------------------
# PerStageLogger façade
# ---------------------------------------------------------------------------


class PerStageLogger:
    """Small façade for emitting per-stage log entries.

    Usage::

        logger = PerStageLogger(pipeline_logger)
        logger.stage_start("1", clustering_id="cl_abc123")
        ...
        logger.stage_end("1", preprocessed_id="pp_xyz", ml_dataset_sha256="...")
        ...
        logger.failure("4", exc=RuntimeError("fit failed"))

    Each entry carries the ``stage`` key so the file log always
    records which pipeline stage produced it.
    """

    _STAGE_KEY = "stage"

    def __init__(self, logger: _StageAdapter | PerStageLogHandler) -> None:
        if isinstance(logger, PerStageLogHandler):
            self._logger: logging.LoggerAdapter = logger.logger
        else:
            self._logger = logger

    def _set_stage(self, stage: str) -> None:
        """Update the adapter's current stage for the next log entry."""
        if hasattr(self._logger, "_current_stage"):
            self._logger._current_stage = stage  # type: ignore[attr-defined]

    def _log(self, level: int, stage: str, message: str, **fields: Any) -> None:
        self._set_stage(stage)
        extra: dict[str, Any] = {self._STAGE_KEY: stage}
        for k, v in fields.items():
            extra[k] = v
        self._logger.log(level, message, extra=extra)

    def stage_start(self, stage: str, **fields: Any) -> None:
        self._log(logging.INFO, stage, f"stage_{stage}.start", **fields)

    def stage_end(self, stage: str, **fields: Any) -> None:
        self._log(logging.INFO, stage, f"stage_{stage}.end", **fields)

    def stage_warning(self, stage: str, message: str, **fields: Any) -> None:
        self._log(logging.WARNING, stage, message, **fields)

    def failure(self, stage: str, exc: BaseException, **fields: Any) -> None:
        self._log(
            logging.ERROR,
            stage,
            f"stage_{stage}.failure: {type(exc).__name__}: {exc}",
            **fields,
        )

    def info(self, stage: str, message: str, **fields: Any) -> None:
        self._log(logging.INFO, stage, message, **fields)


# ---------------------------------------------------------------------------
# Logger management
# ---------------------------------------------------------------------------


def _ensure_logger(logger_name: str) -> _StageAdapter:
    """Return a project-scoped _StageAdapter, creating it with no handlers if
    missing. Detaches any inherited handlers from the root logger.
    """
    base = logging.getLogger(logger_name)
    base.setLevel(logging.DEBUG)
    base.propagate = False
    # Drop pre-existing DEV-04-owned handlers to keep config deterministic.
    for h in list(base.handlers):
        if getattr(h, "_dev04_owned", False):
            base.removeHandler(h)
            with contextlib.suppress(Exception):
                h.close()
    adapter = _StageAdapter(base, {})
    adapter._current_stage = ""  # type: ignore[attr-defined]
    return adapter


def configure_logging(
    *,
    config: Dev04LoggingConfig,
    log_path: Path,
    logger_name: str = DEV04_LOGGER_NAME,
) -> PerStageLogHandler:
    """Attach a file + (optional) console handler to the DEV-04 logger.

    Returns a :class:`PerStageLogHandler` that callers pass to
    :class:`PerStageLogger`. Call :func:`finalize_logging` at the
    end of the run to flush + close the file handler.
    """
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    adapter = _ensure_logger(logger_name)
    base = adapter.logger  # type: ignore[union-attr]

    level = getattr(logging, config.level.upper(), logging.INFO)
    formatter = logging.Formatter(config.format)

    file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    file_handler._dev04_owned = True  # type: ignore[attr-defined]
    base.addHandler(file_handler)

    if config.emit_to_console:
        console_handler = logging.StreamHandler(stream=sys.stderr)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        console_handler._dev04_owned = True  # type: ignore[attr-defined]
        base.addHandler(console_handler)

    return PerStageLogHandler(logger=adapter, handler=file_handler, path=log_path)


def finalize_logging(handle: PerStageLogHandler) -> None:
    """Flush + close the file handler, detach it.

    Idempotent: no-op on already-closed handles.
    """
    with contextlib.suppress(Exception):
        handle.handler.flush()
    with contextlib.suppress(Exception):
        handle.handler.close()
    if handle.handler in handle.logger.logger.handlers:  # type: ignore[union-attr]
        handle.logger.logger.removeHandler(handle.handler)  # type: ignore[union-attr]


def emit_environment_block(
    logger: PerStageLogger,
    *,
    platform_info: Mapping[str, str] | None = None,
) -> None:
    """Emit a single INFO log describing the runtime environment."""
    import platform as _platform

    info = dict(platform_info) if platform_info else {}
    if "python" not in info:
        info["python"] = _platform.python_version()
    if "system" not in info:
        info["system"] = _platform.system()
    if "release" not in info:
        info["release"] = _platform.release()
    if "machine" not in info:
        info["machine"] = _platform.machine()
    logger.info("ENV", "runtime environment", **info)


__ = (Mapping,)
