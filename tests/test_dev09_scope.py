"""Tests for DEV-09 scope, enums, and constants."""

from __future__ import annotations

import pytest

from customer_segmentation.prototype.end_to_end.scope import (
    BANNED_SUBSTRINGS,
    DEFAULT_DISCLAIMER_TEXT,
    E2E_ID_HEX_LEN,
    E2E_ID_PREFIX,
    E2E_STAGE_ORDER,
    END_TO_END_SCHEMA_VERSION,
    Lifecycle,
    StageStatus,
)


class TestSchemaVersion:
    def test_schema_version_is_pinned(self) -> None:
        assert END_TO_END_SCHEMA_VERSION == "1.0.0"

    def test_schema_version_is_string(self) -> None:
        assert isinstance(END_TO_END_SCHEMA_VERSION, str)


class TestIdPrefixes:
    def test_e2e_id_prefix(self) -> None:
        assert E2E_ID_PREFIX == "e2e_"

    def test_e2e_id_hex_len_is_int(self) -> None:
        assert isinstance(E2E_ID_HEX_LEN, int)
        assert E2E_ID_HEX_LEN > 0


class TestStageOrder:
    def test_stage_order_is_tuple(self) -> None:
        assert isinstance(E2E_STAGE_ORDER, tuple)

    def test_stage_order_has_eleven_entries(self) -> None:
        assert len(E2E_STAGE_ORDER) == 11

    def test_stage_order_starts_with_upload(self) -> None:
        assert E2E_STAGE_ORDER[0].value == "UPLOAD"

    def test_stage_order_ends_with_visualization(self) -> None:
        assert E2E_STAGE_ORDER[-1].value == "VISUALIZATION"

    def test_stage_order_canonical(self) -> None:
        names = [s.value for s in E2E_STAGE_ORDER]
        assert names == [
            "UPLOAD",
            "VALIDATION",
            "PREPROCESSING",
            "FEATURE_ENGINEERING",
            "ALGORITHM_SELECT",
            "CLUSTERING",
            "EVALUATION",
            "SEGMENTATION",
            "CUSTOMER_PROFILE",
            "MARKETING",
            "VISUALIZATION",
        ]


class TestLifecycle:
    def test_lifecycle_values(self) -> None:
        assert Lifecycle.SUCCESS.value == "SUCCESS"
        assert Lifecycle.CACHED.value == "CACHED"
        assert Lifecycle.FAILED.value == "FAILED"
        assert Lifecycle.CONDITIONAL.value == "CONDITIONAL"
        assert Lifecycle.BLOCKED.value == "BLOCKED"


class TestStageStatus:
    def test_stage_status_values(self) -> None:
        assert StageStatus.SUCCESS.value == "SUCCESS"
        assert StageStatus.CACHED.value == "CACHED"
        assert StageStatus.FAILED.value == "FAILED"
        assert StageStatus.SKIPPED.value == "SKIPPED"
        assert StageStatus.BLOCKED.value == "BLOCKED"
        assert StageStatus.REVIEW_REQUIRED.value == "REVIEW_REQUIRED"


class TestBannedSubstrings:
    def test_banned_substrings_is_tuple(self) -> None:
        assert isinstance(BANNED_SUBSTRINGS, tuple)

    def test_banned_substrings_non_empty(self) -> None:
        assert len(BANNED_SUBSTRINGS) > 0

    def test_banned_substrings_contains_best(self) -> None:
        assert "best" in BANNED_SUBSTRINGS

    def test_banned_substrings_contains_winner(self) -> None:
        assert "winner" in BANNED_SUBSTRINGS

    def test_banned_substrings_contains_optimal(self) -> None:
        assert "optimal" in BANNED_SUBSTRINGS

    def test_banned_substrings_contains_recommended(self) -> None:
        assert "recommended" in BANNED_SUBSTRINGS


class TestDefaultDisclaimer:
    def test_default_disclaimer_is_string(self) -> None:
        assert isinstance(DEFAULT_DISCLAIMER_TEXT, str)

    def test_default_disclaimer_non_empty(self) -> None:
        assert len(DEFAULT_DISCLAIMER_TEXT) > 0


class TestExceptions:
    def test_errors_are_importable(self) -> None:
        from customer_segmentation.prototype.end_to_end.scope import (
            Dev09ConfigError,
            Dev09Error,
            Dev09InputError,
            Dev09StoragePathError,
        )

        assert issubclass(Dev09Error, RuntimeError)
        assert issubclass(Dev09InputError, ValueError)
        assert issubclass(Dev09ConfigError, ValueError)
        assert issubclass(Dev09StoragePathError, ValueError)


@pytest.mark.parametrize(
    "lifecycle_name",
    ["SUCCESS", "CACHED", "FAILED", "CONDITIONAL", "BLOCKED"],
)
def test_lifecycle_values_present(lifecycle_name: str) -> None:
    assert hasattr(Lifecycle, lifecycle_name)


@pytest.mark.parametrize(
    "status_name",
    ["SUCCESS", "CACHED", "FAILED", "SKIPPED", "BLOCKED", "REVIEW_REQUIRED"],
)
def test_stage_status_values_present(status_name: str) -> None:
    assert hasattr(StageStatus, status_name)
