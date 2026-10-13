"""Per-stage logging façade for DEV-09 End-to-End Prototype.

Mirrors the :class:`PerStageLogger` pattern from the visualization
package and DEV-04..07.

Hard rules
----------
- The logger does not propagate to ancestor loggers (``propagate=False``).
- Log handlers are reset on every ``configure_logging`` call (idempotent).
- No sensitive data (raw customer IDs, raw customer rows) is logged.
"""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path
from typing import Any, Final

__all__ = [
    "DEV09_LOGGER_NAME",
    "PerStageLogger",
    "configure_logging",
    "finalize_logging",
    "get_logger",
]


DEV09_LOGGER_NAME: Final[str] = "customer_segmentation.prototype.end_to_end"

_DEFAULT_FORMAT: Final[str] = "%(asctime)s | %(levelname)-8s | %(name)s | %(stage)s | %(message)s"


class _StageFilter(logging.Filter):
    """Inject a default ``stage`` attribute (used by the formatter)."""

    DEFAULT_STAGE = "general"

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "stage"):
            record.stage = self.DEFAULT_STAGE
        return True


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a logger under :data:`DEV09_LOGGER_NAME`."""
    if name is None:
        return logging.getLogger(DEV09_LOGGER_NAME)
    if name == DEV09_LOGGER_NAME or name.startswith(DEV09_LOGGER_NAME + "."):
        return logging.getLogger(name)
    return logging.getLogger(DEV09_LOGGER_NAME).getChild(name)


def configure_logging(
    *,
    level: str = "INFO",
    fmt: str = _DEFAULT_FORMAT,
    log_file: Path | None = None,
    emit_to_console: bool = True,
) -> logging.Logger:
    """Configure the DEV-09 logger; idempotent."""
    logger = get_logger()
    logger.setLevel(level.upper())
    for h in list(logger.handlers):
        logger.removeHandler(h)
    formatter = logging.Formatter(fmt)
    stage_filter = _StageFilter()
    if log_file is not None:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, mode="w", encoding="utf-8")
        fh.setFormatter(formatter)
        fh.addFilter(stage_filter)
        logger.addHandler(fh)
    if emit_to_console:
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        ch.addFilter(stage_filter)
        logger.addHandler(ch)
    logger.propagate = False
    return logger


class PerStageLogger:
    """Per-stage logger that stamps a ``stage`` field on every record."""

    def __init__(self, logger: logging.Logger, stage: str = "general") -> None:
        self._logger = logger
        self._stage = stage

    @property
    def stage(self) -> str:
        return self._stage

    def stage_start(self, new_stage: str) -> None:
        self._logger.info(f"Stage {new_stage} start", extra={"stage": new_stage})
        self._stage = new_stage

    def stage_end(self, outcome: str = "PASS") -> None:
        self._logger.info(
            f"Stage {self._stage} end ({outcome})",
            extra={"stage": self._stage},
        )

    def info(self, message: str, *args: Any, **kwargs: Any) -> None:
        self._logger.info(message, *args, extra={"stage": self._stage}, **kwargs)

    def warning(self, message: str, *args: Any, **kwargs: Any) -> None:
        self._logger.warning(message, *args, extra={"stage": self._stage}, **kwargs)

    def error(self, message: str, *args: Any, **kwargs: Any) -> None:
        self._logger.error(message, *args, extra={"stage": self._stage}, **kwargs)

    def debug(self, message: str, *args: Any, **kwargs: Any) -> None:
        self._logger.debug(message, *args, extra={"stage": self._stage}, **kwargs)


def finalize_logging(logger: logging.Logger | None = None) -> None:
    """Close all handlers and reset the logger state (idempotent)."""
    if logger is None:
        logger = get_logger()
    for h in list(logger.handlers):
        with contextlib.suppress(Exception):
            h.flush()
        with contextlib.suppress(Exception):
            h.close()
        logger.removeHandler(h)
