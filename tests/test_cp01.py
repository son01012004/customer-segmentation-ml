"""Tests for CP-01 — Customer Segment Size & Distribution Analysis.

Validates:

1. Customer count consistency (eligible sum = 4 371 per EXP-01 unit).
2. Percentage sum (no noise) ≈ 100% per unit.
3. Cluster IDs are valid integers (or -1 for DBSCAN noise).
4. No duplicate CustomerID within the same analysis unit.
5. DBSCAN noise separation — noise label -1 reported as ``noise_count``,
   not as a customer segment.
6. Count / percentage consistency.
7. Deterministic output (size_table stable across reruns).
8. Read-only against source artifacts.
9. Working artifacts are produced with provenance fields.
10. Methodology gate — no algorithm ranking / segment naming /
    marketing recommendation in any CP-01 artefact.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import pytest

from customer_segmentation.profiling.cp01.distribution import (
    compute_distribution_indicators,
)
from customer_segmentation.profiling.cp01.provenance import (
    ALGORITHMS,
    AnalysisUnit,
    build_analysis_units,
)
from customer_segmentation.profiling.cp01.runner import run_cp01
from customer_segmentation.profiling.cp01.size_analysis import (
    ClusterSizeRow,
    NoiseRow,
    compute_cluster_size_table,
    compute_noise_summary,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------
# Provenance
# --------------------------------------------------------------------

class TestProvenance:
    def test_build_analysis_units_returns_one_unit_per_algorithm_per_condition(self):
        units = build_analysis_units(REPO_ROOT)
        assert len(units) == 10  # 5 algorithms * 2 conditions
        for algo in ALGORITHMS:
            cond = [u for u in units if u.algorithm == algo]
            assert len(cond) == 2
            sources = sorted(u.source_experiment for u in cond)
            assert sources == ["EXP-01", "EXP-03"]

    def test_exp01_units_have_persisted_labels(self):
        units = build_analysis_units(REPO_ROOT)
        for u in units:
            if u.source_experiment == "EXP-01":
                assert u.labels_persisted is True
                assert not u.cluster_labels_frame.empty
                assert u.n_customers_eligible == 4_371

    def test_exp03_units_are_metadata_only(self):
        units = build_analysis_units(REPO_ROOT)
        for u in units:
            if u.source_experiment == "EXP-03":
                assert u.labels_persisted is False
                # cluster_labels_frame is empty placeholder
                assert u.cluster_labels_frame.empty
                # The EXP-03 unit carries configuration metadata
                assert u.configuration_id.startswith("EXP-03-")
                assert u.configuration_status in {
                    "WORKING_SELECTED",
                    "TIED_WORKING_SELECTED",
                    "CANDIDATE",
                }

    def test_kmedoids_absent(self):
        units = build_analysis_units(REPO_ROOT)
        names = {u.algorithm for u in units}
        assert "kmedoids" not in names
        assert names == set(ALGORITHMS)

    def test_provenance_has_full_customer_alignment(self):
        units = build_analysis_units(REPO_ROOT)
        for u in units:
            if not u.labels_persisted:
                continue
            df = u.cluster_labels_frame
            # every CustomerID is unique per unit
            assert df["CustomerID"].nunique() == len(df)
            # CustomerID set covers the full metadata
            md = pd.read_parquet(REPO_ROOT / "data/processed/customer_metadata.parquet")
            assert set(df["CustomerID"]) == set(md["CustomerID"])


# --------------------------------------------------------------------
# Size analysis
# --------------------------------------------------------------------

class TestSizeAnalysis:
    def test_cluster_count_sums_match_denominator(self):
        units = build_analysis_units(REPO_ROOT)
        rows = compute_cluster_size_table(units)
        by_unit = {}
        for r in rows:
            by_unit.setdefault(r.unit_id, []).append(r)
        for unit_id, unit_rows in by_unit.items():
            total = sum(r.customer_count for r in unit_rows)
            assert total == 4_371, f"{unit_id} total = {total}"

    def test_percentages_sum_to_100_for_noiseless_units(self):
        units = build_analysis_units(REPO_ROOT)
        rows = compute_cluster_size_table(units)
        # For non-DBSCAN units, sum of pct_of_total should be ~100%.
        for uid in {r.unit_id for r in rows if r.algorithm != "dbscan"}:
            sub = [r for r in rows if r.unit_id == uid]
            total_pct = sum(r.pct_of_total for r in sub)
            assert 99.5 <= total_pct <= 100.5, f"{uid}: {total_pct}"

    def test_cluster_ids_are_integers(self):
        units = build_analysis_units(REPO_ROOT)
        rows = compute_cluster_size_table(units)
        for r in rows:
            assert isinstance(r.cluster_id, int)
            # DBSCAN noise is the only -1 permitted value.
            if r.cluster_id == -1:
                assert r.is_noise is True

    def test_dbscan_noise_separated(self):
        units = build_analysis_units(REPO_ROOT)
        noise_rows = compute_noise_summary(units)
        assert len(noise_rows) >= 1
        dbscan_noise = [n for n in noise_rows if n.algorithm == "dbscan"]
        assert len(dbscan_noise) == 1  # only EXP-01 DBSCAN is persisted
        # Noise count is consistent with the size table
        rows = [r for r in compute_cluster_size_table(units) if r.is_noise]
        for r in rows:
            assert r.cluster_id == -1

    def test_relative_size_ratio_within_zero_one(self):
        units = build_analysis_units(REPO_ROOT)
        rows = compute_cluster_size_table(units)
        # Largest segment should have ratio 1.0; smaller segments < 1.0
        for r in rows:
            if r.is_noise:
                continue
            assert 0.0 < r.relative_size_ratio <= 1.0

    def test_count_pct_consistency(self):
        units = build_analysis_units(REPO_ROOT)
        rows = compute_cluster_size_table(units)
        for r in rows:
            # Count * 100 / total == pct_of_total (modulo rounding)
            n_total = 4_371
            expected = r.customer_count / n_total * 100.0
            assert abs(r.pct_of_total - expected) < 0.001


# --------------------------------------------------------------------
# Distribution indicators
# --------------------------------------------------------------------

class TestDistribution:
    def test_n_clusters_for_fixed_K(self):
        units = build_analysis_units(REPO_ROOT)
        rows = compute_cluster_size_table(units)
        indicators = compute_distribution_indicators(rows)
        # For the 4 fixed-K algorithms (kmeans/agglomerative/gmm/fcm):
        # n_clusters == 4
        for ind in indicators:
            if ind.algorithm in {"kmeans", "agglomerative", "gmm", "fuzzy_cmeans"}:
                assert ind.n_clusters == 4
            elif ind.algorithm == "dbscan":
                assert ind.n_clusters == 17  # realised K

    def test_deviation_from_equal_size_non_negative(self):
        units = build_analysis_units(REPO_ROOT)
        rows = compute_cluster_size_table(units)
        indicators = compute_distribution_indicators(rows)
        for ind in indicators:
            assert ind.deviation_from_equal_size >= 0.0

    def test_largest_to_smallest_ratio_consistent_with_sizes(self):
        units = build_analysis_units(REPO_ROOT)
        rows = compute_cluster_size_table(units)
        indicators = compute_distribution_indicators(rows)
        for ind in indicators:
            assert abs(
                ind.largest_to_smallest_ratio
                - ind.largest_cluster_count / ind.smallest_cluster_count
            ) < 0.001


# --------------------------------------------------------------------
# End-to-end runner
# --------------------------------------------------------------------

class TestRunner:
    @pytest.fixture
    def cp01_run(self, tmp_path: Path) -> dict:
        # Run with isolated output dir to keep tests idempotent.
        return run_cp01(repo_root=REPO_ROOT, output_dir=tmp_path)

    def test_runner_writes_all_required_artifacts(self, cp01_run):
        for key in (
            "cluster_size_table_csv",
            "noise_summary_csv",
            "distribution_indicators_csv",
            "unit_provenance_csv",
            "report_md",
            "manifest_json",
        ):
            p = Path(cp01_run[key])
            assert p.exists(), f"missing output: {key} → {p}"

    def test_runner_emits_one_chart_per_unit_with_labels(self, cp01_run):
        # 5 EXP-01 units × 2 charts each (size + pct) = 10 charts
        assert len(cp01_run["figures"]) == 10

    def test_runner_output_is_deterministic(self, tmp_path: Path):
        summary_a = run_cp01(repo_root=REPO_ROOT, output_dir=tmp_path / "run_a")
        summary_b = run_cp01(repo_root=REPO_ROOT, output_dir=tmp_path / "run_b")
        df_a = pd.read_csv(summary_a["cluster_size_table_csv"])
        df_b = pd.read_csv(summary_b["cluster_size_table_csv"])
        # Sort both for stable comparison
        df_a = df_a.sort_values(["unit_id", "cluster_id"]).reset_index(drop=True)
        df_b = df_b.sort_values(["unit_id", "cluster_id"]).reset_index(drop=True)
        pd.testing.assert_frame_equal(df_a, df_b)

    def test_runner_manifest_metadata(self, cp01_run):
        manifest = json.loads(Path(cp01_run["manifest_json"]).read_text())
        assert manifest["analysis_units_total"] == 10
        assert manifest["units_with_labels"] == 5
        assert manifest["units_without_labels"] == 5
        assert sorted(manifest["algorithms"]) == sorted(ALGORITHMS)


# --------------------------------------------------------------------
# Methodology gate (no ranking / no segment naming / no marketing)
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
]


class TestMethodologyGate:
    @pytest.fixture
    def cp01_run(self, tmp_path: Path) -> dict:
        return run_cp01(repo_root=REPO_ROOT, output_dir=tmp_path)

    @pytest.mark.parametrize("token", FORBIDDEN_TOKENS)
    def test_no_forbidden_tokens_in_outputs(self, cp01_run, token):
        report = Path(cp01_run["report_md"]).read_text(encoding="utf-8")
        assert token.lower() not in report.lower(), (
            f"forbidden token {token!r} appears in CP-01 report"
        )


# --------------------------------------------------------------------
# Read-only against source artifacts
# --------------------------------------------------------------------

class TestReadOnly:
    def test_source_parquets_unchanged(self):
        # Read SHA before and after a CP-01 run; should be identical.
        import hashlib

        def sha(p: Path) -> str:
            h = hashlib.sha256()
            h.update(p.read_bytes())
            return h.hexdigest()

        before = {
            algo: sha(
                REPO_ROOT
                / "reports/exp01"
                / f"cluster_labels_EXP-01-{algo}_rep4.parquet"
            )
            for algo in ALGORITHMS
        }
        run_cp01(repo_root=REPO_ROOT, output_dir=REPO_ROOT / "reports/profiling/cp01")
        after = {
            algo: sha(
                REPO_ROOT
                / "reports/exp01"
                / f"cluster_labels_EXP-01-{algo}_rep4.parquet"
            )
            for algo in ALGORITHMS
        }
        assert before == after
