"""Experiment logging helpers for ML-01.

Two responsibilities:

1. **Console / file logging** with a consistent prefix so ML-01 lines
   are easy to grep out of a CI log.
2. **Experiment log writer** that turns an :class:`ExperimentResult`
   into a JSON file on disk.

The experiment log is the canonical artifact that EPIC-07/08 will read
back. ML-01 only **writes** it; ML-01 never **computes** metrics or
declares winners.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from customer_segmentation.clustering.result import ExperimentResult

__all__ = [
    "get_logger",
    "setup_file_logging",
    "now_utc_iso",
    "write_experiment_log",
]


ML01_LOG_PREFIX = "[ML-01]"


def now_utc_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(UTC).isoformat()


def get_logger(name: str = "customer_segmentation.clustering") -> logging.Logger:
    """Return a module-level logger with consistent formatting.

    The returned logger uses :data:`ML01_LOG_PREFIX` so lines are
    greppable. Callers can attach additional handlers via
    :func:`setup_file_logging`.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(stream=sys.stderr)
        handler.setFormatter(
            logging.Formatter(
                fmt=f"{ML01_LOG_PREFIX} %(asctime)s [%(levelname)s] %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S%z",
            )
        )
        handler.setLevel(logging.INFO)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def setup_file_logging(
    log_dir: Path,
    *,
    logger: logging.Logger | None = None,
    filename: str = "ml01.log",
    level: int = logging.INFO,
) -> Path:
    """Attach a file handler to the ML-01 logger.

    Parameters
    ----------
    log_dir : pathlib.Path
        Directory to write the log file into (created if missing).
    logger : logging.Logger, optional
        Logger to attach to. Defaults to the ML-01 logger.
    filename : str
        Log file name.
    level : int
        Logging level.

    Returns
    -------
    pathlib.Path
        Path to the log file.
    """
    if logger is None:
        logger = get_logger()
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / filename
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter(
            fmt=f"{ML01_LOG_PREFIX} %(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    handler.setLevel(level)
    logger.addHandler(handler)
    logger.setLevel(level)
    return path


def write_experiment_log(
    result: ExperimentResult,
    output_path: Path,
) -> Path:
    """Write the experiment log JSON to disk.

    Parameters
    ----------
    result : ExperimentResult
        Experiment result to serialise.
    output_path : pathlib.Path
        Destination file path (parent directories are created).

    Returns
    -------
    pathlib.Path
        Path the log was written to.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = result.to_dict()
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=False, default=str)
    return output_path
