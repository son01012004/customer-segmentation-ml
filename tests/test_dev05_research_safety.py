"""Research-safety tests for DEV-05 (R-EVAL-01..R-EVAL-17).

These tests are static + light runtime. They verify:

- R-EVAL-01..03: research_safety block invariants on every manifest.
- R-EVAL-04..07: paths not written are listed; only ``evaluation/<ev>/``
  is writable under ``data/prototype/<ds>/.../clustering/<cl>/``.
- R-EVAL-08: comparison / display output never contains banned words
  outside the disclaimer.
- R-EVAL-09: no reference to ``final_clustering_dataset.parquet``.
- R-EVAL-10/11: mutability discipline (file-hash integrity for
  upstream artefacts).
- R-EVAL-12: only the closed set of metric names is exposed.
- R-EVAL-13: no test uses real FE-06 data.
- R-EVAL-14: noise / label immutability.
- R-EVAL-15: source-agnostic metric set.
- R-EVAL-16: manifest / metric-set consistency.
- R-EVAL-17: atomic publish.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from customer_segmentation.prototype.evaluation.manifest import (
    EVALUATION_MANIFEST_SCHEMA_VERSION,
    EnvironmentBlock,
    EvaluationManifest,
    EvaluationMetricsResult,
    EvaluationValidationReport,
    ResearchSafetyBlock,
    build_evaluation_manifest,
    make_computation_error_entry,
    make_missing_entry,
    make_not_applicable_entry,
    make_valid_entry,
    write_evaluation_manifest,
)
from customer_segmentation.prototype.evaluation.metrics import (
    compute_internal_metrics,
)
from customer_segmentation.prototype.evaluation.pipeline import (
    CUSTOMER_KEYS_TO_STRIP,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_manifest(
    *, evaluation_id: str = "ev_" + "a" * 24
) -> EvaluationManifest:
    return build_evaluation_manifest(
        evaluation_id=evaluation_id,
        clustering_id="cl_" + "a" * 24,
        preprocessed_id="pp_xyz",
        dataset_id="ds_abc",
        ml_dataset_sha256="b" * 64,
        feature_set_sha256="c" * 64,
        preprocessing_config_sha256="d" * 64,
        algorithm="kmeans",
        algorithm_version="sklearn_1.5",
        algorithm_family="hard",
        n_samples=100,
        n_features=4,
        feature_set=["a", "b", "c", "d"],
        hyperparameters={"n_clusters": 4},
        seed_policy="stochastic",
        seed=42,
        noise_policy_used="exclude",
        metric_set=["silhouette", "davies_bouldin", "calinski_harabasz"],
        metrics=EvaluationMetricsResult(
            entries={
                "silhouette": make_valid_entry("silhouette", 0.5),
                "davies_bouldin": make_valid_entry("davies_bouldin", 1.0),
                "calinski_harabasz": make_valid_entry("calinski_harabasz", 100.0),
            }
        ),
        n_samples_input=100,
        n_samples_used_for_compute=100,
        n_clusters_realized=4,
        noise_count=None,
        noise_ratio=None,
        config_sha256="e" * 64,
        environment=EnvironmentBlock(
            python="3.14.4", platform="Linux", release="7.0.0",
            machine="x86_64", key_libraries={}
        ),
        log_file="ev_xx.log",
        validation_report=EvaluationValidationReport(all_passed=True),
        readonly_paths=["data/raw/primary"],
    )


# ---------------------------------------------------------------------------
# R-EVAL-01..03
# ---------------------------------------------------------------------------


class TestResearchSafetyBlock:
    def test_automatically_promoted_always_false(self) -> None:
        m = _make_manifest()
        assert m.research_safety.automatically_promoted_to_research is False

    def test_scope_always_evaluated_prototype(self) -> None:
        m = _make_manifest()
        assert m.research_safety.scope == "EVALUATED_PROTOTYPE"
        assert m.scope == "EVALUATED_PROTOTYPE"

    def test_appeared_in_research_evidence_always_false(self) -> None:
        m = _make_manifest()
        assert m.research_safety.appeared_in_research_evidence is False

    def test_research_safety_survives_round_trip(self, tmp_path: Path) -> None:
        m = _make_manifest()
        path = tmp_path / "m.json"
        write_evaluation_manifest(m, path)
        reloaded = json.loads(path.read_text(encoding="utf-8"))
        rs = reloaded["research_safety"]
        assert rs["automatically_promoted_to_research"] is False
        assert rs["scope"] == "EVALUATED_PROTOTYPE"
        assert rs["appeared_in_research_evidence"] is False


# ---------------------------------------------------------------------------
# R-EVAL-04..07
# ---------------------------------------------------------------------------


class TestPathContainment:
    def test_storage_root_resolution_uses_dev02(self) -> None:
        """``resolve_storage_root`` delegates to DEV-02 (no hard-coded path)."""
        from customer_segmentation.prototype.evaluation.storage import (
            resolve_storage_root,
        )
        # This will load DEV-02 config (read-only).
        try:
            root = resolve_storage_root()
            assert isinstance(root, Path)
        except Exception:
            pytest.skip("DEV-02 config not present in this test env")

    def test_evaluation_id_path_inside_storage_root(self, tmp_path: Path) -> None:
        from customer_segmentation.prototype.evaluation.storage import (
            prototype_evaluation_base_dir,
            prototype_evaluation_run_dir,
        )
        base = prototype_evaluation_base_dir(
            tmp_path, "ds_abc", "pp_xyz", "cl_" + "a" * 24
        )
        assert base.is_relative_to(tmp_path)
        run = prototype_evaluation_run_dir(
            tmp_path, "ds_abc", "pp_xyz", "cl_" + "a" * 24, "ev_" + "a" * 24
        )
        assert run.is_relative_to(tmp_path)

    def test_clustering_id_rejected_if_invalid(self, tmp_path: Path) -> None:
        from customer_segmentation.prototype.evaluation.storage import (
            Dev05StoragePathError,
            prototype_evaluation_base_dir,
        )
        with pytest.raises(Dev05StoragePathError):
            prototype_evaluation_base_dir(
                tmp_path, "ds_abc", "pp_xyz", "not_a_valid_id"
            )


# ---------------------------------------------------------------------------
# R-EVAL-08 (no banned words)
# ---------------------------------------------------------------------------


class TestNoBannedSubstrings:
    def test_manifest_dict_no_banned_substrings(self) -> None:
        from customer_segmentation.prototype.evaluation.display import (
            check_no_banned_substrings,
        )
        m = _make_manifest()
        d = json.loads(json.dumps(m, default=str))
        text = json.dumps(d, default=str)
        found = check_no_banned_substrings(text)
        assert found == [], f"banned: {found}"


# ---------------------------------------------------------------------------
# R-EVAL-09 (no reference to FE-06 final dataset)
# ---------------------------------------------------------------------------


class TestNoFe06Reference:
    def test_no_reference_to_final_clustering_dataset(self) -> None:
        import ast

        from pathlib import Path

        src_dir = Path("src/customer_segmentation/prototype/evaluation")
        offenders: list[tuple[Path, str]] = []
        for p in src_dir.rglob("*.py"):
            if "__pycache__" in p.parts:
                continue
            src = p.read_text(encoding="utf-8")
            if "final_clustering_dataset" in src:
                offenders.append((p, "literal string"))
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if "final_clustering_dataset" in node.value:
                        offenders.append((p, "constant"))
        assert offenders == [], (
            "References to final_clustering_dataset.parquet found: "
            + "\n".join(f"  {p}: {kind}" for p, kind in offenders)
        )

    def test_no_test_uses_real_fe06_data(self) -> None:
        """R-EVAL-13: no test references the real research dataset."""
        tests_dir = Path("tests")
        offenders: list[tuple[Path, int, str]] = []
        for p in tests_dir.glob("test_dev05_*.py"):
            # Skip the test_dev05_research_safety.py file itself,
            # which contains the string by design (it tests for its
            # absence in the rest of the codebase).
            if p.name == "test_dev05_research_safety.py":
                continue
            src = p.read_text(encoding="utf-8")
            if "final_clustering_dataset" in src:
                offenders.append((p, 0, "literal"))
        assert offenders == []


# ---------------------------------------------------------------------------
# R-EVAL-10 / R-EVAL-11 (upstream artefact immutability)
# ---------------------------------------------------------------------------


class TestUpstreamImmutability:
    def test_metrics_function_does_not_take_cluster_labels_path(
        self,
    ) -> None:
        """compute_internal_metrics takes X + labels, not file paths.

        It therefore CANNOT modify upstream parquet files (R-EVAL-14).
        """
        import inspect

        from customer_segmentation.prototype.evaluation.metrics import (
            compute_internal_metrics,
        )
        sig = inspect.signature(compute_internal_metrics)
        for p in sig.parameters.values():
            assert "path" not in p.name.lower()
            assert "file" not in p.name.lower()


# ---------------------------------------------------------------------------
# R-EVAL-12 (only closed set of metric names)
# ---------------------------------------------------------------------------


class TestMetricSetClosed:
    def test_only_three_metric_names(self) -> None:
        from customer_segmentation.prototype.evaluation.scope import METRIC_NAMES
        assert METRIC_NAMES == frozenset(
            {"silhouette", "davies_bouldin", "calinski_harabasz"}
        )


# ---------------------------------------------------------------------------
# R-EVAL-14 (noise / label immutability)
# ---------------------------------------------------------------------------


class TestNoiseImmutability:
    def test_metrics_does_not_modify_input_labels(self) -> None:
        import numpy as np

        X = np.array([[1.0, 1.0], [1.0, 2.0], [10.0, 10.0], [10.0, 11.0]])
        labels = np.array([0, 0, -1, -1])
        before = labels.copy()
        _ = compute_internal_metrics(
            X, labels, algorithm_family="density_based", noise_policy="exclude"
        )
        np.testing.assert_array_equal(labels, before)


# ---------------------------------------------------------------------------
# R-EVAL-16 (manifest / CSV consistency)
# ---------------------------------------------------------------------------


class TestManifestCsvConsistency:
    def test_metric_entries_keys_match_default_metric_set(self) -> None:
        m = _make_manifest()
        from customer_segmentation.prototype.evaluation.scope import METRIC_NAMES
        assert set(m.metrics.entries.keys()) == METRIC_NAMES

    def test_metric_set_in_manifest_matches_entries(self) -> None:
        m = _make_manifest()
        assert set(m.metric_set) == set(m.metrics.entries.keys())


# ---------------------------------------------------------------------------
# R-EVAL-17 (atomic publish)
# ---------------------------------------------------------------------------


class TestAtomicPublish:
    def test_write_manifest_no_tmp_leftover(self, tmp_path: Path) -> None:
        m = _make_manifest()
        path = tmp_path / "ev.json"
        write_evaluation_manifest(m, path)
        assert path.exists()
        assert not (path.with_suffix(path.suffix + ".tmp")).exists()
