"""Tests for DEV-09 logging helpers (logging_config.py)."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import pytest

from customer_segmentation.prototype.end_to_end.logging_config import (
    DEV09_LOGGER_NAME,
    PerStageLogger,
    configure_logging,
    finalize_logging,
    get_logger,
)


def test_logger_name_is_string() -> None:
    assert isinstance(DEV09_LOGGER_NAME, str)
    assert DEV09_LOGGER_NAME.startswith("customer_segmentation")


def test_get_logger_returns_logger() -> None:
    logger = get_logger()
    assert isinstance(logger, logging.Logger)


def test_get_logger_with_name() -> None:
    logger = get_logger("child")
    assert isinstance(logger, logging.Logger)


def test_get_logger_under_dev09_tree() -> None:
    logger = get_logger("customer_segmentation.prototype.end_to_end.test")
    assert isinstance(logger, logging.Logger)


def test_configure_logging_idempotent() -> None:
    logger1 = configure_logging(level="INFO", emit_to_console=True)
    logger2 = configure_logging(level="INFO", emit_to_console=True)
    assert logger1 is logger2
    assert len(logger1.handlers) == len(logger2.handlers)


def test_configure_logging_with_file(tmp_path: Path) -> None:
    log_file = tmp_path / "test.log"
    logger = configure_logging(level="DEBUG", log_file=log_file)
    assert log_file.exists()
    logger.info("hello")
    logger.handlers[0].flush()
    finalize_logging(logger)
    content = log_file.read_text(encoding="utf-8")
    assert "hello" in content


def test_configure_logging_no_console(tmp_path: Path) -> None:
    log_file = tmp_path / "test.log"
    logger = configure_logging(level="INFO", log_file=log_file, emit_to_console=False)
    assert any(isinstance(h, logging.FileHandler) for h in logger.handlers)
    finalize_logging(logger)


def test_per_stage_logger_starts() -> None:
    logger = configure_logging(level="INFO", emit_to_console=False)
    psl = PerStageLogger(logger, stage="INIT")
    psl.stage_start("CLUSTERING")
    assert psl.stage == "CLUSTERING"


def test_per_stage_logger_end() -> None:
    logger = configure_logging(level="INFO", emit_to_console=False)
    psl = PerStageLogger(logger, stage="CLUSTERING")
    psl.stage_end("PASS")
    psl.stage_end("FAIL")
    psl.stage_end()
    finalize_logging(logger)


def test_per_stage_logger_info_warning_error_debug() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        log_file_path = Path(f.name)
    logger = configure_logging(level="DEBUG", log_file=log_file_path, emit_to_console=False)
    psl = PerStageLogger(logger, stage="X")
    psl.info("info-msg")
    psl.warning("warn-msg")
    psl.error("err-msg")
    psl.debug("dbg-msg")
    logger.handlers[0].flush()
    finalize_logging(logger)
    content = log_file_path.read_text(encoding="utf-8")
    assert "info-msg" in content
    assert "warn-msg" in content
    assert "err-msg" in content
    assert "dbg-msg" in content


def test_logger_does_not_propagate() -> None:
    logger = configure_logging(level="INFO", emit_to_console=False)
    assert logger.propagate is False


def test_finalize_logging_clears_handlers() -> None:
    logger = configure_logging(level="INFO", emit_to_console=True)
    finalize_logging(logger)
    assert len(logger.handlers) == 0


def test_finalize_logging_idempotent() -> None:
    logger = configure_logging(level="INFO", emit_to_console=False)
    finalize_logging(logger)
    finalize_logging(logger)
    assert len(logger.handlers) == 0


def test_finalize_logging_default_logger() -> None:
    logger = configure_logging(level="INFO", emit_to_console=False)
    finalize_logging()
    assert len(logger.handlers) == 0


def test_configure_logging_invalid_level_raises() -> None:
    with pytest.raises((ValueError, Exception)):
        configure_logging(level="INVALID", emit_to_console=False)
