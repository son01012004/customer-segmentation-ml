"""Tests for the DEV-08 CLI script (scripts/dev08_run_dashboard.py)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from customer_segmentation.prototype.segmentation.manifest import (
    FeatureProfile,
    SegmentationValidationReport,
    SegmentSize,
    build_segmentation_manifest,
    write_segmentation_manifest,
)

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "dev08_run_dashboard.py"
_REPO_ROOT = Path(__file__).resolve().parents[1]


def _seg_args(**overrides):
    base = {
        "segmentation_id": "seg_" + "0" * 24,
        "clustering_id": "cl_" + "1" * 24,
        "preprocessed_id": "pp_x",
        "dataset_id": "ds_x",
        "evaluation_id": None,
        "algorithm": "kmeans",
        "algorithm_version": "1.0",
        "algorithm_family": "hard",
        "ml_dataset_sha256": "a" * 64,
        "feature_set_sha256": "b" * 64,
        "preprocessing_config_sha256": "c" * 64,
        "feature_set": ["Recency", "Frequency", "Monetary"],
        "n_samples_input": 1000,
        "n_samples_used_for_compute": 1000,
        "n_clusters_input": 3,
        "n_segments": 3,
        "noise_count": None,
        "noise_ratio": None,
        "noise_policy_used": "exclude",
        "segment_sizes": [
            SegmentSize(0, 400, 40.0, "n_samples_used_for_compute", False),
            SegmentSize(1, 350, 35.0, "n_samples_used_for_compute", False),
            SegmentSize(2, 250, 25.0, "n_samples_used_for_compute", False),
        ],
        "profiles": [FeatureProfile(0, "Recency", {"mean": 5.0})],
        "characteristics": [],
        "config_sha256": "d" * 64,
        "environment": {
            "python": "3.14",
            "platform": "Linux",
            "release": "7.0",
            "machine": "x86_64",
            "key_libraries": {"pandas": "2.0"},
        },
        "log_file": "seg.log",
        "validation_report": SegmentationValidationReport(all_passed=True, checks=[]),
        "readonly_paths": ["data/raw/primary"],
        "input_clustering_manifest": "clustering_manifest.json",
        "input_cluster_labels": "cluster_labels_x.parquet",
        "input_ml_dataset": "ml_dataset_x.parquet",
        "input_evaluation_manifest": None,
    }
    base.update(overrides)
    return base


def _run(args, *, env=None, cwd=None):
    """Invoke the CLI script and return (rc, stdout, stderr).

    PYTHONPATH is set to ``<repo_root>/src`` so the subprocess can
    import :mod:`customer_segmentation`; without this, the script
    raises :class:`ModuleNotFoundError` (the same convention used by
    ``test_dev06_cli.py`` and ``test_dev07_cli.py``).
    """
    base_env = {"PYTHONPATH": str(_REPO_ROOT / "src")}
    if env:
        base_env.update(env)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)] + list(args),
        capture_output=True,
        text=True,
        env=base_env,
        cwd=cwd if cwd is not None else str(_REPO_ROOT),
        timeout=120,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _repo_root() -> Path:
    return _REPO_ROOT


# ---------------------------------------------------------------------------
# --help
# ---------------------------------------------------------------------------


def test_cli_help() -> None:
    rc, out, err = _run(["--help"], cwd=str(_repo_root()))
    assert rc == 0
    assert "DEV-08 Prototype Visualization Dashboard" in out


def test_cli_render_help() -> None:
    rc, out, err = _run(["render", "--help"], cwd=str(_repo_root()))
    assert rc == 0
    assert "--segmentation-manifest" in out


def test_cli_summary_help() -> None:
    rc, out, err = _run(["summary", "--help"], cwd=str(_repo_root()))
    assert rc == 0
    assert "--dashboard-summary" in out


# ---------------------------------------------------------------------------
# render: validation failures
# ---------------------------------------------------------------------------


def test_cli_render_requires_seg_id_or_path() -> None:
    rc, out, err = _run(["render"], cwd=str(_repo_root()))
    assert rc != 0
    # argparse prints to stderr
    assert "one of the arguments" in err or "one of the arguments" in out


def test_cli_render_invalid_segmentation_id_format() -> None:
    rc, out, err = _run(
        ["render", "--segmentation-id", "bad", "--output-dir", "/tmp/x"],
        cwd=str(_repo_root()),
    )
    # Should fail with input error exit code 2.
    assert rc == 2


def test_cli_render_missing_manifest(tmp_path: Path) -> None:
    rc, out, err = _run(
        [
            "render",
            "--segmentation-manifest",
            str(tmp_path / "missing.json"),
            "--output-dir",
            str(tmp_path / "out"),
        ],
        cwd=str(_repo_root()),
    )
    assert rc != 0


# ---------------------------------------------------------------------------
# render: success
# ---------------------------------------------------------------------------


def test_cli_render_end_to_end(tmp_path: Path) -> None:
    seg_path = tmp_path / "seg.json"
    seg = build_segmentation_manifest(**_seg_args())
    write_segmentation_manifest(seg, seg_path)
    out_dir = tmp_path / "dashboard"
    rc, out, err = _run(
        [
            "render",
            "--segmentation-manifest",
            str(seg_path),
            "--output-dir",
            str(out_dir),
        ],
        cwd=str(_repo_root()),
    )
    assert rc == 0, f"stderr={err}"
    assert "Lifecycle: SUCCESS" in out
    assert "viz_" in out
    assert (out_dir / "cluster_distribution.png").exists()
    assert (out_dir / "segment_profile.txt").exists()
    assert (out_dir / "feature_comparison.png").exists()
    assert (out_dir / "marketing.txt").exists()
    assert (out_dir / "dashboard_summary.txt").exists()
    assert (out_dir / "dashboard_summary.json").exists()


def test_cli_render_with_output_format_svg(tmp_path: Path) -> None:
    seg_path = tmp_path / "seg.json"
    seg = build_segmentation_manifest(**_seg_args())
    write_segmentation_manifest(seg, seg_path)
    out_dir = tmp_path / "dashboard"
    rc, out, err = _run(
        [
            "render",
            "--segmentation-manifest",
            str(seg_path),
            "--output-dir",
            str(out_dir),
            "--output-format",
            "svg",
        ],
        cwd=str(_repo_root()),
    )
    assert rc == 0
    assert (out_dir / "cluster_distribution.svg").exists()


# ---------------------------------------------------------------------------
# summary subcommand
# ---------------------------------------------------------------------------


def test_cli_summary_json(tmp_path: Path) -> None:
    seg_path = tmp_path / "seg.json"
    seg = build_segmentation_manifest(**_seg_args())
    write_segmentation_manifest(seg, seg_path)
    out_dir = tmp_path / "dashboard"
    rc, out, err = _run(
        [
            "render",
            "--segmentation-manifest",
            str(seg_path),
            "--output-dir",
            str(out_dir),
        ],
        cwd=str(_repo_root()),
    )
    assert rc == 0
    summary = out_dir / "dashboard_summary.json"
    rc, out, err = _run(["summary", "--dashboard-summary", str(summary)], cwd=str(_repo_root()))
    assert rc == 0
    parsed = json.loads(out)
    assert "charts" in parsed


def test_cli_summary_txt(tmp_path: Path) -> None:
    seg_path = tmp_path / "seg.json"
    seg = build_segmentation_manifest(**_seg_args())
    write_segmentation_manifest(seg, seg_path)
    out_dir = tmp_path / "dashboard"
    rc, out, err = _run(
        [
            "render",
            "--segmentation-manifest",
            str(seg_path),
            "--output-dir",
            str(out_dir),
        ],
        cwd=str(_repo_root()),
    )
    assert rc == 0
    summary = out_dir / "dashboard_summary.txt"
    rc, out, err = _run(["summary", "--dashboard-summary", str(summary)], cwd=str(_repo_root()))
    assert rc == 0
    assert "dashboard_id" in out


def test_cli_summary_missing_file(tmp_path: Path) -> None:
    rc, out, err = _run(
        ["summary", "--dashboard-summary", str(tmp_path / "missing.json")],
        cwd=str(_repo_root()),
    )
    assert rc == 1


def test_cli_summary_invalid_json(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    rc, out, err = _run(["summary", "--dashboard-summary", str(bad)], cwd=str(_repo_root()))
    assert rc == 1
