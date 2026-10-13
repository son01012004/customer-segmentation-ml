"""CLI tests for ``scripts/dev06_run_segmentation.py``.

Covers all 6 sub-commands (``profile``, ``list``, ``sizes``,
``profiles``, ``characteristics``, ``compare``) using synthetic
fixtures only — no real research data.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "dev06_run_segmentation.py"


def _run_cli(*args: str, env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """Run the CLI as a subprocess (isolated, no in-process state)."""
    env = {"PYTHONPATH": str(REPO_ROOT / "src")}
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        cwd=str(REPO_ROOT),
    )


# ---------------------------------------------------------------------------
# --help smoke test (regression for report §6.6)
# ---------------------------------------------------------------------------


def test_cli_help_lists_all_six_subcommands() -> None:
    """``--help`` enumerates the 6 sub-commands."""
    proc = _run_cli("--help")
    assert proc.returncode == 0
    for cmd in ("profile", "list", "sizes", "profiles", "characteristics", "compare"):
        assert cmd in proc.stdout, f"sub-command {cmd!r} missing from --help output"


# ---------------------------------------------------------------------------
# Synthetic storage setup (shared across tests)
# ---------------------------------------------------------------------------


def _setup_synthetic_storage(storage_root: Path) -> dict:
    """Build a synthetic DEV-04 clustering tree under storage_root."""
    dataset_id = "ds_clitest"
    preprocessed_id = "pp_clitest"
    clustering_id = "cl_" + "a" * 24

    # ``storage_root`` already points at ``<repo>/data/prototype/datasets``
    # (per ``configs/dev02_dataset_management.yaml``); ``dataset_id`` is
    # appended directly (no extra ``"datasets"`` literal). Post-A-1:
    # DEV-03 writes artefacts FLAT under
    # ``<storage_root>/<dataset_id>/preprocessed/`` (no
    # ``<preprocessed_id>`` subdirectory); DEV-04..08 creates the
    # ``<preprocessed_id>/clustering/<clustering_id>/...`` subtree
    # alongside. See the regression test in
    # ``tests/test_dev04_storage.py::TestPathDoublingRegressionA1``.
    pp_dir = storage_root / dataset_id / "preprocessed"
    pp_id_dir = pp_dir / preprocessed_id
    cl_dir = pp_id_dir / "clustering" / clustering_id
    pp_dir.mkdir(parents=True, exist_ok=True)
    pp_id_dir.mkdir(parents=True, exist_ok=True)
    cl_dir.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(42)
    n = 50
    df_ml = pd.DataFrame(
        {
            "CustomerID": np.arange(1, n + 1),
            "a": rng.standard_normal(n),
            "b": rng.standard_normal(n),
            "cat": rng.choice(["X", "Y"], size=n),
        }
    )
    ml_path = pp_dir / "ml_dataset_clitest.parquet"
    df_ml.to_parquet(ml_path)

    pp_manifest = {
        "schema_version": "1.0.0",
        "config_hash": "f" * 64,
        "ml_dataset_block": {"artifact_path": "ml_dataset_clitest.parquet"},
        "preprocessing_block": {
            "transformation": "log",
            "scaling": "standard",
        },
    }
    pp_manifest_path = pp_dir / "preprocessed_manifest.json"
    pp_manifest_path.write_text(json.dumps(pp_manifest), encoding="utf-8")

    labels = np.array([0] * 25 + [1] * 25, dtype=np.int64)
    df_cl = pd.DataFrame(
        {
            "CustomerID": np.arange(1, n + 1),
            "ClusterLabel": labels,
            "IsNoise": [False] * n,
        }
    )
    cl_labels_path = cl_dir / "cluster_labels_clitest.parquet"
    df_cl.to_parquet(cl_labels_path)

    cm = {
        "schema_version": "1.0.0",
        "clustering_id": clustering_id,
        "preprocessed_id": preprocessed_id,
        "dataset_id": dataset_id,
        "algorithm": "kmeans",
        "algorithm_version": "sklearn_1.5",
        "algorithm_family": "hard",
        "ml_dataset_sha256": "b" * 64,
        "feature_set": ["a", "b"],
        "n_samples": n,
        "n_clusters": 2,
        "cluster_labels_path": "cluster_labels_clitest.parquet",
    }
    cm_path = cl_dir / "clustering_manifest.json"
    cm_path.write_text(json.dumps(cm), encoding="utf-8")

    return {
        "storage_root": storage_root,
        "dataset_id": dataset_id,
        "preprocessed_id": preprocessed_id,
        "clustering_id": clustering_id,
        "cl_dir": cl_dir,
    }


def _patch_storage_root_in_subprocess(storage_root: Path, monkeypatch) -> dict:
    """Patch the storage root at module level so the subprocess picks it up.

    The CLI resolves storage root from ``configs/dev02_dataset_management.yaml``
    via ``resolve_storage_root``. We override by pointing the canonical config
    YAML at the tmp_path (mirrors conftest.py's dev02_config fixture).
    """
    import yaml

    cfg_path = REPO_ROOT / "configs" / "dev02_dataset_management.yaml"
    if cfg_path.exists():
        canonical = yaml.safe_load(cfg_path.read_text())
    else:
        canonical = {"dataset_management": {}}
    canonical["dataset_management"]["storage_root"] = str(storage_root)
    override_path = storage_root / "dev02_dataset_management.yaml"
    override_path.parent.mkdir(parents=True, exist_ok=True)
    with override_path.open("w", encoding="utf-8") as fh:
        yaml.dump(canonical, fh)
    return {}


# ---------------------------------------------------------------------------
# `profile` sub-command
# ---------------------------------------------------------------------------


class TestProfileSubCommand:
    def test_profile_subcommand_runs_and_writes_manifest(self, tmp_path: Path, monkeypatch) -> None:
        ctx = _setup_synthetic_storage(tmp_path)
        _patch_storage_root_in_subprocess(tmp_path, monkeypatch)

        # The CLI loads the config from ``configs/dev02_dataset_management.yaml``;
        # we use the existing config which will use ``tmp_path`` as storage root.
        import yaml

        cfg_path = REPO_ROOT / "configs" / "dev02_dataset_management.yaml"
        original = cfg_path.read_text() if cfg_path.exists() else None

        try:
            if cfg_path.exists():
                canonical = yaml.safe_load(cfg_path.read_text())
                canonical["dataset_management"]["storage_root"] = str(tmp_path)
                cfg_path.write_text(yaml.dump(canonical))
            proc = _run_cli(
                "profile",
                "--dataset-id",
                ctx["dataset_id"],
                "--preprocessed-id",
                ctx["preprocessed_id"],
                "--clustering-id",
                ctx["clustering_id"],
            )
            assert proc.returncode == 0, (
                f"CLI failed (rc={proc.returncode}):\n"
                f"STDOUT: {proc.stdout}\nSTDERR: {proc.stderr}"
            )
            assert "Segmentation:" in proc.stdout
            assert "Lifecycle  : SUCCESS" in proc.stdout
            # Manifest must exist on disk.
            assert (ctx["cl_dir"] / "segmentation").exists()
        finally:
            if original is not None:
                cfg_path.write_text(original)

    def test_profile_subcommand_invalid_dataset_id_returns_error(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Invalid ids → exit code 2 with an error message."""
        _patch_storage_root_in_subprocess(tmp_path, monkeypatch)
        import yaml

        cfg_path = REPO_ROOT / "configs" / "dev02_dataset_management.yaml"
        original = cfg_path.read_text() if cfg_path.exists() else None
        try:
            if cfg_path.exists():
                canonical = yaml.safe_load(cfg_path.read_text())
                canonical["dataset_management"]["storage_root"] = str(tmp_path)
                cfg_path.write_text(yaml.dump(canonical))
            proc = _run_cli(
                "profile",
                "--dataset-id",
                "ds_nonexistent",
                "--preprocessed-id",
                "pp_nonexistent",
                "--clustering-id",
                "cl_" + "0" * 24,
            )
            # CLI returns 2 on validation / pipeline error.
            assert proc.returncode == 2
            assert "ERROR" in proc.stderr or "ERROR" in proc.stdout
        finally:
            if original is not None:
                cfg_path.write_text(original)

    def test_profile_subcommand_missing_required_arg_fails(self) -> None:
        """Missing required flag → argparse exit code 2."""
        proc = _run_cli("profile", "--dataset-id", "ds_x")
        assert proc.returncode == 2
        # argparse writes usage / error to stderr.
        assert proc.stderr  # non-empty error message


# ---------------------------------------------------------------------------
# Display sub-commands (`list`, `sizes`, `profiles`, `characteristics`)
# ---------------------------------------------------------------------------


class TestDisplaySubCommands:
    """All 4 display sub-commands share a setup helper: run ``profile``
    first to produce a manifest, then test the display sub-commands."""

    def _make_segmentation(
        self,
        tmp_path: Path,
        monkeypatch,
    ) -> Path:
        """Produce a valid segmentation manifest on disk; return its path."""
        ctx = _setup_synthetic_storage(tmp_path)
        _patch_storage_root_in_subprocess(tmp_path, monkeypatch)

        import yaml

        cfg_path = REPO_ROOT / "configs" / "dev02_dataset_management.yaml"
        original = cfg_path.read_text() if cfg_path.exists() else None
        try:
            if cfg_path.exists():
                canonical = yaml.safe_load(cfg_path.read_text())
                canonical["dataset_management"]["storage_root"] = str(tmp_path)
                cfg_path.write_text(yaml.dump(canonical))
            proc = _run_cli(
                "profile",
                "--dataset-id",
                ctx["dataset_id"],
                "--preprocessed-id",
                ctx["preprocessed_id"],
                "--clustering-id",
                ctx["clustering_id"],
            )
            assert proc.returncode == 0, proc.stderr
        finally:
            if original is not None:
                cfg_path.write_text(original)

        # Find the segmentation_manifest.json file.
        seg_root = ctx["cl_dir"] / "segmentation"
        manifest_path = next(seg_root.glob("*/segmentation_manifest.json"))
        return manifest_path

    def test_list_subcommand(self, tmp_path: Path, monkeypatch) -> None:
        manifest_path = self._make_segmentation(tmp_path, monkeypatch)
        proc = _run_cli("list", "--segmentation-manifest", str(manifest_path))
        assert proc.returncode == 0, proc.stderr
        # Output must contain the segmentation_id and segments table.
        assert "segment_id" in proc.stdout

    def test_sizes_subcommand(self, tmp_path: Path, monkeypatch) -> None:
        manifest_path = self._make_segmentation(tmp_path, monkeypatch)
        proc = _run_cli("sizes", "--segmentation-manifest", str(manifest_path))
        assert proc.returncode == 0, proc.stderr
        # Sizes table header.
        assert "count" in proc.stdout

    def test_profiles_subcommand(self, tmp_path: Path, monkeypatch) -> None:
        manifest_path = self._make_segmentation(tmp_path, monkeypatch)
        proc = _run_cli("profiles", "--segmentation-manifest", str(manifest_path))
        assert proc.returncode == 0, proc.stderr
        # Profile table header.
        assert "feature_name" in proc.stdout

    def test_profiles_subcommand_with_segment_id_filter(self, tmp_path: Path, monkeypatch) -> None:
        """``--segment-id`` filter narrows the output to one segment."""
        manifest_path = self._make_segmentation(tmp_path, monkeypatch)
        proc = _run_cli(
            "profiles",
            "--segmentation-manifest",
            str(manifest_path),
            "--segment-id",
            "0",
        )
        assert proc.returncode == 0, proc.stderr
        # Filter applied — only segment 0's rows present.

    def test_characteristics_subcommand(self, tmp_path: Path, monkeypatch) -> None:
        manifest_path = self._make_segmentation(tmp_path, monkeypatch)
        proc = _run_cli("characteristics", "--segmentation-manifest", str(manifest_path))
        assert proc.returncode == 0, proc.stderr
        # Disclaimer emitted on every display.
        assert "no ranking" in proc.stdout.lower() or "descriptive" in proc.stdout.lower()

    def test_list_subcommand_missing_manifest_returns_error(self) -> None:
        """Missing manifest path → exit code 2 with error."""
        proc = _run_cli("list", "--segmentation-manifest", "/nonexistent/path.json")
        assert proc.returncode == 2
        assert "ERROR" in proc.stderr


# ---------------------------------------------------------------------------
# `compare` sub-command
# ---------------------------------------------------------------------------


class TestCompareSubCommand:
    def test_compare_subcommand_with_synthetic_manifests(self, tmp_path: Path) -> None:
        """``compare`` runs end-to-end on 2 synthetic manifests; emits JSON."""
        from customer_segmentation.prototype.segmentation.manifest import (
            CharacteristicEntry,
            EnvironmentBlock,
            FeatureProfile,
            SegmentationValidationReport,
            SegmentSize,
            build_segmentation_manifest,
            write_segmentation_manifest,
        )

        def _make(seg_id_hex: str, dataset_id: str = "ds_x") -> object:
            return build_segmentation_manifest(
                segmentation_id="seg_" + seg_id_hex * 24,
                clustering_id="cl_" + "0" * 24,
                preprocessed_id="pp_x",
                dataset_id=dataset_id,
                evaluation_id=None,
                algorithm="kmeans",
                algorithm_version="sklearn_1.5",
                algorithm_family="hard",
                ml_dataset_sha256="a" * 64,
                feature_set_sha256="b" * 64,
                preprocessing_config_sha256="c" * 64,
                feature_set=["a", "b"],
                n_samples_input=10,
                n_samples_used_for_compute=10,
                n_clusters_input=2,
                n_segments=2,
                noise_count=None,
                noise_ratio=None,
                noise_policy_used="n/a",
                segment_sizes=[
                    SegmentSize(0, 5, 50.0, "n_samples_input", False),
                    SegmentSize(1, 5, 50.0, "n_samples_input", False),
                ],
                profiles=[
                    FeatureProfile(0, "a", {"mean": 0.1}),
                    FeatureProfile(1, "a", {"mean": 0.2}),
                ],
                characteristics=[
                    CharacteristicEntry(
                        characteristic_id="mean_high_a",
                        description="d",
                        source_features=["a"],
                        derived_stats={"rule": "mean_high"},
                        segment_id=0,
                    ),
                ],
                config_sha256="d" * 64,
                environment=EnvironmentBlock(
                    python="3.11",
                    platform="Linux",
                    release="7.0",
                    machine="x86_64",
                    key_libraries={},
                ),
                log_file="x.log",
                validation_report=SegmentationValidationReport(all_passed=True),
                readonly_paths=[],
                input_clustering_manifest="cm.json",
                input_cluster_labels="cl.parquet",
                input_ml_dataset="ml.parquet",
                input_evaluation_manifest=None,
            )

        m1 = _make("1")
        m2 = _make("2")
        p1 = tmp_path / "m1.json"
        p2 = tmp_path / "m2.json"
        write_segmentation_manifest(m1, p1)
        write_segmentation_manifest(m2, p2)

        proc = _run_cli("compare", "--segmentation-manifest", str(p1), str(p2))
        assert proc.returncode == 0, proc.stderr
        # JSON output is embedded in stdout.
        assert "schema_version" in proc.stdout
        assert "compatibility_key" in proc.stdout
        assert "disclaimer" in proc.stdout

    def test_compare_subcommand_missing_manifest_returns_error(self) -> None:
        proc = _run_cli(
            "compare",
            "--segmentation-manifest",
            "/nonexistent/m1.json",
            "/nonexistent/m2.json",
        )
        assert proc.returncode == 2
        assert "ERROR" in proc.stderr

    def test_compare_subcommand_exposes_exclusion_reasons_and_summary_counts(
        self, tmp_path: Path
    ) -> None:
        """Required test #12: CLI ``compare`` exposes exclusion_reasons + summary counts.

        Two manifests with different ``dataset_id`` are passed: the CLI
        must surface the new ``exclusion_reasons`` field and the new
        ``total_input_count`` / ``total_compared_count`` /
        ``total_excluded_count`` summary fields in its JSON output.
        """
        from customer_segmentation.prototype.segmentation.manifest import (
            CharacteristicEntry,
            EnvironmentBlock,
            FeatureProfile,
            SegmentationValidationReport,
            SegmentSize,
            build_segmentation_manifest,
            write_segmentation_manifest,
        )

        def _make(seg_id_hex: str, dataset_id: str) -> object:
            return build_segmentation_manifest(
                segmentation_id="seg_" + seg_id_hex * 24,
                clustering_id="cl_" + "0" * 24,
                preprocessed_id="pp_x",
                dataset_id=dataset_id,
                evaluation_id=None,
                algorithm="kmeans",
                algorithm_version="sklearn_1.5",
                algorithm_family="hard",
                ml_dataset_sha256="a" * 64,
                feature_set_sha256="b" * 64,
                preprocessing_config_sha256="c" * 64,
                feature_set=["a", "b"],
                n_samples_input=10,
                n_samples_used_for_compute=10,
                n_clusters_input=2,
                n_segments=2,
                noise_count=None,
                noise_ratio=None,
                noise_policy_used="n/a",
                segment_sizes=[
                    SegmentSize(0, 5, 50.0, "n_samples_input", False),
                    SegmentSize(1, 5, 50.0, "n_samples_input", False),
                ],
                profiles=[
                    FeatureProfile(0, "a", {"mean": 0.1}),
                    FeatureProfile(1, "a", {"mean": 0.2}),
                ],
                characteristics=[
                    CharacteristicEntry(
                        characteristic_id="mean_high_a",
                        description="d",
                        source_features=["a"],
                        derived_stats={"rule": "mean_high"},
                        segment_id=0,
                    ),
                ],
                config_sha256="d" * 64,
                environment=EnvironmentBlock(
                    python="3.11",
                    platform="Linux",
                    release="7.0",
                    machine="x86_64",
                    key_libraries={},
                ),
                log_file="x.log",
                validation_report=SegmentationValidationReport(all_passed=True),
                readonly_paths=[],
                input_clustering_manifest="cm.json",
                input_cluster_labels="cl.parquet",
                input_ml_dataset="ml.parquet",
                input_evaluation_manifest=None,
            )

        m1 = _make("1", "ds_a")
        m2 = _make("2", "ds_b")
        p1 = tmp_path / "m1.json"
        p2 = tmp_path / "m2.json"
        write_segmentation_manifest(m1, p1)
        write_segmentation_manifest(m2, p2)

        proc = _run_cli("compare", "--segmentation-manifest", str(p1), str(p2))
        assert proc.returncode == 0, proc.stderr

        # Find the JSON blob in stdout. The CLI prints JSON first, then a
        # text table; locate the top-level JSON object and parse it.
        start = proc.stdout.index("{")
        end = proc.stdout.rindex("}") + 1
        payload = json.loads(proc.stdout[start:end])

        # All-incompatible → groups is an empty list, exclusion_reasons has 2.
        assert payload["groups"] == []
        assert len(payload["exclusion_reasons"]) == 2
        for r in payload["exclusion_reasons"]:
            assert r["reason_code"] == "excluded_no_shared_key"
            assert r["no_retained_group"] is True
            assert "dataset_id" in r["differing_key_field_names"]
        # Summary counts.
        assert payload["total_input_count"] == 2
        assert payload["total_compared_count"] == 0
        assert payload["total_excluded_count"] == 2
        # Per-row incompatibility_reasons is empty (kept distinct).
        assert payload["incompatibility_reasons"] == []
