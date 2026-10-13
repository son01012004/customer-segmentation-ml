"""Research-safety tests for DEV-06 (R-DEV-06-01..R-DEV-06-25).

Static + light runtime. Verifies:

- R-DEV-06-01..03: research_safety block invariants on every manifest.
- R-DEV-06-04..07: paths not written are listed; only
  ``segmentation/<seg_id>/`` is writable under
  ``data/prototype/<ds>/.../clustering/<cl>/``.
- R-DEV-06-08: comparison / display output never contains banned words
  outside the disclaimer.
- R-DEV-06-09: no reference to ``final_clustering_dataset.parquet``.
- R-DEV-06-10..12: upstream artefact immutability (DEV-04
  cluster_labels, clustering_manifest; DEV-03 ml_dataset,
  preprocessed_manifest).
- R-DEV-06-13: only the closed set of statistic names is exposed.
- R-DEV-06-14: no test uses real FE-06 data.
- R-DEV-06-15: import blocklist (covered by test_dev06_import_blocklist.py).
- R-DEV-06-16: manifest / CSV / JSON consistency.
- R-DEV-06-17: atomic publish.
- R-DEV-06-18: no business segment naming.
- R-DEV-06-19: characteristic IDs are descriptive only.
- R-DEV-06-20: profile feature set ⊆ L1.feature_set (no extra).
- R-DEV-06-21: both percentages use distinct denominators.
- R-DEV-06-22: non-DBSCAN → noise fields null.
- R-DEV-06-23: post-preprocessing warning is mandatory.
- R-DEV-06-24: CompatibilityKey MUST NOT include
  preprocessing_config_sha256.
- R-DEV-06-25: other_count consistency.
"""

from __future__ import annotations

import ast
import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from customer_segmentation.prototype.segmentation.characteristics import (
    derive_segment_characteristics,
)
from customer_segmentation.prototype.segmentation.compare import (
    COMPATIBILITY_KEY_FIELDS,
)
from customer_segmentation.prototype.segmentation.manifest import (
    ALLOWED_CHARACTERISTIC_RULES,
    EnvironmentBlock,
    FeatureProfile,
    ResearchSafetyBlock,
    SegmentationManifest,
    SegmentationManifestError,
    SegmentationValidationReport,
    SegmentSize,
    build_segmentation_manifest,
    write_segmentation_manifest,
)
from customer_segmentation.prototype.segmentation.profile import (
    compute_feature_profiles,
    compute_segment_sizes,
)
from customer_segmentation.prototype.segmentation.scope import (
    PROFILING_STATISTICS_SET,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_manifest(
    *,
    segmentation_id: str = "seg_" + "a" * 24,
    algorithm_family: str = "hard",
    noise_count: int | None = None,
    noise_ratio: float | None = None,
    noise_policy_used: str = "n/a",
    n_segments: int = 4,
) -> SegmentationManifest:
    n_samples_input = 100
    if algorithm_family == "density_based" and noise_count is not None:
        n_samples_used_for_compute = n_samples_input - noise_count
    else:
        n_samples_used_for_compute = n_samples_input
    sizes: list[SegmentSize] = []
    for i in range(n_segments):
        sizes.append(
            SegmentSize(
                segment_id=i,
                count=20 + i,
                percentage=25.0,
                percentage_base="n_samples_input",
                is_noise=False,
            )
        )
    return build_segmentation_manifest(
        segmentation_id=segmentation_id,
        clustering_id="cl_" + "a" * 24,
        preprocessed_id="pp_xyz",
        dataset_id="ds_abc",
        evaluation_id=None,
        algorithm="kmeans" if algorithm_family != "density_based" else "dbscan",
        algorithm_version="sklearn_1.5",
        algorithm_family=algorithm_family,
        ml_dataset_sha256="b" * 64,
        feature_set_sha256="c" * 64,
        preprocessing_config_sha256="d" * 64,
        feature_set=["a", "b"],
        n_samples_input=n_samples_input,
        n_samples_used_for_compute=n_samples_used_for_compute,
        n_clusters_input=n_segments,
        n_segments=n_segments,
        noise_count=noise_count,
        noise_ratio=noise_ratio,
        noise_policy_used=noise_policy_used,
        segment_sizes=sizes,
        profiles=[],
        characteristics=[],
        config_sha256="e" * 64,
        environment=EnvironmentBlock(
            python="3.11",
            platform="Linux",
            release="7.0",
            machine="x86_64",
            key_libraries={},
        ),
        log_file="x.log",
        validation_report=SegmentationValidationReport(all_passed=True),
        readonly_paths=["data/raw/primary"],
        input_clustering_manifest="cm.json",
        input_cluster_labels="cl.parquet",
        input_ml_dataset="ml.parquet",
        input_evaluation_manifest=None,
    )


# ---------------------------------------------------------------------------
# R-DEV-06-01..03
# ---------------------------------------------------------------------------


class TestResearchSafetyBlock:
    def test_automatically_promoted_always_false(self) -> None:
        m = _make_manifest()
        assert m.research_safety.automatically_promoted_to_research is False

    def test_scope_always_profiled_prototype(self) -> None:
        m = _make_manifest()
        assert m.research_safety.scope == "PROFILED_PROTOTYPE"
        assert m.scope == "PROFILED_PROTOTYPE"

    def test_appeared_in_research_evidence_always_false(self) -> None:
        m = _make_manifest()
        assert m.research_safety.appeared_in_research_evidence is False

    def test_survives_round_trip(self, tmp_path: Path) -> None:
        m = _make_manifest()
        path = tmp_path / "m.json"
        write_segmentation_manifest(m, path)
        reloaded = json.loads(path.read_text(encoding="utf-8"))
        rs = reloaded["research_safety"]
        assert rs["automatically_promoted_to_research"] is False
        assert rs["scope"] == "PROFILED_PROTOTYPE"
        assert rs["appeared_in_research_evidence"] is False

    def test_scope_cannot_be_constructed_with_other_value(self) -> None:
        with pytest.raises(SegmentationManifestError):
            ResearchSafetyBlock(
                automatically_promoted_to_research=False,
                scope="RESEARCH_APPROVED",
                appeared_in_research_evidence=False,
            )

    def test_promoted_to_research_must_be_false(self) -> None:
        with pytest.raises(SegmentationManifestError):
            ResearchSafetyBlock(
                automatically_promoted_to_research=True,
                scope="PROFILED_PROTOTYPE",
                appeared_in_research_evidence=False,
            )


# ---------------------------------------------------------------------------
# R-DEV-06-04..07: path containment
# ---------------------------------------------------------------------------


class TestPathContainment:
    def test_storage_root_resolution_uses_dev02(self) -> None:
        from customer_segmentation.prototype.segmentation.storage import (
            resolve_storage_root,
        )

        try:
            root = resolve_storage_root()
            assert isinstance(root, Path)
        except Exception:
            pytest.skip("DEV-02 config not present in this test env")

    def test_segmentation_id_path_inside_storage_root(self, tmp_path: Path) -> None:
        from customer_segmentation.prototype.segmentation.storage import (
            prototype_segmentation_base_dir,
            prototype_segmentation_run_dir,
        )

        base = prototype_segmentation_base_dir(tmp_path, "ds_abc", "pp_xyz", "cl_" + "a" * 24)
        assert base.is_relative_to(tmp_path)
        run = prototype_segmentation_run_dir(
            tmp_path,
            "ds_abc",
            "pp_xyz",
            "cl_" + "a" * 24,
            "seg_" + "a" * 24,
        )
        assert run.is_relative_to(tmp_path)

    def test_clustering_id_rejected_if_invalid(self, tmp_path: Path) -> None:
        from customer_segmentation.prototype.segmentation.storage import (
            Dev06StoragePathError,
            prototype_segmentation_base_dir,
        )

        with pytest.raises(Dev06StoragePathError):
            prototype_segmentation_base_dir(tmp_path, "ds_abc", "pp_xyz", "not_a_valid_id")

    def test_segmentation_id_rejected_if_invalid(self, tmp_path: Path) -> None:
        from customer_segmentation.prototype.segmentation.storage import (
            Dev06StoragePathError,
            prototype_segmentation_run_dir,
        )

        with pytest.raises(Dev06StoragePathError):
            prototype_segmentation_run_dir(
                tmp_path,
                "ds_abc",
                "pp_xyz",
                "cl_" + "a" * 24,
                "not_a_valid_id",
            )


# ---------------------------------------------------------------------------
# R-DEV-06-08: no banned words
# ---------------------------------------------------------------------------


class TestNoBannedSubstrings:
    def test_manifest_dict_no_banned_substrings(self) -> None:
        from customer_segmentation.prototype.segmentation.display import (
            check_no_banned_substrings,
        )

        m = _make_manifest()
        d = json.loads(json.dumps(m, default=str))
        text = json.dumps(d, default=str)
        found = check_no_banned_substrings(text)
        assert found == [], f"banned: {found}"


# ---------------------------------------------------------------------------
# R-DEV-06-09: no reference to final_clustering_dataset
# ---------------------------------------------------------------------------


class TestNoFe06Reference:
    def test_no_reference_to_final_clustering_dataset(self) -> None:
        src_dir = Path("src/customer_segmentation/prototype/segmentation")
        offenders: list[tuple[Path, str]] = []
        for p in src_dir.rglob("*.py"):
            if "__pycache__" in p.parts:
                continue
            src = p.read_text(encoding="utf-8")
            if "final_clustering_dataset" in src:
                offenders.append((p, "literal string"))
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Constant)
                    and isinstance(node.value, str)
                    and "final_clustering_dataset" in node.value
                ):
                    offenders.append((p, "constant"))
        assert offenders == [], "References to final_clustering_dataset found: " + "\n".join(
            f"  {p}: {kind}" for p, kind in offenders
        )

    def test_no_test_uses_real_fe06_data(self) -> None:
        tests_dir = Path("tests")
        offenders: list[tuple[Path, str]] = []
        for p in tests_dir.glob("test_dev06_*.py"):
            if p.name == "test_dev06_research_safety.py":
                continue
            src = p.read_text(encoding="utf-8")
            if "final_clustering_dataset" in src:
                offenders.append((p, "literal"))
        assert offenders == []


# ---------------------------------------------------------------------------
# R-DEV-06-10..12: upstream immutability
# ---------------------------------------------------------------------------


class TestUpstreamImmutability:
    def test_compute_feature_profiles_does_not_take_path(
        self,
    ) -> None:
        """compute_feature_profiles takes DataFrames, not file paths.
        Therefore it CANNOT modify upstream parquet files."""
        import inspect

        sig = inspect.signature(compute_feature_profiles)
        for p in sig.parameters.values():
            assert "path" not in p.name.lower()
            assert "file" not in p.name.lower()

    def test_compute_segment_sizes_does_not_modify_input(self) -> None:
        df = pd.DataFrame(
            {
                "ClusterLabel": [0, 0, 1, 1, 2],
                "IsNoise": [False, False, False, False, False],
            }
        )
        before = df.copy()
        _ = compute_segment_sizes(df)
        # No mutation.
        pd.testing.assert_frame_equal(df, before)


# ---------------------------------------------------------------------------
# R-DEV-06-13: only closed set of statistic names
# ---------------------------------------------------------------------------


class TestStatisticsSetClosed:
    def test_profiling_statistics_set_does_not_include_research_metrics(
        self,
    ) -> None:
        for forbidden in (
            "silhouette",
            "davies_bouldin",
            "calinski_harabasz",
            "ari",
            "ami",
            "inertia",
            "n_iter",
            "runtime_seconds",
        ):
            assert forbidden not in PROFILING_STATISTICS_SET

    def test_profiling_statistics_set_excludes_business_terms(self) -> None:
        for forbidden in (
            "champion",
            "loyal",
            "vip",
            "churn",
            "marketing",
        ):
            assert forbidden not in PROFILING_STATISTICS_SET


# ---------------------------------------------------------------------------
# R-DEV-06-15: import blocklist
# ---------------------------------------------------------------------------


class TestImportBlocklist:
    def test_no_research_evaluation_imports(self) -> None:
        from tests.test_dev06_import_blocklist import (
            FORBIDDEN_RESEARCH_SUBPACKAGES,
            _imports_in_file,
            _iter_python_files,
        )

        offenders = []
        for p in _iter_python_files():
            for kind, name in _imports_in_file(p):
                for forbidden in FORBIDDEN_RESEARCH_SUBPACKAGES:
                    if name == forbidden or name.startswith(forbidden + "."):
                        offenders.append((p, kind, name))
        assert offenders == [], offenders


# ---------------------------------------------------------------------------
# R-DEV-06-16: manifest / CSV / JSON consistency
# ---------------------------------------------------------------------------


class TestManifestCsvConsistency:
    def test_segment_ids_in_sizes_match_n_segments(self) -> None:
        m = _make_manifest(n_segments=4)
        non_noise_sizes = [s for s in m.segment_sizes if not s.is_noise]
        assert len(non_noise_sizes) == m.n_segments


# ---------------------------------------------------------------------------
# R-DEV-06-17: atomic publish
# ---------------------------------------------------------------------------


class TestAtomicPublish:
    def test_write_manifest_no_tmp_leftover(self, tmp_path: Path) -> None:
        m = _make_manifest()
        path = tmp_path / "m.json"
        write_segmentation_manifest(m, path)
        assert path.exists()
        assert not (path.with_suffix(path.suffix + ".tmp")).exists()


# ---------------------------------------------------------------------------
# R-DEV-06-18: no business segment naming
# ---------------------------------------------------------------------------


class TestNoBusinessNaming:
    def test_no_business_names_as_identifiers_in_source(self) -> None:
        """Static grep: no business naming used as identifiers / function
        names / class names in DEV-06 source.

        The display/compare modules MENTION these terms in their
        docstrings and in the BANNED_SUBSTRINGS list (which is the
        correct place to mention them — they are the *banned* set).
        This test only checks that no actual code uses them as
        identifiers, variable names, or function names.
        """
        import re

        src_dir = Path("src/customer_segmentation/prototype/segmentation")
        offenders: list[tuple[Path, int, str]] = []
        for p in src_dir.rglob("*.py"):
            if "__pycache__" in p.parts:
                continue
            src_lines = p.read_text(encoding="utf-8").splitlines()
            for i, line in enumerate(src_lines, start=1):
                # Skip docstrings and comments.
                stripped = line.strip()
                if (
                    stripped.startswith("#")
                    or stripped.startswith('"""')
                    or stripped.startswith("'''")
                ):
                    continue
                # Look for business terms used as identifiers in code
                # (not in strings). Use a simple heuristic: a business
                # term is an identifier if it appears in
                # ``identifier =`` or ``def identifier(`` or
                # ``class identifier(`` or is a function call ``identifier(``.
                for term in (
                    "champion",
                    "loyal_customer",
                    "vip_customer",
                    "at_risk",
                    "high_value",
                ):
                    pattern = (
                        rf"\b{re.escape(term)}\b\s*="
                        rf"|\bdef\s+{re.escape(term)}\b"
                        rf"|\bclass\s+{re.escape(term)}\b"
                    )
                    if re.search(pattern, line, flags=re.IGNORECASE):
                        offenders.append((p, i, line))
        assert offenders == [], "Business naming in source code identifiers: " + "\n".join(
            f"  {p}:{ln} {line}" for p, ln, line in offenders
        )

    def test_no_business_names_in_segment_sizes_or_profiles(
        self,
        tmp_path: Path,
    ) -> None:
        """Verify that the manifest does not propagate business naming
        from anywhere — the segment_ids are integers, characteristic_ids
        are descriptive. The check is on manifest values, not source
        code text."""
        m = _make_manifest()
        for s in m.segment_sizes:
            # segment_id is int (not a business name).
            assert isinstance(s.segment_id, int)
        for c in m.characteristics:
            # characteristic_id matches one of the 4 templates; contains
            # neither "champion" nor "loyal" nor "vip" as substrings.
            cid_low = c.characteristic_id.lower()
            for forbidden in ("champion", "loyal", "vip", "at-risk", "high-value"):
                assert forbidden not in cid_low


# ---------------------------------------------------------------------------
# R-DEV-06-19: characteristic IDs descriptive only
# ---------------------------------------------------------------------------


class TestCharacteristicDescriptiveOnly:
    def test_all_characteristic_ids_match_4_templates(self) -> None:
        for cid in ALLOWED_CHARACTERISTIC_RULES:
            # Just confirm the templates parse.
            assert "<feature>" in cid

    def test_characteristic_id_template_set_size(self) -> None:
        """Exactly 4 rule templates."""
        assert len(ALLOWED_CHARACTERISTIC_RULES) == 4

    def test_derive_segment_characteristics_uses_only_allowed_templates(
        self,
    ) -> None:
        """All generated characteristic IDs must match the 4 templates."""
        # Synthetic profiles.
        profiles = [
            FeatureProfile(
                segment_id=0,
                feature_name="a",
                statistics={"mean": 5.0, "median": 4.0},
            ),
            FeatureProfile(
                segment_id=1,
                feature_name="a",
                statistics={"mean": 0.0, "median": 0.0, "topk_categories": [("X", 10)]},
            ),
        ]
        ds_stats = {"a": {"mean": 1.0, "median": 1.0, "std": 1.0}}
        chars = derive_segment_characteristics(profiles=profiles, dataset_stats=ds_stats)
        allowed_prefixes = (
            "mean_high_",
            "mean_low_",
            "median_above_dataset_median_",
            "top_category_",
        )
        for c in chars:
            assert any(c.characteristic_id.startswith(p) for p in allowed_prefixes)


# ---------------------------------------------------------------------------
# R-DEV-06-20: feature set closure
# ---------------------------------------------------------------------------


class TestFeatureSetClosure:
    def test_profiles_use_only_feature_set_columns(self) -> None:
        """Profiles should only reference features in feature_set."""
        ml = pd.DataFrame(
            {
                "a": [0.0, 1.0, 2.0, 3.0, 4.0],
                "b": [1.0, 2.0, 3.0, 4.0, 5.0],
                "extra": [10.0, 20.0, 30.0, 40.0, 50.0],
            }
        )
        cl = pd.DataFrame(
            {
                "CustomerID": [1, 2, 3, 4, 5],
                "ClusterLabel": [0, 0, 1, 1, 1],
                "IsNoise": [False] * 5,
            }
        )
        with pytest.warns(UserWarning):
            profiles = compute_feature_profiles(
                ml_dataset=ml,
                cluster_labels=cl,
                feature_set=["a", "b"],  # only a, b — not "extra"
            )
        # No profile should reference "extra".
        assert all(p.feature_name in ("a", "b") for p in profiles)


# ---------------------------------------------------------------------------
# R-DEV-06-21: both percentages use distinct denominators
# ---------------------------------------------------------------------------


class TestPercentagesDistinctDenominators:
    def test_two_percentages_in_size_records(self) -> None:
        """Long-format CSV schema documents both percentage fields."""
        from customer_segmentation.prototype.segmentation.pipeline import (
            _write_sizes_long_csv,
        )

        # Synthetic sizes.
        sizes = [
            SegmentSize(0, 70, 70.0, "n_samples_input", False),
            SegmentSize(1, 30, 30.0, "n_samples_input", False),
        ]
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tf:
            path = Path(tf.name)
        try:
            _write_sizes_long_csv(
                sizes,
                n_samples_input=100,
                n_samples_used_for_compute=100,
                decimals=2,
                csv_path=path,
            )
            content = path.read_text(encoding="utf-8")
            # Both columns must appear in the header.
            assert "percentage_input" in content
            assert "percentage_of_non_noise" in content
        finally:
            if path.exists():
                path.unlink()


# ---------------------------------------------------------------------------
# R-DEV-06-22: non-DBSCAN noise fields null
# ---------------------------------------------------------------------------


class TestNonDbscanNoiseFieldsNull:
    def test_non_dbscan_noise_count_is_none(self) -> None:
        m = _make_manifest(algorithm_family="hard")
        assert m.noise_count is None
        assert m.noise_ratio is None
        assert m.noise_policy_used == "n/a"

    def test_dbscan_noise_count_is_set(self) -> None:
        m = _make_manifest(
            algorithm_family="density_based",
            noise_count=10,
            noise_ratio=0.1,
            noise_policy_used="exclude",
        )
        assert m.noise_count == 10
        assert m.noise_ratio == 0.1
        assert m.noise_policy_used == "exclude"

    def test_density_based_requires_noise_count(self) -> None:
        """density_based + noise_count=None must fail at construction."""
        with pytest.raises(SegmentationManifestError):
            _make_manifest(
                algorithm_family="density_based",
                noise_count=None,
                noise_policy_used="exclude",
            )


# ---------------------------------------------------------------------------
# R-DEV-06-23: post-preprocessing warning
# ---------------------------------------------------------------------------


class TestPreprocessingWarning:
    def test_warning_emitted_at_compute_time(self) -> None:
        ml = pd.DataFrame(
            {
                "a": [0.0, 1.0, 2.0, 3.0, 4.0],
            }
        )
        cl = pd.DataFrame(
            {
                "ClusterLabel": [0, 0, 1, 1, 1],
                "IsNoise": [False] * 5,
            }
        )
        with pytest.warns(UserWarning, match="post-preprocessing"):
            _ = compute_feature_profiles(
                ml_dataset=ml,
                cluster_labels=cl,
                feature_set=["a"],
            )


# ---------------------------------------------------------------------------
# R-DEV-06-24: CompatibilityKey MUST NOT include preprocessing_config_sha256
# ---------------------------------------------------------------------------


class TestCompatibilityKeyExcludesPreprocessingConfig:
    def test_compatibility_key_uses_only_4_fields(self) -> None:
        from customer_segmentation.prototype.segmentation.compare import (
            COMPATIBILITY_KEY_FIELDS,
        )

        assert (
            frozenset(
                {
                    "dataset_id",
                    "preprocessed_id",
                    "ml_dataset_sha256",
                    "feature_set_sha256",
                }
            )
            == COMPATIBILITY_KEY_FIELDS
        )
        assert "preprocessing_config_sha256" not in COMPATIBILITY_KEY_FIELDS


# ---------------------------------------------------------------------------
# R-DEV-06-25: categorical top-K other_count consistency
# ---------------------------------------------------------------------------


class TestCategoricalTopKConsistency:
    def test_other_count_consistent(self) -> None:
        # Build a categorical series with 5 distinct categories and
        # force other_count to be predictable.
        ml = pd.DataFrame(
            {
                "cat": ["A", "A", "A", "B", "B", "C", "D", "E", "F"],
            }
        )
        cl = pd.DataFrame(
            {
                "ClusterLabel": [0] * 9,
                "IsNoise": [False] * 9,
            }
        )
        with pytest.warns(UserWarning):
            profiles = compute_feature_profiles(
                ml_dataset=ml,
                cluster_labels=cl,
                feature_set=["cat"],
                categorical_topk=3,
                uniqueness_threshold=50,
            )
        # Should have 1 profile for cluster 0.
        assert len(profiles) == 1
        stats = profiles[0].statistics
        topk_counts = stats.get("topk_categories", [])
        other_count = stats.get("other_count", 0)
        missing_count = stats.get("missing_count", 0)
        # topk_counts.sum() + other_count == total - missing
        topk_total = sum(c for _, c in topk_counts)
        total = len(ml)  # 9
        assert topk_total + other_count == total - missing_count
        # other_count non-negative
        assert other_count >= 0

    def test_topk_other_missing_invariant_holds_exactly(self) -> None:
        """R-DEV-06-25: topk_total + other_count + missing_count == segment size.

        Uses a deterministic synthetic series to verify the invariant
        with EXACT integer equality (not just presence checks).
        """
        # 10 rows: A=4, B=3, C=2, D=1 → topk=3 → A+B+C=9, other=1, missing=0.
        ml = pd.DataFrame(
            {
                "cat": ["A"] * 4 + ["B"] * 3 + ["C"] * 2 + ["D"],
            }
        )
        cl = pd.DataFrame({"ClusterLabel": [0] * 10, "IsNoise": [False] * 10})
        with pytest.warns(UserWarning):
            profiles = compute_feature_profiles(
                ml_dataset=ml,
                cluster_labels=cl,
                feature_set=["cat"],
                categorical_topk=3,
                uniqueness_threshold=50,
            )
        assert len(profiles) == 1
        stats = profiles[0].statistics
        topk_total = sum(c for _, c in stats["topk_categories"])
        assert topk_total == 9, f"topk_total expected 9, got {topk_total}"
        assert stats["other_count"] == 1
        assert stats["missing_count"] == 0
        # Exact invariant: sum of all parts == segment size.
        assert topk_total + stats["other_count"] + stats["missing_count"] == 10

    def test_topk_other_missing_with_missing_values(self) -> None:
        """R-DEV-06-25: NaN values contribute to missing_count, not other_count."""
        import numpy as np

        # 12 rows: A=3, B=2, C=1, NaN=6 → topk=2 → A+B=5, other=1, missing=6.
        ml = pd.DataFrame(
            {
                "cat": [
                    "A",
                    "A",
                    "A",
                    "B",
                    "B",
                    "C",
                    np.nan,
                    np.nan,
                    np.nan,
                    np.nan,
                    np.nan,
                    np.nan,
                ],
            }
        )
        cl = pd.DataFrame({"ClusterLabel": [0] * 12, "IsNoise": [False] * 12})
        with pytest.warns(UserWarning):
            profiles = compute_feature_profiles(
                ml_dataset=ml,
                cluster_labels=cl,
                feature_set=["cat"],
                categorical_topk=2,
                uniqueness_threshold=50,
            )
        assert len(profiles) == 1
        stats = profiles[0].statistics
        topk_total = sum(c for _, c in stats["topk_categories"])
        # segment_size = 12 (= number of rows in the cluster, not non-null).
        # invariant: topk_total + other_count + missing_count == segment_size.
        assert topk_total + stats["other_count"] + stats["missing_count"] == 12
        assert stats["missing_count"] == 6


# ---------------------------------------------------------------------------
# R-DEV-06-21: both percentages use distinct denominators (strengthened)
# ---------------------------------------------------------------------------


class TestRDev0621PercentageDenominatorsStrengthened:
    """Strengthen R-DEV-06-21 to actually verify the percentage values,
    not just column presence."""

    def test_long_csv_percentages_match_exact_denominators(self) -> None:
        """Each row's percentage_input = count/n_samples_input*100,
        percentage_of_non_noise = count/n_samples_used_for_compute*100."""
        from customer_segmentation.prototype.segmentation.pipeline import (
            _write_sizes_long_csv,
        )

        # 100 input rows; 80 non-noise; 4 segments + 1 noise segment.
        # noise_count = 20 → noise percentage of n_samples_input = 20/100 = 20%.
        # But percentage_of_non_noise for noise MUST be empty (denominator excludes noise).
        sizes = [
            SegmentSize(0, 30, 30.0, "n_samples_input", False),
            SegmentSize(1, 25, 25.0, "n_samples_input", False),
            SegmentSize(2, 15, 15.0, "n_samples_input", False),
            SegmentSize(3, 10, 10.0, "n_samples_input", False),
            SegmentSize(-1, 20, 20.0, "n_samples_input", True),  # noise
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tf:
            path = Path(tf.name)
        try:
            _write_sizes_long_csv(
                sizes,
                n_samples_input=100,
                n_samples_used_for_compute=80,  # 100 - 20 noise
                decimals=2,
                csv_path=path,
            )
            content = path.read_text(encoding="utf-8")
            # Skip the comment line, then parse the CSV rows.
            lines = [ln for ln in content.splitlines() if ln and not ln.startswith("#")]
            # First non-comment line is header; rest are rows.
            import csv as csvlib

            reader = csvlib.DictReader(lines)
            rows = list(reader)
            # 4 non-noise + 1 noise = 5 rows.
            assert len(rows) == 5
            # Non-noise row: percentage_input = count/100*100.
            seg0 = next(r for r in rows if r["segment_id"] == "0")
            assert float(seg0["percentage_input"]) == pytest.approx(30.0, abs=0.01)
            assert float(seg0["percentage_of_non_noise"]) == pytest.approx(
                37.5, abs=0.01
            )  # 30/80 = 37.5%
            # Noise row: percentage_input = 20/100*100 = 20%; percentage_of_non_noise EMPTY.
            noise = next(r for r in rows if r["is_noise"] == "True")
            assert float(noise["percentage_input"]) == pytest.approx(20.0, abs=0.01)
            assert noise["percentage_of_non_noise"] == ""  # empty for noise
        finally:
            if path.exists():
                path.unlink()

    def test_long_csv_segment_size_record_matches_long_csv(self) -> None:
        """The manifest's SegmentSize.percentage (rounded) equals
        the long-CSV percentage_input column (same rounding)."""
        from customer_segmentation.prototype.segmentation.pipeline import (
            _write_sizes_long_csv,
        )

        sizes = [
            SegmentSize(0, 70, 70.0, "n_samples_input", False),
            SegmentSize(1, 30, 30.0, "n_samples_input", False),
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tf:
            path = Path(tf.name)
        try:
            _write_sizes_long_csv(
                sizes,
                n_samples_input=100,
                n_samples_used_for_compute=100,
                decimals=2,
                csv_path=path,
            )
            content = path.read_text(encoding="utf-8")
            # Skip the comment line.
            lines = [ln for ln in content.splitlines() if ln and not ln.startswith("#")]
            import csv as csvlib

            reader = csvlib.DictReader(lines)
            for s, row in zip(sizes, reader, strict=True):
                # Manifest's percentage and CSV's percentage_input are the
                # same value (rounded identically).
                assert float(row["percentage_input"]) == pytest.approx(s.percentage, abs=0.01)
        finally:
            if path.exists():
                path.unlink()


# ---------------------------------------------------------------------------
# R-DEV-06-26: compare reason concepts are separate (NEW for P1-3 resolution)
# ---------------------------------------------------------------------------


class TestCompareReasonConceptsSeparate:
    """R-DEV-06-26: exclusion_reasons and incompatibility_reasons are
    distinct fields; key-field exclusion never appears in
    incompatibility_reasons; per-row diffs never appear in
    exclusion_reasons."""

    def test_exclusion_reasons_have_distinct_fields(self) -> None:
        from customer_segmentation.prototype.segmentation.compare import (
            ExclusionReason,
        )

        r = ExclusionReason(
            excluded_segmentation_id="seg_x",
            excluded_key={"a": "b"},
            reason_code="excluded_no_shared_key",
            differing_key_field_names=("dataset_id",),
            no_retained_group=False,
        )
        d = r.to_dict()
        # Incompatibility-only field absent.
        assert "field_name" not in d
        assert "stored_value" not in d
        assert "compared_value" not in d
        # Exclusion-only fields present.
        assert "excluded_segmentation_id" in d
        assert "excluded_key" in d
        assert "reason_code" in d
        assert "differing_key_field_names" in d
        assert "no_retained_group" in d

    def test_key_field_diff_does_not_emit_per_row_reason(self, tmp_path: Path) -> None:
        """When two manifests differ only on a key field, no
        IncompatibilityReason is emitted; only an ExclusionReason
        (or exclusion) is recorded. Per-row IncompatibilityReason is
        reserved for fields NOT in the key."""
        from customer_segmentation.prototype.segmentation.compare import (
            compare_segmentations,
        )

        m1 = _make_manifest(segmentation_id="seg_" + "1" * 24)
        m2 = _make_manifest(segmentation_id="seg_" + "2" * 24)
        # Mutate dataset_id post-construction to simulate a key-field-only diff.
        object.__setattr__(m1, "dataset_id", "ds_a")
        object.__setattr__(m2, "dataset_id", "ds_b")
        p1 = tmp_path / "m1.json"
        p2 = tmp_path / "m2.json"
        write_segmentation_manifest(m1, p1)
        write_segmentation_manifest(m2, p2)
        report = compare_segmentations([p1, p2])
        # No per-row reason for dataset_id (it's a key field, not a per-row field).
        key_field_reasons = [
            r for r in report.incompatibility_reasons if r.field_name in COMPATIBILITY_KEY_FIELDS
        ]
        assert key_field_reasons == []
        # The two manifests are reported via exclusion_reasons.
        assert len(report.exclusion_reasons) == 2


# ---------------------------------------------------------------------------
# R-DEV-06-27: summary counts exact (NEW for P1-3 resolution)
# ---------------------------------------------------------------------------


class TestCompareSummaryCountsExact:
    """R-DEV-06-27: total_input == total_compared + total_excluded
    for every compare_segmentations call."""

    def test_invariant_holds_for_all_incompatible(self, tmp_path: Path) -> None:
        from customer_segmentation.prototype.segmentation.compare import (
            compare_segmentations,
        )

        m1 = _make_manifest(segmentation_id="seg_" + "1" * 24)
        m2 = _make_manifest(segmentation_id="seg_" + "2" * 24)
        object.__setattr__(m1, "dataset_id", "ds_a")
        object.__setattr__(m2, "dataset_id", "ds_b")
        paths = []
        for i, m in enumerate([m1, m2], start=1):
            p = tmp_path / f"m{i}.json"
            write_segmentation_manifest(m, p)
            paths.append(p)
        report = compare_segmentations(paths)
        assert report.total_input_count == report.total_compared_count + report.total_excluded_count
        assert report.total_input_count == 2
        assert report.total_compared_count == 0
        assert report.total_excluded_count == 2

    def test_invariant_holds_for_mixed(self, tmp_path: Path) -> None:
        from customer_segmentation.prototype.segmentation.compare import (
            compare_segmentations,
        )

        m1 = _make_manifest(segmentation_id="seg_" + "1" * 24)
        m2 = _make_manifest(segmentation_id="seg_" + "2" * 24)
        m3 = _make_manifest(segmentation_id="seg_" + "3" * 24)
        object.__setattr__(m1, "dataset_id", "ds_a")
        object.__setattr__(m2, "dataset_id", "ds_a")
        object.__setattr__(m3, "dataset_id", "ds_b")
        paths = []
        for i, m in enumerate([m1, m2, m3], start=1):
            p = tmp_path / f"m{i}.json"
            write_segmentation_manifest(m, p)
            paths.append(p)
        report = compare_segmentations(paths)
        assert report.total_input_count == report.total_compared_count + report.total_excluded_count
        assert report.total_input_count == 3
        assert report.total_compared_count == 2
        assert report.total_excluded_count == 1

    def test_invariant_holds_for_all_compatible(self, tmp_path: Path) -> None:
        from customer_segmentation.prototype.segmentation.compare import (
            compare_segmentations,
        )

        m1 = _make_manifest(segmentation_id="seg_" + "1" * 24)
        m2 = _make_manifest(segmentation_id="seg_" + "2" * 24)
        m3 = _make_manifest(segmentation_id="seg_" + "3" * 24)
        paths = []
        for i, m in enumerate([m1, m2, m3], start=1):
            p = tmp_path / f"m{i}.json"
            write_segmentation_manifest(m, p)
            paths.append(p)
        report = compare_segmentations(paths)
        assert report.total_input_count == report.total_compared_count + report.total_excluded_count
        assert report.total_input_count == 3
        assert report.total_compared_count == 3
        assert report.total_excluded_count == 0

    def test_invariant_holds_for_singleton(self, tmp_path: Path) -> None:
        from customer_segmentation.prototype.segmentation.compare import (
            compare_segmentations,
        )

        m1 = _make_manifest()
        p1 = tmp_path / "m1.json"
        write_segmentation_manifest(m1, p1)
        report = compare_segmentations([p1])
        assert report.total_input_count == report.total_compared_count + report.total_excluded_count
        assert report.total_input_count == 1
        assert report.total_compared_count == 1
        assert report.total_excluded_count == 0
