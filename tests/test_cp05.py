"""Tests cho CP-05 — Segment Interpretability & Business Relevance Evaluation.

~60 unit tests covering:
- Provenance
- 6 evaluation axes
- Final Segment Definition
- CP-04 consistency
- Runner
- Methodology gate (forbidden tokens)
- Read-only source integrity
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from customer_segmentation.profiling.cp05 import (
    build_cp05_analysis_units,
    build_final_segment_definition,
    evaluate_business_relevance,
    evaluate_consistency,
    evaluate_distinctiveness,
    evaluate_interpretability,
    evaluate_size,
    evaluate_stability,
)
from customer_segmentation.profiling.cp05.interpretability import (
    ALL_FORBIDDEN_TOKENS,
)
from customer_segmentation.profiling.cp05.provenance import (
    Cp04EvidenceBundle,
    Cp05AnalysisUnit,
    get_cp05_artifact_shas,
    load_cp04_evidence_for_unit,
)
from customer_segmentation.profiling.cp05.runner import (
    Cp05Runner,
    run_cp05,
)

# Repo paths.
ROOT = Path(__file__).resolve().parent.parent
CP01_DIR = ROOT / "reports" / "profiling" / "cp01"
CP02_DIR = ROOT / "reports" / "profiling" / "cp02"
CP03_DIR = ROOT / "reports" / "profiling" / "cp03"
CP04_DIR = ROOT / "reports" / "profiling" / "cp04"
EXP05_DIR = ROOT / "reports" / "exp05"


def _has_cp01_04() -> bool:
    return (CP01_DIR / "cp01_cluster_size_table.csv").exists() and (
        CP04_DIR / "cp04_unit_provenance.csv"
    ).exists()


pytestmark = pytest.mark.skipif(
    not _has_cp01_04(),
    reason="CP-01 / CP-04 artifacts not present",
)


@pytest.fixture
def units() -> list[Cp05AnalysisUnit]:
    return build_cp05_analysis_units(CP04_DIR / "cp04_unit_provenance.csv")


@pytest.fixture
def exp01_units(units) -> list[Cp05AnalysisUnit]:
    return [u for u in units if u.source_experiment == "EXP-01"]


@pytest.fixture
def exp03_units(units) -> list[Cp05AnalysisUnit]:
    return [u for u in units if u.source_experiment == "EXP-03"]


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------


class TestProvenance:
    def test_units_returns_one_unit_per_algorithm_per_condition(self, units):
        assert len(units) == 10
        algos = {u.algorithm for u in units}
        assert algos == {
            "kmeans",
            "agglomerative",
            "dbscan",
            "gmm",
            "fuzzy_cmeans",
        }

    def test_k_medoids_absent(self, units):
        algos = {u.algorithm for u in units}
        assert "kmedoids" not in algos

    def test_exp01_units_have_labels_persisted(self, exp01_units):
        assert len(exp01_units) == 5
        for u in exp01_units:
            assert u.labels_persisted is True

    def test_exp03_units_have_labels_persisted_false(self, exp03_units):
        assert len(exp03_units) == 5
        for u in exp03_units:
            assert u.labels_persisted is False

    def test_configuration_status_in_allowed_set(self, units):
        allowed = {"WORKING_DEFAULT", "WORKING_SELECTED", "TIED_WORKING_SELECTED"}
        for u in units:
            assert u.configuration_status in allowed

    def test_load_evidence_for_unit_returns_size_df(self, exp01_units):
        unit = exp01_units[0]
        bundle = load_cp04_evidence_for_unit(
            unit, cp01_dir=CP01_DIR, cp02_dir=CP02_DIR, cp03_dir=CP03_DIR, cp04_dir=CP04_DIR
        )
        assert isinstance(bundle, Cp04EvidenceBundle)
        assert not bundle.size_df.empty
        assert bundle.size_df["unit_id"].iloc[0] == unit.unit_id

    def test_get_artifact_shas_returns_dict(self, exp01_units):
        paths = [
            CP01_DIR / "cp01_cluster_size_table.csv",
            CP02_DIR / "cp02_feature_profile_table.csv",
            CP03_DIR / "cp03_segment_comparison_matrix.csv",
            CP04_DIR / "cp04_segment_profiles.csv",
        ]
        shas = get_cp05_artifact_shas(paths)
        assert isinstance(shas, dict)
        for p in paths:
            assert str(p) in shas
            assert len(shas[str(p)]) == 64


# ---------------------------------------------------------------------------
# Distinctiveness
# ---------------------------------------------------------------------------


class TestDistinctiveness:
    def test_evaluate_distinctiveness_returns_non_empty_for_exp01(self, exp01_units):
        for unit in exp01_units:
            bundle = load_cp04_evidence_for_unit(
                unit, cp01_dir=CP01_DIR, cp02_dir=CP02_DIR, cp03_dir=CP03_DIR, cp04_dir=CP04_DIR
            )
            results = evaluate_distinctiveness(bundle)
            assert results, f"No results for {unit.unit_id}"

    def test_distinctiveness_status_in_taxonomy(self, exp01_units):
        allowed = {
            "DISTINCT",
            "LIMITED_DIFFERENTIVENESS",
            "NOT_DISTINCT",
            "NOT_ASSESSABLE",
        }
        for unit in exp01_units:
            bundle = load_cp04_evidence_for_unit(
                unit, cp01_dir=CP01_DIR, cp02_dir=CP02_DIR, cp03_dir=CP03_DIR, cp04_dir=CP04_DIR
            )
            results = evaluate_distinctiveness(bundle)
            for r in results:
                assert r.distinctiveness_status in allowed

    def test_redundant_pair_deduplicated(self, exp01_units):
        # Test that AverageQuantity and BasketSize don't both appear.
        for unit in exp01_units:
            bundle = load_cp04_evidence_for_unit(
                unit, cp01_dir=CP01_DIR, cp02_dir=CP02_DIR, cp03_dir=CP03_DIR, cp04_dir=CP04_DIR
            )
            results = evaluate_distinctiveness(bundle)
            for r in results:
                feats = r.supporting_features.split(";")
                assert "BasketSize" not in feats or "AverageQuantity" not in feats


# ---------------------------------------------------------------------------
# Interpretability
# ---------------------------------------------------------------------------


class TestInterpretability:
    def test_evaluate_interpretability_returns_non_empty(self, exp01_units):
        for unit in exp01_units:
            bundle = load_cp04_evidence_for_unit(
                unit, cp01_dir=CP01_DIR, cp02_dir=CP02_DIR, cp03_dir=CP03_DIR, cp04_dir=CP04_DIR
            )
            results = evaluate_interpretability(bundle)
            assert results, f"No results for {unit.unit_id}"

    def test_interpretability_status_in_taxonomy(self, exp01_units):
        allowed = {
            "HIGH_INTERPRETABILITY",
            "INTERPRETABLE",
            "PARTIALLY_INTERPRETABLE",
            "LIMITED_INTERPRETABILITY",
            "COMPARATIVE",
            "NOT_AVAILABLE",
            "NOT_APPLICABLE",
        }
        for unit in exp01_units:
            bundle = load_cp04_evidence_for_unit(
                unit, cp01_dir=CP01_DIR, cp02_dir=CP02_DIR, cp03_dir=CP03_DIR, cp04_dir=CP04_DIR
            )
            results = evaluate_interpretability(bundle)
            for r in results:
                assert r.interpretability_status in allowed

    def test_noise_has_not_applicable_status(self, exp01_units):
        dbscan_unit = next(u for u in exp01_units if u.algorithm == "dbscan")
        bundle = load_cp04_evidence_for_unit(
            dbscan_unit,
            cp01_dir=CP01_DIR,
            cp02_dir=CP02_DIR,
            cp03_dir=CP03_DIR,
            cp04_dir=CP04_DIR,
        )
        results = evaluate_interpretability(bundle)
        noise = [r for r in results if r.cluster_id == -1]
        assert len(noise) == 1
        assert noise[0].interpretability_status == "NOT_APPLICABLE"

    def test_over_inference_check_catches_forbidden_token(self):
        # Build a synthetic result with forbidden text.
        # Use interpretability internal function _has_forbidden_token.
        from customer_segmentation.profiling.cp05.interpretability import (
            _has_forbidden_token,
        )

        assert _has_forbidden_token("This customer is loyal customer") is True
        assert _has_forbidden_token("This is a champion") is True
        assert _has_forbidden_token("Marketing recommendation needed") is True
        assert _has_forbidden_token("CLV is high") is True
        assert _has_forbidden_token("Recent Frequent HighValue LongTenured") is False


# ---------------------------------------------------------------------------
# Consistency
# ---------------------------------------------------------------------------


class TestConsistency:
    def test_consistency_status_in_taxonomy(self, exp01_units):
        allowed = {
            "CONSISTENT",
            "PARTIALLY_CONSISTENT",
            "MODIFIER_INCONSISTENT",
            "RFM_INCONSISTENT",
            "NOT_ASSESSABLE",
            "NOT_APPLICABLE",
        }
        for unit in exp01_units:
            bundle = load_cp04_evidence_for_unit(
                unit, cp01_dir=CP01_DIR, cp02_dir=CP02_DIR, cp03_dir=CP03_DIR, cp04_dir=CP04_DIR
            )
            results = evaluate_consistency(bundle)
            for r in results:
                assert r.consistency_status in allowed

    def test_consistency_for_named_segments(self, exp01_units):
        for unit in exp01_units:
            bundle = load_cp04_evidence_for_unit(
                unit, cp01_dir=CP01_DIR, cp02_dir=CP02_DIR, cp03_dir=CP03_DIR, cp04_dir=CP04_DIR
            )
            results = evaluate_consistency(bundle)
            for r in results:
                if r.naming_status == "NAMED":
                    assert r.consistency_status != "NOT_APPLICABLE"

    def test_modifier_grounding_uses_cp03_classification(self, exp01_units):
        # Smoke test — every modifier evaluation should return a bool.
        for unit in exp01_units:
            bundle = load_cp04_evidence_for_unit(
                unit, cp01_dir=CP01_DIR, cp02_dir=CP02_DIR, cp03_dir=CP03_DIR, cp04_dir=CP04_DIR
            )
            results = evaluate_consistency(bundle)
            for r in results:
                if r.naming_status == "NAMED":
                    for v in (
                        r.modifier_longtenured_grounded,
                        r.modifier_irregularcadence_grounded,
                        r.modifier_bulk_grounded,
                        r.modifier_active_grounded,
                    ):
                        assert isinstance(v, bool)


# ---------------------------------------------------------------------------
# Size
# ---------------------------------------------------------------------------


class TestSize:
    def test_size_band_in_taxonomy(self, exp01_units):
        allowed = {
            "DOMINANT",
            "LARGE",
            "MEDIUM",
            "SMALL",
            "VERY_SMALL",
            "NOT_APPLICABLE",
        }
        for unit in exp01_units:
            bundle = load_cp04_evidence_for_unit(
                unit, cp01_dir=CP01_DIR, cp02_dir=CP02_DIR, cp03_dir=CP03_DIR, cp04_dir=CP04_DIR
            )
            results = evaluate_size(bundle)
            for r in results:
                assert r.size_band in allowed

    def test_reliability_flag_for_small_clusters(self, exp01_units):
        dbscan_unit = next(u for u in exp01_units if u.algorithm == "dbscan")
        bundle = load_cp04_evidence_for_unit(
            dbscan_unit,
            cp01_dir=CP01_DIR,
            cp02_dir=CP02_DIR,
            cp03_dir=CP03_DIR,
            cp04_dir=CP04_DIR,
        )
        results = evaluate_size(bundle)
        small = [r for r in results if r.n_customers > 0 and r.n_customers < 30 and not r.is_noise]
        for r in small:
            assert r.statistical_reliability_flag == "LOW"

    def test_pct_of_total_sums_to_100_for_dbscan(self, exp01_units):
        dbscan_unit = next(u for u in exp01_units if u.algorithm == "dbscan")
        bundle = load_cp04_evidence_for_unit(
            dbscan_unit,
            cp01_dir=CP01_DIR,
            cp02_dir=CP02_DIR,
            cp03_dir=CP03_DIR,
            cp04_dir=CP04_DIR,
        )
        results = evaluate_size(bundle)
        total = sum(r.pct_of_total for r in results)
        assert abs(total - 100.0) < 0.5


# ---------------------------------------------------------------------------
# Stability
# ---------------------------------------------------------------------------


class TestStability:
    def test_stability_status_in_taxonomy(self, exp01_units):
        allowed = {
            "REPRODUCIBILITY_VERIFIED_NO_STABILITY_METRIC",
            "REPRODUCIBILITY_VERIFIED_STABILITY_PENDING_EPIC08",
            "REPRODUCIBILITY_NOT_VERIFIED",
            "STABILITY_RAW_EVIDENCE_PARTIAL",
            "STABILITY_NOT_ASSESSABLE",
            "NOT_APPLICABLE",
        }
        for unit in exp01_units:
            bundle = load_cp04_evidence_for_unit(
                unit, cp01_dir=CP01_DIR, cp02_dir=CP02_DIR, cp03_dir=CP03_DIR, cp04_dir=CP04_DIR
            )
            results = evaluate_stability(bundle, exp05_dir=EXP05_DIR)
            for r in results:
                assert r.stability_status in allowed

    def test_no_ari_ami_computation(self, exp01_units):
        import inspect

        from customer_segmentation.profiling.cp05 import stability as stab_module

        source = inspect.getsource(stab_module)
        assert (
            "compute"
            not in source.lower()
            .replace("compute_ari", "COMPUTE")
            .replace("compute_ami", "COMPUTE")
            or "ari" not in source.lower()
            and "ami" not in source.lower()
        )
        # Explicitly check that no ARI/AMI computation functions exist.
        forbidden_funcs = [
            name
            for name in dir(stab_module)
            if "ari" in name.lower() or "ami" in name.lower() or "nmi" in name.lower()
        ]
        assert not forbidden_funcs, f"Forbidden functions: {forbidden_funcs}"

    def test_segment_level_stability_note_present(self, exp01_units):
        for unit in exp01_units:
            bundle = load_cp04_evidence_for_unit(
                unit, cp01_dir=CP01_DIR, cp02_dir=CP02_DIR, cp03_dir=CP03_DIR, cp04_dir=CP04_DIR
            )
            results = evaluate_stability(bundle, exp05_dir=EXP05_DIR)
            for r in results:
                if not r.is_noise:
                    assert (
                        "EPIC-08" in r.stability_evidence_note
                        or r.stability_status == "STABILITY_NOT_ASSESSABLE"
                    )


# ---------------------------------------------------------------------------
# Business Relevance
# ---------------------------------------------------------------------------


class TestBusinessRelevance:
    def test_business_relevance_status_in_taxonomy(self, exp01_units):
        allowed = {"SUPPORTED", "LIMITED", "NOT_ASSESSABLE", "NOT_APPLICABLE"}
        for unit in exp01_units:
            bundle = load_cp04_evidence_for_unit(
                unit, cp01_dir=CP01_DIR, cp02_dir=CP02_DIR, cp03_dir=CP03_DIR, cp04_dir=CP04_DIR
            )
            results = evaluate_business_relevance(bundle)
            for r in results:
                assert r.business_relevance_status in allowed

    def test_cancellation_rate_excluded(self, exp01_units):
        for unit in exp01_units:
            bundle = load_cp04_evidence_for_unit(
                unit, cp01_dir=CP01_DIR, cp02_dir=CP02_DIR, cp03_dir=CP03_DIR, cp04_dir=CP04_DIR
            )
            results = evaluate_business_relevance(bundle)
            for r in results:
                if not r.is_noise:
                    assert "CancellationRate" not in r.feature_evidence
                    assert "ReturnRate" not in r.feature_evidence

    def test_supported_text_uses_only_allowed_qualifiers(self, exp01_units):
        for unit in exp01_units:
            bundle = load_cp04_evidence_for_unit(
                unit, cp01_dir=CP01_DIR, cp02_dir=CP02_DIR, cp03_dir=CP03_DIR, cp04_dir=CP04_DIR
            )
            results = evaluate_business_relevance(bundle)
            for r in results:
                if r.business_relevance_status == "SUPPORTED":
                    text = r.business_interpretation_text.lower()
                    # No forbidden tokens.
                    for tok in ALL_FORBIDDEN_TOKENS:
                        assert tok.lower() not in text


# ---------------------------------------------------------------------------
# Final Segment Definition
# ---------------------------------------------------------------------------


class TestFinalDefinition:
    def test_final_definition_count_matches_size_table(self, exp01_units):
        for unit in exp01_units:
            bundle = load_cp04_evidence_for_unit(
                unit, cp01_dir=CP01_DIR, cp02_dir=CP02_DIR, cp03_dir=CP03_DIR, cp04_dir=CP04_DIR
            )
            distinct = evaluate_distinctiveness(bundle)
            interp = evaluate_interpretability(bundle)
            cons = evaluate_consistency(bundle)
            size = evaluate_size(bundle)
            stab = evaluate_stability(bundle, exp05_dir=EXP05_DIR)
            biz = evaluate_business_relevance(bundle)

            defs = build_final_segment_definition(
                unit,
                bundle,
                distinctiveness_results=distinct,
                interpretability_results=interp,
                consistency_results=cons,
                size_results=size,
                stability_results=stab,
                business_relevance_results=biz,
            )
            assert len(defs) == len(bundle.size_df)

    def test_interpretation_readiness_in_taxonomy(self, exp01_units):
        for unit in exp01_units:
            bundle = load_cp04_evidence_for_unit(
                unit, cp01_dir=CP01_DIR, cp02_dir=CP02_DIR, cp03_dir=CP03_DIR, cp04_dir=CP04_DIR
            )
            distinct = evaluate_distinctiveness(bundle)
            interp = evaluate_interpretability(bundle)
            cons = evaluate_consistency(bundle)
            size = evaluate_size(bundle)
            stab = evaluate_stability(bundle, exp05_dir=EXP05_DIR)
            biz = evaluate_business_relevance(bundle)
            defs = build_final_segment_definition(
                unit,
                bundle,
                distinctiveness_results=distinct,
                interpretability_results=interp,
                consistency_results=cons,
                size_results=size,
                stability_results=stab,
                business_relevance_results=biz,
            )
            for d in defs:
                assert d.interpretation_readiness in {
                    "READY",
                    "CONDITIONAL",
                    "LIMITED",
                    "NOT_ASSESSABLE",
                }

    def test_is_interpretation_ready_is_bool(self, exp01_units):
        for unit in exp01_units:
            bundle = load_cp04_evidence_for_unit(
                unit, cp01_dir=CP01_DIR, cp02_dir=CP02_DIR, cp03_dir=CP03_DIR, cp04_dir=CP04_DIR
            )
            distinct = evaluate_distinctiveness(bundle)
            interp = evaluate_interpretability(bundle)
            cons = evaluate_consistency(bundle)
            size = evaluate_size(bundle)
            stab = evaluate_stability(bundle, exp05_dir=EXP05_DIR)
            biz = evaluate_business_relevance(bundle)
            defs = build_final_segment_definition(
                unit,
                bundle,
                distinctiveness_results=distinct,
                interpretability_results=interp,
                consistency_results=cons,
                size_results=size,
                stability_results=stab,
                business_relevance_results=biz,
            )
            for d in defs:
                assert isinstance(d.is_interpretation_ready, bool)

    def test_exp03_segments_have_not_assessable_readiness(self, units):
        for unit in units:
            if unit.source_experiment != "EXP-03":
                continue
            bundle = load_cp04_evidence_for_unit(
                unit, cp01_dir=CP01_DIR, cp02_dir=CP02_DIR, cp03_dir=CP03_DIR, cp04_dir=CP04_DIR
            )
            distinct = evaluate_distinctiveness(bundle)
            interp = evaluate_interpretability(bundle)
            cons = evaluate_consistency(bundle)
            size = evaluate_size(bundle)
            stab = evaluate_stability(bundle, exp05_dir=EXP05_DIR)
            biz = evaluate_business_relevance(bundle)
            defs = build_final_segment_definition(
                unit,
                bundle,
                distinctiveness_results=distinct,
                interpretability_results=interp,
                consistency_results=cons,
                size_results=size,
                stability_results=stab,
                business_relevance_results=biz,
            )
            for d in defs:
                assert d.interpretation_readiness == "NOT_ASSESSABLE"
                assert d.is_interpretation_ready is False


# ---------------------------------------------------------------------------
# CP-04 Consistency
# ---------------------------------------------------------------------------


class TestCp04Consistency:
    def test_cluster_ids_match_cp04(self, exp01_units):
        for unit in exp01_units:
            bundle = load_cp04_evidence_for_unit(
                unit, cp01_dir=CP01_DIR, cp02_dir=CP02_DIR, cp03_dir=CP03_DIR, cp04_dir=CP04_DIR
            )
            distinct = evaluate_distinctiveness(bundle)
            interp = evaluate_interpretability(bundle)
            size = evaluate_size(bundle)
            cluster_ids_size = {int(c) for c in bundle.size_df["cluster_id"].tolist()}
            # Distinctiveness excludes noise (correct per plan).
            cluster_ids_distinct = {r.cluster_id for r in distinct}
            cluster_ids_interp = {r.cluster_id for r in interp}
            cluster_ids_size_res = {r.cluster_id for r in size}
            # All except distinct must include noise -1.
            assert -1 in cluster_ids_size
            assert -1 in cluster_ids_interp
            assert -1 in cluster_ids_size_res
            assert cluster_ids_size == cluster_ids_interp
            assert cluster_ids_size == cluster_ids_size_res
            # Distinct: subset of size (no noise).
            assert cluster_ids_distinct.issubset(cluster_ids_size - {-1})

    def test_segment_names_inherit_from_cp04(self, exp01_units):
        for unit in exp01_units:
            bundle = load_cp04_evidence_for_unit(
                unit, cp01_dir=CP01_DIR, cp02_dir=CP02_DIR, cp03_dir=CP03_DIR, cp04_dir=CP04_DIR
            )
            if bundle.naming_df is None or bundle.naming_df.empty:
                continue
            distinct = evaluate_distinctiveness(bundle)
            interp = evaluate_interpretability(bundle)
            cons = evaluate_consistency(bundle)
            size = evaluate_size(bundle)
            stab = evaluate_stability(bundle, exp05_dir=EXP05_DIR)
            biz = evaluate_business_relevance(bundle)
            defs = build_final_segment_definition(
                unit,
                bundle,
                distinctiveness_results=distinct,
                interpretability_results=interp,
                consistency_results=cons,
                size_results=size,
                stability_results=stab,
                business_relevance_results=biz,
            )
            cp04_names = {}
            for _, row in bundle.naming_df.iterrows():
                cp04_names[int(row["cluster_id"])] = str(row.get("segment_name", ""))
            for d in defs:
                if not d.is_noise and d.cluster_id in cp04_names and cp04_names[d.cluster_id]:
                    assert d.segment_name == cp04_names[d.cluster_id]


# ---------------------------------------------------------------------------
# Methodology gate — forbidden tokens
# ---------------------------------------------------------------------------


class TestMethodologyGate:
    FORBIDDEN_TOKENS = [
        "best segment",
        "best cluster",
        "best customer",
        "promising customer",
        "declining customer",
        "loyalty indicator",
        "purchase probability",
        "high-value customer",
        "tier 1 customer",
        "tier 2 customer",
        "marketing recommendation",
        "campaign recommendation",
        "churn risk",
        "retention risk",
        "customer lifetime value",
        "CLV",
        "champion",
        "vip customer",
        "at-risk customer",
        "low-engagement customer",
        "loyal customer",
        "outreach campaign",
        "remarketing",
        "campaign targeting",
        "best algorithm",
        "winner algorithm",
        "optimal algorithm",
        "recommended algorithm",
        "engagement",
        "preferred segment",
        "winning segment",
        "most stable",
        "highly stable",
        "proven stability",
    ]

    @pytest.fixture
    def cp05_csvs(self, tmp_path):
        runner = Cp05Runner(output_dir=tmp_path)
        runner.run()
        return list(tmp_path.glob("*.csv"))

    @pytest.mark.parametrize("token", FORBIDDEN_TOKENS)
    def test_no_forbidden_token_in_csv(self, cp05_csvs, token):
        # The token list intentionally includes forbidden terms;
        # CP-05 must not appear in CSV contents.
        for csv_path in cp05_csvs:
            text = csv_path.read_text(encoding="utf-8")
            assert token not in text.lower(), f"Forbidden token '{token}' found in {csv_path.name}"

    def test_no_forbidden_token_in_report_md(self, tmp_path):
        runner = Cp05Runner(output_dir=tmp_path)
        runner.run()
        report = (tmp_path / "cp05_report.md").read_text(encoding="utf-8")
        for token in self.FORBIDDEN_TOKENS:
            # Tokens like "campaign" might appear in legitimate contexts
            # (e.g., documentation of what is FORBIDDEN). Only check
            # for the most specific tokens.
            if token in (
                "best segment",
                "winner segment",
                "preferred segment",
                "marketing recommendation",
                "campaign recommendation",
                "CLV",
                "churn risk",
                "retention risk",
                "best algorithm",
                "winner algorithm",
                "champion",
                "vip customer",
                "at-risk customer",
                "loyal customer",
                "low-engagement customer",
                "outreach campaign",
                "remarketing",
                "campaign targeting",
            ):
                assert (
                    token not in report.lower()
                ), f"Forbidden token '{token}' found in cp05_report.md"


# ---------------------------------------------------------------------------
# Runner + determinism + read-only
# ---------------------------------------------------------------------------


class TestRunner:
    def test_runner_creates_all_artifacts(self, tmp_path):
        runner = Cp05Runner(output_dir=tmp_path)
        runner.run()
        for name in [
            "cp05_distinctiveness_evaluation.csv",
            "cp05_interpretability_evaluation.csv",
            "cp05_behavioral_consistency_evaluation.csv",
            "cp05_segment_size_evaluation.csv",
            "cp05_stability_evaluation.csv",
            "cp05_business_relevance_evaluation.csv",
            "cp05_final_segment_definition.csv",
            "cp05_unit_provenance.csv",
            "cp05_runner_manifest.json",
            "cp05_report.md",
        ]:
            assert (tmp_path / name).exists(), f"Missing {name}"

    def test_runner_manifest_contains_sha_chain(self, tmp_path):
        runner = Cp05Runner(output_dir=tmp_path)
        runner.run()
        manifest = json.loads((tmp_path / "cp05_runner_manifest.json").read_text())
        assert "input_shas" in manifest
        assert "output_shas" in manifest
        assert manifest["n_units"] == 10
        assert manifest["n_definitions"] >= 39

    def test_runner_no_exp03(self, tmp_path):
        runner = Cp05Runner(output_dir=tmp_path, include_exp03=False)
        result = runner.run()
        assert result.n_units == 5
        # Read final definitions and ensure no EXP-03 rows.
        df = pd.read_csv(tmp_path / "cp05_final_segment_definition.csv")
        assert all(df["source_experiment"] == "EXP-01")

    def test_runner_determinism(self, tmp_path):
        out1 = tmp_path / "run1"
        out2 = tmp_path / "run2"
        out1.mkdir()
        out2.mkdir()
        Cp05Runner(output_dir=out1).run()
        Cp05Runner(output_dir=out2).run()
        for name in [
            "cp05_distinctiveness_evaluation.csv",
            "cp05_interpretability_evaluation.csv",
            "cp05_behavioral_consistency_evaluation.csv",
            "cp05_segment_size_evaluation.csv",
            "cp05_stability_evaluation.csv",
            "cp05_business_relevance_evaluation.csv",
            "cp05_final_segment_definition.csv",
        ]:
            h1 = hashlib.sha256((out1 / name).read_bytes()).hexdigest()
            h2 = hashlib.sha256((out2 / name).read_bytes()).hexdigest()
            assert h1 == h2, f"{name} differs across runs"

    def test_runner_read_only_source(self, tmp_path):
        # Compute input SHAs before run.
        before_shas = {}
        for p in [
            CP01_DIR / "cp01_cluster_size_table.csv",
            CP02_DIR / "cp02_feature_profile_table.csv",
            CP03_DIR / "cp03_segment_comparison_matrix.csv",
            CP04_DIR / "cp04_segment_profiles.csv",
            CP04_DIR / "cp04_unit_provenance.csv",
        ]:
            if p.exists():
                before_shas[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()

        # Run.
        Cp05Runner(output_dir=tmp_path).run()

        # Compute input SHAs after run.
        for p, sha in before_shas.items():
            path = Path(p)
            if path.exists():
                after_sha = hashlib.sha256(path.read_bytes()).hexdigest()
                assert after_sha == sha, f"Source {p} modified by CP-05"


# ---------------------------------------------------------------------------
# Final-segment-id and segment_id format
# ---------------------------------------------------------------------------


class TestSchema:
    @pytest.fixture
    def final_df(self, tmp_path):
        Cp05Runner(output_dir=tmp_path).run()
        return pd.read_csv(tmp_path / "cp05_final_segment_definition.csv")

    def test_segment_id_format(self, final_df):
        for sid in final_df["segment_id"]:
            assert "__" in sid

    def test_required_columns_present(self, final_df):
        required = {
            "segment_id",
            "unit_id",
            "algorithm",
            "cluster_id",
            "naming_status",
            "size_band",
            "distinctiveness_status",
            "interpretability_status",
            "consistency_status",
            "stability_status",
            "business_relevance_status",
            "is_interpretation_ready",
            "interpretation_readiness",
        }
        assert required.issubset(final_df.columns)

    def test_dbscan_noise_has_not_applicable_flags(self, final_df):
        dbscan = final_df[(final_df["algorithm"] == "dbscan") & (final_df["cluster_id"] == -1)]
        assert len(dbscan) == 1
        for col in [
            "size_band",
            "interpretability_status",
            "consistency_status",
            "stability_status",
            "business_relevance_status",
        ]:
            assert dbscan[col].iloc[0] == "NOT_APPLICABLE"
        assert not dbscan["is_interpretation_ready"].iloc[0]
        assert dbscan["interpretation_readiness"].iloc[0] == "NOT_ASSESSABLE"


# ---------------------------------------------------------------------------
# Integration: run_cp05 functional entrypoint
# ---------------------------------------------------------------------------


class TestFunctionalEntrypoint:
    def test_run_cp05_functional(self, tmp_path):
        result = run_cp05(output_dir=tmp_path)
        assert result.n_units == 10
        assert result.n_definitions >= 30
        assert (tmp_path / "cp05_runner_manifest.json").exists()


# ---------------------------------------------------------------------------
# No-ARI/AMI source verification
# ---------------------------------------------------------------------------


class TestNoAriAmiInSrc:
    """Defensive: scan CP-05 source for any ARI/AMI/NMI/Hungarian compute."""

    SRC_FILES = [
        "src/customer_segmentation/profiling/cp05/provenance.py",
        "src/customer_segmentation/profiling/cp05/size_evaluation.py",
        "src/customer_segmentation/profiling/cp05/distinctiveness.py",
        "src/customer_segmentation/profiling/cp05/interpretability.py",
        "src/customer_segmentation/profiling/cp05/consistency.py",
        "src/customer_segmentation/profiling/cp05/stability.py",
        "src/customer_segmentation/profiling/cp05/business_relevance.py",
        "src/customer_segmentation/profiling/cp05/final_definition.py",
        "src/customer_segmentation/profiling/cp05/runner.py",
        "src/customer_segmentation/profiling/cp05/report.py",
    ]

    FORBIDDEN_COMPUTE_FUNCS = ("ari", "ami", "nmi", "hungarian")

    @pytest.mark.parametrize("src_file", SRC_FILES)
    def test_no_ari_ami_compute_in_src(self, src_file):
        path = ROOT / src_file
        if not path.exists():
            pytest.skip(f"{src_file} not present")
        text = path.read_text(encoding="utf-8").lower()
        for func in self.FORBIDDEN_COMPUTE_FUNCS:
            # Allow mentions like "ARI/AMI deferred to EPIC-08".
            assert f"compute_{func}" not in text
            assert f"_compute_{func}" not in text
            assert f"def {func}" not in text
            assert f"def compute_{func}" not in text
