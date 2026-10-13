"""Per-stage logging façade for DEV-08 Prototype Visualization.

Mirrors the :class:`PerStageLogger` pattern from
:mod:`customer_segmentation.prototype.marketing.logging_config` and
:mod:`customer_segmentation.prototype.segmentation.logging_config`.

The logger name is ``customer_segmentation.prototype.visualization``.

Hard rules
----------
- No sensitive data in log messages. The dashboard never logs raw
  customer data, manifest contents, or PII.
- Log handlers are reset on every ``configure_logging`` call (idempotent).
- The logger does not propagate to ancestor loggers (``propagate=False``)
  to keep prototype-layer logging scoped to the visualization module.
- The stage field appears in the log formatter. The stage is a free-form
  identifier (typically ``A`` → ``F`` for the dashboard pipeline).
"""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path
from typing import Any, Final

__all__ = [
    "DEV08_LOGGER_NAME",
    "PerStageLogger",
    "configure_logging",
    "finalize_logging",
    "get_logger",
]


DEV08_LOGGER_NAME: Final[str] = "customer_segmentation.prototype.visualization"

_DEFAULT_FORMAT: Final[str] = "%(asctime)s | %(levelname)-8s | %(name)s | %(stage)s | %(message)s"


class _StageFilter(logging.Filter):
    """Inject a default ``stage`` attribute (used by the formatter)."""

    DEFAULT_STAGE = "general"

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "stage"):
            record.stage = self.DEFAULT_STAGE
        return True


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a logger under :data:`DEV08_LOGGER_NAME`.

    Parameters
    ----------
    name : str or None
        If None, returns the package root logger. Otherwise, returns a
        child logger under the DEV-08 namespace if ``name`` starts with
        :data:`DEV08_LOGGER_NAME`, or a child of the package root otherwise.
    """
    if name is None:
        return logging.getLogger(DEV08_LOGGER_NAME)
    if name == DEV08_LOGGER_NAME or name.startswith(DEV08_LOGGER_NAME + "."):
        return logging.getLogger(name)
    return logging.getLogger(DEV08_LOGGER_NAME).getChild(name)


def configure_logging(
    *,
    level: str = "INFO",
    fmt: str = _DEFAULT_FORMAT,
    log_file: Path | None = None,
    emit_to_console: bool = True,
) -> logging.Logger:
    """Configure the DEV-08 logger and return it.

    Idempotent: calling twice resets handlers to a single file handler
    (if provided) and a single console handler (if enabled).

    Parameters
    ----------
    level : str
        Log level (DEBUG / INFO / WARNING / ERROR / CRITICAL).
    fmt : str
        Log format string. Must reference ``%(stage)s`` (added by the
        :class:`_StageFilter`).
    log_file : pathlib.Path or None
        If provided, log records are also written to this file (parent
        directories are created).
    emit_to_console : bool
        If True, a console handler is added.

    Returns
    -------
    logging.Logger
        The DEV-08 root logger.
    """
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
    """Per-stage logger that stamps a ``stage`` field on every record.

    The stage name appears in the log formatter (e.g. ``A``, ``B``,
    ... ``F`` for DEV-08 stages).
    """

    def __init__(
        self,
        logger: logging.Logger,
        stage: str = "general",
    ) -> None:
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
    """Close all handlers and reset the logger state. Idempotent.

    Parameters
    ----------
    logger : logging.Logger or None
        Logger to finalize. If None, uses the DEV-08 root logger.
    """
    if logger is None:
        logger = get_logger()
    for h in list(logger.handlers):
        with contextlib.suppress(Exception):
            h.flush()
        with contextlib.suppress(Exception):
            h.close()
        logger.removeHandler(h)
