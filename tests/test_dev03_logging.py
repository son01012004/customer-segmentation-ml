"""Tests for the preprocessing logging module."""

from __future__ import annotations

import logging
from pathlib import Path

from customer_segmentation.prototype.preprocessing.config_loader import (
    PreprocessingLoggingConfig,
)
from customer_segmentation.prototype.preprocessing.logging_config import (
    DEFAULT_LOG_DIR_RELATIVE,
    DEV03_LOG_FORMAT,
    DEV03_LOGGER_NAME,
    PerStageLogger,
    configure_logging,
    finalize_logging,
    now_iso,
)


def test_dev03_constants_are_well_formed() -> None:
    assert "asctime" in DEV03_LOG_FORMAT
    assert "levelname" in DEV03_LOG_FORMAT
    assert "name" in DEV03_LOG_FORMAT
    assert "message" in DEV03_LOG_FORMAT
    assert "data/prototype/datasets" in DEFAULT_LOG_DIR_RELATIVE
    assert DEV03_LOGGER_NAME.startswith("customer_segmentation")


def test_now_iso_returns_z_suffix_utc() -> None:
    s = now_iso()
    assert s.endswith("Z")
    # ISO-8601 basic shape.
    assert len(s) == 20
    assert s[4] == "-"
    assert s[10] == "T"


def test_configure_logging_creates_file_and_handlers(tmp_path: Path) -> None:
    log_path = tmp_path / "sub" / "test.log"
    cfg = PreprocessingLoggingConfig(level="INFO", emit_to_console=True)
    handle = configure_logging(config=cfg, log_path=log_path)
    try:
        assert handle.path == log_path
        assert log_path.parent.exists()
        # File handler is attached.
        logger = logging.getLogger(DEV03_LOGGER_NAME)
        assert any(h is handle.handler for h in logger.handlers)
    finally:
        finalize_logging(handle)


def test_per_stage_logger_emits_stage_in_extra(tmp_path: Path) -> None:
    # Use the standard format that includes %(stage)s.
    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(stage)s | %(message)s"
    log_path = tmp_path / "log.txt"
    cfg = PreprocessingLoggingConfig(level="INFO", format=fmt, emit_to_console=False)
    handle = configure_logging(config=cfg, log_path=log_path)
    try:
        psl = PerStageLogger(handle)
        psl.stage_start("A", rows_in=10)
        psl.stage_end("A", rows_out=5)
        psl.stage_warning("B", "test warning", rows=2)
        psl.failure("C", ValueError("boom"))
    finally:
        finalize_logging(handle)

    text = log_path.read_text(encoding="utf-8")
    assert "stage_A.start" in text
    assert "stage_A.end" in text
    # Stage key is part of the format.
    assert " | A | " in text


def test_per_stage_logger_facade(tmp_path: Path) -> None:
    log_path = tmp_path / "log2.txt"
    cfg = PreprocessingLoggingConfig(level="DEBUG", emit_to_console=False)
    handle = configure_logging(config=cfg, log_path=log_path)
    try:
        psl = PerStageLogger(handle)
        psl.info("X", "msg", extra_field=42)
    finally:
        finalize_logging(handle)
    text = log_path.read_text(encoding="utf-8")
    assert "msg" in text


def test_finalize_is_idempotent(tmp_path: Path) -> None:
    cfg = PreprocessingLoggingConfig(level="INFO", emit_to_console=False)
    handle = configure_logging(config=cfg, log_path=tmp_path / "a.log")
    finalize_logging(handle)
    # Calling again must not raise.
    finalize_logging(handle)
