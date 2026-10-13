"""Tests for DEV-07 MKT framework loader.

Phase A behaviour: ``load_mkt_framework`` returns ``None`` when no MKT
framework directory exists. This is the canonical current state of the
repository (no MKT-01..MKT-05 files in ``docs/marketing/``).

Phase B behaviour (unblocked once MKT-01..05 exist): return a
:class:`MktFrameworkRef` with a version string matching the configured
pattern.

Hard rules tested
-----------------
- Does NOT fabricate a MKT framework.
- Does NOT raise when path is absent (Phase A → ``None``).
- Reads only ``.md`` files starting with ``MKT-``.
- All 5 MKT-NN docs required to construct a ref.
- Version string extracted from filename must match config pattern.
"""

from __future__ import annotations

from pathlib import Path

from customer_segmentation.prototype.marketing.config_loader import (
    Dev07Config,
    Dev07DisplayConfig,
    Dev07LoggingConfig,
    Dev07MktFrameworkConfig,
    Dev07ResearchSafetyConfig,
    Dev07StorageConfig,
    Dev07ValidationConfig,
)
from customer_segmentation.prototype.marketing.mkt_framework_loader import (
    MktFrameworkRef,
    framework_version_string,
    load_mkt_framework,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(
    *,
    path_relative: str = "docs/marketing",
    version_pattern: str | None = None,
) -> Dev07Config:
    """Build a DEV-07 config with a configurable MKT framework block.

    The default ``version_pattern`` matches the loader's canonical
    format ``MKT-01..05__vN`` (which is what the loader checks against
    after extracting the per-file version).
    """
    if version_pattern is None:
        # Matches the canonical "MKT-01..05__vN" form used internally.
        version_pattern = r"^MKT-01\.\.05__v\d+(?:\.\d+)*$"
    return Dev07Config(
        schema_version="1.0.0",
        availability_default="REVIEW_REQUIRED",
        mkt_framework=Dev07MktFrameworkConfig(
            path_relative=path_relative,
            version_pattern=version_pattern,
        ),
        display=Dev07DisplayConfig(
            percentage_decimals=2,
            missing_value_placeholder="--",
            csv_missing_value="",
            disclaimer_text="descriptive only",
        ),
        storage=Dev07StorageConfig(
            output_dir_relative="marketing",
            emit_manifest_json=True,
            emit_recommendations_csv=False,
            emit_recommendations_jsonl=False,
        ),
        logging=Dev07LoggingConfig(
            level="INFO",
            format="%(message)s",
            log_dir_relative="data/prototype/datasets",
            emit_to_console=True,
        ),
        research_safety=Dev07ResearchSafetyConfig(
            readonly_paths=["data/raw/primary"],
            never_promote_to_research=True,
            marketing_scope="MARKETING_PROTOTYPE",
        ),
        validation=Dev07ValidationConfig(
            forbid_internal_metrics_as_kpi=True,
            forbid_marketing_terminology=True,
            require_no_duplicate_segment_id=True,
            exclude_dbscan_noise=True,
        ),
    )


def _create_mkt_framework(
    repo_root: Path,
    *,
    path_relative: str = "docs/marketing",
    docs: dict[str, str] | None = None,
) -> Path:
    """Create a synthetic MKT framework directory under ``repo_root``.

    Default: all 5 MKT-NN docs present.
    ``docs`` lets the test override individual doc filenames / contents.
    """
    framework_dir = repo_root / path_relative
    framework_dir.mkdir(parents=True, exist_ok=True)
    if docs is None:
        # Default Phase-B-shape: 5 MKT-NN files, each with a v1 suffix.
        docs = {
            "MKT-01__v1.md": "Framework overview.",
            "MKT-02__v1.md": "Marketing objective templates.",
            "MKT-03__v1.md": "Strategy + action templates.",
            "MKT-04__v1.md": "KPI definitions.",
            "MKT-05__v1.md": "Limitation framework.",
        }
    for name, content in docs.items():
        (framework_dir / name).write_text(content, encoding="utf-8")
    return framework_dir


# ---------------------------------------------------------------------------
# Phase A: framework absent (current repo state)
# ---------------------------------------------------------------------------


class TestLoadMktFrameworkAbsent:
    def test_returns_none_when_directory_missing(self, tmp_path: Path) -> None:
        cfg = _make_config(path_relative="does/not/exist")
        ref = load_mkt_framework(cfg, repo_root=tmp_path)
        assert ref is None

    def test_returns_none_when_empty_directory(self, tmp_path: Path) -> None:
        (tmp_path / "docs" / "marketing").mkdir(parents=True)
        cfg = _make_config(path_relative="docs/marketing")
        ref = load_mkt_framework(cfg, repo_root=tmp_path)
        assert ref is None

    def test_returns_none_with_partial_docs(self, tmp_path: Path) -> None:
        """Only 3 of 5 MKT docs present → still None."""
        docs = {
            "MKT-01__v1.md": "x",
            "MKT-02__v1.md": "x",
            "MKT-03__v1.md": "x",
            # MKT-04, MKT-05 missing
        }
        _create_mkt_framework(tmp_path, docs=docs)
        cfg = _make_config()
        ref = load_mkt_framework(cfg, repo_root=tmp_path)
        assert ref is None

    def test_does_not_raise_on_absent_path(self, tmp_path: Path) -> None:
        """Phase A contract: missing framework must not raise."""
        cfg = _make_config(path_relative="totally/missing")
        # Should silently return None, not raise.
        ref = load_mkt_framework(cfg, repo_root=tmp_path)
        assert ref is None


# ---------------------------------------------------------------------------
# Phase B: framework present (synthetic)
# ---------------------------------------------------------------------------


class TestLoadMktFrameworkPresent:
    def test_returns_ref_when_all_five_docs_present(self, tmp_path: Path) -> None:
        _create_mkt_framework(tmp_path)
        cfg = _make_config()
        ref = load_mkt_framework(cfg, repo_root=tmp_path)
        assert ref is not None
        assert isinstance(ref, MktFrameworkRef)
        assert ref.version == "v1"

    def test_ref_files_listed(self, tmp_path: Path) -> None:
        _create_mkt_framework(tmp_path)
        cfg = _make_config()
        ref = load_mkt_framework(cfg, repo_root=tmp_path)
        assert ref is not None
        # All 5 files listed.
        assert len(ref.files) == 5
        # All files start with "MKT-".
        for f in ref.files:
            assert Path(f).name.startswith("MKT-")

    def test_ref_files_repo_relative(self, tmp_path: Path) -> None:
        _create_mkt_framework(tmp_path)
        cfg = _make_config()
        ref = load_mkt_framework(cfg, repo_root=tmp_path)
        assert ref is not None
        # Files are repo-relative paths; absolute paths must NOT appear.
        for f in ref.files:
            assert not Path(f).is_absolute()

    def test_ref_framework_dir_resolves(self, tmp_path: Path) -> None:
        framework_dir = _create_mkt_framework(tmp_path)
        cfg = _make_config()
        ref = load_mkt_framework(cfg, repo_root=tmp_path)
        assert ref is not None
        # The framework_dir may be absolute (resolved); check it points
        # to the right place.
        assert Path(ref.framework_dir).resolve() == framework_dir.resolve()

    def test_version_extracted_with_double_underscore(self, tmp_path: Path) -> None:
        docs = {
            "MKT-01__v2.md": "x",
            "MKT-02__v2.md": "x",
            "MKT-03__v2.md": "x",
            "MKT-04__v2.md": "x",
            "MKT-05__v2.md": "x",
        }
        _create_mkt_framework(tmp_path, docs=docs)
        cfg = _make_config()
        ref = load_mkt_framework(cfg, repo_root=tmp_path)
        assert ref is not None
        assert ref.version == "v2"

    def test_version_extracted_with_single_underscore(self, tmp_path: Path) -> None:
        docs = {
            "MKT-01_v3.md": "x",
            "MKT-02_v3.md": "x",
            "MKT-03_v3.md": "x",
            "MKT-04_v3.md": "x",
            "MKT-05_v3.md": "x",
        }
        _create_mkt_framework(tmp_path, docs=docs)
        cfg = _make_config()
        ref = load_mkt_framework(cfg, repo_root=tmp_path)
        assert ref is not None
        assert ref.version == "v3"

    def test_version_with_dot_in_version(self, tmp_path: Path) -> None:
        docs = {
            "MKT-01__v1.2.md": "x",
            "MKT-02__v1.2.md": "x",
            "MKT-03__v1.2.md": "x",
            "MKT-04__v1.2.md": "x",
            "MKT-05__v1.2.md": "x",
        }
        _create_mkt_framework(tmp_path, docs=docs)
        cfg = _make_config()
        ref = load_mkt_framework(cfg, repo_root=tmp_path)
        assert ref is not None
        assert ref.version == "v1.2"

    def test_extra_mkt_files_ignored(self, tmp_path: Path) -> None:
        """Extra .md files are tolerated; load still requires ≥5 MKT-*."""
        docs = {
            "MKT-01__v1.md": "x",
            "MKT-02__v1.md": "x",
            "MKT-03__v1.md": "x",
            "MKT-04__v1.md": "x",
            "MKT-05__v1.md": "x",
            "extra_notes.md": "x",
            "README.md": "x",
        }
        _create_mkt_framework(tmp_path, docs=docs)
        cfg = _make_config()
        ref = load_mkt_framework(cfg, repo_root=tmp_path)
        assert ref is not None
        # Files list may include extras; ≥5 required.
        assert len(ref.files) >= 5

    def test_non_md_files_ignored(self, tmp_path: Path) -> None:
        """Files without .md suffix are ignored."""
        framework_dir = _create_mkt_framework(tmp_path)
        # Add a non-md file with MKT- prefix.
        (framework_dir / "MKT-extra.txt").write_text("ignored")
        cfg = _make_config()
        ref = load_mkt_framework(cfg, repo_root=tmp_path)
        assert ref is not None
        # The .txt file is not in files list.
        for f in ref.files:
            assert Path(f).name.endswith(".md")

    def test_subdirectories_ignored(self, tmp_path: Path) -> None:
        """Subdirectories starting with MKT- are ignored."""
        framework_dir = _create_mkt_framework(tmp_path)
        # Add a subdirectory with MKT- prefix.
        (framework_dir / "MKT-archive").mkdir()
        cfg = _make_config()
        ref = load_mkt_framework(cfg, repo_root=tmp_path)
        assert ref is not None
        # No MKT-archive entry in files list.
        for f in ref.files:
            assert "MKT-archive" not in f


# ---------------------------------------------------------------------------
# framework_version_string
# ---------------------------------------------------------------------------


class TestFrameworkVersionString:
    def test_canonical_format(self, tmp_path: Path) -> None:
        _create_mkt_framework(tmp_path)
        cfg = _make_config()
        ref = load_mkt_framework(cfg, repo_root=tmp_path)
        assert ref is not None
        v = framework_version_string(ref)
        assert v == "MKT-01..05__v1"
        assert v.startswith("MKT-01..05__")

    def test_version_v2(self, tmp_path: Path) -> None:
        docs = {f"MKT-0{i}__v2.md": "x" for i in range(1, 6)}
        _create_mkt_framework(tmp_path, docs=docs)
        cfg = _make_config()
        ref = load_mkt_framework(cfg, repo_root=tmp_path)
        assert ref is not None
        assert framework_version_string(ref) == "MKT-01..05__v2"

    def test_version_dot_version(self, tmp_path: Path) -> None:
        docs = {f"MKT-0{i}__v1.5.md": "x" for i in range(1, 6)}
        _create_mkt_framework(tmp_path, docs=docs)
        cfg = _make_config()
        ref = load_mkt_framework(cfg, repo_root=tmp_path)
        assert ref is not None
        assert framework_version_string(ref) == "MKT-01..05__v1.5"


# ---------------------------------------------------------------------------
# Pattern matching
# ---------------------------------------------------------------------------


class TestVersionPattern:
    def test_invalid_version_returns_none(self, tmp_path: Path) -> None:
        """File with no parseable version → None."""
        docs = {f"MKT-0{i}_NOTES.md": "x" for i in range(1, 6)}
        _create_mkt_framework(tmp_path, docs=docs)
        cfg = _make_config()
        ref = load_mkt_framework(cfg, repo_root=tmp_path)
        # Pattern requires '__vN' suffix; '_NOTES' does not match.
        assert ref is None

    def test_extra_mkt_files_with_bad_version(self, tmp_path: Path) -> None:
        """Files with bad version strings are tolerated if ≥5 valid files exist."""
        docs = {f"MKT-0{i}__v1.md": "x" for i in range(1, 6)}
        docs["MKT-extra_bad.md"] = "x"
        _create_mkt_framework(tmp_path, docs=docs)
        cfg = _make_config()
        ref = load_mkt_framework(cfg, repo_root=tmp_path)
        # At least 5 valid files present → ref loaded with version v1.
        assert ref is not None
        assert ref.version == "v1"


# ---------------------------------------------------------------------------
# Custom repo_root
# ---------------------------------------------------------------------------


def test_explicit_repo_root_used(tmp_path: Path) -> None:
    """Explicit repo_root overrides the default config-derived path."""
    _create_mkt_framework(tmp_path)
    cfg = _make_config(path_relative="marketing")  # would not be found in tmp
    ref = load_mkt_framework(cfg, repo_root=tmp_path)
    # The framework dir is "docs/marketing" under tmp, but config says
    # "marketing" → none found.
    assert ref is None


def test_explicit_repo_root_overrides_default(tmp_path: Path) -> None:
    """With explicit repo_root, path_relative resolves under it."""
    _create_mkt_framework(tmp_path, path_relative="marketing")
    cfg = _make_config(path_relative="marketing")
    ref = load_mkt_framework(cfg, repo_root=tmp_path)
    assert ref is not None


# ---------------------------------------------------------------------------
# Default-config integration tests
#
# These tests use ``load_dev07_config()`` (no overrides) and feed a
# synthetic MKT framework via ``repo_root``/``tmp_path``. They
# exercise the production code path of the loader — no helper-side
# version_pattern override. This guards against the audit-flagged
# regression where the default config pattern never co-existed with
# a real MKT framework in tests (audit §4.1, §7.2).
# ---------------------------------------------------------------------------


class TestDefaultConfigIntegration:
    """End-to-end tests using ``load_dev07_config()`` (no overrides)."""

    def test_default_config_loads(self) -> None:
        """Smoke: default config must load without error."""
        from customer_segmentation.prototype.marketing.config_loader import (
            load_dev07_config,
        )

        cfg = load_dev07_config()
        # Default config pattern is the canonical aggregate form
        # ``MKT-01..05__vN`` (ADR-0008, Option A). The loader
        # constructs this aggregate form internally; the default
        # pattern accepts it.
        assert cfg.mkt_framework.version_pattern == (r"^MKT-01\.\.05__v\d+(?:\.\d+)*$")

    def test_default_config_framework_absent_returns_none(self, tmp_path: Path) -> None:
        """Default config + no MKT framework dir → ``None`` (Phase A)."""
        from customer_segmentation.prototype.marketing.config_loader import (
            load_dev07_config,
        )

        cfg = load_dev07_config()
        # repo_root has no ``docs/marketing/`` subdir.
        ref = load_mkt_framework(cfg, repo_root=tmp_path)
        assert ref is None

    def test_default_config_with_per_file_filenames_matches(self, tmp_path: Path, caplog) -> None:
        """Default config pattern is aggregate form; per-file
        filenames (e.g. ``MKT-01__v1.md``) are accepted because the
        loader constructs the aggregate form ``MKT-01..05__v1`` from
        the per-file version and matches it against the configured
        aggregate pattern.

        This documents ADR-0008 Option A behaviour (canonical
        aggregate form): per-file shape on disk → aggregate form in
        loader → match against default config.
        """
        import logging

        from customer_segmentation.prototype.marketing.config_loader import (
            load_dev07_config,
        )

        # Build MKT files with per-file shape (e.g. MKT-01__v1.md).
        docs = {f"MKT-0{i}__v1.md": "x" for i in range(1, 6)}
        _create_mkt_framework(tmp_path, docs=docs)
        cfg = load_dev07_config()

        # Capture WARNING-level logs from the loader (should be NONE:
        # the default config matches the constructed aggregate form).
        with caplog.at_level(
            logging.WARNING,
            logger="customer_segmentation.prototype.marketing.mkt_framework_loader",
        ):
            ref = load_mkt_framework(cfg, repo_root=tmp_path)
        # Default config pattern matches the constructed aggregate
        # form → ref is returned (ADR-0008 Option A canonical form).
        assert ref is not None
        assert ref.version == "v1"
        # NO WARNING log should be emitted (default config is
        # consistent with the loader's constructed form).
        assert not any(
            record.levelno == logging.WARNING
            and "version extraction failed" in record.message.lower()
            for record in caplog.records
        )

    def test_default_config_with_aggregate_pattern_default_loads_framework(
        self, tmp_path: Path
    ) -> None:
        """End-to-end: the default config (aggregate pattern) plus
        per-file MKT filenames returns a valid ref, demonstrating
        the canonical form is consistent across config + loader.

        This is the primary acceptance test for ADR-0008 Option A
        (no override; production path only).
        """
        from customer_segmentation.prototype.marketing.config_loader import (
            load_dev07_config,
        )

        cfg = load_dev07_config()
        # Sanity: default config is aggregate form.
        assert cfg.mkt_framework.version_pattern == (r"^MKT-01\.\.05__v\d+(?:\.\d+)*$")
        docs = {f"MKT-0{i}__v1.md": "x" for i in range(1, 6)}
        _create_mkt_framework(tmp_path, docs=docs)
        ref = load_mkt_framework(cfg, repo_root=tmp_path)
        assert ref is not None
        assert ref.version == "v1"
        # framework_version_string returns the canonical aggregate form.
        assert framework_version_string(ref) == "MKT-01..05__v1"

    def test_default_config_partial_docs_returns_none(self, tmp_path: Path) -> None:
        """Default config + only some MKT docs → ``None``."""
        from customer_segmentation.prototype.marketing.config_loader import (
            load_dev07_config,
        )

        docs = {
            "MKT-01__v1.md": "x",
            "MKT-02__v1.md": "x",
            "MKT-03__v1.md": "x",
            # MKT-04, MKT-05 missing
        }
        _create_mkt_framework(tmp_path, docs=docs)
        cfg = load_dev07_config()
        ref = load_mkt_framework(cfg, repo_root=tmp_path)
        assert ref is None

    def test_default_config_warning_emitted_on_explicit_pattern_mismatch(
        self, tmp_path: Path, caplog
    ) -> None:
        """When the configured pattern does NOT match the constructed
        aggregate form, the loader emits a ``WARNING`` log (not just
        debug) so operators see the silent-failure-prevention
        diagnostic.

        Per ADR-0008 Option A, the *default* config pattern matches
        the constructed aggregate form; this test demonstrates the
        diagnostic path still works by overriding the config with an
        explicit per-file pattern (a config that would mismatch
        against the loader's constructed form).
        """
        import logging

        from customer_segmentation.prototype.marketing.config_loader import (
            load_dev07_config,
        )

        docs = {f"MKT-0{i}__v1.md": "x" for i in range(1, 6)}
        _create_mkt_framework(tmp_path, docs=docs)
        # Override default (aggregate) with explicit per-file pattern
        # to demonstrate the WARNING diagnostic on pattern mismatch.
        cfg = load_dev07_config()
        cfg = Dev07Config(
            schema_version=cfg.schema_version,
            availability_default=cfg.availability_default,
            mkt_framework=Dev07MktFrameworkConfig(
                path_relative=cfg.mkt_framework.path_relative,
                # Explicit per-file pattern: does NOT match the
                # loader's constructed aggregate form.
                version_pattern=r"^MKT-0[1-5]__v[0-9]+$",
            ),
            display=cfg.display,
            storage=cfg.storage,
            logging=cfg.logging,
            research_safety=cfg.research_safety,
            validation=cfg.validation,
            raw=cfg.raw,
        )

        with caplog.at_level(
            logging.WARNING, logger="customer_segmentation.prototype.marketing.mkt_framework_loader"
        ):
            ref = load_mkt_framework(cfg, repo_root=tmp_path)
        assert ref is None
        # A WARNING message should be present (audit §4.1 silent-failure
        # prevention; diagnostic remains operational for any config
        # that does not match the constructed aggregate form).
        assert any(
            record.levelno == logging.WARNING
            and "version extraction failed" in record.message.lower()
            for record in caplog.records
        )

    def test_default_config_rejects_per_file_naming_convention(self, tmp_path: Path) -> None:
        """Per ADR-0008 Option A: aggregate form is canonical.
        Filenames that do NOT yield a parseable per-file version
        (e.g. ``MKT-01_NOTES.md``) are rejected even with the default
        config pattern, because the loader cannot extract ``vN`` to
        construct the aggregate form.

        This documents the "per-file naming convention required"
        contract: filenames must carry a ``__vN`` or ``_vN`` suffix.
        """
        from customer_segmentation.prototype.marketing.config_loader import (
            load_dev07_config,
        )

        # Filenames without a parseable version suffix.
        docs = {f"MKT-0{i}_NOTES.md": "x" for i in range(1, 6)}
        _create_mkt_framework(tmp_path, docs=docs)
        cfg = load_dev07_config()
        ref = load_mkt_framework(cfg, repo_root=tmp_path)
        assert ref is None
