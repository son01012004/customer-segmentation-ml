"""Tests for DEV-08 logging_config."""

from __future__ import annotations

import logging
from pathlib import Path

from customer_segmentation.prototype.visualization.logging_config import (
    DEV08_LOGGER_NAME,
    PerStageLogger,
    configure_logging,
    finalize_logging,
    get_logger,
)


def test_get_logger_returns_package_logger() -> None:
    logger = get_logger()
    assert logger.name == DEV08_LOGGER_NAME


def test_get_logger_child_under_dev08() -> None:
    logger = get_logger(DEV08_LOGGER_NAME + ".sub")
    assert logger.name == DEV08_LOGGER_NAME + ".sub"


def test_get_logger_other_name_attaches_under_dev08() -> None:
    logger = get_logger("custom")
    assert logger.name == DEV08_LOGGER_NAME + ".custom"


def test_configure_logging_idempotent() -> None:
    logger = configure_logging(level="INFO")
    n_initial = len(logger.handlers)
    logger = configure_logging(level="INFO")
    assert len(logger.handlers) == n_initial


def test_configure_logging_level_set() -> None:
    logger = configure_logging(level="DEBUG")
    assert logger.level == logging.DEBUG


def test_configure_logging_console_handler() -> None:
    logger = configure_logging(level="INFO", emit_to_console=True)
    has_stream = any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        for h in logger.handlers
    )
    assert has_stream


def test_configure_logging_file_handler(tmp_path: Path) -> None:
    log_file = tmp_path / "dev08.log"
    logger = configure_logging(level="INFO", log_file=log_file, emit_to_console=False)
    assert log_file.exists()
    assert any(isinstance(h, logging.FileHandler) for h in logger.handlers)
    finalize_logging(logger)


def test_per_stage_logger_basic() -> None:
    logger = configure_logging(level="INFO", emit_to_console=False)
    psl = PerStageLogger(logger, stage="A")
    psl.stage_start("B")
    psl.info("test message")
    psl.stage_end("PASS")
    assert psl.stage == "B"
    finalize_logging(logger)


def test_per_stage_logger_stage_property() -> None:
    logger = configure_logging(level="INFO", emit_to_console=False)
    psl = PerStageLogger(logger)
    assert psl.stage == "general"
    psl.stage_start("B")
    assert psl.stage == "B"
    finalize_logging(logger)


def test_finalize_logging_removes_handlers() -> None:
    logger = configure_logging(level="INFO", emit_to_console=True)
    assert len(logger.handlers) >= 1
    finalize_logging(logger)
    assert len(logger.handlers) == 0


def test_finalize_logging_idempotent() -> None:
    logger = configure_logging(level="INFO", emit_to_console=False)
    finalize_logging(logger)
    # Second call should not raise.
    finalize_logging(logger)


def test_propagate_is_false() -> None:
    logger = configure_logging(level="INFO", emit_to_console=False)
    assert logger.propagate is False
    finalize_logging(logger)


def test_stage_filter_injects_default() -> None:
    """A log record without 'stage' gets DEFAULT_STAGE injected by the filter."""
    from customer_segmentation.prototype.visualization.logging_config import _StageFilter

    rec = logging.LogRecord(
        name="x", level=logging.INFO, pathname="x", lineno=1, msg="hi", args=(), exc_info=None
    )
    f = _StageFilter()
    f.filter(rec)
    assert rec.stage == _StageFilter.DEFAULT_STAGE
