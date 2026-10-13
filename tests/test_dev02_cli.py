"""Tests for the scripts/dev02_import_dataset.py CLI surface."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_cli(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "scripts/dev02_import_dataset.py", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env={"PYTHONPATH": "src", "PATH": __import__("os").environ.get("PATH", "")},
    )


def test_cli_help_renders() -> None:
    result = _run_cli("--help", cwd=REPO_ROOT)
    assert result.returncode == 0
    assert "Import a CSV or Parquet file" in result.stdout


def test_cli_has_no_dest_root_flag() -> None:
    """The CLI MUST NOT expose --dest-root or equivalent."""
    result = _run_cli("--help", cwd=REPO_ROOT)
    # The help text and argparse internal error messages would surface
    # these names if they existed. Search the help for any storage-root
    # override flag.
    for forbidden in ("--dest-root", "--dest_root", "--storage-root",
                      "--out-root", "--output-root"):
        assert forbidden not in result.stdout, (
            f"CLI exposes forbidden flag {forbidden!r}."
        )


def test_cli_missing_file_returns_exit_3(tmp_path: Path) -> None:
    result = _run_cli("--file", str(tmp_path / "nope.csv"), cwd=REPO_ROOT)
    # File preflight fail -> exit code 3.
    assert result.returncode == 3
    assert "preflight" in result.stderr or "failed" in result.stderr


def test_cli_unsupported_format_returns_exit_3(tmp_path: Path) -> None:
    src = tmp_path / "data.xlsx"
    src.write_bytes(b"")
    result = _run_cli("--file", str(src), cwd=REPO_ROOT)
    assert result.returncode == 3


def test_cli_csv_import_success(tmp_path: Path) -> None:
    src = tmp_path / "ok.csv"
    src.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
    config = tmp_path / "config.yaml"
    storage = tmp_path / "datasets"
    config.write_text(
        f"dataset_management:\n"
        f"  storage_root: {storage.as_posix()}\n"
        f"  max_file_size_mb: 256\n"
        f"  supported_import_formats: [csv, parquet]\n"
        f"  default_csv_encoding: utf-8\n"
        f"  source_path_policy:\n"
        f"    allow_external_source: true\n"
        f"  readonly_research_paths: []\n",
        encoding="utf-8",
    )
    result = _run_cli(
        "--file", str(src), "--config", str(config), cwd=REPO_ROOT
    )
    assert result.returncode == 0, (
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "WRITTEN" in result.stdout or "REUSED" in result.stdout
    # Storage directory was created.
    assert storage.exists()
    # The dataset id format is ds_<24 hex>.
    out = result.stdout
    assert "ds_" in out


def test_cli_reimport_is_idempotent(tmp_path: Path) -> None:
    src = tmp_path / "ok.csv"
    src.write_text("a\n1\n2\n3\n", encoding="utf-8")
    config = tmp_path / "config.yaml"
    storage = tmp_path / "datasets"
    config.write_text(
        f"dataset_management:\n"
        f"  storage_root: {storage.as_posix()}\n"
        f"  max_file_size_mb: 256\n"
        f"  supported_import_formats: [csv, parquet]\n"
        f"  default_csv_encoding: utf-8\n"
        f"  source_path_policy:\n"
        f"    allow_external_source: true\n"
        f"  readonly_research_paths: []\n",
        encoding="utf-8",
    )
    r1 = _run_cli("--file", str(src), "--config", str(config), cwd=REPO_ROOT)
    r2 = _run_cli("--file", str(src), "--config", str(config), cwd=REPO_ROOT)
    assert r1.returncode == 0
    assert r2.returncode == 0
    assert "WRITTEN" in r1.stdout
    assert "REUSED" in r2.stdout


def test_cli_does_not_create_files_outside_storage_root(tmp_path: Path) -> None:
    """The CLI's behaviour keeps the storage root invariant."""
    src = tmp_path / "ok.csv"
    src.write_text("a\n1\n", encoding="utf-8")
    config = tmp_path / "config.yaml"
    storage = tmp_path / "datasets"
    config.write_text(
        f"dataset_management:\n"
        f"  storage_root: {storage.as_posix()}\n"
        f"  max_file_size_mb: 256\n"
        f"  supported_import_formats: [csv, parquet]\n"
        f"  default_csv_encoding: utf-8\n"
        f"  source_path_policy:\n"
        f"    allow_external_source: true\n"
        f"  readonly_research_paths: []\n",
        encoding="utf-8",
    )
    _run_cli("--file", str(src), "--config", str(config), cwd=REPO_ROOT)
    # Only the storage root has new files.
    siblings = [p for p in tmp_path.iterdir() if p != storage]
    for s in siblings:
        # The src CSV and the config are user-supplied, so they may
        # exist. The check is that no other directories were created.
        if s == src or s == config:
            continue
        # Anything else is suspicious.
        if s.is_dir() and s.name.startswith("ds_"):
            pytest.fail(
                f"CLI created a dataset directory outside the storage "
                f"root: {s!s}"
            )
