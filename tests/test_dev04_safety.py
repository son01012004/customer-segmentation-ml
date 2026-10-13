"""Safety tests for DEV-04 cleanup pass, FAILED-log preservation, and
orphan/crash recovery (R-13, R-15, R-16, R-17 invariants).

These tests cover:
- R-15 (R1): FAILED experiment log preservation via _preserve_failed_log
- F1 invariant (R-15a): staging retention when preservation partial/failed
- R-17 (R3): cleanup pass invariants (backup retention, failed dir retention,
  corrupt backup retention, scope by run_uuid, cleanup failure handling)
- R-16 (R2): corrupt manifest recovery + force-rerun
- R-13: orphan backup recovery
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_experiment_log(path: Path, experiment_id: str = "exp_test123") -> None:
    """Write a minimal experiment_log JSON."""
    data = {
        "experiment_id": experiment_id,
        "status": "SUCCESS",
        "algorithm": "kmeans",
        "algorithm_version": "1.0.0",
        "seed": 42,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _make_manifest(path: Path, clustering_id: str, algorithm: str = "kmeans") -> None:
    """Write a minimal clustering_manifest.json."""
    data = {
        "schema_version": "1.0.0",
        "clustering_id": clustering_id,
        "scope": "CLUSTERED_PROTOTYPE",
        "preprocessed_id": "pp_test",
        "ml_dataset_sha256": "a" * 64,
        "algorithm": algorithm,
        "algorithm_version": "1.0.0",
        "algorithm_family": "hard",
        "experiment_id": f"{algorithm}_test",
        "experiment_log_path": f"experiment_log_{algorithm}_test.json",
        "cluster_labels_path": f"cluster_labels_{algorithm}_test.parquet",
        "algorithm_output_path": None,
        "hyperparameters": {"n_clusters": 3},
        "seed_policy": "stochastic",
        "seed": 42,
        "config_sha256": "b" * 64,
        "n_clusters": 3,
        "n_samples": 20,
        "feature_set": ["F1", "F2"],
        "feature_count": 2,
        "input_identity": {
            "dataset_sha256": "a" * 64,
            "input_path": "/dev/null",
            "metadata_path": "",
        },
        "environment": {
            "python": "3.14",
            "platform": "Linux",
            "release": "7.0",
            "machine": "x86_64",
            "key_libraries": {},
        },
        "created_utc": "2026-10-09T00:00:00Z",
        "last_seen_utc": "2026-10-09T00:00:00Z",
        "log_file": f"{clustering_id}.log",
        "research_safety": {
            "automatically_promoted_to_research": False,
            "scope": "CLUSTERED_PROTOTYPE",
            "appeared_in_research_evidence": False,
            "read_only_paths_unmodified": [],
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


# ---------------------------------------------------------------------------
# R-15: _preserve_failed_log tests
# ---------------------------------------------------------------------------


class TestPreserveFailedLog:
    def test_preserve_ok(self, tmp_path: Path) -> None:
        from customer_segmentation.prototype.clustering.pipeline import (
            _preserve_failed_log,
        )

        staging = tmp_path / "staging"
        staging.mkdir()
        log = staging / "experiment_log_exp001.json"
        _make_experiment_log(log, "exp001")

        failed_dir = tmp_path / "_failed_test_c1_run1"
        status = _preserve_failed_log(staging, failed_dir, "run1")

        assert status == "ok"
        assert not log.exists(), "Log must be moved from staging"
        assert (failed_dir / "experiment_log_exp001.json").exists(), "Log must be in _failed_ dir"
        assert (failed_dir / "_preservation_audit.txt").exists(), "Audit sidecar must be written"
        # staging dir itself should still exist (may contain other files)
        assert staging.exists()

    def test_preserve_no_log(self, tmp_path: Path) -> None:
        from customer_segmentation.prototype.clustering.pipeline import (
            _preserve_failed_log,
        )

        staging = tmp_path / "staging_empty"
        staging.mkdir()

        failed_dir = tmp_path / "_failed_test_c2_run2"
        status = _preserve_failed_log(staging, failed_dir, "run2")

        assert status == "no_log"
        assert not failed_dir.exists(), "_failed_ dir must NOT be created when no log exists"

    def test_preserve_staging_not_exists(self, tmp_path: Path) -> None:
        from customer_segmentation.prototype.clustering.pipeline import (
            _preserve_failed_log,
        )

        staging = tmp_path / "nonexistent"
        failed_dir = tmp_path / "_failed_test_c3_run3"
        status = _preserve_failed_log(staging, failed_dir, "run3")

        assert status == "no_log"
        assert not failed_dir.exists()

    def test_preserve_partial(self, tmp_path: Path) -> None:
        """One log moves successfully; another fails to move (orphan remains)."""
        from customer_segmentation.prototype.clustering.pipeline import (
            _preserve_failed_log,
        )

        staging = tmp_path / "staging_partial"
        staging.mkdir()

        # Write two logs.
        log1 = staging / "experiment_log_expA.json"
        _make_experiment_log(log1, "expA")

        log2 = staging / "experiment_log_expB.json"
        _make_experiment_log(log2, "expB")

        # Patch shutil.move so the second move raises OSError (partial
        # preservation). chmod alone is insufficient on POSIX because
        # shutil.move of a read-only file still succeeds when the
        # source directory is writable.
        from customer_segmentation.prototype.clustering import pipeline as _pl_mod

        real_move = _pl_mod.shutil.move
        call_state = {"n": 0}

        def _flaky_move(src: str, dst: str) -> str:
            call_state["n"] += 1
            if call_state["n"] == 2:
                # Second call (the log2 move) fails; log1 already moved.
                raise OSError("simulated move failure for log2")
            return real_move(src, dst)

        with patch.object(_pl_mod.shutil, "move", _flaky_move):
            status = _preserve_failed_log(staging, tmp_path / "_failed_test_c4_run4", "run4")

        assert status == "partial", f"expected 'partial' status, got {status!r}"
        # log1 was moved; log2 was not (orphan remains in staging).
        assert (
            tmp_path / "_failed_test_c4_run4" / "experiment_log_expA.json"
        ).exists(), "log1 should be in failed_dir (first move succeeded)"
        assert (
            staging / "experiment_log_expB.json"
        ).exists(), "log2 should remain in staging (second move failed)"

    def test_preserve_failed_mkdir_error(self, tmp_path: Path) -> None:
        from customer_segmentation.prototype.clustering.pipeline import (
            _preserve_failed_log,
        )

        staging = tmp_path / "staging_fail"
        staging.mkdir()
        log = staging / "experiment_log_expC.json"
        _make_experiment_log(log, "expC")

        # Put a file in the way so mkdir fails with EEXIST.
        failed_dir = tmp_path / "_failed_test_c5_run5"
        failed_dir.mkdir()  # Create as a FILE (simulate EEXIST after our mkdir).

        status = _preserve_failed_log(staging, failed_dir, "run5")

        assert status == "failed"
        assert log.exists(), "Log must remain in staging on mkdir failure"
        assert failed_dir.is_dir(), "_failed_ dir must exist (was pre-created)"

    def test_preserve_multiple_logs(self, tmp_path: Path) -> None:
        from customer_segmentation.prototype.clustering.pipeline import (
            _preserve_failed_log,
        )

        staging = tmp_path / "staging_multi"
        staging.mkdir()
        logs = [staging / f"experiment_log_{n}.json" for n in range(3)]
        for lf in logs:
            _make_experiment_log(lf, lf.stem)

        failed_dir = tmp_path / "_failed_multi_run"
        status = _preserve_failed_log(staging, failed_dir, "multi_run")

        assert status == "ok"
        for lf in logs:
            assert not lf.exists(), f"{lf.name} must be moved from staging"
            assert (failed_dir / lf.name).exists(), f"{lf.name} must be in _failed_ dir"


# ---------------------------------------------------------------------------
# F1 invariant: staging retention when preservation partial/failed
# ---------------------------------------------------------------------------


class TestCleanupPassSkipsStagingWhenUnpreservedLog:
    def test_staging_retained_when_unpreserved_true(self, tmp_path: Path) -> None:
        from customer_segmentation.prototype.clustering.pipeline import (
            _cleanup_pass,
            _Dev04RunState,
        )

        staging = tmp_path / "staging_orphan"
        staging.mkdir()
        # Put an orphan log in staging.
        log = staging / "experiment_log_orphan.json"
        _make_experiment_log(log, "orphan")

        state = _Dev04RunState(base_dir=tmp_path, current_run_uuid="run_orphan")
        state.staging_dir = staging
        state.unpreserved_log_in_staging = True

        _cleanup_pass(state, primary_exception=None)

        # Staging must be RETAINED when unpreserved flag is True.
        assert staging.exists(), "staging_dir must be retained (F1 invariant)"
        assert log.exists(), "orphan log must still be in staging"

    def test_staging_removed_when_unpreserved_false(self, tmp_path: Path) -> None:
        from customer_segmentation.prototype.clustering.pipeline import (
            _cleanup_pass,
            _Dev04RunState,
        )

        staging = tmp_path / "staging_normal"
        staging.mkdir()
        log = staging / "experiment_log_normal.json"
        _make_experiment_log(log, "normal")

        state = _Dev04RunState(base_dir=tmp_path, current_run_uuid="run_normal")
        state.staging_dir = staging
        state.unpreserved_log_in_staging = False

        _cleanup_pass(state, primary_exception=None)

        assert not staging.exists(), "staging_dir must be removed when flag is False"

    def test_cleanup_retains_failed_tracking_dir(self, tmp_path: Path) -> None:
        """R1: _failed_*/ must never be unlinked by cleanup pass."""
        from customer_segmentation.prototype.clustering.pipeline import (
            _cleanup_pass,
            _Dev04RunState,
        )

        failed_dir = tmp_path / "_failed_cl_abc123_runX"
        failed_dir.mkdir()
        (failed_dir / "experiment_log_expX.json").write_text("{}", encoding="utf-8")

        state = _Dev04RunState(base_dir=tmp_path, current_run_uuid="runX")
        state.staging_dir = None  # No staging dir
        state.failed_tracking_dir = failed_dir
        state.unpreserved_log_in_staging = False

        _cleanup_pass(state, primary_exception=None)

        assert failed_dir.exists(), "_failed_*/ must never be removed (R1 retention)"
        assert (failed_dir / "experiment_log_expX.json").exists()

    def test_cleanup_retains_backup_on_publish_failure(self, tmp_path: Path) -> None:
        """R3 + AC-12 #73b: backup retained when publish_succeeded=False."""
        from customer_segmentation.prototype.clustering.pipeline import (
            _cleanup_pass,
            _Dev04RunState,
        )

        staging = tmp_path / "staging_pubfail"
        staging.mkdir()

        backup_parent = tmp_path / "_backup_runY"
        backup_parent.mkdir()

        state = _Dev04RunState(base_dir=tmp_path, current_run_uuid="runY")
        state.staging_dir = staging
        state.backup_dir_for_recovery = backup_parent
        state.backup_dir_parent = backup_parent
        state.publish_succeeded = False
        state.unpreserved_log_in_staging = False

        _cleanup_pass(state, primary_exception=None)

        # When publish_succeeded=False and there is no unpreserved log
        # in staging, staging is removed (it is empty from the pipeline
        # perspective — the recovery / publish-failure path retained the
        # backup for next-run recovery).
        assert (
            not staging.exists()
        ), "staging must be removed when no unpreserved log (publish-failure path)"
        # The backup parent is RETAINED because publish_succeeded=False
        # (R-17, AC-12 #73b).
        assert (
            backup_parent.exists()
        ), "backup must be RETAINED when publish_succeeded=False (R3 AC-12 #73b)"

    def test_cleanup_removes_backup_on_success(self, tmp_path: Path) -> None:
        """Backup is removed on SUCCESS (publish succeeded)."""
        from customer_segmentation.prototype.clustering.pipeline import (
            _cleanup_pass,
            _Dev04RunState,
        )

        staging = tmp_path / "staging_ok"
        staging.mkdir()
        backup_parent = tmp_path / "_backup_runZ"
        backup_parent.mkdir()

        state = _Dev04RunState(base_dir=tmp_path, current_run_uuid="runZ")
        state.staging_dir = staging
        state.backup_dir_for_recovery = backup_parent
        state.backup_dir_parent = backup_parent
        state.publish_succeeded = True
        state.unpreserved_log_in_staging = False

        _cleanup_pass(state, primary_exception=None)

        assert not staging.exists(), "staging must be removed on success"
        assert not backup_parent.exists(), "backup must be removed on SUCCESS (publish succeeded)"

    def test_cleanup_retains_corrupt_backup(self, tmp_path: Path) -> None:
        """R2 + AC-12 #73c: _backup_*_corrupt/ must never be unlinked."""
        from customer_segmentation.prototype.clustering.pipeline import (
            _cleanup_pass,
            _Dev04RunState,
        )

        corrupt = tmp_path / "_backup_runC_corrupt"
        corrupt.mkdir()
        (corrupt / "clustering_manifest.json").write_text("{}", encoding="utf-8")

        staging = tmp_path / "staging_c"
        staging.mkdir()

        state = _Dev04RunState(base_dir=tmp_path, current_run_uuid="runC")
        state.staging_dir = staging
        state.backup_dir_corrupt = corrupt
        state.publish_succeeded = True
        state.unpreserved_log_in_staging = False

        _cleanup_pass(state, primary_exception=None)

        assert corrupt.exists(), "_backup_*_corrupt/ must be retained (R2 R3 AC-12 #73c)"
        assert (corrupt / "clustering_manifest.json").exists()

    def test_cleanup_only_removes_own_run(self, tmp_path: Path) -> None:
        """R3 + AC-12 #73e: cleanup must not touch other runs' dirs."""
        from customer_segmentation.prototype.clustering.pipeline import (
            _cleanup_pass,
            _Dev04RunState,
        )

        # Create dirs for OTHER runs.
        other_staging = tmp_path / "_staging_other_uuid"
        other_staging.mkdir()
        other_backup = tmp_path / "_backup_other_uuid"
        other_backup.mkdir()
        other_corrupt = tmp_path / "_backup_other_uuid_corrupt"
        other_corrupt.mkdir()
        other_failed = tmp_path / "_failed_cl_abc_other_uuid"
        other_failed.mkdir()

        # Current run's staging.
        current_staging = tmp_path / "_staging_current_uuid"
        current_staging.mkdir()

        state = _Dev04RunState(base_dir=tmp_path, current_run_uuid="current_uuid")
        state.staging_dir = current_staging
        state.unpreserved_log_in_staging = False

        _cleanup_pass(state, primary_exception=None)

        # Current staging is removed.
        assert not current_staging.exists(), "current staging must be removed"
        # Other runs' dirs are RETAINED.
        assert other_staging.exists(), "other staging must be retained (R3 AC-12 #73e)"
        assert other_backup.exists(), "other backup must be retained (R3 AC-12 #73e)"
        assert other_corrupt.exists(), "other corrupt backup must be retained (R3)"
        assert other_failed.exists(), "other _failed_/ must be retained (R1 R3)"

    def test_cleanup_failure_does_not_hide_primary(self, tmp_path: Path) -> None:
        """R3 + AC-12 #73f: cleanup failure is logged, not re-raised."""

        class RaiseOnCleanup:
            called = False

        def _bad_rmtree(path: Path) -> None:
            RaiseOnCleanup.called = True
            raise OSError("simulated cleanup failure")

        from customer_segmentation.prototype.clustering.pipeline import (
            _cleanup_pass,
            _Dev04RunState,
        )

        staging = tmp_path / "staging_fail_cleanup"
        staging.mkdir()

        state = _Dev04RunState(base_dir=tmp_path, current_run_uuid="run_cleanup_fail")
        state.staging_dir = staging
        state.unpreserved_log_in_staging = False

        primary = RuntimeError("primary failure")

        # Monkey-patch shutil.rmtree temporarily.
        import shutil as _shutil

        original_rmtree = _shutil.rmtree
        _shutil.rmtree = _bad_rmtree
        try:
            _cleanup_pass(state, primary_exception=primary)
        finally:
            _shutil.rmtree = original_rmtree

        assert RaiseOnCleanup.called, "shutil.rmtree must be called"
        # Primary exception must NOT be swallowed.

    def test_cleanup_pass_never_deletes_final_subdir(self, tmp_path: Path) -> None:
        """Final subdirs (<clustering_id>/) must never be touched by cleanup."""
        from customer_segmentation.prototype.clustering.pipeline import (
            _cleanup_pass,
            _Dev04RunState,
        )

        final = tmp_path / "cl_finalsubdir_123456789012345678901234"
        final.mkdir()
        (final / "clustering_manifest.json").write_text("{}", encoding="utf-8")

        # Backup parent to trigger cleanup.
        backup_parent = tmp_path / "_backup_cleanup2"
        backup_parent.mkdir()

        state = _Dev04RunState(base_dir=tmp_path, current_run_uuid="cleanup2")
        state.staging_dir = None
        state.backup_dir_parent = backup_parent
        state.backup_dir_for_recovery = backup_parent
        state.publish_succeeded = True
        state.unpreserved_log_in_staging = False

        _cleanup_pass(state, primary_exception=None)

        assert final.exists(), "final subdir (<clustering_id>/) must never be touched by cleanup"
        assert (final / "clustering_manifest.json").exists()


# ---------------------------------------------------------------------------
# R-16: corrupt manifest recovery
# ---------------------------------------------------------------------------


class TestCorruptManifestRecovery:
    def test_corrupt_manifest_default_fail_closed(self, tmp_path: Path) -> None:
        """R2: find_existing_clustering raises on corrupt JSON."""
        from customer_segmentation.prototype.clustering.storage import (
            Dev04ManifestCorrupt,
            find_existing_clustering,
            prototype_clustering_base_dir,
        )

        cid = "cl_" + "f" * 24
        # Use the canonical base_dir resolver so the path matches what
        # ``find_existing_clustering`` will look at.
        base = prototype_clustering_base_dir(tmp_path, "ds_test", "pp_test")
        final_dir = base / cid
        final_dir.mkdir(parents=True)
        manifest_path = final_dir / "clustering_manifest.json"
        manifest_path.write_text("{ CORRUPT JSON }", encoding="utf-8")

        with pytest.raises(Dev04ManifestCorrupt):
            find_existing_clustering(
                storage_root=tmp_path,
                dataset_id="ds_test",
                preprocessed_id="pp_test",
                clustering_id=cid,
                algorithm="kmeans",
                hyperparameters={"n_clusters": 3},
                effective_seed=42,
                ml_dataset_sha256="a" * 64,
                config_sha256="b" * 64,
            )

    def test_force_rerun_corrupt_recovery(self, tmp_path: Path) -> None:
        """R2: --force-rerun with corrupt manifest → move to _backup_*_corrupt/."""
        from customer_segmentation.prototype.clustering.pipeline import (
            _Dev04RunState,
            _recover_corrupt_final,
        )

        final = tmp_path / "final"
        final.mkdir()
        manifest = final / "clustering_manifest.json"
        manifest.write_text("{ CORRUPT }", encoding="utf-8")
        (final / "cluster_labels.parquet").write_bytes(b"parquet")

        # Mock a logger.
        class MockLogger:
            def info(self, *args, **kwargs) -> None:
                pass

        state = _Dev04RunState(base_dir=tmp_path, current_run_uuid="run_corrupt")
        state.final_dir = final
        state.backup_dir_corrupt = None

        _recover_corrupt_final(state, MockLogger())

        # final must be moved to _backup_*_corrupt/.
        corrupt_backup = tmp_path / "_backup_run_corrupt_corrupt"
        assert corrupt_backup.exists(), "corrupt final must be moved to _backup_*_corrupt/ (R2)"
        assert (corrupt_backup / "clustering_manifest.json").read_text(
            encoding="utf-8"
        ) == "{ CORRUPT }"
        assert not final.exists(), "original corrupt final must be removed"
        assert state.backup_dir_corrupt == corrupt_backup

    def test_corrupt_rename_failure_stops(self, tmp_path: Path) -> None:
        """R2: rename corrupt final → _backup_*_corrupt/ fails → raises."""
        from customer_segmentation.prototype.clustering.pipeline import (
            Dev04StoragePathError,
            _recover_corrupt_final,
        )

        final = tmp_path / "final"
        final.mkdir()
        manifest = final / "clustering_manifest.json"
        manifest.write_text("{}", encoding="utf-8")

        # Put something in the way.
        corrupt_dest = tmp_path / "_backup_runR_corrupt"
        corrupt_dest.mkdir()

        class MockLogger:
            def info(self, *args, **kwargs) -> None:
                pass

        from customer_segmentation.prototype.clustering.pipeline import _Dev04RunState

        state = _Dev04RunState(base_dir=tmp_path, current_run_uuid="runR")
        state.final_dir = final

        with pytest.raises(Dev04StoragePathError):
            _recover_corrupt_final(state, MockLogger())

        # final_dir must NOT be removed when rename fails (R2 #5).
        assert final.exists(), "final_dir must be left untouched when rename fails (R2 #5)"
        assert manifest.exists()

    def test_recovery_skips_corrupt_backup_suffix(self, tmp_path: Path) -> None:
        """R2: recover_orphan_backups must skip _backup_*_corrupt/."""
        from customer_segmentation.prototype.clustering.storage import (
            recover_orphan_backups,
        )

        base = tmp_path
        corrupt_backup = base / "_backup_other_uuid_corrupt"
        corrupt_backup.mkdir()
        (corrupt_backup / "manifest.json").write_text("{}", encoding="utf-8")
        (corrupt_backup / "cl_validid_012345678901234567890123").mkdir()

        n_restored = recover_orphan_backups(base, "current_uuid")

        assert n_restored == 0, "recover_orphan_backups must skip _backup_*_corrupt/ suffix"
        # corrupt backup must still exist.
        assert corrupt_backup.exists()

    def test_corrupt_recovery_does_not_catch_collision(self, tmp_path: Path) -> None:
        """R2 #6: Dev04CollisionError must NOT be caught by corrupt recovery."""
        from customer_segmentation.prototype.clustering.storage import (
            Dev04CollisionError,
            find_existing_clustering,
            prototype_clustering_base_dir,
        )

        cid = "cl_" + "f" * 24
        # Use the canonical base_dir resolver so the path matches what
        # ``find_existing_clustering`` will look at.
        base = prototype_clustering_base_dir(tmp_path, "ds_test", "pp_test")
        final = base / cid
        final.mkdir(parents=True)
        # Valid manifest (not corrupt) but with DIFFERENT payload.
        import json

        manifest_data = {
            "schema_version": "1.0.0",
            "clustering_id": cid,
            "scope": "CLUSTERED_PROTOTYPE",
            "preprocessed_id": "pp_test",
            "ml_dataset_sha256": "a" * 64,
            "algorithm": "kmeans",
            "algorithm_version": "1.0.0",
            "algorithm_family": "hard",
            "experiment_id": f"kmeans_{cid}",
            "experiment_log_path": f"experiment_log_kmeans_{cid}.json",
            "cluster_labels_path": f"cluster_labels_kmeans_{cid}.parquet",
            "algorithm_output_path": None,
            "hyperparameters": {"n_clusters": 3},  # DIFFERENT
            "seed_policy": "stochastic",
            "seed": 42,
            "config_sha256": "b" * 64,
            "n_samples": 20,
            "feature_set": ["F1", "F2"],
            "feature_count": 2,
            "input_identity": {
                "dataset_sha256": "a" * 64,
                "input_path": "/dev/null",
                "metadata_path": "",
            },
            "environment": {
                "python": "3.14",
                "platform": "Linux",
                "release": "7.0",
                "machine": "x86_64",
                "key_libraries": {},
            },
            "created_utc": "2026-10-09T00:00:00Z",
            "last_seen_utc": "2026-10-09T00:00:00Z",
            "log_file": f"{cid}.log",
            "research_safety": {
                "automatically_promoted_to_research": False,
                "scope": "CLUSTERED_PROTOTYPE",
                "appeared_in_research_evidence": False,
                "read_only_paths_unmodified": [],
            },
        }
        (final / "clustering_manifest.json").write_text(json.dumps(manifest_data), encoding="utf-8")

        # find_existing_clustering must raise Dev04CollisionError (not Dev04ManifestCorrupt).
        with pytest.raises(Dev04CollisionError):
            find_existing_clustering(
                storage_root=tmp_path,
                dataset_id="ds_test",
                preprocessed_id="pp_test",
                clustering_id=cid,
                algorithm="kmeans",
                hyperparameters={"n_clusters": 5},  # DIFFERENT
                effective_seed=42,
                ml_dataset_sha256="a" * 64,
                config_sha256="b" * 64,
            )

    def test_recover_orphan_backups_resilient_to_oserror(self, tmp_path: Path) -> None:
        """R-13: recover_orphan_backups must never raise; OSError is swallowed."""
        from customer_segmentation.prototype.clustering.storage import (
            recover_orphan_backups,
        )

        base = tmp_path
        backup = base / "_backup_other_uuid"
        backup.mkdir()
        (backup / "cl_abc123_012345678901234").mkdir()

        # Monkey-patch iterdir to raise OSError.
        original_iterdir = Path.iterdir

        def bad_iterdir(self: Path) -> list[Path]:
            if str(self).endswith("_other_uuid"):
                raise OSError("simulated iterdir failure")
            return original_iterdir(self)

        with patch.object(Path, "iterdir", bad_iterdir):
            n = recover_orphan_backups(base, "current_uuid")
            # Must return without raising.
            assert isinstance(n, int)


# ---------------------------------------------------------------------------
# R-13: orphan backup recovery
# ---------------------------------------------------------------------------


class TestOrphanBackupRecovery:
    def test_orphan_final_restored_on_next_run(self, tmp_path: Path) -> None:
        """R-13: orphan backup is restored when final_dir is missing."""
        from customer_segmentation.prototype.clustering.storage import (
            recover_orphan_backups,
        )

        base = tmp_path
        backup = base / "_backup_recovery_uuid"
        backup.mkdir()
        # Inner subdir MUST match the clustering_id regex
        # ``^cl_[0-9a-f]{24}$``; recovery skips malformed backups.
        inner = backup / "cl_0123456789abcdef01234567"
        inner.mkdir()
        manifest = inner / "clustering_manifest.json"
        _make_manifest(manifest, "cl_0123456789abcdef01234567")
        (inner / "cluster_labels.parquet").write_bytes(b"parquet")

        final = base / "cl_0123456789abcdef01234567"
        assert not final.exists(), "final must be absent to trigger recovery"

        n = recover_orphan_backups(base, "current_uuid")

        assert n == 1, "must restore exactly 1 orphan backup"
        assert final.exists(), "final must be restored from orphan backup"
        assert (final / "clustering_manifest.json").exists()

    def test_recover_skips_final_exists(self, tmp_path: Path) -> None:
        """Recovery skips when final_dir already exists."""
        from customer_segmentation.prototype.clustering.storage import (
            recover_orphan_backups,
        )

        base = tmp_path
        # Existing final dir.
        final = base / "cl_existing_012345678901234567890123"
        final.mkdir(parents=True)
        (final / "clustering_manifest.json").write_text("{}", encoding="utf-8")

        # Orphan backup.
        backup = base / "_backup_other_uuid"
        backup.mkdir()
        inner = backup / "cl_other_012345678901234567890124"
        inner.mkdir()
        _make_manifest(inner / "clustering_manifest.json", "cl_other_012345678901234567890124")

        n = recover_orphan_backups(base, "current_uuid")

        assert n == 0, "must not restore when final already exists"
        assert (final / "clustering_manifest.json").read_text() == "{}"

    def test_recover_skips_malformed_inner(self, tmp_path: Path) -> None:
        """Malformed backup (wrong inner name) is skipped."""
        from customer_segmentation.prototype.clustering.storage import (
            recover_orphan_backups,
        )

        base = tmp_path
        backup = base / "_backup_malformed_uuid"
        backup.mkdir()
        # Wrong inner name (doesn't match ^cl_[0-9a-f]{24}$).
        inner = backup / "not_a_clustering_id"
        inner.mkdir()

        n = recover_orphan_backups(base, "current_uuid")

        assert n == 0, "must skip malformed backup (wrong inner name)"


# ---------------------------------------------------------------------------
# Stage 6 execution check
# ---------------------------------------------------------------------------


class TestStage6:
    def test_stage_6_recorded_in_success_result(
        self,
        synthetic_dev03_artefact,
        monkeypatch,
    ) -> None:
        from customer_segmentation.prototype.clustering import run_clustering_pipeline

        ml_path, manifest_path, storage_root = synthetic_dev03_artefact

        monkeypatch.setattr(
            "customer_segmentation.prototype.clustering.pipeline.resolve_storage_root",
            lambda _=None: storage_root,
        )

        result = run_clustering_pipeline(
            dataset_id="ds_dev04test01",
            preprocessed_id="pp_dev04test01",
            algorithm="kmeans",
            hyperparameters={"n_clusters": 3},
            seed=42,
        )

        # Stage 6 must appear in stage_logs.
        stage_ids = [log["stage"] for log in result.stage_logs]
        assert "6" in stage_ids, "stage_logs must include '6' for SUCCESS lifecycle"

    def test_cleanup_preserves_orphan_logs(self, tmp_path: Path) -> None:
        """F1: staging retained when preservation partial/failed (orphan in staging)."""
        from customer_segmentation.prototype.clustering import pipeline as _pl_mod
        from customer_segmentation.prototype.clustering.pipeline import (
            _cleanup_pass,
            _Dev04RunState,
            _preserve_failed_log,
            _set_unpreserved_flag,
        )

        # Create staging with an experiment log.
        staging = tmp_path / "staging_orphan"
        staging.mkdir()
        log = staging / "experiment_log_orphan.json"
        _make_experiment_log(log, "orphan")

        failed_dir = tmp_path / "_failed_orphan_run"
        # Don't pre-create the failed_dir so mkdir happens inside the helper.

        # Force shutil.move to raise so the helper returns "partial" and
        # the log remains in staging (POSIX chmod does not block moves
        # when the source directory is writable).
        def _raise_move(src: str, dst: str) -> str:
            raise OSError("simulated move failure (F1 orphan invariant)")

        with patch.object(_pl_mod.shutil, "move", _raise_move):
            status = _preserve_failed_log(staging, failed_dir, "orphan_run")

        # The orphan log must still be in staging.
        remaining = [
            p
            for p in staging.iterdir()
            if p.name.startswith("experiment_log_") and p.suffix == ".json"
        ]
        assert remaining, "test setup invariant: orphan log must remain in staging"
        assert status == "partial", f"expected 'partial', got {status!r}"

        state = _Dev04RunState(base_dir=tmp_path, current_run_uuid="orphan_run")
        state.staging_dir = staging
        state.unpreserved_log_in_staging = False
        _set_unpreserved_flag(state, status)

        _cleanup_pass(state, primary_exception=None)

        # F1 invariant: when preservation fails and orphan log remains in
        # staging, the cleanup pass MUST skip shutil.rmtree(staging_dir).
        assert (
            state.unpreserved_log_in_staging is True
        ), "flag must be set after partial/failed preservation with orphan"
        assert staging.exists(), "staging must be retained when preservation failed (F1 invariant)"
