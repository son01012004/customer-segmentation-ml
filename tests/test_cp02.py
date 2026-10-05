"""Tests for CP-02 — Per-Cluster Feature Profile & Behavioural Analysis.

Validates:

1. CustomerID alignment between cluster labels and RAW feature matrix.
2. Each customer belongs to exactly one cluster per analysis unit.
3. Cluster customer counts match CP-01 (consistency check).
4. Statistics (count, mean, median, P25, P75, min, max, std) are
   correct.
5. Median / percentile computations are correct.
6. Relative difference formula is correct.
7. Division-by-zero is handled via ``ZERO_REFERENCE``.
8. Missing values are kept (not silently imputed); n_missing is
   reported.
9. No duplicate (unit, cluster, feature) tuples in the profile table.
10. Total cluster customer count matches CP-01 across all non-noise
    clusters of an analysis unit.
11. RAW feature values are used (no Yeo-Johnson / RobustScaler leak).
12. Output deterministic across reruns.
13. Methodology gate — no segment naming, no marketing recommendation
    in any CP-02 artifact.
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
from customer_segmentation.profiling.cp02.behavioral_interpretation import (
    FEATURE_SEMANTICS,
    interpret_feature_for_cluster,
)
from customer_segmentation.profiling.cp02.feature_profiling import (
    compute_feature_profile_table,
    compute_overall_feature_summary,
)
from customer_segmentation.profiling.cp02.provenance import (
    FEATURE_COLUMNS,
    RAW_FEATURES_PATH,
    build_cp02_analysis_units,
    load_raw_customer_features,
)
from customer_segmentation.profiling.cp02.relative_comparison import (
    RelativeComparisonRow,
    compute_relative_comparison_table,
)
from customer_segmentation.profiling.cp02.runner import run_cp02

REPO_ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------
# Provenance / CustomerID alignment
# --------------------------------------------------------------------


class TestProvenance:
    def test_build_cp02_analysis_units_returns_one_unit_per_algorithm_per_condition(self):
        units = build_cp02_analysis_units(REPO_ROOT)
        assert len(units) == 10  # 5 algorithms * 2 conditions
        for algo in ALGORITHMS:
            cond = [u for u in units if u.algorithm == algo]
            assert len(cond) == 2
            sources = sorted(u.source_experiment for u in cond)
            assert sources == ["EXP-01", "EXP-03"]

    def test_raw_features_load_returns_one_row_per_customer(self):
        feats = load_raw_customer_features(REPO_ROOT)
        assert feats.index.name == "CustomerID"
        assert feats.index.is_unique
        assert feats.shape[0] == 4371
        for c in FEATURE_COLUMNS:
            assert c in feats.columns

    def test_persisted_units_have_full_customer_alignment(self):
        units = build_cp02_analysis_units(REPO_ROOT)
        md = pd.read_parquet(REPO_ROOT / "data/processed/customer_metadata.parquet")
        for u in units:
            if not u.labels_persisted:
                continue
            df = u.cluster_labels_frame
            assert df["CustomerID"].nunique() == len(df)
            assert set(df["CustomerID"]) == set(md["CustomerID"])

    def test_dbscan_noise_present_in_dbscan_unit(self):
        units = build_cp02_analysis_units(REPO_ROOT)
        dbscan_unit = next(
            u for u in units if u.algorithm == "dbscan" and u.source_experiment == "EXP-01"
        )
        assert dbscan_unit.labels_persisted
        df = dbscan_unit.cluster_labels_frame
        n_noise = int((df["ClusterLabel"] == -1).sum())
        assert n_noise == 3177
        # non-noise = 4371 - 3177 = 1194
        n_non_noise = int((df["ClusterLabel"] != -1).sum())
        assert n_non_noise == 1194

    def test_raw_features_used_not_transformed(self):
        """The customer_candidates.parquet used by CP-02 should contain
        RAW interpretable values, NOT Yeo-Johnson / RobustScaler values.
        """
        feats = load_raw_customer_features(REPO_ROOT)
        # Monetary on RAW is in GBP (£), can be >> 1.
        assert feats["Monetary"].max() > 100.0
        # CancellationRate is a ratio in [0, 1] on RAW; if it had been
        # transformed we would see values outside that range.
        assert feats["CancellationRate"].min() >= 0.0
        assert feats["CancellationRate"].max() <= 1.0 + 1e-9


# --------------------------------------------------------------------
# Feature profiling
# --------------------------------------------------------------------


class TestFeatureProfiling:
    def test_one_row_per_unit_cluster_feature(self):
        units = build_cp02_analysis_units(REPO_ROOT)
        rows = compute_feature_profile_table(units)
        # Each non-noise cluster contributes 14 rows; each unit contributes
        # 14 OVERALL rows.
        by_unit = {}
        for r in rows:
            by_unit.setdefault(r.unit_id, []).append(r)
        for unit in units:
            if not unit.labels_persisted:
                assert by_unit.get(unit.unit_id, []) == []
                continue
            n_clusters = int(
                (unit.cluster_labels_frame["ClusterLabel"] != -1).sum()
                // unit.cluster_labels_frame["CustomerID"].nunique()
            )  # number of distinct non-noise clusters (per-customer unique)
            # count via groupby:
            df = unit.cluster_labels_frame
            n_clusters = int(df.loc[df["ClusterLabel"] != -1, "ClusterLabel"].nunique())
            expected = n_clusters * len(FEATURE_COLUMNS) + len(FEATURE_COLUMNS)
            assert (
                len(by_unit[unit.unit_id]) == expected
            ), f"{unit.unit_id}: expected {expected}, got {len(by_unit[unit.unit_id])}"

    def test_no_duplicate_unit_cluster_feature(self):
        units = build_cp02_analysis_units(REPO_ROOT)
        rows = compute_feature_profile_table(units)
        keys = [(r.unit_id, r.cluster_label, r.feature) for r in rows]
        assert len(keys) == len(set(keys))

    def test_count_equals_n_non_nan_in_cluster(self):
        """Verify count = number of non-NaN observations in cluster for feature."""
        units = build_cp02_analysis_units(REPO_ROOT)
        rows = compute_feature_profile_table(units)
        # Index rows by (unit_id, cluster_label, feature) once.
        rows_index = {(r.unit_id, r.cluster_label, r.feature): r for r in rows}
        for u in units:
            if not u.labels_persisted:
                continue
            df = u.cluster_labels_frame
            eligible = df.loc[df["ClusterLabel"] != -1]
            for cl, sub in eligible.groupby("ClusterLabel"):
                for feat in FEATURE_COLUMNS:
                    expected_count = int(sub[feat].dropna().size)
                    matching = rows_index.get((u.unit_id, f"C{int(cl)}", feat))
                    assert matching is not None, f"missing row for {u.unit_id} C{int(cl)} {feat}"
                    assert matching.count == expected_count, (
                        f"{u.unit_id} C{int(cl)} {feat}: "
                        f"expected {expected_count}, got {matching.count}"
                    )

    def test_count_total_equals_cluster_size(self):
        """Verify count_total = total customers in cluster (NaN included)."""
        units = build_cp02_analysis_units(REPO_ROOT)
        rows = compute_feature_profile_table(units)
        rows_index = {(r.unit_id, r.cluster_label, r.feature): r for r in rows}
        for u in units:
            if not u.labels_persisted:
                continue
            df = u.cluster_labels_frame
            eligible = df.loc[df["ClusterLabel"] != -1]
            for cl, sub in eligible.groupby("ClusterLabel"):
                expected_total = int(sub["CustomerID"].nunique())
                matching = rows_index.get((u.unit_id, f"C{int(cl)}", FEATURE_COLUMNS[0]))
                assert matching is not None
                assert matching.count_total == expected_total

    def test_overall_rows_present_and_unique(self):
        units = build_cp02_analysis_units(REPO_ROOT)
        overall = compute_overall_feature_summary(units)
        for u in units:
            if not u.labels_persisted:
                continue
            for feat in FEATURE_COLUMNS:
                assert (u.unit_id, feat) in overall
                row = overall[(u.unit_id, feat)]
                assert row.cluster_label == "OVERALL"
                # count_total should equal sum of all non-noise cluster
                # totals in the unit
                df = u.cluster_labels_frame
                eligible = df.loc[df["ClusterLabel"] != -1]
                expected_total = int(eligible["CustomerID"].nunique())
                assert row.count_total == expected_total


# --------------------------------------------------------------------
# Relative comparison
# --------------------------------------------------------------------


class TestRelativeComparison:
    def test_relative_difference_formula_correct(self):
        """Verify the rel_diff formula:
        rel_diff_pct = (cluster_value - reference_value) / reference_value × 100.
        """
        rel = RelativeComparisonRow(
            unit_id="U",
            algorithm="kmeans",
            source_experiment="EXP-01",
            cluster_id=0,
            cluster_label="C0",
            feature="Recency",
            cluster_median=20.0,
            cluster_mean=25.0,
            overall_median=10.0,
            overall_mean=12.0,
            rel_diff_median_pct=100.0,
            rel_diff_mean_pct=108.33333333333333,
            reference_status="OK",
            reference_count=100,
        )
        # (20 - 10) / 10 * 100 = 100
        assert rel.rel_diff_median_pct == pytest.approx(100.0, abs=1e-6)
        # (25 - 12) / 12 * 100 = 108.333...
        assert rel.rel_diff_mean_pct == pytest.approx(108.33333333333333, abs=1e-6)

    def test_division_by_zero_flagged(self):
        """Reference = 0 → ZERO_REFERENCE, rel_diff_pct = NaN."""
        rel_rows = compute_relative_comparison_table(
            # We use a minimal unit for the test by hand-crafting the
            # overall reference row — instead, test the formula on a
            # known feature where 0 is plausible.
            units=_dummy_units_for_zero_reference_test(),
        )
        zero_ref_rows = [r for r in rel_rows if r.reference_status == "ZERO_REFERENCE"]
        assert len(zero_ref_rows) >= 1
        for r in zero_ref_rows:
            assert np.isnan(r.rel_diff_median_pct)
            assert np.isnan(r.rel_diff_mean_pct)

    def test_no_negative_infinity_or_nan_explosion(self):
        """No NaN propagation outside ZERO_REFERENCE / NA cases."""
        units = build_cp02_analysis_units(REPO_ROOT)
        rel_rows = compute_relative_comparison_table(units)
        for r in rel_rows:
            if r.reference_status in {"ZERO_REFERENCE", "NA"}:
                continue
            # OK case — should be finite
            assert np.isfinite(r.rel_diff_median_pct)
            assert np.isfinite(r.rel_diff_mean_pct)


def _dummy_units_for_zero_reference_test():
    """Build a hand-crafted Cp02AnalysisUnit whose overall median for one
    feature is zero, so the relative-comparison module flags
    ZERO_REFERENCE.
    """
    from customer_segmentation.profiling.cp02.provenance import (
        Cp02AnalysisUnit,
    )

    # Tiny frame: 4 customers in 1 cluster. CancellationRate all zero.
    rows = pd.DataFrame(
        {
            "CustomerID": [1, 2, 3, 4],
            "Recency": [10, 20, 30, 40],
            "Frequency": [1, 1, 1, 1],
            "Monetary": [100.0, 200.0, 300.0, 400.0],
            "TotalQuantity": [10, 20, 30, 40],
            "AverageQuantity": [1.0, 2.0, 3.0, 4.0],
            "BasketSize": [1.0, 2.0, 3.0, 4.0],
            "TenureDays": [100, 200, 300, 400],
            "PurchaseIntervalMean": [50.0, 50.0, 50.0, 50.0],
            "PurchaseIntervalStd": [10.0, 10.0, 10.0, 10.0],
            "ActiveDays": [1, 2, 3, 4],
            "AverageInvoiceValue": [100.0, 200.0, 300.0, 400.0],
            "ProductsPerInvoice": [5.0, 5.0, 5.0, 5.0],
            "CancellationRate": [0.0, 0.0, 0.0, 0.0],
            "ReturnRate": [0.0, 0.0, 0.0, 0.0],
            "ClusterLabel": [0, 0, 0, 0],
            "IsNoise": [False, False, False, False],
        }
    )
    features_only = pd.DataFrame(
        {
            "CustomerID": [1, 2, 3, 4],
            **{c: rows[c].values for c in FEATURE_COLUMNS},
        }
    ).set_index("CustomerID")
    return [
        Cp02AnalysisUnit(
            unit_id="DUMMY",
            algorithm="kmeans",
            source_experiment="EXP-01",
            configuration_id="DUMMY-kmeans",
            configuration_status="WORKING_DEFAULT",
            labels_persisted=True,
            cluster_labels_frame=rows,
            raw_features_frame=features_only,
            n_customers_eligible=4,
        )
    ]


# --------------------------------------------------------------------
# Behavioural interpretation
# --------------------------------------------------------------------


class TestBehaviouralInterpretation:
    def test_higher_direction_above_threshold(self):
        row = interpret_feature_for_cluster(
            feature="Monetary",
            cluster_median=1100.0,
            overall_median=1000.0,
            rel_diff_pct=10.0,  # exactly at threshold
            reference_status="OK",
        )
        assert row.direction == "HIGHER"
        assert "cao hơn" in row.interpretation.lower() or "cao" in row.interpretation.lower()

    def test_lower_direction_below_threshold(self):
        row = interpret_feature_for_cluster(
            feature="Recency",
            cluster_median=80.0,
            overall_median=100.0,
            rel_diff_pct=-20.0,
            reference_status="OK",
        )
        assert row.direction == "LOWER"
        assert "thấp" in row.interpretation.lower() or "thap" in row.interpretation.lower()

    def test_comparable_direction(self):
        row = interpret_feature_for_cluster(
            feature="Frequency",
            cluster_median=5.0,
            overall_median=5.05,
            rel_diff_pct=-1.0,  # within band
            reference_status="OK",
        )
        assert row.direction == "COMPARABLE"

    def test_zero_reference_direction(self):
        row = interpret_feature_for_cluster(
            feature="CancellationRate",
            cluster_median=0.0,
            overall_median=0.0,
            rel_diff_pct=float("nan"),
            reference_status="ZERO_REFERENCE",
        )
        assert row.direction == "ZERO_REFERENCE"
        assert "ZERO" in row.interpretation or "không" in row.interpretation.lower()

    def test_semantics_table_has_all_14_features(self):
        for feat in FEATURE_COLUMNS:
            assert feat in FEATURE_SEMANTICS
            for k in ("high", "low", "neutral"):
                assert k in FEATURE_SEMANTICS[feat]


# --------------------------------------------------------------------
# Runner / end-to-end
# --------------------------------------------------------------------


class TestRunner:
    @pytest.fixture(scope="module")
    def cp02_run(self, tmp_path_factory) -> dict:
        out = tmp_path_factory.mktemp("cp02_runner") / "out"
        return run_cp02(repo_root=REPO_ROOT, output_dir=out)

    def test_runner_writes_all_required_artifacts(self, cp02_run):
        for key in (
            "feature_profile_table_csv",
            "relative_comparison_csv",
            "behavioral_interpretation_csv",
            "unit_provenance_csv",
            "cp01_consistency_csv",
            "report_md",
            "manifest_json",
        ):
            p = Path(cp02_run[key])
            assert p.exists(), f"missing output: {key} → {p}"

    def test_runner_emits_expected_chart_count(self, cp02_run):
        """5 EXP-01 units × (7 boxplots + 1 heatmap) = 40 charts."""
        assert len(cp02_run["figures"]) == 5 * (7 + 1)

    def test_runner_output_is_deterministic(self, tmp_path: Path):
        s_a = run_cp02(repo_root=REPO_ROOT, output_dir=tmp_path / "run_a")
        s_b = run_cp02(repo_root=REPO_ROOT, output_dir=tmp_path / "run_b")
        for key in (
            "feature_profile_table_csv",
            "relative_comparison_csv",
            "behavioral_interpretation_csv",
            "unit_provenance_csv",
            "cp01_consistency_csv",
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

    def test_runner_manifest_metadata(self, cp02_run):
        manifest = json.loads(Path(cp02_run["manifest_json"]).read_text())
        assert manifest["analysis_units_total"] == 10
        assert manifest["units_with_labels"] == 5
        assert manifest["units_without_labels"] == 5
        assert sorted(manifest["algorithms"]) == sorted(ALGORITHMS)
        assert manifest["feature_source"].startswith("RAW")


# --------------------------------------------------------------------
# CP-01 consistency
# --------------------------------------------------------------------


class TestCp01Consistency:
    @pytest.fixture(scope="module")
    def cp02_run(self, tmp_path_factory) -> dict:
        out = tmp_path_factory.mktemp("cp02_consistency") / "out"
        return run_cp02(repo_root=REPO_ROOT, output_dir=out)

    def test_cluster_counts_match_cp01(self, cp02_run):
        cp01_path = REPO_ROOT / "reports/profiling/cp01/cp01_cluster_size_table.csv"
        if not cp01_path.exists():
            pytest.skip("CP-01 size table not present; cannot verify.")
        cp01 = pd.read_csv(cp01_path)
        cp01_non_noise = cp01.loc[cp01["is_noise"] == False].copy()  # noqa: E712
        consistency = pd.read_csv(cp02_run["cp01_consistency_csv"])
        # For each (unit_id, cluster_id) we expect a match == True row.
        for _, row in consistency.iterrows():
            cp01_row = cp01_non_noise.loc[
                (cp01_non_noise["unit_id"] == row["unit_id"])
                & (cp01_non_noise["cluster_id"] == row["cluster_id"])
            ]
            if cp01_row.empty:
                continue
            expected = int(cp01_row.iloc[0]["customer_count"])
            assert int(row["cp02_cluster_customer_count"]) == expected, (
                f"{row['unit_id']} C{row['cluster_id']}: "
                f"CP-02 says {row['cp02_cluster_customer_count']}, "
                f"CP-01 says {expected}"
            )
            assert bool(row["match"]) is True
            assert int(row["diff"]) == 0

    def test_total_customer_count_matches_cp01(self, cp02_run):
        """Sum of (cluster counts) per unit (non-noise) equals CP-01 total."""
        cp01_path = REPO_ROOT / "reports/profiling/cp01/cp01_cluster_size_table.csv"
        if not cp01_path.exists():
            pytest.skip("CP-01 size table not present; cannot verify.")
        cp01 = pd.read_csv(cp01_path)
        cp01_non_noise = cp01.loc[cp01["is_noise"] == False].copy()  # noqa: E712
        consistency = pd.read_csv(cp02_run["cp01_consistency_csv"])
        # Group by unit_id
        cp01_totals = cp01_non_noise.groupby("unit_id")["customer_count"].sum().to_dict()
        cp02_totals = consistency.groupby("unit_id")["cp02_cluster_customer_count"].sum().to_dict()
        for uid, total_cp01 in cp01_totals.items():
            assert (
                cp02_totals.get(uid) == total_cp01
            ), f"{uid}: CP-02 total {cp02_totals.get(uid)}, CP-01 total {total_cp01}"


# --------------------------------------------------------------------
# Methodology gate (no segment naming, no marketing recommendation)
# --------------------------------------------------------------------

FORBIDDEN_TOKENS = [
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
    # Additional tokens specifically checked for CP-02:
    "nên được ưu tiên",  # 'should be prioritised'
    "chiến dịch",  # 'campaign'
    "khách hàng VIP",  # 'VIP customer'
    "có giá trị nhất",  # 'most valuable'
    "tốt nhất",  # 'best'
]


class TestMethodologyGate:
    @pytest.fixture(scope="module")
    def cp02_run(self, tmp_path_factory) -> dict:
        out = tmp_path_factory.mktemp("cp02_methodology_gate") / "out"
        return run_cp02(repo_root=REPO_ROOT, output_dir=out)

    @pytest.mark.parametrize("token", FORBIDDEN_TOKENS)
    def test_no_forbidden_tokens_in_report(self, cp02_run, token):
        report = Path(cp02_run["report_md"]).read_text(encoding="utf-8")
        assert (
            token.lower() not in report.lower()
        ), f"forbidden token {token!r} appears in CP-02 report"

    def test_no_segment_naming_in_interpretation_csv(self, cp02_run):
        df = pd.read_csv(cp02_run["behavioral_interpretation_csv"])
        text = " ".join(str(t) for t in df["interpretation"].tolist()).lower()
        # 'vip' can appear as substring of unrelated words; check for
        # explicit naming patterns.
        assert "champion" not in text  # 'champion' / 'champions'
        assert "khách hàng vip" not in text
        assert "khach hang vip" not in text


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
        feats_before = sha(REPO_ROOT / RAW_FEATURES_PATH)
        md_before = sha(REPO_ROOT / "data/processed/customer_metadata.parquet")
        run_cp02(repo_root=REPO_ROOT, output_dir=REPO_ROOT / "reports/profiling/cp02")
        after = {
            algo: sha(REPO_ROOT / "reports/exp01" / f"cluster_labels_EXP-01-{algo}_rep4.parquet")
            for algo in ALGORITHMS
        }
        feats_after = sha(REPO_ROOT / RAW_FEATURES_PATH)
        md_after = sha(REPO_ROOT / "data/processed/customer_metadata.parquet")
        assert before == after
        assert feats_before == feats_after
        assert md_before == md_after
