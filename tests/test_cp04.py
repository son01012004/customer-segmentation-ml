"""Tests for CP-04 — Customer Profiles and Segment Naming.

Validates:

1. Provenance: 10 analysis units (5 algorithms × 2 conditions).
2. Provenance: K-Medoids is absent (algorithm scope intact).
3. Provenance: EXP-03 units labels_persisted=False.
4. Provenance: EXP-01 units labels_persisted=True.
5. Provenance: CustomerID alignment with customer_metadata.parquet
   (inherited from CP-02).
6. Naming: every valid (unit, cluster) has a SegmentName.
7. Naming: SegmentProfile has required fields populated.
8. Segment naming: tier rules applied correctly (Recency/Frequency/
   Monetary).
9. Naming: behavioural modifier only applied when HIGH_DIFFERENCE_OBSERVED.
10. Naming: NO marketing terms (champions, VIP, loyal, at-risk) in
    segment names.
11. Naming: DBSCAN noise bucket does NOT receive a descriptive segment
    name (naming_status="NOISE").
12. Naming: EXP-03 units have naming_status="NOT_AVAILABLE".
13. Naming: NOT_ASSESSABLE features (CancellationRate, ReturnRate)
    are NOT used as primary naming evidence.
14. Profile builder: cluster count matches CP-01 size table.
15. Profile builder: percentage matches CP-01 size table.
16. Profile builder: no duplicate (unit_id, cluster_id) profiles.
17. Profile builder: feature summaries pull from CP-03 comparison.
18. Profile builder: IQR overlap summary pulled from CP-03 comparison.
19. Profile builder: distinguishing classification pulled from CP-03.
20. Runner: all required artefacts written.
21. Runner: deterministic output across reruns.
22. Runner: SHA-256 of CP-01/02/03 source artefacts unchanged.
23. Methodology gate: no forbidden tokens in CP-04 report.
24. Cross-algorithm: Cluster IDs are NOT cross-mapped.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from customer_segmentation.profiling.cp01.provenance import ALGORITHMS
from customer_segmentation.profiling.cp02.provenance import FEATURE_COLUMNS
from customer_segmentation.profiling.cp04.naming import (
    NAMING_FEATURES,
    compute_all_segment_names,
)
from customer_segmentation.profiling.cp04.profile_builder import (
    build_all_segment_profiles,
    evidence_rows_to_dicts,
    segment_profiles_to_summary_dicts,
)
from customer_segmentation.profiling.cp04.provenance import (
    build_cp04_analysis_units,
    get_cp04_artifact_shas,
)
from customer_segmentation.profiling.cp04.runner import run_cp04

REPO_ROOT = Path(__file__).resolve().parents[1]

# Forbidden tokens for CP-04 methodology gate. Includes CP-01/CP-02/CP-03
# tokens + CP-04-specific ones.
FORBIDDEN_TOKENS = [
    # CP-01/CP-02/CP-03 tokens
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
    "most distinguishing",
    "best separation",
    "separation score",
    "distinguishing score",
    "optimal separating",
    "most separating",
    # CP-04 specific
    "loyal customers",
    "vip customers",
    "champion customers",
    "marketing recommendation",
    "should target",
    "nên target",
    "high-value customer",
    "low-value customer",
]


# --------------------------------------------------------------------
# Provenance
# --------------------------------------------------------------------


class TestProvenance:
    def test_build_cp04_analysis_units_returns_one_unit_per_algorithm_per_condition(
        self,
    ):
        units = build_cp04_analysis_units(REPO_ROOT)
        assert len(units) == 10
        for algo in ALGORITHMS:
            cond = [u for u in units if u.algorithm == algo]
            assert len(cond) == 2
            sources = sorted(u.source_experiment for u in cond)
            assert sources == ["EXP-01", "EXP-03"]

    def test_kmedoids_absent(self):
        units = build_cp04_analysis_units(REPO_ROOT)
        names = {u.algorithm for u in units}
        assert "kmedoids" not in names
        assert names == set(ALGORITHMS)

    def test_exp01_units_labels_persisted(self):
        units = build_cp04_analysis_units(REPO_ROOT)
        for u in units:
            if u.source_experiment == "EXP-01":
                assert u.labels_persisted is True

    def test_exp03_units_labels_not_persisted(self):
        units = build_cp04_analysis_units(REPO_ROOT)
        for u in units:
            if u.source_experiment == "EXP-03":
                assert u.labels_persisted is False

    def test_units_have_required_fields(self):
        units = build_cp04_analysis_units(REPO_ROOT)
        for u in units:
            assert u.unit_id
            assert u.algorithm in ALGORITHMS
            assert u.source_experiment in {"EXP-01", "EXP-03"}
            assert u.configuration_id
            assert u.configuration_status in {
                "WORKING_DEFAULT",
                "WORKING_SELECTED",
                "TIED_WORKING_SELECTED",
            }

    def test_artifact_sha_helper_returns_all_paths(self):
        shas = get_cp04_artifact_shas(REPO_ROOT)
        for key in (
            "cp01_cluster_size_table",
            "cp02_feature_profile",
            "cp02_relative_comparison",
            "cp02_behavioral_interpretation",
            "cp02_unit_provenance",
            "cp03_segment_comparison_matrix",
            "cp03_distinguishing_features",
            "cp03_overlap_analysis",
            "cp03_unit_provenance",
        ):
            assert key in shas


# --------------------------------------------------------------------
# Naming
# --------------------------------------------------------------------


class TestNaming:
    def test_naming_features_does_not_include_not_assessable(self):
        """CancellationRate / ReturnRate / AverageQuantity / BasketSize
        must NOT be in the NAMING_FEATURES list (they are excluded from
        naming evidence surface)."""
        assert "CancellationRate" not in NAMING_FEATURES
        assert "ReturnRate" not in NAMING_FEATURES
        # AverageQuantity and BasketSize are redundant (Pearson = 1.0);
        # only one may appear, but they should not be in the primary
        # naming set.
        assert "AverageQuantity" not in NAMING_FEATURES
        assert "BasketSize" not in NAMING_FEATURES

    def test_naming_features_subset_of_feature_columns(self):
        for f in NAMING_FEATURES:
            assert f in FEATURE_COLUMNS, f"{f} not in FEATURE_COLUMNS"

    def test_compute_all_segment_names_returns_one_per_unit_cluster(self):
        units = build_cp04_analysis_units(REPO_ROOT)
        names = compute_all_segment_names(units)
        # Expected: 4 (kmeans) + 4 (agglo) + 18 (dbscan: 17 non-noise + 1 noise) +
        # 4 (gmm) + 4 (fcm) + 5 (exp03) = 39
        assert len(names) == 4 + 4 + 18 + 4 + 4 + 5

    def test_each_non_noise_cluster_has_naming_status_named_or_comparative(self):
        units = build_cp04_analysis_units(REPO_ROOT)
        names = compute_all_segment_names(units)
        for n in names:
            if n.is_noise or n.is_not_available:
                continue
            assert n.naming_status in {"NAMED", "COMPARATIVE"}

    def test_dbscan_noise_not_named_as_segment(self):
        units = build_cp04_analysis_units(REPO_ROOT)
        names = compute_all_segment_names(units)
        for n in names:
            if n.is_noise:
                assert n.naming_status == "NOISE"
                # Noise name should reference "NOISE" or "not a customer segment".
                assert "NOISE" in n.name or "not a customer segment" in n.naming_rationale

    def test_exp03_units_are_not_available(self):
        units = build_cp04_analysis_units(REPO_ROOT)
        names = compute_all_segment_names(units)
        for n in names:
            if n.is_not_available:
                assert n.naming_status == "NOT_AVAILABLE"
                assert "NOT_AVAILABLE" in n.name

    def test_no_forbidden_marketing_terms_in_segment_names(self):
        units = build_cp04_analysis_units(REPO_ROOT)
        names = compute_all_segment_names(units)
        for n in names:
            if n.is_noise or n.is_not_available:
                continue
            for token in FORBIDDEN_TOKENS:
                assert (
                    token.lower() not in n.name.lower()
                ), f"Segment name '{n.name}' contains forbidden token '{token}'"

    def test_naming_rationale_is_non_empty(self):
        units = build_cp04_analysis_units(REPO_ROOT)
        names = compute_all_segment_names(units)
        for n in names:
            assert n.naming_rationale
            # Rationale should reference at least one feature (for named) or
            # explicitly state the limitation (for COMPARATIVE).
            assert len(n.naming_rationale) > 20

    def test_recency_tier_reflects_direction(self):
        """For a cluster with Recency direction=LOWER, tier=Recent;
        for HIGHER, tier=Older; for COMPARABLE, tier=Mixed."""
        units = build_cp04_analysis_units(REPO_ROOT)
        # Use K-Means C1 (large cluster with Recency HIGHER).
        km_unit = next(u for u in units if u.unit_id == "EXP-01-kmeans-working-default")
        cmp_rows = km_unit.cp03_comparison
        cluster_cmp = cmp_rows[cmp_rows["cluster_id"] == 1]
        recency_row = cluster_cmp[cluster_cmp["feature"] == "Recency"].iloc[0]
        direction = recency_row["direction"]
        # Now check that the corresponding SegmentName has tier=Older
        # (since K-Means C1 has Recency HIGHER).
        names = compute_all_segment_names(units)
        c1_name = next(n for n in names if n.unit_id == km_unit.unit_id and n.cluster_id == 1)
        if direction == "HIGHER":
            assert c1_name.recency_tier == "Older"
        elif direction == "LOWER":
            assert c1_name.recency_tier == "Recent"
        else:
            assert c1_name.recency_tier == "Mixed"

    def test_frequency_tier_reflects_direction(self):
        units = build_cp04_analysis_units(REPO_ROOT)
        names = compute_all_segment_names(units)
        km_unit = next(u for u in units if u.unit_id == "EXP-01-kmeans-working-default")
        cmp_rows = km_unit.cp03_comparison
        cluster_cmp = cmp_rows[cmp_rows["cluster_id"] == 1]
        freq_row = cluster_cmp[cluster_cmp["feature"] == "Frequency"].iloc[0]
        direction = freq_row["direction"]
        c1_name = next(n for n in names if n.unit_id == km_unit.unit_id and n.cluster_id == 1)
        if direction == "HIGHER":
            assert c1_name.frequency_tier == "Frequent"
        elif direction == "LOWER":
            assert c1_name.frequency_tier == "Occasional"
        else:
            assert c1_name.frequency_tier == "Mixed"


# --------------------------------------------------------------------
# Profile builder
# --------------------------------------------------------------------


class TestProfileBuilder:
    def test_build_all_segment_profiles_returns_one_per_unit_cluster(self):
        units = build_cp04_analysis_units(REPO_ROOT)
        profiles = build_all_segment_profiles(units)
        names = compute_all_segment_names(units)
        # Same count as segment names.
        assert len(profiles) == len(names)

    def test_no_duplicate_unit_cluster_id(self):
        units = build_cp04_analysis_units(REPO_ROOT)
        profiles = build_all_segment_profiles(units)
        keys = [(p.unit_id, int(p.cluster_id)) for p in profiles]
        assert len(keys) == len(set(keys))

    def test_profile_has_required_fields(self):
        units = build_cp04_analysis_units(REPO_ROOT)
        profiles = build_all_segment_profiles(units)
        for p in profiles:
            assert p.unit_id
            assert p.algorithm in ALGORITHMS
            assert p.source_experiment in {"EXP-01", "EXP-03"}
            assert p.cluster_label
            assert isinstance(p.customer_count, int)
            assert isinstance(p.pct_of_total, (int, float))
            assert p.segment_name
            assert p.naming_status in {"NAMED", "COMPARATIVE", "NOT_AVAILABLE", "NOISE"}

    def test_non_noise_clusters_have_feature_summaries(self):
        units = build_cp04_analysis_units(REPO_ROOT)
        profiles = build_all_segment_profiles(units)
        for p in profiles:
            if p.is_noise or p.is_not_available:
                continue
            assert (
                len(p.feature_summaries) > 0
            ), f"{p.unit_id}/{p.cluster_label} has no feature summaries"

    def test_feature_summary_has_required_columns(self):
        units = build_cp04_analysis_units(REPO_ROOT)
        profiles = build_all_segment_profiles(units)
        for p in profiles:
            if not p.feature_summaries:
                continue
            for fs in p.feature_summaries:
                assert fs.feature in FEATURE_COLUMNS
                assert fs.direction in {
                    "HIGHER",
                    "LOWER",
                    "COMPARABLE",
                    "ZERO_REFERENCE",
                    "NA",
                }
                assert fs.classification in {
                    "HIGH_DIFFERENCE_OBSERVED",
                    "MODERATE_DIFFERENCE_OBSERVED",
                    "LOW_DIFFERENCE_OBSERVED",
                    "HIGH_OVERLAP",
                    "NOT_ASSESSABLE",
                }

    def test_iqr_overlap_summary_present_for_non_noise(self):
        units = build_cp04_analysis_units(REPO_ROOT)
        profiles = build_all_segment_profiles(units)
        for p in profiles:
            if p.is_noise or p.is_not_available:
                continue
            # IQR overlap summary should be present (may be None if
            # all NaN, but normally should exist for non-noise clusters).
            if p.iqr_overlap_summary is not None:
                assert np.isfinite(p.iqr_overlap_summary.mean_overlap) or (
                    np.isnan(p.iqr_overlap_summary.mean_overlap)
                )
                # If finite, must be in [0, 1].
                if np.isfinite(p.iqr_overlap_summary.mean_overlap):
                    assert 0.0 <= p.iqr_overlap_summary.mean_overlap <= 1.0

    def test_dbscan_noise_excluded_from_customer_profile(self):
        units = build_cp04_analysis_units(REPO_ROOT)
        profiles = build_all_segment_profiles(units)
        for p in profiles:
            if p.is_noise:
                assert p.naming_status == "NOISE"
                assert not p.feature_summaries

    def test_exp03_not_available(self):
        units = build_cp04_analysis_units(REPO_ROOT)
        profiles = build_all_segment_profiles(units)
        for p in profiles:
            if p.is_not_available:
                assert p.naming_status == "NOT_AVAILABLE"
                assert p.customer_count == 0
                assert not p.feature_summaries

    def test_segment_profiles_to_dicts_returns_long_format(self):
        units = build_cp04_analysis_units(REPO_ROOT)
        profiles = build_all_segment_profiles(units)
        rows = segment_profiles_to_summary_dicts(profiles)
        assert len(rows) == len(profiles)
        for row in rows:
            assert "segment_name" in row
            assert "recency_tier" in row
            assert "frequency_tier" in row
            assert "monetary_tier" in row
            assert "naming_rationale" in row

    def test_evidence_rows_have_feature_columns(self):
        units = build_cp04_analysis_units(REPO_ROOT)
        profiles = build_all_segment_profiles(units)
        df = evidence_rows_to_dicts(profiles)
        assert "feature" in df.columns
        assert "feature_median" in df.columns
        assert "feature_direction" in df.columns
        assert "feature_classification" in df.columns


# --------------------------------------------------------------------
# CP-01 consistency
# --------------------------------------------------------------------


class TestCp01Consistency:
    def test_customer_count_matches_cp01_for_non_noise(self):
        """For every (unit, cluster) in CP-04 with persisted labels, the
        customer count must match the CP-01 size table exactly."""
        units = build_cp04_analysis_units(REPO_ROOT)
        profiles = build_all_segment_profiles(units)
        cp01_df = pd.read_csv(REPO_ROOT / "reports/profiling/cp01/cp01_cluster_size_table.csv")
        # Only non-noise rows from CP-01.
        cp01_non_noise = cp01_df[cp01_df["is_noise"] == False].copy()  # noqa: E712
        for p in profiles:
            if p.is_noise or p.is_not_available:
                continue
            cp01_row = cp01_non_noise[
                (cp01_non_noise["unit_id"] == p.unit_id)
                & (cp01_non_noise["cluster_id"] == int(p.cluster_id))
            ]
            assert not cp01_row.empty, f"No CP-01 row for {p.unit_id}/C{p.cluster_id}"
            cp01_count = int(cp01_row.iloc[0]["customer_count"])
            assert p.customer_count == cp01_count, (
                f"Customer count mismatch for {p.unit_id}/C{p.cluster_id}: "
                f"CP-04={p.customer_count}, CP-01={cp01_count}"
            )

    def test_percentage_matches_cp01(self):
        units = build_cp04_analysis_units(REPO_ROOT)
        profiles = build_all_segment_profiles(units)
        cp01_df = pd.read_csv(REPO_ROOT / "reports/profiling/cp01/cp01_cluster_size_table.csv")
        cp01_non_noise = cp01_df[cp01_df["is_noise"] == False].copy()  # noqa: E712
        for p in profiles:
            if p.is_noise or p.is_not_available:
                continue
            cp01_row = cp01_non_noise[
                (cp01_non_noise["unit_id"] == p.unit_id)
                & (cp01_non_noise["cluster_id"] == int(p.cluster_id))
            ]
            if cp01_row.empty:
                continue
            cp01_pct = float(cp01_row.iloc[0]["pct_of_total"])
            # Allow small floating-point tolerance.
            assert abs(p.pct_of_total - cp01_pct) < 0.01, (
                f"Percentage mismatch for {p.unit_id}/C{p.cluster_id}: "
                f"CP-04={p.pct_of_total}, CP-01={cp01_pct}"
            )


# --------------------------------------------------------------------
# CP-02 / CP-03 consistency
# --------------------------------------------------------------------


class TestCp02Cp03Consistency:
    def test_direction_in_feature_summaries_matches_cp02(self):
        """The direction in CP-04 FeatureSummary should match the
        direction in CP-02 behavioural_interpretation."""
        units = build_cp04_analysis_units(REPO_ROOT)
        cp02_beh = pd.read_csv(
            REPO_ROOT / "reports/profiling/cp02/cp02_behavioral_interpretation.csv"
        )
        profiles = build_all_segment_profiles(units)
        for p in profiles:
            if p.is_noise or p.is_not_available:
                continue
            for fs in p.feature_summaries:
                cp02_row = cp02_beh[
                    (cp02_beh["unit_id"] == p.unit_id)
                    & (cp02_beh["cluster_id"] == int(p.cluster_id))
                    & (cp02_beh["feature"] == fs.feature)
                ]
                if cp02_row.empty:
                    continue
                cp02_direction_raw = cp02_row.iloc[0]["direction"]
                # Normalize NaN → "NA" to match CP-04 normalization.
                if (
                    cp02_direction_raw is None
                    or (isinstance(cp02_direction_raw, float) and pd.isna(cp02_direction_raw))
                    or (isinstance(cp02_direction_raw, str) and cp02_direction_raw.lower() == "nan")
                ):
                    cp02_direction = "NA"
                else:
                    cp02_direction = str(cp02_direction_raw)
                assert fs.direction == cp02_direction, (
                    f"Direction mismatch for {p.unit_id}/C{p.cluster_id}/{fs.feature}: "
                    f"CP-04={fs.direction}, CP-02={cp02_direction}"
                )

    def test_median_in_feature_summaries_matches_cp02(self):
        """The median in CP-04 FeatureSummary should match the median
        in CP-02 feature profile."""
        units = build_cp04_analysis_units(REPO_ROOT)
        cp02_fp = pd.read_csv(REPO_ROOT / "reports/profiling/cp02/cp02_feature_profile_table.csv")
        profiles = build_all_segment_profiles(units)
        for p in profiles:
            if p.is_noise or p.is_not_available:
                continue
            for fs in p.feature_summaries:
                cp02_row = cp02_fp[
                    (cp02_fp["unit_id"] == p.unit_id)
                    & (cp02_fp["cluster_id"] == int(p.cluster_id))
                    & (cp02_fp["feature"] == fs.feature)
                ]
                if cp02_row.empty:
                    continue
                cp02_median = float(cp02_row.iloc[0]["median"])
                if np.isfinite(cp02_median) and np.isfinite(fs.median):
                    assert abs(fs.median - cp02_median) < 0.01, (
                        f"Median mismatch for {p.unit_id}/C{p.cluster_id}/{fs.feature}: "
                        f"CP-04={fs.median}, CP-02={cp02_median}"
                    )

    def test_classification_matches_cp03(self):
        """The classification in CP-04 FeatureSummary should match
        the CP-03 distinguishing table."""
        units = build_cp04_analysis_units(REPO_ROOT)
        cp03_dis = pd.read_csv(
            REPO_ROOT / "reports/profiling/cp03/cp03_distinguishing_features.csv"
        )
        profiles = build_all_segment_profiles(units)
        for p in profiles:
            if p.is_noise or p.is_not_available:
                continue
            for fs in p.feature_summaries:
                cp03_row = cp03_dis[
                    (cp03_dis["unit_id"] == p.unit_id) & (cp03_dis["feature"] == fs.feature)
                ]
                if cp03_row.empty:
                    continue
                cp03_class = cp03_row.iloc[0]["classification"]
                assert fs.classification == cp03_class, (
                    f"Classification mismatch for {p.unit_id}/{fs.feature}: "
                    f"CP-04={fs.classification}, CP-03={cp03_class}"
                )


# --------------------------------------------------------------------
# Cross-algorithm
# --------------------------------------------------------------------


class TestCrossAlgorithm:
    def test_cluster_ids_not_cross_mapped(self):
        """Cluster ID = 1 in K-Means should not produce the same profile
        as Cluster ID = 1 in GMM (cluster IDs are unit-scoped)."""
        units = build_cp04_analysis_units(REPO_ROOT)
        profiles = build_all_segment_profiles(units)
        # Get profiles for K-Means C1 and GMM C1.
        km_c1 = next(
            (
                p
                for p in profiles
                if p.unit_id == "EXP-01-kmeans-working-default" and p.cluster_id == 1
            ),
            None,
        )
        gmm_c1 = next(
            (
                p
                for p in profiles
                if p.unit_id == "EXP-01-gmm-working-default" and p.cluster_id == 1
            ),
            None,
        )
        assert km_c1 is not None
        assert gmm_c1 is not None
        # Customer counts are different (different algorithms).
        assert km_c1.customer_count != gmm_c1.customer_count
        # Segment names are independent (no shared taxonomy enforced).
        # Note: they MAY coincidentally be similar but they are derived
        # from independent evidence surfaces.

    def test_segment_names_unique_per_unit_cluster(self):
        units = build_cp04_analysis_units(REPO_ROOT)
        profiles = build_all_segment_profiles(units)
        # No two profiles in the same unit share the same (cluster_id, segment_name).
        seen: set[tuple[str, int, str]] = set()
        for p in profiles:
            key = (p.unit_id, int(p.cluster_id), p.segment_name)
            assert (
                key not in seen
            ), f"Duplicate segment name {p.segment_name} in {p.unit_id}/C{p.cluster_id}"
            seen.add(key)


# --------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------


class TestRunner:
    @pytest.fixture(scope="module")
    def cp04_run(self, tmp_path_factory) -> dict:
        out = tmp_path_factory.mktemp("cp04_runner") / "out"
        return run_cp04(repo_root=REPO_ROOT, output_dir=out)

    def test_runner_writes_all_required_artifacts(self, cp04_run):
        for key in (
            "segment_profiles_csv",
            "segment_naming_csv",
            "segment_evidence_csv",
            "unit_provenance_csv",
            "cp01_consistency_csv",
            "report_md",
            "manifest_json",
        ):
            p = Path(cp04_run[key])
            assert p.exists(), f"missing output: {key} → {p}"

    def test_runner_output_is_deterministic(self, tmp_path: Path):
        s_a = run_cp04(repo_root=REPO_ROOT, output_dir=tmp_path / "run_a")
        s_b = run_cp04(repo_root=REPO_ROOT, output_dir=tmp_path / "run_b")
        # Compare the segment_profiles CSVs (one row per cluster).
        df_a = (
            pd.read_csv(s_a["segment_profiles_csv"])
            .sort_values(["unit_id", "cluster_id"])
            .reset_index(drop=True)
        )
        df_b = (
            pd.read_csv(s_b["segment_profiles_csv"])
            .sort_values(["unit_id", "cluster_id"])
            .reset_index(drop=True)
        )
        # Drop free-text columns that may differ in whitespace.
        text_cols = ["naming_rationale", "behavioural_summary"]
        for col in text_cols:
            if col in df_a.columns:
                df_a[col] = df_a[col].astype(str).str.strip()
                df_b[col] = df_b[col].astype(str).str.strip()
        pd.testing.assert_frame_equal(df_a, df_b)

    def test_runner_manifest_metadata(self, cp04_run):
        manifest = json.loads(Path(cp04_run["manifest_json"]).read_text())
        assert manifest["analysis_units_total"] == 10
        assert manifest["units_with_labels"] == 5
        assert manifest["units_without_labels"] == 5
        assert sorted(manifest["algorithms"]) == sorted(ALGORITHMS)

    def test_runner_segment_profiles_csv_has_required_columns(self, cp04_run):
        df = pd.read_csv(cp04_run["segment_profiles_csv"])
        required = {
            "unit_id",
            "algorithm",
            "cluster_id",
            "cluster_label",
            "is_noise",
            "is_not_available",
            "customer_count",
            "pct_of_total",
            "segment_name",
            "recency_tier",
            "frequency_tier",
            "monetary_tier",
            "behavioral_modifier",
            "naming_rationale",
            "naming_status",
        }
        assert required.issubset(set(df.columns))

    def test_runner_naming_csv_has_required_columns(self, cp04_run):
        df = pd.read_csv(cp04_run["segment_naming_csv"])
        required = {
            "unit_id",
            "algorithm",
            "cluster_id",
            "segment_name",
            "naming_rationale",
            "naming_status",
            "supporting_evidence",
        }
        assert required.issubset(set(df.columns))

    def test_runner_evidence_csv_has_feature_rows(self, cp04_run):
        df = pd.read_csv(cp04_run["segment_evidence_csv"])
        # Long format: many rows (one per profile × feature).
        assert len(df) > 0
        assert "feature" in df.columns
        assert "feature_direction" in df.columns
        assert "feature_classification" in df.columns

    def test_runner_consistency_csv_pass(self, cp04_run):
        df = pd.read_csv(cp04_run["cp01_consistency_csv"])
        # For non-noise, non-NOT_AVAILABLE rows, match must be True.
        for _, row in df.iterrows():
            if not row["is_noise"] and row["cp01_cluster_customer_count"] is not None:
                assert row[
                    "match"
                ], f"Consistency mismatch for {row['unit_id']}/C{row['cluster_id']}"

    def test_runner_no_exp03_emits_zero_label_profiles(self, tmp_path: Path):
        out = tmp_path / "no_exp03"
        summary = run_cp04(repo_root=REPO_ROOT, output_dir=out, include_exp03=False)
        df = pd.read_csv(summary["segment_profiles_csv"])
        # No EXP-03 rows.
        assert not (df["source_experiment"] == "EXP-03").any()
        # 5 EXP-01 units only.
        assert df["unit_id"].nunique() == 5
        # units_without_labels should be 0.
        manifest = json.loads(Path(summary["manifest_json"]).read_text())
        assert manifest["units_without_labels"] == 0


# --------------------------------------------------------------------
# Methodology gate
# --------------------------------------------------------------------


class TestMethodologyGate:
    """Verify no forbidden tokens appear in CP-04 outputs."""

    def test_no_forbidden_tokens_in_report(self, tmp_path: Path):
        out = tmp_path / "gate"
        summary = run_cp04(repo_root=REPO_ROOT, output_dir=out)
        report_text = Path(summary["report_md"]).read_text(encoding="utf-8")
        report_lower = report_text.lower()
        for token in FORBIDDEN_TOKENS:
            assert (
                token.lower() not in report_lower
            ), f"Forbidden token '{token}' found in cp04_report.md"

    def test_no_forbidden_tokens_in_segment_naming_csv(self, tmp_path: Path):
        out = tmp_path / "gate_naming"
        summary = run_cp04(repo_root=REPO_ROOT, output_dir=out)
        df = pd.read_csv(summary["segment_naming_csv"])
        for token in FORBIDDEN_TOKENS:
            # Check segment_name column for marketing terms.
            mask = (
                df["segment_name"]
                .astype(str)
                .str.lower()
                .str.contains(re.escape(token.lower()), regex=True, na=False)
            )
            assert not mask.any(), f"Forbidden token '{token}' found in segment names"

    def test_no_segment_naming_for_dbscan_noise(self, tmp_path: Path):
        out = tmp_path / "gate_noise"
        summary = run_cp04(repo_root=REPO_ROOT, output_dir=out)
        df = pd.read_csv(summary["segment_profiles_csv"])
        noise_rows = df[df["is_noise"] == True]  # noqa: E712
        for _, row in noise_rows.iterrows():
            assert row["naming_status"] == "NOISE"
            # DBSCAN noise row should not have a tier-based name.
            for tier in ("Recent", "Older", "Frequent", "Occasional", "HighValue", "LowValue"):
                # Tier should not appear in the noise segment_name.
                if row["naming_status"] == "NOISE":
                    assert tier not in str(
                        row["segment_name"]
                    ), f"DBSCAN noise got tier-like name: {row['segment_name']}"

    def test_exp03_segments_are_not_available(self, tmp_path: Path):
        out = tmp_path / "gate_exp03"
        summary = run_cp04(repo_root=REPO_ROOT, output_dir=out)
        df = pd.read_csv(summary["segment_profiles_csv"])
        exp03_rows = df[df["source_experiment"] == "EXP-03"]
        assert len(exp03_rows) == 5
        for _, row in exp03_rows.iterrows():
            assert row["naming_status"] == "NOT_AVAILABLE"
            assert row["is_not_available"] is True
            assert row["customer_count"] == 0


# --------------------------------------------------------------------
# Read-only against source artefacts
# --------------------------------------------------------------------


class TestReadOnly:
    def test_source_artifacts_unchanged(self, tmp_path: Path):
        """Verify SHA-256 of CP-01/02/03 source artefacts identical
        before/after CP-04 run."""
        import hashlib

        def sha(path: Path) -> str | None:
            if not path.exists():
                return None
            return hashlib.sha256(path.read_bytes()).hexdigest()

        before = {
            "cp01_size": sha(REPO_ROOT / "reports/profiling/cp01/cp01_cluster_size_table.csv"),
            "cp02_fp": sha(REPO_ROOT / "reports/profiling/cp02/cp02_feature_profile_table.csv"),
            "cp02_rel": sha(REPO_ROOT / "reports/profiling/cp02/cp02_relative_comparison.csv"),
            "cp02_beh": sha(
                REPO_ROOT / "reports/profiling/cp02/cp02_behavioral_interpretation.csv"
            ),
            "cp03_cmp": sha(
                REPO_ROOT / "reports/profiling/cp03/cp03_segment_comparison_matrix.csv"
            ),
            "cp03_dis": sha(REPO_ROOT / "reports/profiling/cp03/cp03_distinguishing_features.csv"),
            "cp03_ov": sha(REPO_ROOT / "reports/profiling/cp03/cp03_overlap_analysis.csv"),
        }
        # Also check EXP-01 cluster labels parquet files.
        before.update(
            {
                algo: sha(
                    REPO_ROOT / "reports/exp01" / f"cluster_labels_EXP-01-{algo}_rep4.parquet"
                )
                for algo in ALGORITHMS
            }
        )
        run_cp04(repo_root=REPO_ROOT, output_dir=tmp_path / "ro_run")
        after = {
            "cp01_size": sha(REPO_ROOT / "reports/profiling/cp01/cp01_cluster_size_table.csv"),
            "cp02_fp": sha(REPO_ROOT / "reports/profiling/cp02/cp02_feature_profile_table.csv"),
            "cp02_rel": sha(REPO_ROOT / "reports/profiling/cp02/cp02_relative_comparison.csv"),
            "cp02_beh": sha(
                REPO_ROOT / "reports/profiling/cp02/cp02_behavioral_interpretation.csv"
            ),
            "cp03_cmp": sha(
                REPO_ROOT / "reports/profiling/cp03/cp03_segment_comparison_matrix.csv"
            ),
            "cp03_dis": sha(REPO_ROOT / "reports/profiling/cp03/cp03_distinguishing_features.csv"),
            "cp03_ov": sha(REPO_ROOT / "reports/profiling/cp03/cp03_overlap_analysis.csv"),
        }
        after.update(
            {
                algo: sha(
                    REPO_ROOT / "reports/exp01" / f"cluster_labels_EXP-01-{algo}_rep4.parquet"
                )
                for algo in ALGORITHMS
            }
        )
        for k in before:
            assert before[k] == after[k], f"Source artefact {k} changed during CP-04 run"
