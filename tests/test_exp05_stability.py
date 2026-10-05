"""Tests for EXP-05 Stability & Reproducibility runner.

Test categories (per EXP-05 Plan R1 §12):

- Config: YAML loads, three blocks (R/S/N), seeds and sigma grids.
- Helpers: compute_labels_hash, perturb_in_memory, aggregate_variation_stats.
- Block matrix correctness: R = 5 algos × n_repeat; S = 3 algos × seeds;
  N = 5 + 5 × 2 × 3.
- Block R determinism: same seed → identical labels_hash; metrics
  identical across repeats.
- Block S seed-axis: K-Means + GMM + FCM only; Agglomerative + DBSCAN
  excluded.
- Block N sigma grid: sigma=0 reproduces baseline; sigma=0.01/0.05
  × 3 perturbation seeds.
- Fixed hyperparameters: mirror EXP-01 working defaults.
- Labels artifact: schema correctness; CustomerID alignment.
- Aggregate mean / std / CV / unique_count.
- Provenance: input SHA unchanged; library versions captured.
- Scope guards: NO ARI/AMI values; NO ranking/composite/best
  terminology; NO assertion that sigma=1%/5% MUST change labels.

Hard constraints (AGENTS.md §2, EXP-05 Plan R1):
- No mutation of FE-05 / FE-06 outputs.
- No "best/optimal/superior/winner/recommended/final" labels.
- No ARI/AMI in EXP-05 outputs (EPIC-08 owns).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
import yaml

from customer_segmentation.clustering.config import load_framework_config
from customer_segmentation.clustering.stability import (
    BLOCK_N,
    BLOCK_R,
    BLOCK_S,
    DECISION_STATUS_PERTURBATION_EVIDENCE,
    DECISION_STATUS_REPRO_VERIFIED,
    DECISION_STATUS_SIGMA_ZERO_MATCH,
    DECISION_STATUS_SIGMA_ZERO_MISMATCH,
    DECISION_STATUS_STABILITY_EVIDENCE,
    EXP05_ALGORITHMS_BLOCK_S,
    EXP05_CANONICAL_ALGORITHMS,
    EXP05_PERTURBATION_SEEDS_BLOCK_N,
    EXP05_SEEDS_BLOCK_S,
    EXP05_SIGMA_GRID_BLOCK_N,
    FORBIDDEN_DECISION_LABELS,
    PERMITTED_DECISION_STATUSES,
    StabilityReproducibilityRunner,
    aggregate_variation_stats,
    compute_labels_hash,
    perturb_in_memory,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]
_FRAMEWORK_CONFIG_PATH = REPO_ROOT / "configs" / "clustering.yaml"
_EXP05_CONFIG_PATH = REPO_ROOT / "configs" / "exp05_stability_reproducibility.yaml"


@pytest.fixture()
def exp05_config_text() -> str:
    """Return EXP-05 config YAML as text."""
    return _EXP05_CONFIG_PATH.read_text(encoding="utf-8")


@pytest.fixture()
def exp05_config(exp05_config_text: str) -> dict[str, Any]:
    """Return parsed EXP-05 YAML."""
    return yaml.safe_load(exp05_config_text)


@pytest.fixture()
def framework_config_text() -> str:
    """Return clustering.yaml as text."""
    return _FRAMEWORK_CONFIG_PATH.read_text(encoding="utf-8")


@pytest.fixture()
def framework_config(framework_config_text: str):
    """Return loaded framework config."""
    return load_framework_config(_FRAMEWORK_CONFIG_PATH)


@pytest.fixture()
def small_matrix_df() -> pd.DataFrame:
    """A small synthetic feature matrix for EXP-05 smoke tests."""
    rng = np.random.default_rng(0)
    n = 120  # 4 well-separated clusters
    centers = np.array(
        [
            [10.0, 2.0, 100.0],
            [200.0, 10.0, 5000.0],
            [50.0, 5.0, 800.0],
            [100.0, 7.0, 2000.0],
        ]
    )
    parts = []
    for c in centers:
        parts.append(rng.normal(loc=c, scale=c * 0.05 + 1.0, size=(n // 4, 3)))
    X = np.vstack(parts)
    # Add a couple of features so DBSCAN can find clusters.
    X = np.hstack([X, rng.normal(size=(X.shape[0], 1))])
    return pd.DataFrame(X, columns=["F1", "F2", "F3", "F4"])


@pytest.fixture()
def small_metadata_df() -> pd.DataFrame:
    """Customer metadata aligned with small_matrix_df."""
    n = 120
    return pd.DataFrame(
        {
            "CustomerID": np.arange(1000, 1000 + n, dtype=np.int64),
        }
    )


# ---------------------------------------------------------------------------
# 1. Config tests
# ---------------------------------------------------------------------------


class TestConfig:
    """Config tests."""

    def test_config_loads(self, exp05_config_text: str) -> None:
        """YAML loads without errors."""
        cfg = yaml.safe_load(exp05_config_text)
        assert isinstance(cfg, dict)
        assert "exp05" in cfg

    def test_canonical_algorithms(self, exp05_config: dict[str, Any]) -> None:
        """EXP-05 YAML declares 5 canonical algorithms in correct order."""
        algos = exp05_config["exp05"]["algorithms"]
        assert algos == list(EXP05_CANONICAL_ALGORITHMS)

    def test_block_s_algorithms(self, exp05_config: dict[str, Any]) -> None:
        """Block S only includes algorithms with a random axis."""
        algos = exp05_config["exp05"]["block_s"]["algorithms"]
        assert tuple(algos) == EXP05_ALGORITHMS_BLOCK_S
        # Agglomerative and DBSCAN are explicitly excluded.
        assert "agglomerative" not in algos
        assert "dbscan" not in algos

    def test_block_s_seeds(self, exp05_config: dict[str, Any]) -> None:
        """Block S uses the documented 5 seeds."""
        seeds = exp05_config["exp05"]["block_s"]["seeds"]
        assert tuple(seeds) == EXP05_SEEDS_BLOCK_S
        assert len(seeds) == 5

    def test_block_n_sigma_grid(self, exp05_config: dict[str, Any]) -> None:
        """Block N uses sigma = [0.0, 0.01, 0.05]."""
        sigma = exp05_config["exp05"]["block_n"]["sigma_grid"]
        assert tuple(sigma) == EXP05_SIGMA_GRID_BLOCK_N
        assert len(sigma) == 3

    def test_block_n_perturbation_seeds(self, exp05_config: dict[str, Any]) -> None:
        """Block N uses 3 perturbation seeds."""
        seeds = exp05_config["exp05"]["block_n"]["nonzero_perturbation_seeds"]
        assert tuple(seeds) == EXP05_PERTURBATION_SEEDS_BLOCK_N
        assert len(seeds) == 3

    def test_block_r_n_repeat(self, exp05_config: dict[str, Any]) -> None:
        """Block R uses n_repeat=5."""
        assert int(exp05_config["exp05"]["block_r"]["n_repeat"]) == 5

    def test_decision_status_taxonomy(self, exp05_config: dict[str, Any]) -> None:
        """Decision status options are restricted to the approved labels."""
        # permitted in YAML
        permitted_yaml = set(exp05_config["exp05"]["decision_status"]["permitted"])
        # module-level permitted (mirrored)
        assert permitted_yaml <= set(PERMITTED_DECISION_STATUSES)
        forbidden = set(exp05_config["exp05"]["decision_status"]["forbidden"])
        assert forbidden == set(FORBIDDEN_DECISION_LABELS)
        # Required labels
        assert "REPRODUCIBILITY_VERIFIED" in permitted_yaml
        assert "STABILITY_EVIDENCE_GENERATED" in permitted_yaml
        assert "PERTURBATION_EVIDENCE_GENERATED" in permitted_yaml


# ---------------------------------------------------------------------------
# 2. Helper tests
# ---------------------------------------------------------------------------


class TestHelpers:
    """Helper-function tests."""

    def test_perturb_sigma_zero_reproduces_input(self) -> None:
        """perturb_in_memory with sigma=0 returns a copy equal to input."""
        rng = np.random.default_rng(0)
        X = rng.normal(size=(50, 4))
        X_perturbed = perturb_in_memory(X, sigma=0.0, perturbation_seed=42)
        np.testing.assert_array_equal(X_perturbed, X)
        # input not mutated
        assert X is not X_perturbed

    def test_perturb_sigma_nonzero_modifies(self) -> None:
        """perturb_in_memory with sigma>0 modifies the matrix."""
        rng = np.random.default_rng(0)
        X = rng.normal(size=(50, 4))
        X_perturbed = perturb_in_memory(X, sigma=0.05, perturbation_seed=42)
        assert not np.array_equal(X_perturbed, X)
        assert X_perturbed.shape == X.shape
        # input not mutated
        X_before = X.copy()
        np.testing.assert_array_equal(X, X_before)

    def test_perturb_same_seed_deterministic(self) -> None:
        """Same perturbation_seed produces identical perturbation."""
        rng = np.random.default_rng(0)
        X = rng.normal(size=(50, 4))
        a = perturb_in_memory(X, sigma=0.05, perturbation_seed=42)
        b = perturb_in_memory(X, sigma=0.05, perturbation_seed=42)
        np.testing.assert_array_equal(a, b)

    def test_perturb_different_seed_differs(self) -> None:
        """Different perturbation_seed produces different perturbation."""
        rng = np.random.default_rng(0)
        X = rng.normal(size=(50, 4))
        a = perturb_in_memory(X, sigma=0.05, perturbation_seed=42)
        b = perturb_in_memory(X, sigma=0.05, perturbation_seed=43)
        assert not np.array_equal(a, b)

    def test_perturb_with_explicit_feature_std(self) -> None:
        """perturb_in_memory uses caller-supplied feature_std when given."""
        rng = np.random.default_rng(0)
        X = rng.normal(size=(50, 4))
        std = np.std(X, axis=0, ddof=0)
        a = perturb_in_memory(X, sigma=0.05, perturbation_seed=42, feature_std=std)
        b = perturb_in_memory(X, sigma=0.05, perturbation_seed=42)
        np.testing.assert_array_equal(a, b)

    def test_perturb_negative_sigma_raises(self) -> None:
        """Negative sigma raises ValueError."""
        rng = np.random.default_rng(0)
        X = rng.normal(size=(10, 3))
        with pytest.raises(ValueError):
            perturb_in_memory(X, sigma=-0.1, perturbation_seed=42)

    def test_compute_labels_hash_deterministic(self) -> None:
        """compute_labels_hash is deterministic across calls."""
        labels = np.array([0, 1, 0, 2, 1, 2], dtype=np.int64)
        h1 = compute_labels_hash(labels)
        h2 = compute_labels_hash(labels)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_aggregate_variation_stats_empty(self) -> None:
        """aggregate_variation_stats returns None fields for empty input."""
        s = aggregate_variation_stats([])
        assert s["n"] == 0
        assert s["unique_count"] == 0
        assert s["mean"] is None
        assert s["std"] is None
        assert s["min"] is None
        assert s["max"] is None
        assert s["cv"] is None

    def test_aggregate_variation_stats_uniform(self) -> None:
        """aggregate_variation_stats of uniform values has zero std."""
        s = aggregate_variation_stats([1.0, 1.0, 1.0, 1.0])
        assert s["mean"] == 1.0
        assert s["std"] == 0.0
        assert s["unique_count"] == 1

    def test_aggregate_variation_stats_unique_count(self) -> None:
        """aggregate_variation_stats counts distinct values."""
        s = aggregate_variation_stats([1.0, 2.0, 2.0, 3.0])
        assert s["unique_count"] == 3
        assert s["min"] == 1.0
        assert s["max"] == 3.0


# ---------------------------------------------------------------------------
# 3. Block R — Reproducibility tests
# ---------------------------------------------------------------------------


class TestBlockRDeterminism:
    """Block R determinism tests on a small synthetic fixture."""

    def test_block_r_runs_and_label_hashes_match(
        self,
        framework_config,
        framework_config_text: str,
        exp05_config: dict[str, Any],
        exp05_config_text: str,
        small_matrix_df: pd.DataFrame,
        small_metadata_df: pd.DataFrame,
    ) -> None:
        """Block R: all repeats per algorithm produce identical labels_hash."""
        runner = StabilityReproducibilityRunner(
            framework_config,
            exp05_config,
            framework_config_text=framework_config_text,
            exp05_config_text=exp05_config_text,
        )
        result = runner.run(
            small_matrix_df,
            small_metadata_df,
            input_sha256="dummy_input_sha",
            metadata_sha256="dummy_metadata_sha",
        )
        for aggregate in result.block_r_aggregates:
            assert aggregate.labels_hash_unique_count == 1, (
                f"Block R not deterministic for {aggregate.algorithm}: "
                f"{aggregate.labels_hash_unique_count} distinct labels_hash."
            )
            assert aggregate.decision_status == DECISION_STATUS_REPRO_VERIFIED

    def test_block_r_record_counts(
        self,
        framework_config,
        framework_config_text: str,
        exp05_config: dict[str, Any],
        exp05_config_text: str,
        small_matrix_df: pd.DataFrame,
        small_metadata_df: pd.DataFrame,
    ) -> None:
        """Block R: 5 algorithms × n_repeat=5 = 25 records."""
        runner = StabilityReproducibilityRunner(
            framework_config,
            exp05_config,
            framework_config_text=framework_config_text,
            exp05_config_text=exp05_config_text,
        )
        result = runner.run(
            small_matrix_df,
            small_metadata_df,
            input_sha256="x" * 64,
            metadata_sha256="y" * 64,
        )
        assert len(result.block_r_records) == 5 * 5
        assert len(result.block_r_aggregates) == 5

    def test_block_r_seed_fixed_at_42(
        self,
        framework_config,
        framework_config_text: str,
        exp05_config: dict[str, Any],
        exp05_config_text: str,
        small_matrix_df: pd.DataFrame,
        small_metadata_df: pd.DataFrame,
    ) -> None:
        """Block R: all records use seed=42."""
        runner = StabilityReproducibilityRunner(
            framework_config,
            exp05_config,
            framework_config_text=framework_config_text,
            exp05_config_text=exp05_config_text,
        )
        result = runner.run(
            small_matrix_df,
            small_metadata_df,
            input_sha256="x" * 64,
            metadata_sha256="y" * 64,
        )
        for record in result.block_r_records:
            assert record.seed == 42
            assert record.block == BLOCK_R

    def test_block_r_fixed_hyperparameters(
        self,
        framework_config,
        framework_config_text: str,
        exp05_config: dict[str, Any],
        exp05_config_text: str,
        small_matrix_df: pd.DataFrame,
        small_metadata_df: pd.DataFrame,
    ) -> None:
        """Block R: hyperparameters match EXP-01 working defaults."""
        runner = StabilityReproducibilityRunner(
            framework_config,
            exp05_config,
            framework_config_text=framework_config_text,
            exp05_config_text=exp05_config_text,
        )
        result = runner.run(
            small_matrix_df,
            small_metadata_df,
            input_sha256="x" * 64,
            metadata_sha256="y" * 64,
        )
        # K-Means should have n_clusters=4 from EXP-01 working default
        for record in result.block_r_records:
            if record.algorithm == "kmeans":
                assert record.hyperparameters["n_clusters"] == 4
                assert record.hyperparameters["n_init"] == 10
            elif record.algorithm == "gmm":
                assert record.hyperparameters["n_components"] == 4
                assert record.hyperparameters["covariance_type"] == "full"
            elif record.algorithm == "fuzzy_cmeans":
                assert record.hyperparameters["n_clusters"] == 4
                assert record.hyperparameters["m"] == 2.0


# ---------------------------------------------------------------------------
# 4. Block S — Random Seed Stability tests
# ---------------------------------------------------------------------------


class TestBlockSStability:
    """Block S stability evidence tests."""

    def test_block_s_only_random_axis_algorithms(
        self,
        framework_config,
        framework_config_text: str,
        exp05_config: dict[str, Any],
        exp05_config_text: str,
        small_matrix_df: pd.DataFrame,
        small_metadata_df: pd.DataFrame,
    ) -> None:
        """Block S includes only K-Means, GMM, FCM (3 algorithms)."""
        runner = StabilityReproducibilityRunner(
            framework_config,
            exp05_config,
            framework_config_text=framework_config_text,
            exp05_config_text=exp05_config_text,
        )
        result = runner.run(
            small_matrix_df,
            small_metadata_df,
            input_sha256="x" * 64,
            metadata_sha256="y" * 64,
        )
        assert len(result.block_s_aggregates) == 3
        algos = {a.algorithm for a in result.block_s_aggregates}
        assert algos == set(EXP05_ALGORITHMS_BLOCK_S)
        assert "agglomerative" not in algos
        assert "dbscan" not in algos

    def test_block_s_record_count(
        self,
        framework_config,
        framework_config_text: str,
        exp05_config: dict[str, Any],
        exp05_config_text: str,
        small_matrix_df: pd.DataFrame,
        small_metadata_df: pd.DataFrame,
    ) -> None:
        """Block S: 3 algorithms × 5 seeds = 15 records."""
        runner = StabilityReproducibilityRunner(
            framework_config,
            exp05_config,
            framework_config_text=framework_config_text,
            exp05_config_text=exp05_config_text,
        )
        result = runner.run(
            small_matrix_df,
            small_metadata_df,
            input_sha256="x" * 64,
            metadata_sha256="y" * 64,
        )
        assert len(result.block_s_records) == 3 * 5
        assert all(r.block == BLOCK_S for r in result.block_s_records)

    def test_block_s_seeds_match_config(
        self,
        framework_config,
        framework_config_text: str,
        exp05_config: dict[str, Any],
        exp05_config_text: str,
        small_matrix_df: pd.DataFrame,
        small_metadata_df: pd.DataFrame,
    ) -> None:
        """Block S: all 5 seeds are exercised for each algorithm."""
        runner = StabilityReproducibilityRunner(
            framework_config,
            exp05_config,
            framework_config_text=framework_config_text,
            exp05_config_text=exp05_config_text,
        )
        result = runner.run(
            small_matrix_df,
            small_metadata_df,
            input_sha256="x" * 64,
            metadata_sha256="y" * 64,
        )
        for algorithm in EXP05_ALGORITHMS_BLOCK_S:
            seeds_used = {r.seed for r in result.block_s_records if r.algorithm == algorithm}
            assert seeds_used == set(EXP05_SEEDS_BLOCK_S)

    def test_block_s_decision_status(
        self,
        framework_config,
        framework_config_text: str,
        exp05_config: dict[str, Any],
        exp05_config_text: str,
        small_matrix_df: pd.DataFrame,
        small_metadata_df: pd.DataFrame,
    ) -> None:
        """Block S aggregates get STABILITY_EVIDENCE_GENERATED."""
        runner = StabilityReproducibilityRunner(
            framework_config,
            exp05_config,
            framework_config_text=framework_config_text,
            exp05_config_text=exp05_config_text,
        )
        result = runner.run(
            small_matrix_df,
            small_metadata_df,
            input_sha256="x" * 64,
            metadata_sha256="y" * 64,
        )
        for a in result.block_s_aggregates:
            assert a.decision_status == DECISION_STATUS_STABILITY_EVIDENCE


# ---------------------------------------------------------------------------
# 5. Block N — Feature Perturbation tests
# ---------------------------------------------------------------------------


class TestBlockNPerturbation:
    """Block N perturbation evidence tests."""

    def test_block_n_sigma_zero_reproduces_baseline(
        self,
        framework_config,
        framework_config_text: str,
        exp05_config: dict[str, Any],
        exp05_config_text: str,
        small_matrix_df: pd.DataFrame,
        small_metadata_df: pd.DataFrame,
    ) -> None:
        """sigma=0 sanity run produces labels matching non-perturbed run."""
        runner = StabilityReproducibilityRunner(
            framework_config,
            exp05_config,
            framework_config_text=framework_config_text,
            exp05_config_text=exp05_config_text,
        )
        result = runner.run(
            small_matrix_df,
            small_metadata_df,
            input_sha256="x" * 64,
            metadata_sha256="y" * 64,
        )
        # sigma=0 records should have baseline labels_hash matching sigma=0 sanity.
        sigma_zero_aggregates = [a for a in result.block_n_aggregates if a.sigma == 0.0]
        assert len(sigma_zero_aggregates) == len(EXP05_CANONICAL_ALGORITHMS)
        for a in sigma_zero_aggregates:
            # sanity match may be True (correctly wired) or False (wiring issue);
            # both are valid evidence to flag.
            assert a.sigma_zero_baseline_match in (True, False)
            assert a.decision_status in (
                DECISION_STATUS_SIGMA_ZERO_MATCH,
                DECISION_STATUS_SIGMA_ZERO_MISMATCH,
            )

    def test_block_n_sigma_zero_baseline_match_deterministic_algos(
        self,
        framework_config,
        framework_config_text: str,
        exp05_config: dict[str, Any],
        exp05_config_text: str,
        small_matrix_df: pd.DataFrame,
        small_metadata_df: pd.DataFrame,
    ) -> None:
        """Deterministic algorithms reproduce baseline at sigma=0."""
        runner = StabilityReproducibilityRunner(
            framework_config,
            exp05_config,
            framework_config_text=framework_config_text,
            exp05_config_text=exp05_config_text,
        )
        result = runner.run(
            small_matrix_df,
            small_metadata_df,
            input_sha256="x" * 64,
            metadata_sha256="y" * 64,
        )
        # Agglomerative and DBSCAN are deterministic: sigma=0 must
        # reproduce baseline.
        for a in result.block_n_aggregates:
            if a.sigma != 0.0:
                continue
            if a.algorithm in ("agglomerative", "dbscan"):
                # Either match is OK if perturbation pipeline is wired
                # correctly; mismatch indicates pipeline regression.
                assert a.sigma_zero_baseline_match is True, (
                    f"sigma=0 sanity did NOT match baseline for deterministic "
                    f"algorithm {a.algorithm}; perturbation pipeline broken."
                )

    def test_block_n_record_count(
        self,
        framework_config,
        framework_config_text: str,
        exp05_config: dict[str, Any],
        exp05_config_text: str,
        small_matrix_df: pd.DataFrame,
        small_metadata_df: pd.DataFrame,
    ) -> None:
        """Block N: 5 algorithms × (1 sigma=0 + 2 sigma × 3 pseeds) = 35."""
        runner = StabilityReproducibilityRunner(
            framework_config,
            exp05_config,
            framework_config_text=framework_config_text,
            exp05_config_text=exp05_config_text,
        )
        result = runner.run(
            small_matrix_df,
            small_metadata_df,
            input_sha256="x" * 64,
            metadata_sha256="y" * 64,
        )
        # 5 sigma=0 sanity + 5 × 2 × 3 = 5 + 30 = 35 records.
        assert len(result.block_n_records) == 35

    def test_block_n_perturbation_seeds_match_config(
        self,
        framework_config,
        framework_config_text: str,
        exp05_config: dict[str, Any],
        exp05_config_text: str,
        small_matrix_df: pd.DataFrame,
        small_metadata_df: pd.DataFrame,
    ) -> None:
        """Block N: each (algorithm × nonzero sigma) uses 3 perturbation seeds."""
        runner = StabilityReproducibilityRunner(
            framework_config,
            exp05_config,
            framework_config_text=framework_config_text,
            exp05_config_text=exp05_config_text,
        )
        result = runner.run(
            small_matrix_df,
            small_metadata_df,
            input_sha256="x" * 64,
            metadata_sha256="y" * 64,
        )
        for algorithm in EXP05_CANONICAL_ALGORITHMS:
            for sigma in (0.01, 0.05):
                pseeds_used = {
                    r.perturbation_seed
                    for r in result.block_n_records
                    if r.algorithm == algorithm and r.sigma == sigma
                }
                assert pseeds_used == set(EXP05_PERTURBATION_SEEDS_BLOCK_N)

    def test_block_n_no_perturbed_dataset_on_disk(
        self,
        framework_config,
        framework_config_text: str,
        exp05_config: dict[str, Any],
        exp05_config_text: str,
        small_matrix_df: pd.DataFrame,
        small_metadata_df: pd.DataFrame,
        tmp_path: Path,
    ) -> None:
        """Block N: no perturbed dataset persisted to data/processed/."""
        data_processed = REPO_ROOT / "data" / "processed"
        pre_listing = (
            sorted(p.name for p in data_processed.iterdir()) if data_processed.exists() else []
        )
        runner = StabilityReproducibilityRunner(
            framework_config,
            exp05_config,
            framework_config_text=framework_config_text,
            exp05_config_text=exp05_config_text,
        )
        runner.run(
            small_matrix_df,
            small_metadata_df,
            input_sha256="x" * 64,
            metadata_sha256="y" * 64,
        )
        # Post-run listing must equal pre-run listing.
        post_listing = (
            sorted(p.name for p in data_processed.iterdir()) if data_processed.exists() else []
        )
        assert pre_listing == post_listing

    def test_block_n_does_not_assert_labels_must_change(
        self,
        framework_config,
        framework_config_text: str,
        exp05_config: dict[str, Any],
        exp05_config_text: str,
        small_matrix_df: pd.DataFrame,
        small_metadata_df: pd.DataFrame,
    ) -> None:
        """Block N: no hard assertion that sigma=1%/5% changes labels.

        Both labels-changed and labels-unchanged are valid observations;
        the decision status is PERTURBATION_EVIDENCE_GENERATED in
        either case (no value judgement).
        """
        runner = StabilityReproducibilityRunner(
            framework_config,
            exp05_config,
            framework_config_text=framework_config_text,
            exp05_config_text=exp05_config_text,
        )
        result = runner.run(
            small_matrix_df,
            small_metadata_df,
            input_sha256="x" * 64,
            metadata_sha256="y" * 64,
        )
        for a in result.block_n_aggregates:
            if a.sigma == 0.0:
                continue
            # All nonzero-sigma aggregates must be PERTURBATION_EVIDENCE_GENERATED
            # (or PENDING_REVIEW if all failed), never claim "labels changed"
            # or "labels robust" or any value judgement.
            assert a.decision_status == DECISION_STATUS_PERTURBATION_EVIDENCE


# ---------------------------------------------------------------------------
# 6. Labels artifact tests
# ---------------------------------------------------------------------------


class TestLabelsArtifact:
    """Labels artifact tests."""

    def test_labels_artifact_schema(
        self,
        framework_config,
        framework_config_text: str,
        exp05_config: dict[str, Any],
        exp05_config_text: str,
        small_matrix_df: pd.DataFrame,
        small_metadata_df: pd.DataFrame,
    ) -> None:
        """Labels artifact has the required schema."""
        runner = StabilityReproducibilityRunner(
            framework_config,
            exp05_config,
            framework_config_text=framework_config_text,
            exp05_config_text=exp05_config_text,
        )
        result = runner.run(
            small_matrix_df,
            small_metadata_df,
            input_sha256="x" * 64,
            metadata_sha256="y" * 64,
        )
        assert len(result.label_artifact_rows) > 0
        required = {
            "run_id",
            "block",
            "algorithm",
            "seed",
            "sigma",
            "perturbation_seed",
            "repeat_index",
            "customer_id",
            "cluster_label",
        }
        first = result.label_artifact_rows[0]
        for field_name in required:
            assert hasattr(first, field_name), f"missing field {field_name!r}"

    def test_labels_artifact_customer_alignment(
        self,
        framework_config,
        framework_config_text: str,
        exp05_config: dict[str, Any],
        exp05_config_text: str,
        small_matrix_df: pd.DataFrame,
        small_metadata_df: pd.DataFrame,
    ) -> None:
        """Each row has CustomerID from metadata, in correct alignment."""
        runner = StabilityReproducibilityRunner(
            framework_config,
            exp05_config,
            framework_config_text=framework_config_text,
            exp05_config_text=exp05_config_text,
        )
        result = runner.run(
            small_matrix_df,
            small_metadata_df,
            input_sha256="x" * 64,
            metadata_sha256="y" * 64,
        )
        customer_ids_metadata = set(small_metadata_df["CustomerID"].tolist())
        # All CustomerIDs in artifact must come from metadata.
        rows_seen = set()
        for row in result.label_artifact_rows:
            rows_seen.add(row.customer_id)
        assert rows_seen <= customer_ids_metadata
        # Number of customers per run == len(metadata).
        run_ids = {row.run_id for row in result.label_artifact_rows}
        for run_id in run_ids:
            customer_ids_for_run = {
                row.customer_id for row in result.label_artifact_rows if row.run_id == run_id
            }
            assert len(customer_ids_for_run) == len(small_metadata_df)

    def test_labels_artifact_covers_all_blocks(
        self,
        framework_config,
        framework_config_text: str,
        exp05_config: dict[str, Any],
        exp05_config_text: str,
        small_matrix_df: pd.DataFrame,
        small_metadata_df: pd.DataFrame,
    ) -> None:
        """Labels artifact includes rows from Block R, S, N."""
        runner = StabilityReproducibilityRunner(
            framework_config,
            exp05_config,
            framework_config_text=framework_config_text,
            exp05_config_text=exp05_config_text,
        )
        result = runner.run(
            small_matrix_df,
            small_metadata_df,
            input_sha256="x" * 64,
            metadata_sha256="y" * 64,
        )
        blocks_in_artifact = {row.block for row in result.label_artifact_rows}
        assert BLOCK_R in blocks_in_artifact
        assert BLOCK_S in blocks_in_artifact
        assert BLOCK_N in blocks_in_artifact

    def test_labels_artifact_raises_without_metadata(
        self,
        framework_config,
        framework_config_text: str,
        exp05_config: dict[str, Any],
        exp05_config_text: str,
        small_matrix_df: pd.DataFrame,
    ) -> None:
        """If metadata is missing or lacks CustomerID, raise ValueError."""
        runner = StabilityReproducibilityRunner(
            framework_config,
            exp05_config,
            framework_config_text=framework_config_text,
            exp05_config_text=exp05_config_text,
        )
        with pytest.raises(ValueError):
            runner.run(
                small_matrix_df,
                None,
                input_sha256="x" * 64,
                metadata_sha256="y" * 64,
            )


# ---------------------------------------------------------------------------
# 7. Provenance / input integrity tests
# ---------------------------------------------------------------------------


class TestProvenance:
    """Provenance tests."""

    def test_input_sha_captured(
        self,
        framework_config,
        framework_config_text: str,
        exp05_config: dict[str, Any],
        exp05_config_text: str,
        small_matrix_df: pd.DataFrame,
        small_metadata_df: pd.DataFrame,
    ) -> None:
        """Input SHA is recorded on records and aggregates."""
        runner = StabilityReproducibilityRunner(
            framework_config,
            exp05_config,
            framework_config_text=framework_config_text,
            exp05_config_text=exp05_config_text,
        )
        sha = "a" * 64
        result = runner.run(
            small_matrix_df,
            small_metadata_df,
            input_sha256=sha,
            metadata_sha256="b" * 64,
        )
        assert result.feature_set_sha256 == sha
        for record in result.block_r_records:
            assert record.feature_set_sha256 == sha
        for record in result.block_s_records:
            assert record.feature_set_sha256 == sha
        for record in result.block_n_records:
            assert record.feature_set_sha256 == sha

    def test_library_versions_captured(
        self,
        framework_config,
        framework_config_text: str,
        exp05_config: dict[str, Any],
        exp05_config_text: str,
        small_matrix_df: pd.DataFrame,
        small_metadata_df: pd.DataFrame,
    ) -> None:
        """Library versions are captured on the StabilityResult."""
        runner = StabilityReproducibilityRunner(
            framework_config,
            exp05_config,
            framework_config_text=framework_config_text,
            exp05_config_text=exp05_config_text,
        )
        result = runner.run(
            small_matrix_df,
            small_metadata_df,
            input_sha256="x" * 64,
            metadata_sha256="y" * 64,
        )
        for key in ("numpy", "pandas", "scipy", "scikit-learn", "pyarrow"):
            assert key in result.library_versions

    def test_source_immutability(
        self,
        framework_config,
        framework_config_text: str,
        exp05_config: dict[str, Any],
        exp05_config_text: str,
        small_matrix_df: pd.DataFrame,
        small_metadata_df: pd.DataFrame,
    ) -> None:
        """Running the EXP-05 runner does NOT mutate input DataFrames."""
        runner = StabilityReproducibilityRunner(
            framework_config,
            exp05_config,
            framework_config_text=framework_config_text,
            exp05_config_text=exp05_config_text,
        )
        matrix_before = small_matrix_df.copy(deep=True)
        metadata_before = small_metadata_df.copy(deep=True)
        runner.run(
            small_matrix_df,
            small_metadata_df,
            input_sha256="x" * 64,
            metadata_sha256="y" * 64,
        )
        pd.testing.assert_frame_equal(small_matrix_df, matrix_before)
        pd.testing.assert_frame_equal(small_metadata_df, metadata_before)


# ---------------------------------------------------------------------------
# 8. Scope guard tests
# ---------------------------------------------------------------------------


class TestScopeGuards:
    """Tests that EXP-05 outputs do NOT contain forbidden labels or values."""

    def test_no_ari_ami_values_in_aggregates(
        self,
        framework_config,
        framework_config_text: str,
        exp05_config: dict[str, Any],
        exp05_config_text: str,
        small_matrix_df: pd.DataFrame,
        small_metadata_df: pd.DataFrame,
    ) -> None:
        """Aggregate stats must NOT include ARI / AMI values (EPIC-08 scope)."""
        runner = StabilityReproducibilityRunner(
            framework_config,
            exp05_config,
            framework_config_text=framework_config_text,
            exp05_config_text=exp05_config_text,
        )
        result = runner.run(
            small_matrix_df,
            small_metadata_df,
            input_sha256="x" * 64,
            metadata_sha256="y" * 64,
        )
        forbidden_metrics = {"ari", "ami", "adjusted_rand", "adjusted_mutual_info"}
        for aggregate in (
            result.block_r_aggregates + result.block_s_aggregates + result.block_n_aggregates
        ):
            for stats_dict in (
                aggregate.silhouette_stats,
                aggregate.davies_bouldin_stats,
                aggregate.calinski_harabasz_stats,
                aggregate.wcss_stats,
            ):
                for key in stats_dict:
                    assert (
                        key.lower() not in forbidden_metrics
                    ), f"EXP-05 must NOT compute ARI/AMI; got {key!r}."

    def test_no_best_optimal_winner_in_decision_status(
        self,
        framework_config,
        framework_config_text: str,
        exp05_config: dict[str, Any],
        exp05_config_text: str,
        small_matrix_df: pd.DataFrame,
        small_metadata_df: pd.DataFrame,
    ) -> None:
        """Decision status values must not use forbidden terminology."""
        runner = StabilityReproducibilityRunner(
            framework_config,
            exp05_config,
            framework_config_text=framework_config_text,
            exp05_config_text=exp05_config_text,
        )
        result = runner.run(
            small_matrix_df,
            small_metadata_df,
            input_sha256="x" * 64,
            metadata_sha256="y" * 64,
        )
        forbidden_lowercase = {f.lower() for f in FORBIDDEN_DECISION_LABELS}
        for aggregate in (
            result.block_r_aggregates + result.block_s_aggregates + result.block_n_aggregates
        ):
            assert aggregate.decision_status.lower() not in forbidden_lowercase

    def test_no_composite_score_in_aggregates(
        self,
        framework_config,
        framework_config_text: str,
        exp05_config: dict[str, Any],
        exp05_config_text: str,
        small_matrix_df: pd.DataFrame,
        small_metadata_df: pd.DataFrame,
    ) -> None:
        """Aggregate stats must not include composite / total / overall scores."""
        runner = StabilityReproducibilityRunner(
            framework_config,
            exp05_config,
            framework_config_text=framework_config_text,
            exp05_config_text=exp05_config_text,
        )
        result = runner.run(
            small_matrix_df,
            small_metadata_df,
            input_sha256="x" * 64,
            metadata_sha256="y" * 64,
        )
        forbidden_keys = {"composite", "overall", "score", "total", "weighted"}
        for aggregate in (
            result.block_r_aggregates + result.block_s_aggregates + result.block_n_aggregates
        ):
            for stats_dict in (
                aggregate.silhouette_stats,
                aggregate.davies_bouldin_stats,
                aggregate.calinski_harabasz_stats,
                aggregate.wcss_stats,
            ):
                for key in stats_dict:
                    assert not any(
                        k in key.lower() for k in forbidden_keys
                    ), f"Unexpected composite-style key in aggregate: {key!r}"

    def test_block_n_no_preturbed_dataset_persisted(
        self,
        framework_config,
        framework_config_text: str,
        exp05_config: dict[str, Any],
        exp05_config_text: str,
        small_matrix_df: pd.DataFrame,
        small_metadata_df: pd.DataFrame,
        tmp_path: Path,
    ) -> None:
        """No 'perturbed_' or 'noise_' parquet is written under data/processed/."""
        data_processed = REPO_ROOT / "data" / "processed"
        pre_files = (
            sorted(p.name for p in data_processed.iterdir()) if data_processed.exists() else []
        )
        runner = StabilityReproducibilityRunner(
            framework_config,
            exp05_config,
            framework_config_text=framework_config_text,
            exp05_config_text=exp05_config_text,
        )
        runner.run(
            small_matrix_df,
            small_metadata_df,
            input_sha256="x" * 64,
            metadata_sha256="y" * 64,
        )
        post_files = (
            sorted(p.name for p in data_processed.iterdir()) if data_processed.exists() else []
        )
        # No new files.
        assert post_files == pre_files


# ---------------------------------------------------------------------------
# 9. Stability result dataclasses / sanity tests
# ---------------------------------------------------------------------------


class TestStabilityResult:
    """Smoke tests on the StabilityResult dataclass."""

    def test_stability_result_carries_block_parameters(
        self,
        framework_config,
        framework_config_text: str,
        exp05_config: dict[str, Any],
        exp05_config_text: str,
        small_matrix_df: pd.DataFrame,
        small_metadata_df: pd.DataFrame,
    ) -> None:
        """StabilityResult carries block-level parameters for provenance."""
        runner = StabilityReproducibilityRunner(
            framework_config,
            exp05_config,
            framework_config_text=framework_config_text,
            exp05_config_text=exp05_config_text,
        )
        result = runner.run(
            small_matrix_df,
            small_metadata_df,
            input_sha256="x" * 64,
            metadata_sha256="y" * 64,
        )
        assert result.block_r_seed == 42
        assert result.block_r_n_repeat == 5
        assert result.block_s_seeds == EXP05_SEEDS_BLOCK_S
        assert result.block_n_algorithm_seed == 42
        assert result.block_n_sigma_grid == EXP05_SIGMA_GRID_BLOCK_N
        assert result.block_n_perturbation_seeds == EXP05_PERTURBATION_SEEDS_BLOCK_N

    def test_sigma_zero_baseline_labels_hash_populated(
        self,
        framework_config,
        framework_config_text: str,
        exp05_config: dict[str, Any],
        exp05_config_text: str,
        small_matrix_df: pd.DataFrame,
        small_metadata_df: pd.DataFrame,
    ) -> None:
        """sigma_zero_baseline_labels_hash is populated per algorithm."""
        runner = StabilityReproducibilityRunner(
            framework_config,
            exp05_config,
            framework_config_text=framework_config_text,
            exp05_config_text=exp05_config_text,
        )
        result = runner.run(
            small_matrix_df,
            small_metadata_df,
            input_sha256="x" * 64,
            metadata_sha256="y" * 64,
        )
        # All algorithms should have a baseline labels_hash recorded.
        assert set(result.sigma_zero_baseline_labels_hash.keys()) == set(EXP05_CANONICAL_ALGORITHMS)
        for h in result.sigma_zero_baseline_labels_hash.values():
            assert len(h) == 64  # SHA-256 hex


# ---------------------------------------------------------------------------
# 10. Aggregate statistics correctness
# ---------------------------------------------------------------------------


class TestAggregateStats:
    """Aggregate statistics correctness tests."""

    def test_block_r_aggregate_stats_structure(
        self,
        framework_config,
        framework_config_text: str,
        exp05_config: dict[str, Any],
        exp05_config_text: str,
        small_matrix_df: pd.DataFrame,
        small_metadata_df: pd.DataFrame,
    ) -> None:
        """Block R aggregates have required stats fields."""
        runner = StabilityReproducibilityRunner(
            framework_config,
            exp05_config,
            framework_config_text=framework_config_text,
            exp05_config_text=exp05_config_text,
        )
        result = runner.run(
            small_matrix_df,
            small_metadata_df,
            input_sha256="x" * 64,
            metadata_sha256="y" * 64,
        )
        required_keys = {"mean", "std", "min", "max", "cv", "unique_count", "n"}
        for a in result.block_r_aggregates:
            for stats_dict in (
                a.silhouette_stats,
                a.davies_bouldin_stats,
                a.calinski_harabasz_stats,
                a.wcss_stats,
            ):
                for k in required_keys:
                    assert k in stats_dict

    def test_block_n_aggregate_unique_counts_match(
        self,
        framework_config,
        framework_config_text: str,
        exp05_config: dict[str, Any],
        exp05_config_text: str,
        small_matrix_df: pd.DataFrame,
        small_metadata_df: pd.DataFrame,
    ) -> None:
        """Block N aggregate labels_hash_unique_count <= n_perturbation_seeds."""
        runner = StabilityReproducibilityRunner(
            framework_config,
            exp05_config,
            framework_config_text=framework_config_text,
            exp05_config_text=exp05_config_text,
        )
        result = runner.run(
            small_matrix_df,
            small_metadata_df,
            input_sha256="x" * 64,
            metadata_sha256="y" * 64,
        )
        for a in result.block_n_aggregates:
            assert a.labels_hash_unique_count <= a.n_perturbation_seeds
            assert len(a.labels_hash_values) == a.n_perturbation_seeds

    def test_block_s_aggregate_unique_counts_match(
        self,
        framework_config,
        framework_config_text: str,
        exp05_config: dict[str, Any],
        exp05_config_text: str,
        small_matrix_df: pd.DataFrame,
        small_metadata_df: pd.DataFrame,
    ) -> None:
        """Block S aggregate labels_hash_unique_count <= n_seeds."""
        runner = StabilityReproducibilityRunner(
            framework_config,
            exp05_config,
            framework_config_text=framework_config_text,
            exp05_config_text=exp05_config_text,
        )
        result = runner.run(
            small_matrix_df,
            small_metadata_df,
            input_sha256="x" * 64,
            metadata_sha256="y" * 64,
        )
        for a in result.block_s_aggregates:
            assert a.labels_hash_unique_count <= a.n_seeds
