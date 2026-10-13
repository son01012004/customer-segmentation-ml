"""Regression test for DEV-04 storage-root resolution.

Defect (D1, second location): ``run_clustering_pipeline`` (and the
underlying ``resolve_storage_root`` in the clustering storage module)
previously ignored the DEV-02 ``--config`` override, similar to the
DEV-03 defect. Callers importing via ``--config /tmp/iso.yaml`` could
not cluster the same dataset because DEV-04 looked in the default
storage root.

Fix: ``run_clustering_pipeline(..., dev02_config_path=...)`` and the
underlying :func:`resolve_storage_root` now accept an explicit DEV-02
config path. The CLI exposes ``--dev02-config`` so the cluster
command can be chained after a non-canonical DEV-02 import.

This test pins the contract end-to-end: a DEV-02 import followed by
a DEV-03 preprocess followed by a DEV-04 clustering (all using the
same custom dev02 config) must succeed and write artefacts into the
custom root.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_PATH = str(_REPO_ROOT / "src")
if _SRC_PATH not in sys.path:
    sys.path.insert(0, _SRC_PATH)


def _write_custom_dev02_config(storage_root: Path) -> Path:
    import yaml

    canonical = _REPO_ROOT / "configs" / "dev02_dataset_management.yaml"
    cfg = yaml.safe_load(canonical.read_text())
    cfg["dataset_management"]["storage_root"] = str(storage_root)
    custom = storage_root / "dev02.yaml"
    custom.write_text(yaml.dump(cfg))
    return custom


def _write_custom_dev03_config(storage_root: Path) -> Path:
    import yaml

    canonical = _REPO_ROOT / "configs" / "dev03_preprocessing.yaml"
    cfg = yaml.safe_load(canonical.read_text())
    custom = storage_root / "dev03.yaml"
    custom.write_text(yaml.dump(cfg))
    return custom


def _import_synthetic_dataset(dev02_config: Path, csv_path: Path):
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


def test_dev02_dev03_dev04_share_storage_root(tmp_path: Path) -> None:
    """Full DEV-02 → DEV-03 → DEV-04 chain must use one storage root."""
    from customer_segmentation.prototype.clustering import (
        run_clustering_pipeline,
    )
    from customer_segmentation.prototype.preprocessing import (
        run_preprocessing_pipeline,
    )
    from tests.fixtures.generate_synthetic import generate_synthetic_csv

    dev02_cfg = _write_custom_dev02_config(tmp_path)
    dev03_cfg = _write_custom_dev03_config(tmp_path)

    synth_csv = tmp_path / "synthetic.csv"
    generate_synthetic_csv(synth_csv)
    import_result = _import_synthetic_dataset(dev02_cfg, synth_csv)
    dataset_id = import_result.dataset_id

    pp_result = run_preprocessing_pipeline(
        dataset_id,
        config_path=dev03_cfg,
        dev02_config_path=dev02_cfg,
    )
    assert pp_result.lifecycle == "VALID"

    cluster_result = run_clustering_pipeline(
        dataset_id=dataset_id,
        preprocessed_id=pp_result.preprocessed_id,
        algorithm="kmeans",
        dev02_config_path=dev02_cfg,
        hyperparameters={"n_clusters": 3},
        seed=42,
    )
    assert cluster_result.lifecycle == "SUCCESS", (
        f"Clustering lifecycle was {cluster_result.lifecycle!r}; "
        f"storage_root={cluster_result.storage_root}"
    )

    # All artefacts must be in the custom storage root, not default.
    clustering_dir = (
        tmp_path
        / dataset_id
        / "preprocessed"
        / pp_result.preprocessed_id
        / "clustering"
        / cluster_result.clustering_id
    )
    assert clustering_dir.exists()
    assert (clustering_dir / "clustering_manifest.json").exists()
    # Labels parquet must exist (suffix varies by algo+id).
    labels = list(clustering_dir.glob("cluster_labels_*.parquet"))
    assert labels, f"No cluster labels parquet under {clustering_dir}"
    assert labels[0].stat().st_size > 0
