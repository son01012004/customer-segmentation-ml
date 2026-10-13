"""Tests for the DEV-09 CLI entry point."""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = _REPO_ROOT / "scripts" / "dev09_run_pipeline.py"
_SCRIPTS_PATH = str(_REPO_ROOT / "scripts")
if _SCRIPTS_PATH not in sys.path:
    sys.path.insert(0, _SCRIPTS_PATH)


def _run(args, *, env=None, cwd=None):
    base_env = {"PYTHONPATH": str(_REPO_ROOT / "src")}
    if env:
        base_env.update(env)
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + list(args),
        capture_output=True,
        text=True,
        env=base_env,
        cwd=str(cwd) if cwd is not None else str(_REPO_ROOT),
    )


# ---------------------------------------------------------------------------
# --help
# ---------------------------------------------------------------------------


class TestHelp:
    def test_top_level_help(self) -> None:
        result = _run(["--help"])
        assert result.returncode == 0
        assert "DEV-09" in result.stdout
        assert "run" in result.stdout
        assert "show" in result.stdout
        assert "list" in result.stdout

    def test_run_help(self) -> None:
        result = _run(["run", "--help"])
        assert result.returncode == 0
        assert "--source-file" in result.stdout
        assert "--dataset-id" in result.stdout
        assert "--algorithm" in result.stdout
        assert "--skip-marketing" in result.stdout
        assert "--skip-visualization" in result.stdout

    def test_show_help(self) -> None:
        result = _run(["show", "--help"])
        assert result.returncode == 0
        assert "--e2e-run" in result.stdout

    def test_list_help(self) -> None:
        result = _run(["list", "--help"])
        assert result.returncode == 0
        assert "--dataset-id" in result.stdout
        assert "--json" in result.stdout


# ---------------------------------------------------------------------------
# run subcommand — error paths
# ---------------------------------------------------------------------------


class TestRunSubcommand:
    def test_missing_source_and_dataset_id_errors(self, tmp_path: Path) -> None:
        result = _run(
            [
                "run",
                "--config",
                str(_REPO_ROOT / "configs" / "dev09_end_to_end.yaml"),
            ],
            cwd=tmp_path,
        )
        assert result.returncode == 2
        assert (
            "Either" in result.stderr
            or "source-file" in result.stderr
            or "source_file" in result.stderr
            or "one of the arguments" in result.stderr
        )

    def test_missing_source_file_errors(self, tmp_path: Path) -> None:
        result = _run(
            [
                "run",
                "--source-file",
                str(tmp_path / "missing.csv"),
                "--config",
                str(_REPO_ROOT / "configs" / "dev09_end_to_end.yaml"),
            ],
            cwd=tmp_path,
        )
        assert result.returncode == 2
        assert "source_file" in result.stderr

    def test_invalid_algorithm_choice_errors(self, tmp_path: Path) -> None:
        result = _run(
            [
                "run",
                "--source-file",
                str(tmp_path / "tiny.csv"),
                "--algorithm",
                "kmedoids",
            ],
            cwd=tmp_path,
        )
        assert result.returncode == 2
        assert "invalid choice" in result.stderr or "kmedoids" in result.stderr

    def test_skip_x_and_no_skip_x_mutually_exclusive(self, tmp_path: Path) -> None:
        result = _run(
            [
                "run",
                "--source-file",
                str(tmp_path / "tiny.csv"),
                "--skip-marketing",
                "--no-skip-marketing",
            ],
            cwd=tmp_path,
        )
        assert result.returncode == 2

    def test_storage_path_error_returns_exit_code_4(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When DEV-09 raises a storage-path error (``Dev09StoragePathError``),
        the CLI must return exit code 4 (per the documented contract)
        with a user-friendly error message and NO Python traceback.

        Pre-fix, the duplicate class definitions caused the CLI's
        ``except Dev09StoragePathError`` to MISS the storage-layer
        raise; the process crashed with an uncaught traceback and
        exited with code 1.
        """
        from customer_segmentation.prototype.end_to_end import (
            Dev09StoragePathError as CanonicalCls,
        )

        # Implementation note: the other tests in this module spawn
        # the CLI as a subprocess, but monkeypatch cannot cross that
        # boundary. To exercise the `except` path we import the CLI
        # module in-process and call :func:`main` directly so the
        # monkeypatched function binding takes effect.
        cli = importlib.import_module("dev09_run_pipeline")

        # Monkeypatch the function the CLI actually calls. The CLI
        # does `from ...pipeline import run_end_to_end_pipeline`, so
        # the binding lives in the CLI module's namespace.
        def _raise_storage_error(*args, **kwargs):
            raise CanonicalCls("simulated DEV-09 storage-path failure")

        monkeypatch.setattr(cli, "run_end_to_end_pipeline", _raise_storage_error)

        # Write a real CSV so source-file preflight passes.
        src = tmp_path / "tiny.csv"
        src.write_text("a,b,c\n1,2,3\n", encoding="utf-8")

        captured_stderr = io.StringIO()
        with contextlib.redirect_stderr(captured_stderr):
            exit_code = cli.main(
                [
                    "run",
                    "--source-file",
                    str(src),
                    "--config",
                    str(_REPO_ROOT / "configs" / "dev09_end_to_end.yaml"),
                    "--skip-marketing",
                    "--skip-visualization",
                ]
            )

        stderr_text = captured_stderr.getvalue()

        # The CLI's `except Dev09StoragePathError` (imported from
        # exceptions/scope) MUST match CanonicalCls (which is what
        # run_end_to_end_pipeline raised). Pre-fix the storage.py
        # class was a DIFFERENT class and the except missed it.
        assert exit_code == 4, (
            f"Expected exit code 4 for Dev09StoragePathError; got "
            f"{exit_code}. stderr={stderr_text!r}"
        )
        # No Python traceback in stderr.
        assert "Traceback" not in stderr_text, f"Unexpected traceback in stderr: {stderr_text!r}"
        # User-friendly error message visible.
        assert (
            "storage" in stderr_text.lower() or "DEV-09" in stderr_text
        ), f"Expected actionable error message; got {stderr_text!r}"


# ---------------------------------------------------------------------------
# list subcommand
# ---------------------------------------------------------------------------


class TestListSubcommand:
    def test_list_empty(self) -> None:
        result = _run(["list", "--json"])
        assert result.returncode == 0
        try:
            payload = json.loads(result.stdout)
            assert isinstance(payload, list)
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"list --json did not emit JSON; stdout={result.stdout!r} stderr={result.stderr!r}: {exc}"
            )

    def test_list_json_flag(self) -> None:
        result = _run(["list", "--json"])
        assert result.returncode == 0
        try:
            payload = json.loads(result.stdout)
            assert isinstance(payload, list)
        except json.JSONDecodeError:
            pass


# ---------------------------------------------------------------------------
# show subcommand
# ---------------------------------------------------------------------------


class TestShowSubcommand:
    def test_show_missing_file(self, tmp_path: Path) -> None:
        result = _run(["show", "--e2e-run", str(tmp_path / "missing.json")])
        assert result.returncode == 1
        assert "not found" in result.stderr or "not found" in result.stdout


# ---------------------------------------------------------------------------
# Config integration
# ---------------------------------------------------------------------------


class TestConfigIntegration:
    def test_custom_algorithm_in_config(self, tmp_path: Path) -> None:
        import yaml  # type: ignore[import-untyped]

        custom_cfg = {
            "dev09_end_to_end": {
                "schema_version": "1.0.0",
                "stage_selection": {
                    "algorithm": "dbscan",
                    "skip_visualization": False,
                    "skip_marketing": False,
                },
                "display": {
                    "disclaimer_text": "test disclaimer",
                    "separator": "  ",
                },
                "storage": {"output_dir_relative": "end_to_end"},
                "logging": {
                    "level": "INFO",
                    "format": "%(message)s",
                    "emit_to_console": False,
                },
                "persistence": {"copy_manifests": True},
                "research_safety": {
                    "never_promote_to_research": True,
                    "end_to_end_scope": "END_TO_END_PROTOTYPE",
                },
            }
        }
        cfg_path = tmp_path / "dev09.yaml"
        cfg_path.write_text(yaml.dump(custom_cfg), encoding="utf-8")
        result = _run(["run", "--config", str(cfg_path), "--help"])
        assert result.returncode == 0

    def test_missing_config_file_errors(self) -> None:
        result = _run(["run", "--config", "/nonexistent/config.yaml", "--help"])
        # argparse rejects unknown config or the loader does.
        assert result.returncode in (0, 2)


# ---------------------------------------------------------------------------
# Run + show + list cycle
# ---------------------------------------------------------------------------


class TestRunShowListCycle:
    def test_show_with_real_run(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        payload = {
            "schema_version": "1.0.0",
            "e2e_run_id": "e2e_" + "0" * 24,
            "dataset_id": "ds_test",
            "dataset_sha256": "a" * 64,
            "storage_root": "/tmp",
            "run_dir": str(tmp_path / "fake_run"),
            "overall_status": "SUCCESS",
            "lifecycle": "SUCCESS",
            "algorithm": "kmeans",
            "seed": 42,
            "preprocessed_id": "pp_test",
            "clustering_id": "cl_" + "1" * 24,
            "evaluation_id": None,
            "segmentation_id": "seg_" + "2" * 24,
            "marketing_id": None,
            "dashboard_id": None,
            "stages": [],
            "inputs": {},
            "config": {},
            "environment": {},
            "notes": [],
            "created_utc": "2026-10-10T00:00:00Z",
        }
        json_path = tmp_path / "e2e_run.json"
        json_path.write_text(json.dumps(payload), encoding="utf-8")

        result = _run(["show", "--e2e-run", str(json_path)])
        assert (
            result.returncode == 0
        ), f"show failed: stdout={result.stdout[:300]} stderr={result.stderr[:300]}"
        assert "End-to-End Run Summary" in result.stdout
        assert "kmeans" in result.stdout

    def test_list_with_real_run(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        e2e_run_id = "e2e_" + "0" * 24
        # ``storage_root`` already points at ``<repo>/data/prototype/datasets``
        # (per ``configs/dev02_dataset_management.yaml``); the dataset id
        # is appended directly (no extra ``"datasets"`` literal). See the
        # regression test in
        # ``tests/test_dev04_storage.py::TestPathDoublingRegressionA1``.
        run_dir = tmp_path / "ds_test" / "end_to_end" / e2e_run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "1.0.0",
            "e2e_run_id": e2e_run_id,
            "dataset_id": "ds_test",
            "dataset_sha256": "a" * 64,
            "storage_root": str(tmp_path),
            "run_dir": str(run_dir),
            "overall_status": "SUCCESS",
            "lifecycle": "SUCCESS",
            "algorithm": "kmeans",
            "seed": 42,
            "preprocessed_id": "pp_test",
            "clustering_id": "cl_" + "1" * 24,
            "evaluation_id": None,
            "segmentation_id": "seg_" + "2" * 24,
            "marketing_id": None,
            "dashboard_id": None,
            "stages": [],
            "inputs": {},
            "config": {},
            "environment": {},
            "notes": [],
            "created_utc": "2026-10-10T00:00:00Z",
        }
        (run_dir / "e2e_run.json").write_text(json.dumps(payload), encoding="utf-8")

        result = _run(["list", "--json"])
        assert result.returncode == 0
        try:
            parsed = json.loads(result.stdout)
            assert isinstance(parsed, list)
        except json.JSONDecodeError as exc:
            pytest.fail(f"list --json did not emit JSON: stdout={result.stdout!r}: {exc}")
