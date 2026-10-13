"""Per-stage logging configuration for DEV-03 Prototype Preprocessing.

DEV-03 emits one log file per ``preprocessed_id`` under
``data/prototype/<dataset_id>/preprocessed/<preprocessed_id>.log``.
Each stage (A→G) writes a structured log entry with timestamp,
level, stage name, and key metrics.

The module wraps the stdlib :mod:`logging` to:

- configure a project-scoped logger name ``"customer_segmentation.prototype.preprocessing"``
  (and a sub-logger for each Stage when run by
  :func:`customer_segmentation.prototype.preprocessing.pipeline.run_preprocessing_pipeline`);
- attach a per-preprocessed_id file handler in addition to a
  console handler (level controlled by the YAML config);
- expose a small :class:`PerStageLogger` façade so callers can
  emit `stage_X.start / .end / .failure` without thinking about
  handler management.

Hard rules
----------
- Log files MUST live under
  ``<storage_root>/<dataset_id>/preprocessed/`` (the only writable
  container for DEV-03). See :func:`configure_logging`.
- The project root logger name is reserved: do not propagate to the
  root logger.
- Failures MUST emit ERROR log; log file is preserved on failure
  (handlers are flushed + closed in :func:`finalize_logging`).
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

from customer_segmentation.prototype.preprocessing.config_loader import (
    PreprocessingLoggingConfig,
)

__all__ = [
    "DEV03_LOG_FORMAT",
    "DEFAULT_LOG_DIR_RELATIVE",
    "DEV03_LOGGER_NAME",
    "PerStageLogger",
    "PerStageLogHandler",
    "configure_logging",
    "finalize_logging",
    "now_iso",
]


DEV03_LOGGER_NAME: str = "customer_segmentation.prototype.preprocessing"
DEV03_LOG_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(stage)s | %(message)s"
DEFAULT_LOG_DIR_RELATIVE: str = "data/prototype/datasets"


def now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string with 'Z' suffix."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class PerStageLogHandler:
    """Track a file-handler attached to one preprocessed run.

    Attributes
    ----------
    logger : logging.Logger
        The logger that owns the file handler.
    handler : logging.FileHandler
        The file handler.
    path : pathlib.Path
        Path to the log file.
    """

    logger: logging.Logger
    handler: logging.FileHandler
    path: Path


class PerStageLogger:
    """Small façade for emitting per-stage log entries.

    Usage::

        logger = PerStageLogger(pipeline_logger)
        logger.stage_start("A", rows_in=0)
        ...
        logger.stage_end("A", rows_out=123)
        ...
        logger.failure("C", exc=ValueError("bad row"))

    Each entry carries the ``stage`` key so the file log always
    records which stage produced it.
    """

    _STAGE_KEY = "stage"

    def __init__(self, logger: logging.Logger | PerStageLogHandler) -> None:
        if isinstance(logger, PerStageLogHandler):
            self._logger = logger.logger
        else:
            self._logger = logger

    def _log(self, level: int, stage: str, message: str, **fields: Any) -> None:
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


def _ensure_logger(logger_name: str) -> logging.Logger:
    """Return a project-scoped logger, creating it with no handlers if
    missing. Detaches any inherited handlers from the root logger.
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)  # base; handlers enforce effective level
    logger.propagate = False
    # Drop pre-existing handlers we own (project handlers), to keep
    # the configuration deterministic.
    for h in list(logger.handlers):
        if getattr(h, "_dev03_owned", False):
            logger.removeHandler(h)
            with contextlib.suppress(Exception):
                h.close()
    return logger


def configure_logging(
    *,
    config: PreprocessingLoggingConfig,
    log_path: Path,
    logger_name: str = DEV03_LOGGER_NAME,
) -> PerStageLogHandler:
    """Attach a file + (optional) console handler to the project logger.

    Returns a :class:`PerStageLogHandler` that callers can pass to
    :class:`PerStageLogger`. Call :func:`finalize_logging` at the end
    of the run to flush + close the file handler.
    """
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    base_logger = _ensure_logger(logger_name)

    level = getattr(logging, config.level.upper(), logging.INFO)

    file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(config.format))
    file_handler._dev03_owned = True  # type: ignore[attr-defined]
    base_logger.addHandler(file_handler)

    if config.emit_to_console:
        console_handler = logging.StreamHandler(stream=sys.stderr)
        console_handler.setLevel(level)
        console_handler.setFormatter(logging.Formatter(config.format))
        console_handler._dev03_owned = True  # type: ignore[attr-defined]
        base_logger.addHandler(console_handler)

    return PerStageLogHandler(logger=base_logger, handler=file_handler, path=log_path)


def finalize_logging(handle: PerStageLogHandler) -> None:
    """Flush + close the file handler, detach it, and stop propagation.

    Idempotent: calling on an already-closed handle is a no-op.
    """
    with contextlib.suppress(Exception):
        handle.handler.flush()
    with contextlib.suppress(Exception):
        handle.handler.close()
    if handle.handler in handle.logger.handlers:
        handle.logger.removeHandler(handle.handler)


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
