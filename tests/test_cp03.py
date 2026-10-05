"""Tests for CP-03 — Cluster Comparison and Distinguishing Feature Analysis.

Validates:

1. CP-03 analysis units identical to CP-02.
2. Segment comparison matrix: no duplicates, all clusters covered.
3. IQR overlap coefficient: deterministic, bounded [0, 1].
4. IQR overlap with population lookup correct.
5. Distinguishing indicators: effect_range, IQR overlap, direction counts.
6. Analytical classification: HIGH / MODERATE / LOW / HIGH_OVERLAP / NOT_ASSESSABLE.
7. Comparison matrix matches CP-02 statistics (median, P25, P75).
8. Runner writes all required artifacts.
9. Output deterministic across reruns.
10. CP-02 consistency: cluster counts match.
11. Methodology gate: no forbidden tokens.
12. Read-only against source artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from customer_segmentation.profiling.cp01.provenance import (
    ALGORITHMS,
)
from customer_segmentation.profiling.cp02.provenance import (
    FEATURE_COLUMNS,
)
from customer_segmentation.profiling.cp03.comparison import (
    compute_segment_comparison_matrix,
)
from customer_segmentation.profiling.cp03.difference_analysis import (
    classify_distinguishing_feature,
    compute_distinguishing_feature_table,
)
from customer_segmentation.profiling.cp03.overlap_analysis import (
    compute_pairwise_overlap_table,
    compute_population_overlap_lookup,
    iqr_overlap_coefficient,
)
from customer_segmentation.profiling.cp03.provenance import (
    build_cp03_analysis_units,
)
from customer_segmentation.profiling.cp03.runner import run_cp03

REPO_ROOT = Path(__file__).resolve().parents[1]

# Forbidden tokens for CP-03 methodology gate. Includes CP-01/CP-02
# tokens + CP-03-specific ones (distinguishing ranking, separation
# score, best separation, most distinguishing feature).
FORBIDDEN_TOKENS = [
    # CP-01/CP-02 tokens
    "best algorithm",
    "winner algorithm",
    "optimal algorithm",
    "recommended algorithm",
    "champions",
    "vip customer",
    "at-risk customer",
    "low-engagement customer",
    "loyal customer",
    "outreach campaign",
    "remarketing",
    "campaign targeting",
    "nên được ưu tiên",
    "chiến dịch",
    "khách hàng VIP",
    "có giá trị nhất",
    "tốt nhất",
    # CP-03 specific
    "most distinguishing",
    "best separation",
    "separation score",
    "distinguishing score",
    "optimal separating",
    "most separating",
]


# --------------------------------------------------------------------
# Provenance
# --------------------------------------------------------------------


class TestProvenance:
    def test_build_cp03_analysis_units_returns_one_unit_per_algorithm_per_condition(
        self,
    ):
        units = build_cp03_analysis_units(REPO_ROOT)
        assert len(units) == 10
        for algo in ALGORITHMS:
            cond = [u for u in units if u.algorithm == algo]
            assert len(cond) == 2
            sources = sorted(u.source_experiment for u in cond)
            assert sources == ["EXP-01", "EXP-03"]

    def test_kmedoids_absent(self):
        units = build_cp03_analysis_units(REPO_ROOT)
        names = {u.algorithm for u in units}
        assert "kmedoids" not in names

    def test_exp03_units_labels_not_persisted(self):
        units = build_cp03_analysis_units(REPO_ROOT)
        for u in units:
            if u.source_experiment == "EXP-03":
                assert u.labels_persisted is False

    def test_exp01_units_labels_persisted(self):
        units = build_cp03_analysis_units(REPO_ROOT)
        for u in units:
            if u.source_experiment == "EXP-01":
                assert u.labels_persisted is True


# --------------------------------------------------------------------
# IQR overlap coefficient
# --------------------------------------------------------------------


class TestIQROverlapCoefficient:
    def test_identical_iqr_returns_one(self):
        # Two identical IQRs: [10, 20] and [10, 20].
        coef = iqr_overlap_coefficient(10.0, 20.0, 10.0, 20.0)
        assert coef == pytest.approx(1.0)

    def test_disjoint_iqr_returns_zero(self):
        # Two disjoint IQRs: [0, 10] and [20, 30].
        coef = iqr_overlap_coefficient(0.0, 10.0, 20.0, 30.0)
        assert coef == pytest.approx(0.0)

    def test_partial_overlap(self):
        # IQR A = [0, 10], IQR B = [5, 15], intersection = [5, 10], width = 5.
        # max(IQR A, IQR B) = 10. So overlap = 5 / 10 = 0.5.
        coef = iqr_overlap_coefficient(0.0, 10.0, 5.0, 15.0)
        assert coef == pytest.approx(0.5)

    def test_nan_inputs_return_nan(self):
        assert np.isnan(iqr_overlap_coefficient(np.nan, 10.0, 5.0, 15.0))
        assert np.isnan(iqr_overlap_coefficient(0.0, np.nan, 5.0, 15.0))

    def test_both_zero_width_identical_medians_returns_one(self):
        # Both IQRs are zero-width (point): [5, 5] and [5, 5], median 5.
        coef = iqr_overlap_coefficient(5.0, 5.0, 5.0, 5.0)
        assert coef == pytest.approx(1.0)

    def test_both_zero_width_different_medians_returns_zero(self):
        # Both IQRs are zero-width but different points.
        coef = iqr_overlap_coefficient(5.0, 5.0, 10.0, 10.0)
        assert coef == pytest.approx(0.0)


# --------------------------------------------------------------------
# Overlap analysis
# --------------------------------------------------------------------


class TestOverlapAnalysis:
    def test_pairwise_overlap_produces_no_duplicate_pairs(self):
        units = build_cp03_analysis_units(REPO_ROOT)
        rows = compute_pairwise_overlap_table(units)
        for unit_id in {r.unit_id for r in rows}:
            unit_rows = [r for r in rows if r.unit_id == unit_id]
            for feat in {r.feature for r in unit_rows}:
                feat_rows = [
                    r for r in unit_rows if r.feature == feat and r.cluster_a_id < r.cluster_b_id
                ]
                pair_keys = [(r.cluster_a_id, r.cluster_b_id) for r in feat_rows]
                assert len(pair_keys) == len(set(pair_keys))

    def test_pairwise_overlap_coefficient_bounded_zero_to_one(self):
        units = build_cp03_analysis_units(REPO_ROOT)
        rows = compute_pairwise_overlap_table(units)
        for r in rows:
            if r.feature == "CancellationRate":
                # CancellationRate often ZERO_REFERENCE — IQR may be degenerate
                continue
            if not np.isnan(r.iqr_overlap_coefficient):
                assert 0.0 <= r.iqr_overlap_coefficient <= 1.0

    def test_population_overlap_lookup_keys_match_cluster_rows(self):
        units = build_cp03_analysis_units(REPO_ROOT)
        pop_overlap = compute_population_overlap_lookup(units)
        for key in pop_overlap:
            unit_id, cluster_id, feature = key
            assert unit_id.startswith("EXP-01-")
            assert cluster_id >= 0
            assert feature in FEATURE_COLUMNS


# --------------------------------------------------------------------
# Comparison matrix
# --------------------------------------------------------------------


class TestComparisonMatrix:
    def test_no_duplicate_unit_cluster_feature(self):
        units = build_cp03_analysis_units(REPO_ROOT)
        rows = compute_segment_comparison_matrix(units)
        keys = [(r.unit_id, r.cluster_label, r.feature) for r in rows]
        assert len(keys) == len(set(keys))

    def test_all_clusters_from_cp02_covered(self):
        units = build_cp03_analysis_units(REPO_ROOT)
        rows = compute_segment_comparison_matrix(units)
        # Verify all 33 non-noise clusters (from CP-02) appear.
        # CP-02: 4+4+17+4+4 = 33 cluster×feature rows per feature.
        # For K=4 algos: 4 clusters × 14 features = 56 rows.
        # For DBSCAN: 17 clusters × 14 features = 238 rows.
        for unit_id in {f"EXP-01-{algo}-working-default" for algo in ALGORITHMS}:
            unit_rows = [r for r in rows if r.unit_id == unit_id]
            if "dbscan" in unit_id:
                assert len(unit_rows) == 17 * len(FEATURE_COLUMNS)
            elif unit_id.startswith("EXP-01-"):
                assert len(unit_rows) == 4 * len(FEATURE_COLUMNS)

    def test_comparison_matrix_has_all_required_columns(self):
        units = build_cp03_analysis_units(REPO_ROOT)
        rows = compute_segment_comparison_matrix(units)
        assert len(rows) > 0
        r = rows[0]
        for attr in (
            "unit_id",
            "algorithm",
            "cluster_id",
            "cluster_label",
            "feature",
            "median",
            "p25",
            "p75",
            "overall_median",
            "overall_p25",
            "overall_p75",
            "rel_diff_median_pct",
            "reference_status",
            "iqr_overlap_with_population",
            "direction",
        ):
            assert hasattr(r, attr), f"Missing attribute: {attr}"

    def test_comparison_matrix_median_matches_cp02(self):
        """Spot-check: K-Means C0 Recency median should match CP-02."""
        units = build_cp03_analysis_units(REPO_ROOT)
        rows = compute_segment_comparison_matrix(units)
        kmeans_c0_recency = next(
            (
                r
                for r in rows
                if r.unit_id == "EXP-01-kmeans-working-default"
                and r.cluster_label == "C0"
                and r.feature == "Recency"
            ),
            None,
        )
        assert kmeans_c0_recency is not None
        # From CP-02: K-Means C0 Recency median = 33.0.
        assert kmeans_c0_recency.median == pytest.approx(33.0, abs=0.5)
        # From CP-02: K-Means C0 Recency overall_median ≈ 51.0.
        assert kmeans_c0_recency.overall_median == pytest.approx(51.0, abs=0.5)

    def test_dbscan_noise_excluded_from_matrix(self):
        units = build_cp03_analysis_units(REPO_ROOT)
        rows = compute_segment_comparison_matrix(units)
        dbscan_rows = [r for r in rows if "dbscan" in r.unit_id]
        assert all(r.cluster_id != -1 for r in dbscan_rows)

    def test_exp03_units_produce_zero_comparison_rows(self):
        units = build_cp03_analysis_units(REPO_ROOT)
        rows = compute_segment_comparison_matrix(units)
        exp03_rows = [r for r in rows if "EXP-03" in r.unit_id]
        assert len(exp03_rows) == 0


# --------------------------------------------------------------------
# Difference analysis / classification
# --------------------------------------------------------------------


class TestDifferenceAnalysis:
    def test_classify_high_difference(self):
        # Effect range ≥ 50% AND IQR overlap mean ≤ 0.5.
        cls = classify_distinguishing_feature(
            effect_range_rel_pct=60.0,
            iqr_overlap_mean=0.3,
            n_clusters_assessable=4,
        )
        assert cls == "HIGH_DIFFERENCE_OBSERVED"

    def test_classify_moderate_difference(self):
        # Effect range ≥ 15% but not ≥ 50%.
        cls = classify_distinguishing_feature(
            effect_range_rel_pct=20.0,
            iqr_overlap_mean=0.5,
            n_clusters_assessable=4,
        )
        assert cls == "MODERATE_DIFFERENCE_OBSERVED"

    def test_classify_low_difference(self):
        # Effect range < 15%.
        cls = classify_distinguishing_feature(
            effect_range_rel_pct=5.0,
            iqr_overlap_mean=0.5,
            n_clusters_assessable=4,
        )
        assert cls == "LOW_DIFFERENCE_OBSERVED"

    def test_classify_high_overlap(self):
        # IQR overlap mean ≥ 0.7.
        cls = classify_distinguishing_feature(
            effect_range_rel_pct=10.0,
            iqr_overlap_mean=0.75,
            n_clusters_assessable=4,
        )
        assert cls == "HIGH_OVERLAP"

    def test_classify_not_assessable_too_few_clusters(self):
        cls = classify_distinguishing_feature(
            effect_range_rel_pct=60.0,
            iqr_overlap_mean=0.3,
            n_clusters_assessable=1,
        )
        assert cls == "NOT_ASSESSABLE"

    def test_classify_not_assessable_nan_inputs(self):
        cls = classify_distinguishing_feature(
            effect_range_rel_pct=float("nan"),
            iqr_overlap_mean=0.3,
            n_clusters_assessable=4,
        )
        assert cls == "NOT_ASSESSABLE"

    def test_distinguishing_table_has_one_row_per_unit_per_feature(self):
        units = build_cp03_analysis_units(REPO_ROOT)
        rows = compute_distinguishing_feature_table(units)
        exp01_rows = [r for r in rows if r.unit_id.startswith("EXP-01-")]
        # 5 algorithms × 14 features = 70 rows for EXP-01 units.
        assert len(exp01_rows) == 5 * len(FEATURE_COLUMNS)
        keys = {(r.unit_id, r.feature) for r in rows}
        assert len(keys) == len(rows)

    def test_distinguishing_row_has_all_required_fields(self):
        units = build_cp03_analysis_units(REPO_ROOT)
        rows = compute_distinguishing_feature_table(units)
        r = next(iter(rows))
        for attr in (
            "unit_id",
            "algorithm",
            "feature",
            "n_clusters_assessable",
            "effect_range",
            "effect_range_rel_pct",
            "iqr_overlap_mean",
            "iqr_overlap_median",
            "n_clusters_higher",
            "n_clusters_lower",
            "n_clusters_comparable",
            "n_clusters_zero_reference",
            "classification",
        ):
            assert hasattr(r, attr), f"Missing attribute: {attr}"

    def test_effect_range_is_finite_for_assessable_units(self):
        units = build_cp03_analysis_units(REPO_ROOT)
        rows = compute_distinguishing_feature_table(units)
        kmeans_recency = next(
            (
                r
                for r in rows
                if r.unit_id == "EXP-01-kmeans-working-default" and r.feature == "Recency"
            ),
            None,
        )
        assert kmeans_recency is not None
        assert np.isfinite(kmeans_recency.effect_range)
        assert np.isfinite(kmeans_recency.effect_range_rel_pct)

    def test_iqr_overlap_is_bounded_zero_to_one(self):
        units = build_cp03_analysis_units(REPO_ROOT)
        rows = compute_distinguishing_feature_table(units)
        for r in rows:
            if np.isfinite(r.iqr_overlap_mean):
                assert 0.0 <= r.iqr_overlap_mean <= 1.0
            if np.isfinite(r.iqr_overlap_median):
                assert 0.0 <= r.iqr_overlap_median <= 1.0


# --------------------------------------------------------------------
# Runner / end-to-end
# --------------------------------------------------------------------


class TestRunner:
    @pytest.fixture(scope="module")
    def cp03_run(self, tmp_path_factory) -> dict:
        out = tmp_path_factory.mktemp("cp03_runner") / "out"
        return run_cp03(repo_root=REPO_ROOT, output_dir=out)

    def test_runner_writes_all_required_artifacts(self, cp03_run):
        for key in (
            "segment_comparison_matrix_csv",
            "distinguishing_features_csv",
            "overlap_analysis_csv",
            "unit_provenance_csv",
            "report_md",
            "manifest_json",
        ):
            p = Path(cp03_run[key])
            assert p.exists(), f"missing output: {key} → {p}"

    def test_runner_emits_expected_chart_count(self, cp03_run):
        """5 EXP-01 units × (7 violin + 1 distinguishing + 1 IQR) = 45 charts."""
        assert len(cp03_run["figures"]) == 5 * (7 + 1 + 1)

    def test_runner_output_is_deterministic(self, tmp_path: Path):
        s_a = run_cp03(repo_root=REPO_ROOT, output_dir=tmp_path / "run_a")
        s_b = run_cp03(repo_root=REPO_ROOT, output_dir=tmp_path / "run_b")
        for key in (
            "segment_comparison_matrix_csv",
            "distinguishing_features_csv",
            "overlap_analysis_csv",
            "unit_provenance_csv",
        ):
            df_a = (
                pd.read_csv(s_a[key])
                .sort_values(list(pd.read_csv(s_a[key]).columns[:3]))
                .reset_index(drop=True)
            )
            df_b = (
                pd.read_csv(s_b[key])
                .sort_values(list(pd.read_csv(s_b[key]).columns[:3]))
                .reset_index(drop=True)
            )
            pd.testing.assert_frame_equal(df_a, df_b)

    def test_runner_manifest_metadata(self, cp03_run):
        manifest = json.loads(Path(cp03_run["manifest_json"]).read_text())
        assert manifest["analysis_units_total"] == 10
        assert manifest["units_with_labels"] == 5
        assert manifest["units_without_labels"] == 5
        assert sorted(manifest["algorithms"]) == sorted(ALGORITHMS)

    def test_comparison_csv_has_required_columns(self, cp03_run):
        df = pd.read_csv(cp03_run["segment_comparison_matrix_csv"])
        required = {
            "unit_id",
            "algorithm",
            "cluster_id",
            "cluster_label",
            "feature",
            "median",
            "p25",
            "p75",
            "overall_median",
            "rel_diff_median_pct",
            "iqr_overlap_with_population",
            "direction",
        }
        assert required.issubset(set(df.columns))

    def test_distinguishing_csv_has_required_columns(self, cp03_run):
        df = pd.read_csv(cp03_run["distinguishing_features_csv"])
        required = {
            "unit_id",
            "algorithm",
            "feature",
            "effect_range",
            "effect_range_rel_pct",
            "iqr_overlap_mean",
            "classification",
            "n_clusters_assessable",
        }
        assert required.issubset(set(df.columns))

    def test_overlap_csv_has_required_columns(self, cp03_run):
        df = pd.read_csv(cp03_run["overlap_analysis_csv"])
        required = {
            "unit_id",
            "feature",
            "cluster_a_label",
            "cluster_b_label",
            "iqr_overlap_coefficient",
        }
        assert required.issubset(set(df.columns))


# --------------------------------------------------------------------
# CP-02 consistency
# --------------------------------------------------------------------


class TestCp02Consistency:
    @pytest.fixture(scope="module")
    def cp03_run(self, tmp_path_factory) -> dict:
        out = tmp_path_factory.mktemp("cp03_cp02_consistency") / "out"
        return run_cp03(repo_root=REPO_ROOT, output_dir=out)

    def test_cluster_counts_match_cp02(self, cp03_run):
        """Verify cluster counts in comparison matrix match CP-02."""
        comp_df = pd.read_csv(cp03_run["segment_comparison_matrix_csv"])
        # Group by (unit, cluster) and take count_total from any feature row.
        cluster_counts = (
            comp_df.groupby(["unit_id", "cluster_id"])["count_total"].first().reset_index()
        )
        # Load CP-02 consistency table.
        cp02_consistency = REPO_ROOT / "reports/profiling/cp02/cp02_cp01_consistency.csv"
        if not cp02_consistency.exists():
            pytest.skip("CP-02 consistency CSV not present.")
        cp02_df = pd.read_csv(cp02_consistency)
        for _, row in cluster_counts.iterrows():
            uid = row["unit_id"]
            cid = int(row["cluster_id"])
            cp03_count = int(row["count_total"])
            cp02_row = cp02_df.loc[(cp02_df["unit_id"] == uid) & (cp02_df["cluster_id"] == cid)]
            if cp02_row.empty:
                continue
            cp02_count = int(cp02_row.iloc[0]["cp02_cluster_customer_count"])
            assert (
                cp03_count == cp02_count
            ), f"{uid} C{cid}: CP-03 says {cp03_count}, CP-02 says {cp02_count}"

    def test_median_values_match_cp02(self, cp03_run):
        """Spot-check: verify K-Means C1 Frequency median matches CP-02."""
        comp_df = pd.read_csv(cp03_run["segment_comparison_matrix_csv"])
        row = comp_df.loc[
            (comp_df["unit_id"] == "EXP-01-kmeans-working-default")
            & (comp_df["cluster_label"] == "C1")
            & (comp_df["feature"] == "Frequency")
        ]
        assert len(row) == 1
        # From CP-02: K-Means C1 Frequency median = 2.0.
        assert row.iloc[0]["median"] == pytest.approx(2.0, abs=0.1)
        # From CP-02: K-Means C1 Frequency overall_median = 3.0.
        assert row.iloc[0]["overall_median"] == pytest.approx(3.0, abs=0.1)

    def test_rel_diff_matches_cp02(self, cp03_run):
        """Spot-check: K-Means C0 TenureDays rel_diff ≈ +157%."""
        comp_df = pd.read_csv(cp03_run["segment_comparison_matrix_csv"])
        row = comp_df.loc[
            (comp_df["unit_id"] == "EXP-01-kmeans-working-default")
            & (comp_df["cluster_label"] == "C0")
            & (comp_df["feature"] == "TenureDays")
        ]
        assert len(row) == 1
        # CP-02: K-Means C0 TenureDays rel_diff ≈ +157%.
        assert row.iloc[0]["rel_diff_median_pct"] == pytest.approx(157.0, abs=1.0)


# --------------------------------------------------------------------
# Methodology gate
# --------------------------------------------------------------------


class TestMethodologyGate:
    @pytest.fixture(scope="module")
    def cp03_run(self, tmp_path_factory) -> dict:
        out = tmp_path_factory.mktemp("cp03_methodology_gate") / "out"
        return run_cp03(repo_root=REPO_ROOT, output_dir=out)

    @pytest.mark.parametrize("token", FORBIDDEN_TOKENS)
    def test_no_forbidden_tokens_in_report(self, cp03_run, token):
        report = Path(cp03_run["report_md"]).read_text(encoding="utf-8")
        assert (
            token.lower() not in report.lower()
        ), f"forbidden token {token!r} appears in CP-03 report"

    def test_distinguishing_features_csv_no_forbidden_tokens(self, cp03_run):
        df = pd.read_csv(cp03_run["distinguishing_features_csv"])
        text = " ".join(str(v) for v in df.values.flatten()).lower()
        for token in FORBIDDEN_TOKENS:
            assert token.lower() not in text

    def test_segment_comparison_csv_no_segment_naming(self, cp03_run):
        df = pd.read_csv(cp03_run["segment_comparison_matrix_csv"])
        for col in df.columns:
            if df[col].dtype == object:
                text = " ".join(str(v) for v in df[col]).lower()
                assert "champion" not in text
                assert "khách hàng vip" not in text


# --------------------------------------------------------------------
# Read-only against source artifacts
# --------------------------------------------------------------------


class TestReadOnly:
    def test_source_artifacts_unchanged(self):
        import hashlib

        def sha(p: Path) -> str:
            h = hashlib.sha256()
            h.update(p.read_bytes())
            return h.hexdigest()

        before = {
            algo: sha(REPO_ROOT / "reports/exp01" / f"cluster_labels_EXP-01-{algo}_rep4.parquet")
            for algo in ALGORITHMS
        }
        feats_before = sha(REPO_ROOT / "data/processed/customer_candidates.parquet")
        md_before = sha(REPO_ROOT / "data/processed/customer_metadata.parquet")
        # Run CP-03 to the default output dir (same as CP-02, which is
        # already verified as read-only by test_cp02.py's TestReadOnly).
        run_cp03(repo_root=REPO_ROOT, output_dir=REPO_ROOT / "reports/profiling/cp03")
        after = {
            algo: sha(REPO_ROOT / "reports/exp01" / f"cluster_labels_EXP-01-{algo}_rep4.parquet")
            for algo in ALGORITHMS
        }
        feats_after = sha(REPO_ROOT / "data/processed/customer_candidates.parquet")
        md_after = sha(REPO_ROOT / "data/processed/customer_metadata.parquet")
        assert before == after
        assert feats_before == feats_after
        assert md_before == md_after
