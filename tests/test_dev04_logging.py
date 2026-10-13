"""Tests for the DEV-04 per-stage logging configuration."""

from __future__ import annotations

import logging
from pathlib import Path

from customer_segmentation.prototype.clustering.logging_config import (
    PerStageLogger,
    PerStageLogHandler,
    configure_logging,
    finalize_logging,
    now_iso,
)


class TestNowIso:
    def test_format(self) -> None:
        ts = now_iso()
        assert ts.endswith("Z")
        assert "T" in ts
        assert len(ts) == 20

    def test_different_values(self) -> None:
        # now_iso() has second-level granularity.
        # Verify it returns a valid ISO timestamp with Z suffix.
        import re

        a = now_iso()
        assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", a)


class TestConfigureLogging:
    def test_creates_file_handler(self, tmp_path: Path) -> None:
        from customer_segmentation.prototype.clustering.config_loader import (
            Dev04LoggingConfig,
        )

        log_path = tmp_path / "test.log"
        config = Dev04LoggingConfig(level="INFO", emit_to_console=False)
        handle = configure_logging(config=config, log_path=log_path)

        assert isinstance(handle, PerStageLogHandler)
        assert log_path.exists()
        finalize_logging(handle)

    def test_emits_to_console(self, tmp_path: Path, capsys) -> None:
        from customer_segmentation.prototype.clustering.config_loader import (
            Dev04LoggingConfig,
        )

        log_path = tmp_path / "console.log"
        config = Dev04LoggingConfig(level="INFO", emit_to_console=True)
        handle = configure_logging(config=config, log_path=log_path)
        logger = PerStageLogger(handle)
        logger.info("0", "test message", foo="bar")

        captured = capsys.readouterr()
        finalize_logging(handle)
        # Log should appear in stderr (console handler).
        assert "test message" in captured.err

    def test_stage_format_in_log_file(self, tmp_path: Path) -> None:
        from customer_segmentation.prototype.clustering.config_loader import (
            Dev04LoggingConfig,
        )

        log_path = tmp_path / "stage.log"
        config = Dev04LoggingConfig(level="DEBUG", emit_to_console=False)
        handle = configure_logging(config=config, log_path=log_path)
        logger = PerStageLogger(handle)
        logger.stage_start("1", preprocessed_id="pp_abc")
        logger.stage_end("1", rows=100)
        finalize_logging(handle)

        content = log_path.read_text(encoding="utf-8")
        assert "stage_1.start" in content
        assert "stage_1.end" in content

    def test_stage_fields_recorded_in_extra(self, tmp_path: Path) -> None:
        # Verify keyword arguments passed to stage_start/stage_end are
        # recorded in the LogRecord extra dict (visible via
        # captured log handler).
        from customer_segmentation.prototype.clustering.config_loader import (
            Dev04LoggingConfig,
        )

        records: list[logging.LogRecord] = []

        class CaptureHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                records.append(record)

        log_path = tmp_path / "extra.log"
        config = Dev04LoggingConfig(level="DEBUG", emit_to_console=False)
        handle = configure_logging(config=config, log_path=log_path)
        logger = PerStageLogger(handle)

        # Attach a capture handler.
        capture = CaptureHandler()
        handle.logger.logger.addHandler(capture)

        logger.stage_start("1", preprocessed_id="pp_abc", rows=50)
        finalize_logging(handle)

        assert len(records) >= 1
        rec = records[0]
        # Keyword arguments become LogRecord attributes.
        assert getattr(rec, "preprocessed_id", None) == "pp_abc"
        assert getattr(rec, "rows", None) == 50
        assert "stage_1.start" in rec.getMessage()


class TestPerStageLogger:
    def test_stage_start_emits_info(self, tmp_path: Path) -> None:
        from customer_segmentation.prototype.clustering.config_loader import (
            Dev04LoggingConfig,
        )

        log_path = tmp_path / "stages.log"
        config = Dev04LoggingConfig(level="INFO", emit_to_console=False)
        handle = configure_logging(config=config, log_path=log_path)
        logger = PerStageLogger(handle)
        logger.stage_start("3", clustering_id="cl_abc123")
        finalize_logging(handle)

        content = log_path.read_text(encoding="utf-8")
        assert "stage_3.start" in content

    def test_failure_emits_error(self, tmp_path: Path) -> None:
        from customer_segmentation.prototype.clustering.config_loader import (
            Dev04LoggingConfig,
        )

        log_path = tmp_path / "failure.log"
        config = Dev04LoggingConfig(level="INFO", emit_to_console=False)
        handle = configure_logging(config=config, log_path=log_path)
        logger = PerStageLogger(handle)
        logger.failure("4", RuntimeError("fit failed"))
        finalize_logging(handle)

        content = log_path.read_text(encoding="utf-8")
        assert "stage_4.failure" in content
        assert "RuntimeError" in content

    def test_stage_warning_emits_warning(self, tmp_path: Path) -> None:
        from customer_segmentation.prototype.clustering.config_loader import (
            Dev04LoggingConfig,
        )

        log_path = tmp_path / "warning.log"
        config = Dev04LoggingConfig(level="WARNING", emit_to_console=False)
        handle = configure_logging(config=config, log_path=log_path)
        logger = PerStageLogger(handle)
        logger.stage_warning("2", "validation warning")
        finalize_logging(handle)

        content = log_path.read_text(encoding="utf-8")
        assert "validation warning" in content


class TestFinalizeLogging:
    def test_idempotent(self, tmp_path: Path) -> None:
        from customer_segmentation.prototype.clustering.config_loader import (
            Dev04LoggingConfig,
        )

        log_path = tmp_path / "finalize.log"
        config = Dev04LoggingConfig(level="INFO", emit_to_console=False)
        handle = configure_logging(config=config, log_path=log_path)
        finalize_logging(handle)
        finalize_logging(handle)  # Idempotent — should not raise.
