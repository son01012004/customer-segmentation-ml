"""Tests for the DEV-05 storage helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from customer_segmentation.prototype.evaluation.scope import (
    EVALUATION_MANIFEST_SCHEMA_VERSION,
)
from customer_segmentation.prototype.evaluation.storage import (
    EVALUATION_ID_HEX_LEN,
    EVALUATION_ID_PREFIX,
    Dev05CollisionError,
    Dev05ManifestCorrupt,
    Dev05StoragePathError,
    compute_config_sha256,
    compute_metric_set_hash,
    derive_evaluation_id,
    find_existing_evaluation,
    prototype_evaluation_base_dir,
    prototype_evaluation_run_dir,
)


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

VALID_CLUSTERING_ID = "cl_" + "a" * 24
VALID_ML_DATASET_SHA = "b" * 64
VALID_CONFIG_SHA = "c" * 64
VALID_METRIC_SET = frozenset(
    {"silhouette", "davies_bouldin", "calinski_harabasz"}
)


def _make_eval_id(
    *,
    clustering_id: str = VALID_CLUSTERING_ID,
    preprocessed_id: str = "pp_xyz",
    dataset_id: str = "ds_abc",
    ml_dataset_sha256: str = VALID_ML_DATASET_SHA,
    config_sha256: str = VALID_CONFIG_SHA,
    noise_policy: str = "exclude",
    metric_set=VALID_METRIC_SET,
) -> str:
    return derive_evaluation_id(
        clustering_id=clustering_id,
        preprocessed_id=preprocessed_id,
        dataset_id=dataset_id,
        ml_dataset_sha256=ml_dataset_sha256,
        config_sha256=config_sha256,
        noise_policy=noise_policy,
        metric_set=metric_set,
    )


# ---------------------------------------------------------------------------
# derive_evaluation_id
# ---------------------------------------------------------------------------


class TestDeriveEvaluationId:
    def test_format_prefix_and_length(self) -> None:
        eid = _make_eval_id()
        assert eid.startswith(EVALUATION_ID_PREFIX)
        assert len(eid) == len(EVALUATION_ID_PREFIX) + EVALUATION_ID_HEX_LEN
        assert eid == EVALUATION_ID_PREFIX + eid[len(EVALUATION_ID_PREFIX):]

    def test_same_inputs_produce_same_id(self) -> None:
        e1 = _make_eval_id()
        e2 = _make_eval_id()
        assert e1 == e2

    def test_different_clustering_id_different_id(self) -> None:
        e1 = _make_eval_id(clustering_id="cl_" + "a" * 24)
        e2 = _make_eval_id(clustering_id="cl_" + "b" * 24)
        assert e1 != e2

    def test_different_noise_policy_different_id(self) -> None:
        """Per ADR-0006 + plan §4.4: noise_policy must be in canonical payload."""
        e_exclude = _make_eval_id(noise_policy="exclude")
        e_include = _make_eval_id(noise_policy="include")
        assert e_exclude != e_include

    def test_different_metric_set_different_id(self) -> None:
        e1 = _make_eval_id(
            metric_set=frozenset({"silhouette", "davies_bouldin", "calinski_harabasz"})
        )
        e2 = _make_eval_id(
            metric_set=frozenset({"silhouette", "davies_bouldin"})
        )
        assert e1 != e2

    def test_different_config_sha_different_id(self) -> None:
        e1 = _make_eval_id(config_sha256="c" * 64)
        e2 = _make_eval_id(config_sha256="d" * 64)
        assert e1 != e2

    def test_metric_set_order_does_not_matter(self) -> None:
        e1 = _make_eval_id(
            metric_set=["silhouette", "davies_bouldin", "calinski_harabasz"]
        )
        e2 = _make_eval_id(
            metric_set=frozenset({"calinski_harabasz", "silhouette", "davies_bouldin"})
        )
        assert e1 == e2

    def test_rejects_invalid_clustering_id_format(self) -> None:
        with pytest.raises(Dev05StoragePathError):
            derive_evaluation_id(
                clustering_id="invalid_id",
                preprocessed_id="pp_xyz",
                dataset_id="ds_abc",
                ml_dataset_sha256=VALID_ML_DATASET_SHA,
                config_sha256=VALID_CONFIG_SHA,
                noise_policy="exclude",
                metric_set=VALID_METRIC_SET,
            )

    def test_rejects_empty_preprocessed_id(self) -> None:
        with pytest.raises(Dev05StoragePathError):
            derive_evaluation_id(
                clustering_id=VALID_CLUSTERING_ID,
                preprocessed_id="",
                dataset_id="ds_abc",
                ml_dataset_sha256=VALID_ML_DATASET_SHA,
                config_sha256=VALID_CONFIG_SHA,
                noise_policy="exclude",
                metric_set=VALID_METRIC_SET,
            )

    def test_rejects_empty_dataset_id(self) -> None:
        with pytest.raises(Dev05StoragePathError):
            derive_evaluation_id(
                clustering_id=VALID_CLUSTERING_ID,
                preprocessed_id="pp_xyz",
                dataset_id="",
                ml_dataset_sha256=VALID_ML_DATASET_SHA,
                config_sha256=VALID_CONFIG_SHA,
                noise_policy="exclude",
                metric_set=VALID_METRIC_SET,
            )

    def test_rejects_invalid_noise_policy(self) -> None:
        with pytest.raises(Dev05StoragePathError):
            derive_evaluation_id(
                clustering_id=VALID_CLUSTERING_ID,
                preprocessed_id="pp_xyz",
                dataset_id="ds_abc",
                ml_dataset_sha256=VALID_ML_DATASET_SHA,
                config_sha256=VALID_CONFIG_SHA,
                noise_policy="drop",  # not in closed set
                metric_set=VALID_METRIC_SET,
            )

    def test_rejects_unknown_metric_name(self) -> None:
        with pytest.raises(Dev05StoragePathError):
            derive_evaluation_id(
                clustering_id=VALID_CLUSTERING_ID,
                preprocessed_id="pp_xyz",
                dataset_id="ds_abc",
                ml_dataset_sha256=VALID_ML_DATASET_SHA,
                config_sha256=VALID_CONFIG_SHA,
                noise_policy="exclude",
                metric_set=frozenset({"silhouette", "wcss"}),
            )

    def test_rejects_empty_metric_set(self) -> None:
        with pytest.raises(Dev05StoragePathError):
            derive_evaluation_id(
                clustering_id=VALID_CLUSTERING_ID,
                preprocessed_id="pp_xyz",
                dataset_id="ds_abc",
                ml_dataset_sha256=VALID_ML_DATASET_SHA,
                config_sha256=VALID_CONFIG_SHA,
                noise_policy="exclude",
                metric_set=frozenset(),
            )

    def test_schema_version_in_canonical_payload(self) -> None:
        """Bumping schema_version must change evaluation_id."""
        e_v1 = _make_eval_id()
        e_v2 = derive_evaluation_id(
            clustering_id=VALID_CLUSTERING_ID,
            preprocessed_id="pp_xyz",
            dataset_id="ds_abc",
            ml_dataset_sha256=VALID_ML_DATASET_SHA,
            config_sha256=VALID_CONFIG_SHA,
            noise_policy="exclude",
            metric_set=VALID_METRIC_SET,
            schema_version="0.9.0",
        )
        assert e_v1 != e_v2

    def test_default_schema_version_matches_constant(self) -> None:
        e1 = _make_eval_id()
        e2 = derive_evaluation_id(
            clustering_id=VALID_CLUSTERING_ID,
            preprocessed_id="pp_xyz",
            dataset_id="ds_abc",
            ml_dataset_sha256=VALID_ML_DATASET_SHA,
            config_sha256=VALID_CONFIG_SHA,
            noise_policy="exclude",
            metric_set=VALID_METRIC_SET,
            schema_version=EVALUATION_MANIFEST_SCHEMA_VERSION,
        )
        assert e1 == e2


# ---------------------------------------------------------------------------
# compute_metric_set_hash
# ---------------------------------------------------------------------------


class TestComputeMetricSetHash:
    def test_same_set_produces_same_hash(self) -> None:
        h1 = compute_metric_set_hash({"silhouette", "davies_bouldin"})
        h2 = compute_metric_set_hash(frozenset({"davies_bouldin", "silhouette"}))
        assert h1 == h2

    def test_different_set_produces_different_hash(self) -> None:
        h1 = compute_metric_set_hash({"silhouette", "davies_bouldin"})
        h2 = compute_metric_set_hash({"silhouette", "calinski_harabasz"})
        assert h1 != h2

    def test_hash_is_64_hex(self) -> None:
        h = compute_metric_set_hash({"silhouette"})
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_rejects_unknown_metric(self) -> None:
        with pytest.raises(Dev05StoragePathError):
            compute_metric_set_hash({"silhouette", "wcss"})

    def test_rejects_empty_set(self) -> None:
        with pytest.raises(Dev05StoragePathError):
            compute_metric_set_hash(set())


# ---------------------------------------------------------------------------
# compute_config_sha256
# ---------------------------------------------------------------------------


class TestComputeConfigSha256:
    def test_same_text_produces_same_hash(self) -> None:
        h1 = compute_config_sha256("config: 1")
        h2 = compute_config_sha256("config: 1")
        assert h1 == h2

    def test_different_text_produces_different_hash(self) -> None:
        h1 = compute_config_sha256("config: 1")
        h2 = compute_config_sha256("config: 2")
        assert h1 != h2

    def test_hash_is_64_hex(self) -> None:
        h = compute_config_sha256("any text")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


# ---------------------------------------------------------------------------
# prototype_evaluation_base_dir
# ---------------------------------------------------------------------------


class TestPrototypeEvaluationBaseDir:
    def test_inside_storage_root(self, tmp_path: Path) -> None:
        base = prototype_evaluation_base_dir(
            tmp_path, "ds_abc123", "pp_xyz789", VALID_CLUSTERING_ID
        )
        assert base.is_relative_to(tmp_path)

    def test_path_structure(self, tmp_path: Path) -> None:
        base = prototype_evaluation_base_dir(
            tmp_path, "ds_abc", "pp_xyz", VALID_CLUSTERING_ID
        )
        parts = base.relative_to(tmp_path).parts
        assert parts == (
            "ds_abc",
            "preprocessed",
            "pp_xyz",
            "clustering",
            "cl_" + "a" * 24,
            "evaluation",
        )

    def test_rejects_empty_dataset_id(self, tmp_path: Path) -> None:
        with pytest.raises(Dev05StoragePathError):
            prototype_evaluation_base_dir(
                tmp_path, "", "pp_xyz", VALID_CLUSTERING_ID
            )

    def test_rejects_empty_preprocessed_id(self, tmp_path: Path) -> None:
        with pytest.raises(Dev05StoragePathError):
            prototype_evaluation_base_dir(
                tmp_path, "ds_abc", "", VALID_CLUSTERING_ID
            )

    def test_rejects_invalid_clustering_id(self, tmp_path: Path) -> None:
        with pytest.raises(Dev05StoragePathError):
            prototype_evaluation_base_dir(tmp_path, "ds_abc", "pp_xyz", "not_cl_xxx")


# ---------------------------------------------------------------------------
# prototype_evaluation_run_dir
# ---------------------------------------------------------------------------


class TestPrototypeEvaluationRunDir:
    def test_inside_storage_root(self, tmp_path: Path) -> None:
        eid = _make_eval_id()
        run = prototype_evaluation_run_dir(
            tmp_path, "ds_abc", "pp_xyz", VALID_CLUSTERING_ID, eid
        )
        assert run.is_relative_to(tmp_path)

    def test_path_structure(self, tmp_path: Path) -> None:
        eid = _make_eval_id()
        run = prototype_evaluation_run_dir(
            tmp_path, "ds_abc", "pp_xyz", VALID_CLUSTERING_ID, eid
        )
        parts = run.relative_to(tmp_path).parts
        assert parts == (
            "ds_abc",
            "preprocessed",
            "pp_xyz",
            "clustering",
            "cl_" + "a" * 24,
            "evaluation",
            eid,
        )

    def test_rejects_invalid_evaluation_id(self, tmp_path: Path) -> None:
        with pytest.raises(Dev05StoragePathError):
            prototype_evaluation_run_dir(
                tmp_path, "ds_abc", "pp_xyz", VALID_CLUSTERING_ID, "not_ev_xxx"
            )

    def test_rejects_short_evaluation_id(self, tmp_path: Path) -> None:
        with pytest.raises(Dev05StoragePathError):
            prototype_evaluation_run_dir(
                tmp_path, "ds_abc", "pp_xyz", VALID_CLUSTERING_ID, "ev_short"
            )


# ---------------------------------------------------------------------------
# find_existing_evaluation
# ---------------------------------------------------------------------------


class TestFindExistingEvaluation:
    def _write_manifest(
        self,
        base_dir: Path,
        eid: str,
        canonical: dict,
    ) -> Path:
        run_dir = base_dir / eid
        run_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "schema_version": canonical["schema_version"],
            "evaluation_id": eid,
            "scope": "EVALUATED_PROTOTYPE",
            "clustering_id": canonical["clustering_id"],
            "preprocessed_id": canonical["preprocessed_id"],
            "dataset_id": canonical["dataset_id"],
            "ml_dataset_sha256": canonical["ml_dataset_sha256"],
            "config_sha256": canonical["config_sha256"],
            "noise_policy": canonical["noise_policy"],
            "metric_set_hash": canonical["metric_set_hash"],
            "metrics": {},
        }
        manifest_path = run_dir / "evaluation_manifest.json"
        with manifest_path.open("w", encoding="utf-8") as fh:
            json.dump(manifest, fh)
        return manifest_path

    def test_returns_false_when_no_directory(self, tmp_path: Path) -> None:
        eid = _make_eval_id()
        found, path = find_existing_evaluation(
            base_dir=tmp_path,
            evaluation_id=eid,
            expected_canonical={
                "clustering_id": VALID_CLUSTERING_ID,
                "preprocessed_id": "pp_xyz",
                "dataset_id": "ds_abc",
                "ml_dataset_sha256": VALID_ML_DATASET_SHA,
                "config_sha256": VALID_CONFIG_SHA,
                "noise_policy": "exclude",
                "metric_set_hash": "h" * 64,
                "schema_version": EVALUATION_MANIFEST_SCHEMA_VERSION,
            },
        )
        assert found is False
        assert path is None

    def test_returns_true_when_cached(self, tmp_path: Path) -> None:
        from customer_segmentation.prototype.evaluation.storage import (
            compute_metric_set_hash,
        )

        eid = _make_eval_id()
        msh = compute_metric_set_hash(VALID_METRIC_SET)
        canonical = {
            "clustering_id": VALID_CLUSTERING_ID,
            "preprocessed_id": "pp_xyz",
            "dataset_id": "ds_abc",
            "ml_dataset_sha256": VALID_ML_DATASET_SHA,
            "config_sha256": VALID_CONFIG_SHA,
            "noise_policy": "exclude",
            "metric_set_hash": msh,
            "schema_version": EVALUATION_MANIFEST_SCHEMA_VERSION,
        }
        manifest_path = self._write_manifest(tmp_path, eid, canonical)
        found, path = find_existing_evaluation(
            base_dir=tmp_path,
            evaluation_id=eid,
            expected_canonical=canonical,
        )
        assert found is True
        assert path == manifest_path

    def test_collision_raises_dev05collisionerror(self, tmp_path: Path) -> None:
        from customer_segmentation.prototype.evaluation.storage import (
            compute_metric_set_hash,
        )

        eid = _make_eval_id()
        msh = compute_metric_set_hash(VALID_METRIC_SET)
        stored = {
            "clustering_id": VALID_CLUSTERING_ID,
            "preprocessed_id": "pp_xyz",
            "dataset_id": "ds_abc",
            "ml_dataset_sha256": VALID_ML_DATASET_SHA,
            "config_sha256": VALID_CONFIG_SHA,
            "noise_policy": "exclude",
            "metric_set_hash": msh,
            "schema_version": EVALUATION_MANIFEST_SCHEMA_VERSION,
        }
        self._write_manifest(tmp_path, eid, stored)
        # Different canonical (e.g. different config_sha256).
        expected = dict(stored)
        expected["config_sha256"] = "d" * 64
        with pytest.raises(Dev05CollisionError):
            find_existing_evaluation(
                base_dir=tmp_path,
                evaluation_id=eid,
                expected_canonical=expected,
            )

    def test_corrupt_manifest_raises_dev05manifestcorrupt(
        self, tmp_path: Path
    ) -> None:
        eid = _make_eval_id()
        run_dir = tmp_path / eid
        run_dir.mkdir(parents=True, exist_ok=True)
        # Missing required canonical key (clustering_id).
        bad = {
            "schema_version": EVALUATION_MANIFEST_SCHEMA_VERSION,
            "evaluation_id": eid,
            "scope": "EVALUATED_PROTOTYPE",
        }
        (run_dir / "evaluation_manifest.json").write_text(
            json.dumps(bad), encoding="utf-8"
        )
        with pytest.raises(Dev05ManifestCorrupt):
            find_existing_evaluation(
                base_dir=tmp_path,
                evaluation_id=eid,
                expected_canonical={
                    "clustering_id": VALID_CLUSTERING_ID,
                    "preprocessed_id": "pp_xyz",
                    "dataset_id": "ds_abc",
                    "ml_dataset_sha256": VALID_ML_DATASET_SHA,
                    "config_sha256": VALID_CONFIG_SHA,
                    "noise_policy": "exclude",
                    "metric_set_hash": "h" * 64,
                    "schema_version": EVALUATION_MANIFEST_SCHEMA_VERSION,
                },
            )

    def test_corrupt_json_raises_dev05manifestcorrupt(self, tmp_path: Path) -> None:
        eid = _make_eval_id()
        run_dir = tmp_path / eid
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "evaluation_manifest.json").write_text(
            "{not valid json", encoding="utf-8"
        )
        with pytest.raises(Dev05ManifestCorrupt):
            find_existing_evaluation(
                base_dir=tmp_path,
                evaluation_id=eid,
                expected_canonical={
                    "clustering_id": VALID_CLUSTERING_ID,
                    "preprocessed_id": "pp_xyz",
                    "dataset_id": "ds_abc",
                    "ml_dataset_sha256": VALID_ML_DATASET_SHA,
                    "config_sha256": VALID_CONFIG_SHA,
                    "noise_policy": "exclude",
                    "metric_set_hash": "h" * 64,
                    "schema_version": EVALUATION_MANIFEST_SCHEMA_VERSION,
                },
            )

    def test_schema_version_mismatch_raises_corrupt(self, tmp_path: Path) -> None:
        """Old schema_version means stored manifest is corrupt for current schema."""
        eid = _make_eval_id()
        bad = {
            "schema_version": "0.9.0",
            "evaluation_id": eid,
            "scope": "EVALUATED_PROTOTYPE",
            "clustering_id": VALID_CLUSTERING_ID,
            "preprocessed_id": "pp_xyz",
            "dataset_id": "ds_abc",
            "ml_dataset_sha256": VALID_ML_DATASET_SHA,
            "config_sha256": VALID_CONFIG_SHA,
            "noise_policy": "exclude",
            "metric_set_hash": "h" * 64,
            "metrics": {},
        }
        run_dir = tmp_path / eid
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "evaluation_manifest.json").write_text(
            json.dumps(bad), encoding="utf-8"
        )
        with pytest.raises(Dev05ManifestCorrupt):
            find_existing_evaluation(
                base_dir=tmp_path,
                evaluation_id=eid,
                expected_canonical={
                    "clustering_id": VALID_CLUSTERING_ID,
                    "preprocessed_id": "pp_xyz",
                    "dataset_id": "ds_abc",
                    "ml_dataset_sha256": VALID_ML_DATASET_SHA,
                    "config_sha256": VALID_CONFIG_SHA,
                    "noise_policy": "exclude",
                    "metric_set_hash": "h" * 64,
                    "schema_version": EVALUATION_MANIFEST_SCHEMA_VERSION,
                },
            )
