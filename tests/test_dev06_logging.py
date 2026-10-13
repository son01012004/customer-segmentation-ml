"""Tests for the DEV-06 logging façade (Phase 2G)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from customer_segmentation.prototype.segmentation.logging_config import (
    DEV06_LOGGER_NAME,
    PerStageLogger,
    configure_logging,
    finalize_logging,
    get_logger,
)

# ---------------------------------------------------------------------------
# get_logger
# ---------------------------------------------------------------------------


class TestGetLogger:
    def test_default_logger_name(self) -> None:
        logger = get_logger()
        assert logger.name == DEV06_LOGGER_NAME

    def test_child_logger(self) -> None:
        logger = get_logger("test_child")
        assert logger.name == f"{DEV06_LOGGER_NAME}.test_child"

    def test_same_package_name_returns_same_logger(self) -> None:
        logger = get_logger(DEV06_LOGGER_NAME)
        assert logger.name == DEV06_LOGGER_NAME


# ---------------------------------------------------------------------------
# configure_logging
# ---------------------------------------------------------------------------


class TestConfigureLogging:
    def test_default_level(self) -> None:
        logger = configure_logging()
        try:
            assert logger.level == logging.INFO
        finally:
            finalize_logging(logger)

    def test_custom_level(self) -> None:
        logger = configure_logging(level="DEBUG")
        try:
            assert logger.level == logging.DEBUG
        finally:
            finalize_logging(logger)

    def test_invalid_level_raises(self) -> None:
        # logging.setLevel validates; an unknown level should raise.
        with pytest.raises(ValueError):
            configure_logging(level="NOT_A_LEVEL")

    def test_console_handler_added(self) -> None:
        logger = configure_logging(emit_to_console=True)
        try:
            assert any(isinstance(h, logging.StreamHandler) for h in logger.handlers)
        finally:
            finalize_logging(logger)

    def test_file_handler_added(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        logger = configure_logging(log_file=log_file)
        try:
            assert any(isinstance(h, logging.FileHandler) for h in logger.handlers)
            assert log_file.exists()
        finally:
            finalize_logging(logger)

    def test_idempotent_resets_handlers(self) -> None:
        logger = configure_logging(emit_to_console=True)
        try:
            n1 = len(logger.handlers)
            configure_logging(emit_to_console=True)
            n2 = len(logger.handlers)
            assert n1 == n2
        finally:
            finalize_logging(logger)


# ---------------------------------------------------------------------------
# PerStageLogger
# ---------------------------------------------------------------------------


class TestPerStageLogger:
    def test_initial_stage(self) -> None:
        logger = configure_logging(emit_to_console=False)
        try:
            psl = PerStageLogger(logger, stage="A")
            assert psl.stage == "A"
        finally:
            finalize_logging(logger)

    def test_stage_start_switches_stage(self) -> None:
        logger = configure_logging(emit_to_console=False)
        try:
            psl = PerStageLogger(logger, stage="A")
            psl.stage_start("B")
            assert psl.stage == "B"
        finally:
            finalize_logging(logger)

    def test_log_methods(self) -> None:
        logger = configure_logging(emit_to_console=False)
        try:
            psl = PerStageLogger(logger, stage="D")
            psl.info("hello")
            psl.warning("warn")
            psl.error("err")
            psl.debug("dbg")
        finally:
            finalize_logging(logger)


# ---------------------------------------------------------------------------
# finalize_logging
# ---------------------------------------------------------------------------


class TestFinalizeLogging:
    def test_finalize_removes_handlers(self) -> None:
        logger = configure_logging(emit_to_console=True)
        finalize_logging(logger)
        assert logger.handlers == []

    def test_finalize_idempotent(self) -> None:
        logger = configure_logging(emit_to_console=True)
        finalize_logging(logger)
        finalize_logging(logger)  # should not raise
        assert logger.handlers == []
