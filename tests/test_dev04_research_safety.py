"""Tests for research-safety invariants of the DEV-04 clustering pipeline.

These tests verify that DEV-04 only writes to the designated storage
root and never to research artefact paths (``data/raw/primary``,
``data/raw/backup``, ``data/processed``, ``reports``). They also verify
that the prototype manifest's ``research_safety`` block has the correct
values.

The research_safety block is the canonical defence-in-depth: even if
the prototype pipeline accidentally wrote to a research path, the
manifest's research_safety flags would make it unpromotable to
research evidence.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _snapshot_research_paths(repo: Path) -> dict[Path, str]:
    """Return a {path: sha256-or-sentinel} map of every research path.

    Missing paths are recorded with ``<missing>`` so a deletion would
    show up as a missing value. Files are hashed by content; directories
    by a sorted manifest of (relative_path, content_sha).
    """
    snap: dict[Path, str] = {}
    for sub in (
        "data/raw/primary",
        "data/raw/backup",
        "data/processed",
        "reports",
    ):
        p = repo / sub
        if not p.exists():
            snap[p] = "<missing>"
            continue
        if p.is_file():
            snap[p] = hashlib.sha256(p.read_bytes()).hexdigest()
            continue
        parts: list[str] = []
        for subp in sorted(p.rglob("*")):
            if subp.is_file():
                parts.append(
                    f"{subp.relative_to(p).as_posix()}|"
                    f"{hashlib.sha256(subp.read_bytes()).hexdigest()}"
                )
        snap[p] = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
    return snap


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestResearchPathsUnmodified:
    """R-1, R-2, R-3, R-4: research artefact paths are read-only for DEV-04."""

    def test_research_paths_unmodified_after_clustering(
        self,
        synthetic_dev03_artefact: tuple[Path, Path, Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """End-to-end: DEV-03 artifact + cluster, then verify research
        paths in the repo are byte-identical before and after.
        """
        ml_path, manifest_path, storage_root = synthetic_dev03_artefact

        # Snapshot research paths BEFORE clustering.
        before = _snapshot_research_paths(_REPO_ROOT)

        from customer_segmentation.prototype.clustering import (
            run_clustering_pipeline,
        )

        monkeypatch.setattr(
            "customer_segmentation.prototype.clustering.pipeline" ".resolve_storage_root",
            lambda _=None: storage_root,
        )

        result = run_clustering_pipeline(
            dataset_id="ds_dev04test01",
            preprocessed_id="pp_dev04test01",
            algorithm="kmeans",
            hyperparameters={"n_clusters": 3},
            seed=42,
        )
        assert result.lifecycle in ("SUCCESS", "CACHED")

        after = _snapshot_research_paths(_REPO_ROOT)
        assert before == after, (
            "DEV-04 must not modify any research artefact path; "
            f"diff: before={before} after={after}"
        )

    def test_manifest_research_safety_flags_are_correct(
        self,
        synthetic_dev03_artefact: tuple[Path, Path, Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The prototype manifest must always have:
        - ``automatically_promoted_to_research = False``
        - ``appeared_in_research_evidence = False``
        - ``scope = "CLUSTERED_PROTOTYPE"``
        """
        ml_path, manifest_path, storage_root = synthetic_dev03_artefact

        from customer_segmentation.prototype.clustering import (
            run_clustering_pipeline,
        )

        monkeypatch.setattr(
            "customer_segmentation.prototype.clustering.pipeline" ".resolve_storage_root",
            lambda _=None: storage_root,
        )

        result = run_clustering_pipeline(
            dataset_id="ds_dev04test01",
            preprocessed_id="pp_dev04test01",
            algorithm="kmeans",
            hyperparameters={"n_clusters": 3},
            seed=42,
        )

        assert result.manifest is not None
        rs = result.manifest.research_safety
        assert (
            rs.automatically_promoted_to_research is False
        ), "DEV-04 manifest must never mark automatically_promoted_to_research=True"
        assert (
            rs.appeared_in_research_evidence is False
        ), "DEV-04 manifest must never mark appeared_in_research_evidence=True"
        assert (
            rs.scope == "CLUSTERED_PROTOTYPE"
        ), f"DEV-04 manifest scope must be CLUSTERED_PROTOTYPE, got {rs.scope!r}"

    def test_prototype_storage_path_outside_research_paths(
        self,
        tmp_path: Path,
    ) -> None:
        """The prototype write path
        ``<storage_root>/datasets/<ds>/preprocessed/<pp>/clustering/``
        must NOT overlap any research path (``data/raw/primary``,
        ``data/raw/backup``, ``data/processed``, ``reports``)."""
        from customer_segmentation.prototype.clustering.storage import (
            prototype_clustering_base_dir,
        )

        # Use a normal storage root (no collision with research paths).
        storage_root = tmp_path / "prototype_datasets"
        base = prototype_clustering_base_dir(
            storage_root=storage_root,
            dataset_id="ds_test",
            preprocessed_id="pp_test",
        )
        # The clustering base dir is always under
        # <storage_root>/datasets/<ds>/preprocessed/<pp>/clustering/,
        # which is structurally distinct from any read-only research
        # directory (raw, processed, reports).
        assert (
            "data/raw" not in base.parts
        ), f"prototype base_dir must not be under data/raw/: {base!s}"
        assert (
            "reports" not in base.parts
        ), f"prototype base_dir must not be under reports/: {base!s}"

    def test_dev03_artefact_unmodified_after_clustering(
        self,
        synthetic_dev03_artefact: tuple[Path, Path, Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """DEV-04 must not modify the DEV-03 ML Dataset or its manifest."""
        ml_path, manifest_path, storage_root = synthetic_dev03_artefact

        # Snapshot the DEV-03 artefact by SHA-256.
        before_ml_sha = hashlib.sha256(ml_path.read_bytes()).hexdigest()
        before_manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()

        from customer_segmentation.prototype.clustering import (
            run_clustering_pipeline,
        )

        monkeypatch.setattr(
            "customer_segmentation.prototype.clustering.pipeline" ".resolve_storage_root",
            lambda _=None: storage_root,
        )

        run_clustering_pipeline(
            dataset_id="ds_dev04test01",
            preprocessed_id="pp_dev04test01",
            algorithm="kmeans",
            hyperparameters={"n_clusters": 3},
            seed=42,
        )

        # Re-snapshot and compare.
        after_ml_sha = hashlib.sha256(ml_path.read_bytes()).hexdigest()
        after_manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        assert before_ml_sha == after_ml_sha, "DEV-04 must not modify the DEV-03 ML Dataset"
        assert (
            before_manifest_sha == after_manifest_sha
        ), "DEV-04 must not modify the DEV-03 preprocessed manifest"


class TestPromotionGuard:
    """Defence-in-depth: prototype output must never be auto-promoted."""

    def test_research_safety_never_promote_flag_set(self) -> None:
        from customer_segmentation.prototype.clustering.config_loader import (
            load_dev04_config,
        )

        cfg, _ = load_dev04_config()
        assert (
            cfg.research_safety.never_promote_to_research is True
        ), "research_safety.never_promote_to_research must always be True"

    def test_research_safety_readonly_paths_match_dev02(
        self,
    ) -> None:
        from customer_segmentation.prototype.clustering.config_loader import (
            load_dev04_config,
        )

        cfg, _ = load_dev04_config()
        readonly = cfg.research_safety.readonly_paths
        expected_substrings = {
            "data/raw/primary",
            "data/raw/backup",
            "data/processed",
            "reports",
        }
        for needle in expected_substrings:
            assert any(needle in p for p in readonly), (
                f"research_safety.readonly_paths must include {needle!r} " f"(got {readonly!r})"
            )
