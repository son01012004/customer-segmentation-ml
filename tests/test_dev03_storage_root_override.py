"""Regression test for DEV-03 storage-root resolution.

Defect (D1): ``run_preprocessing_pipeline`` previously ignored the
DEV-02 ``--config`` override and always loaded the canonical
``configs/dev02_dataset_management.yaml``. As a result, callers who
imported a dataset with ``--config /tmp/iso.yaml`` (storage root =
``/tmp/iso``) saw ``DatasetNotFound`` because Stage A looked in the
default storage root.

Fix: ``run_preprocessing_pipeline(..., dev02_config_path=...)`` now
forwards the override to ``resolve_storage_root`` (and to Stage A's
internal call), so the preprocessed artefacts land in the same
storage root that holds the imported dataset.

This test pins the contract end-to-end: a DEV-02 import followed by
a DEV-03 preprocess using a custom dev02 config must succeed and
write the artefacts into the custom root.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_PATH = str(_REPO_ROOT / "src")
if _SRC_PATH not in sys.path:
    sys.path.insert(0, _SRC_PATH)


def _write_custom_dev02_config(storage_root: Path) -> Path:
    """Create a custom DEV-02 config YAML pointing at ``storage_root``."""
    import yaml

    canonical = _REPO_ROOT / "configs" / "dev02_dataset_management.yaml"
    cfg = yaml.safe_load(canonical.read_text())
    cfg["dataset_management"]["storage_root"] = str(storage_root)
    custom = storage_root / "dev02.yaml"
    custom.write_text(yaml.dump(cfg))
    return custom


def _write_custom_dev03_config(storage_root: Path) -> Path:
    """Create a custom DEV-03 config YAML (same content, different path)."""
    import yaml

    canonical = _REPO_ROOT / "configs" / "dev03_preprocessing.yaml"
    cfg = yaml.safe_load(canonical.read_text())
    custom = storage_root / "dev03.yaml"
    custom.write_text(yaml.dump(cfg))
    return custom


def _import_synthetic_dataset(dev02_config: Path, csv_path: Path):
    """Run a DEV-02 import on the synthetic CSV and return the result."""
    from argparse import Namespace

    from customer_segmentation.dataset_management import (
        build_request_from_args,
        import_dataset,
    )

    args = Namespace(
        file=str(csv_path),
        name="regression_synthetic",
        allow_external_source=True,
        config=str(dev02_config),
    )
    request = build_request_from_args(args, repo_root=_REPO_ROOT, cwd=_REPO_ROOT)
    return import_dataset(request)


def test_dev02_dev03_share_storage_root(tmp_path: Path) -> None:
    """DEV-02 + DEV-03 with custom config must end up in the same root."""
    from customer_segmentation.prototype.preprocessing import (
        run_preprocessing_pipeline,
    )
    from tests.fixtures.generate_synthetic import generate_synthetic_csv

    # 1. Custom configs in an isolated root.
    dev02_cfg = _write_custom_dev02_config(tmp_path)
    dev03_cfg = _write_custom_dev03_config(tmp_path)

    # 2. Generate a small synthetic CSV inside the same root.
    synth_csv = tmp_path / "synthetic.csv"
    generate_synthetic_csv(synth_csv)

    # 3. Import via DEV-02 using the custom config.
    import_result = _import_synthetic_dataset(dev02_cfg, synth_csv)
    assert import_result.manifest.row_count == 2000
    dataset_id = import_result.dataset_id

    # Manifest must be in the custom root (sanity).
    manifest_path = tmp_path / dataset_id / "manifest.json"
    assert manifest_path.exists()

    # 4. Preprocess via DEV-03 passing the SAME custom dev02 config.
    pp_result = run_preprocessing_pipeline(
        dataset_id,
        config_path=dev03_cfg,
        dev02_config_path=dev02_cfg,
    )

    # 5. Pipeline must succeed.
    assert pp_result.lifecycle == "VALID", (
        f"Pipeline lifecycle was {pp_result.lifecycle!r}; "
        f"stage_outcomes={pp_result.stage_outcomes}"
    )
    assert pp_result.preprocessed_id  # non-empty
    assert pp_result.cleaning.rows_in == 2000
    assert pp_result.cleaning.rows_out > 0
    assert pp_result.feature_generation.customer_count > 0
    assert pp_result.feature_generation.candidate_feature_count > 0

    # 6. Artefacts must live in the custom storage root, not the
    #    default pytest path.
    preprocessed_dir = tmp_path / dataset_id / "preprocessed"
    assert (
        preprocessed_dir.exists()
    ), f"Preprocessed dir not in custom root: expected {preprocessed_dir}"
    assert (preprocessed_dir / "preprocessed_manifest.json").exists()
    log_file = preprocessed_dir / f"{pp_result.preprocessed_id}.log"
    assert log_file.exists(), f"Expected log file at {log_file}"
    assert log_file.stat().st_size > 0, "Log file is empty"


def test_dev03_omits_dev02_config_override_fails_loudly(tmp_path: Path) -> None:
    """Without the dev02 override, the pipeline must report FAILED lifecycle.

    The previous behaviour was an exit-code-0 silent failure (lifecycle
    FAILED but the process reported success). This test pins the
    lifecycle/return contract: an unresolvable dataset must surface as
    FAILED, and the manifest path returned must point at the dataset
    directory under the default storage root (NOT a fabricated path
    inside tmp_path).
    """
    from customer_segmentation.prototype.preprocessing import (
        run_preprocessing_pipeline,
    )
    from tests.fixtures.generate_synthetic import generate_synthetic_csv

    dev02_cfg = _write_custom_dev02_config(tmp_path)
    dev03_cfg = _write_custom_dev03_config(tmp_path)

    # Use a UNIQUE seed so the dataset_id differs from any existing
    # canonical storage entries (e.g. the one imported in E2E runs).
    # This prevents test pollution when the canonical storage already
    # has a dataset with the same SHA.
    synth_csv = tmp_path / "synthetic.csv"
    generate_synthetic_csv(synth_csv, seed=99999)
    import_result = _import_synthetic_dataset(dev02_cfg, synth_csv)
    dataset_id = import_result.dataset_id

    # Omit dev02_config_path — pipeline must fall back to canonical.
    pp_result = run_preprocessing_pipeline(
        dataset_id,
        config_path=dev03_cfg,
        # dev02_config_path=None  # explicit
    )

    # Dataset was created in tmp_path, but pipeline looked in canonical
    # root. Lifecycle must be FAILED.
    assert pp_result.lifecycle == "FAILED"
    # Storage root in the result reflects the canonical (default) path.
    # We don't assert the literal path (it depends on env), but it
    # must NOT be the tmp_path we wrote to.
    assert str(pp_result.storage_root) != str(tmp_path.resolve())
