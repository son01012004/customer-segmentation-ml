"""Tests for DEV-07 Phase B MKT framework structural metadata loader.

The structure loader is an extension of the Phase A
``load_mkt_framework`` that returns per-doc structural metadata
(file existence + sha256 + byte_count + token_count). It does NOT
parse business content (objective / strategy / action / KPI /
limitation templates are NOT extracted).

Tests verify:
- Returns ``None`` when framework absent (Phase A contract).
- Returns ``MktFrameworkStructure`` when 5 MKT-NN files present.
- Per-doc metadata is correctly computed.
- ``is_complete`` property returns True when 5 docs present.
- ``MktDocRef`` invariants enforced.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

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
    MktDocRef,
    MktFrameworkStructure,
    load_mkt_framework_structure,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(
    *,
    path_relative: str = "docs/marketing",
    version_pattern: str | None = None,
) -> Dev07Config:
    if version_pattern is None:
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
    framework_dir = repo_root / path_relative
    framework_dir.mkdir(parents=True, exist_ok=True)
    if docs is None:
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
# Phase A: structure absent
# ---------------------------------------------------------------------------


class TestStructureAbsent:
    def test_returns_none_when_directory_missing(self, tmp_path: Path) -> None:
        cfg = _make_config(path_relative="does/not/exist")
        result = load_mkt_framework_structure(cfg, repo_root=tmp_path)
        assert result is None

    def test_returns_none_when_empty_directory(self, tmp_path: Path) -> None:
        (tmp_path / "docs" / "marketing").mkdir(parents=True)
        cfg = _make_config()
        result = load_mkt_framework_structure(cfg, repo_root=tmp_path)
        assert result is None

    def test_returns_none_with_partial_docs(self, tmp_path: Path) -> None:
        """Only 3 of 5 MKT docs → None."""
        docs = {
            "MKT-01__v1.md": "x",
            "MKT-02__v1.md": "x",
            "MKT-03__v1.md": "x",
        }
        _create_mkt_framework(tmp_path, docs=docs)
        cfg = _make_config()
        result = load_mkt_framework_structure(cfg, repo_root=tmp_path)
        assert result is None


# ---------------------------------------------------------------------------
# Phase B: structure present
# ---------------------------------------------------------------------------


class TestStructurePresent:
    def test_returns_structure_when_all_five_docs_present(self, tmp_path: Path) -> None:
        _create_mkt_framework(tmp_path)
        cfg = _make_config()
        result = load_mkt_framework_structure(cfg, repo_root=tmp_path)
        assert result is not None
        assert isinstance(result, MktFrameworkStructure)
        assert result.version == "v1"

    def test_is_complete_true(self, tmp_path: Path) -> None:
        _create_mkt_framework(tmp_path)
        cfg = _make_config()
        result = load_mkt_framework_structure(cfg, repo_root=tmp_path)
        assert result is not None
        assert result.is_complete is True

    def test_contains_all_five_doc_refs(self, tmp_path: Path) -> None:
        _create_mkt_framework(tmp_path)
        cfg = _make_config()
        result = load_mkt_framework_structure(cfg, repo_root=tmp_path)
        assert result is not None
        assert set(result.docs.keys()) == {"MKT-01", "MKT-02", "MKT-03", "MKT-04", "MKT-05"}

    def test_per_doc_sha256_correct(self, tmp_path: Path) -> None:
        docs = {f"MKT-0{i}__v1.md": f"content-{i}" for i in range(1, 6)}
        _create_mkt_framework(tmp_path, docs=docs)
        cfg = _make_config()
        result = load_mkt_framework_structure(cfg, repo_root=tmp_path)
        assert result is not None
        for i in range(1, 6):
            ref = result.docs[f"MKT-0{i}"]
            expected = hashlib.sha256(f"content-{i}".encode()).hexdigest()
            assert ref.sha256 == expected

    def test_per_doc_byte_count(self, tmp_path: Path) -> None:
        docs = {f"MKT-0{i}__v1.md": f"hello-{i}" for i in range(1, 6)}
        _create_mkt_framework(tmp_path, docs=docs)
        cfg = _make_config()
        result = load_mkt_framework_structure(cfg, repo_root=tmp_path)
        assert result is not None
        for i in range(1, 6):
            ref = result.docs[f"MKT-0{i}"]
            assert ref.byte_count == len(f"hello-{i}".encode())

    def test_per_doc_token_count(self, tmp_path: Path) -> None:
        """Token count is whitespace-split."""
        docs = {
            "MKT-01__v1.md": "one two three",
            "MKT-02__v1.md": "alpha beta",
        }
        # Pad missing with placeholders.
        for i in range(3, 6):
            docs[f"MKT-0{i}__v1.md"] = "x"
        _create_mkt_framework(tmp_path, docs=docs)
        cfg = _make_config()
        result = load_mkt_framework_structure(cfg, repo_root=tmp_path)
        assert result is not None
        assert result.docs["MKT-01"].token_count == 3
        assert result.docs["MKT-02"].token_count == 2

    def test_version_string_format(self, tmp_path: Path) -> None:
        _create_mkt_framework(tmp_path)
        cfg = _make_config()
        result = load_mkt_framework_structure(cfg, repo_root=tmp_path)
        assert result is not None
        assert result.version == "v1"

    def test_version_v2(self, tmp_path: Path) -> None:
        docs = {f"MKT-0{i}__v2.md": "x" for i in range(1, 6)}
        _create_mkt_framework(tmp_path, docs=docs)
        cfg = _make_config()
        result = load_mkt_framework_structure(cfg, repo_root=tmp_path)
        assert result is not None
        assert result.version == "v2"

    def test_extra_mkt_files_included(self, tmp_path: Path) -> None:
        """Extra .md files do not break the 5-doc contract."""
        framework_dir = _create_mkt_framework(tmp_path)
        (framework_dir / "extra_notes.md").write_text("ignored", encoding="utf-8")
        cfg = _make_config()
        result = load_mkt_framework_structure(cfg, repo_root=tmp_path)
        assert result is not None
        # Still only 5 MKT-* docs.
        assert set(result.docs.keys()) == {"MKT-01", "MKT-02", "MKT-03", "MKT-04", "MKT-05"}


# ---------------------------------------------------------------------------
# MktDocRef / MktFrameworkStructure invariants
# ---------------------------------------------------------------------------


class TestInvariants:
    def test_mkt_doc_ref_sha256_length_64(self) -> None:
        with pytest.raises(ValueError, match="64-character"):
            MktDocRef(
                mkt_id="MKT-01",
                file_path=Path("/tmp/x.md"),
                sha256="abc",
                byte_count=10,
                token_count=2,
            )

    def test_mkt_doc_ref_id_must_start_with_mkt(self) -> None:
        with pytest.raises(ValueError, match="must start with 'MKT-'"):
            MktDocRef(
                mkt_id="BAD",
                file_path=Path("/tmp/x.md"),
                sha256="0" * 64,
                byte_count=10,
                token_count=2,
            )

    def test_structure_rejects_missing_docs(self) -> None:
        with pytest.raises(ValueError, match="missing"):
            MktFrameworkStructure(
                framework_dir=Path("/tmp"),
                version="v1",
                docs={
                    "MKT-01": MktDocRef(
                        mkt_id="MKT-01",
                        file_path=Path("/tmp/MKT-01.md"),
                        sha256="0" * 64,
                        byte_count=1,
                        token_count=0,
                    )
                },
            )

    def test_structure_rejects_extra_docs(self) -> None:
        with pytest.raises(ValueError, match="extra"):
            docs = {
                f"MKT-0{i}": MktDocRef(
                    mkt_id=f"MKT-0{i}",
                    file_path=Path(f"/tmp/MKT-0{i}.md"),
                    sha256="0" * 64,
                    byte_count=1,
                    token_count=1,
                )
                for i in range(1, 6)
            }
            docs["MKT-99"] = MktDocRef(
                mkt_id="MKT-99",
                file_path=Path("/tmp/MKT-99.md"),
                sha256="0" * 64,
                byte_count=1,
                token_count=1,
            )
            MktFrameworkStructure(
                framework_dir=Path("/tmp"),
                version="v1",
                docs=docs,
            )

    def test_structure_accepts_exactly_five(self) -> None:
        docs = {
            f"MKT-0{i}": MktDocRef(
                mkt_id=f"MKT-0{i}",
                file_path=Path(f"/tmp/MKT-0{i}.md"),
                sha256="0" * 64,
                byte_count=1,
                token_count=1,
            )
            for i in range(1, 6)
        }
        s = MktFrameworkStructure(
            framework_dir=Path("/tmp"),
            version="v1",
            docs=docs,
        )
        assert s.is_complete is True


# ---------------------------------------------------------------------------
# Default-config integration
# ---------------------------------------------------------------------------


class TestDefaultConfigIntegration:
    def test_default_config_loads_structure(self, tmp_path: Path) -> None:
        """Default config + synthetic MKT framework → structure returned."""
        from customer_segmentation.prototype.marketing.config_loader import (
            load_dev07_config,
        )

        _create_mkt_framework(tmp_path)
        cfg = load_dev07_config()
        result = load_mkt_framework_structure(cfg, repo_root=tmp_path)
        assert result is not None
        assert result.version == "v1"
        assert result.is_complete is True

    def test_default_config_returns_none_when_absent(self, tmp_path: Path) -> None:
        from customer_segmentation.prototype.marketing.config_loader import (
            load_dev07_config,
        )

        cfg = load_dev07_config()
        result = load_mkt_framework_structure(cfg, repo_root=tmp_path)
        assert result is None
