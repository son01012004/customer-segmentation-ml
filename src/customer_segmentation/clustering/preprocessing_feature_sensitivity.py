"""Preprocessing & Feature Set Sensitivity runner for EXP-04.

EXP-04 (Plan Revision 2, approved 2026-09-21) is a controlled
sensitivity analysis with two families:

Family A — Feature Set Sensitivity (RFM vs RFM Extended): DEFERRED.
  The RFM-only clustering-ready dataset does NOT exist in the
  repository, and EXP-04 does NOT create one ad-hoc. The deferred
  ownership belongs to FE-06 (future ADR).

Family B — Preprocessing Sensitivity (transformation × scaling)
  on the RFM Extended feature set: EXECUTED.

Six full-matrix preprocessing scenarios (C0, C1, C2, C3, C6, C7) are
evaluated with the following fixed controls:

- Algorithm: K-Means (``CONTROLLED_REFERENCE_ALGORITHM``).
- Algorithm hyperparameters: EXP-01 working defaults
  (``CONTROLLED_REFERENCE_HYPERPARAMETERS``): init=k-means++,
  n_init=10, max_iter=300, tol=1.0e-4, random_state=42.
- K = 4 (``CONTROLLED_REFERENCE_K``).
- Imputation = median with FE-06 C7 fitted median values
  (``CONTROLLED_REFERENCE_IMPUTATION``): PurchaseIntervalMean=41.0,
  PurchaseIntervalStd=32.58504379012092.
- Repeated execution (n_repeat=5, seed=42) is REPRODUCIBILITY
  verification — NOT stability analysis. With K-Means being seeded,
  labels_hash and metrics MUST be identical across repeats; only
  wall-clock runtime may vary.

Hard constraints (AGENTS.md §2, FE-06 contract):

- FE-05 / FE-06 outputs are READ-ONLY. EXP-04 never mutates them
  on disk; only SHA verification and READ-ONLY loads happen.
- EXP-04 does NOT introduce composite scores, weighted rankings,
  or algorithm rankings.
- EXP-04 does NOT call any scenario / algorithm / configuration
  "best" / "optimal" / "superior" / "winner" / "recommended" /
  "final".
- EXP-04 does NOT use EXP-03 working / selected configurations as
  EXP-04 hyperparameters.
- EXP-04 does NOT re-sweep K = 2..10.
- EXP-04 does NOT compute ARI / AMI / bootstrap stability.

The module exposes:

- :func:`compute_labels_hash` — deterministic SHA-256 over a label
  vector.
- :class:`ScenarioSpec` — declarative scenario description
  (feature_set / transformation / scaling / imputation / role).
- :class:`ScenarioRepeatRecord` — per-``(scenario, repeat)`` result.
- :class:`ScenarioAggregateRecord` — per-scenario aggregate
  (runtime mean / std, determinism flag, decision status).
- :class:`ScenarioMatrixValidator` — pure validation of the YAML
  scenario matrix (count = 6, IDs unique, etc.).
- :class:`ImputationApplier` — pure utility that applies the
  CONTROLLED_REFERENCE_IMPUTATION median values verbatim.
- :class:`ScenarioPipelineBuilder` — builds an in-memory
  ``Pipeline(transformation + scaling)`` from a
  :class:`ScenarioSpec`. Never persisted to disk.
- :class:`PreprocessingFeatureSensitivityRunner` — orchestrator
  that runs all six scenarios × ``n_repeat`` repeats.
"""

from __future__ import annotations

import hashlib
import math
import platform as platform_module
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from customer_segmentation.clustering.config import (
    FrameworkConfig,
    compute_text_sha256,
)
from customer_segmentation.clustering.metrics import (
    attach_metrics_with_status,
    compute_runtime_stats,
)
from customer_segmentation.clustering.runner import ExperimentRunner, ExperimentSpec

__all__ = [
    "TRANSFORMATION_NONE",
    "TRANSFORMATION_YEO_JOHNSON",
    "SCALING_NONE",
    "SCALING_STANDARD",
    "SCALING_MINMAX",
    "SCALING_ROBUST",
    "SUPPORTED_TRANSFORMATIONS",
    "SUPPORTED_SCALINGS",
    "EXP04_SCENARIO_IDS",
    "DECISION_STATUS_CANDIDATE",
    "DECISION_STATUS_TIED",
    "DECISION_STATUS_PENDING_REVIEW",
    "DECISION_STATUS_DEFERRED",
    "PERMITTED_DECISION_STATUSES",
    "FORBIDDEN_DECISION_LABELS",
    "compute_labels_hash",
    "ScenarioSpec",
    "ScenarioRepeatRecord",
    "ScenarioAggregateRecord",
    "SensitivitySweepResult",
    "ScenarioMatrixValidator",
    "ScenarioMatrixValidationError",
    "ImputationApplier",
    "ImputationValueError",
    "ScenarioPipelineBuilder",
    "ScenarioPipelineBuildError",
    "PreprocessingFeatureSensitivityRunner",
]


# ---------------------------------------------------------------------------
# Constants — supported preprocessing primitives
# ---------------------------------------------------------------------------

TRANSFORMATION_NONE = "none"
TRANSFORMATION_YEO_JOHNSON = "yeo_johnson"

SUPPORTED_TRANSFORMATIONS: frozenset[str] = frozenset(
    {TRANSFORMATION_NONE, TRANSFORMATION_YEO_JOHNSON}
)

SCALING_NONE = "none"
SCALING_STANDARD = "standard"
SCALING_MINMAX = "minmax"
SCALING_ROBUST = "robust"

SUPPORTED_SCALINGS: frozenset[str] = frozenset(
    {SCALING_NONE, SCALING_STANDARD, SCALING_MINMAX, SCALING_ROBUST}
)


# ---------------------------------------------------------------------------
# Constants — expected EXP-04 scenario matrix (Plan R2)
# ---------------------------------------------------------------------------

EXP04_SCENARIO_IDS: tuple[str, ...] = (
    "EXP04-S01",
    "EXP04-S02",
    "EXP04-S03",
    "EXP04-S04",
    "EXP04-S05",
    "EXP04-S06",
)

# Config IDs as defined in FE-06 experimental matrix and EXP-04 plan R2.
EXP04_CONFIG_IDS: tuple[str, ...] = ("C0", "C1", "C2", "C3", "C6", "C7")

# Decision status taxonomy (only these values are permitted).
DECISION_STATUS_CANDIDATE = "CANDIDATE_SCENARIO"
DECISION_STATUS_TIED = "TIED_SCENARIOS"
DECISION_STATUS_PENDING_REVIEW = "PENDING_REVIEW"
DECISION_STATUS_DEFERRED = "DEFERRED"

PERMITTED_DECISION_STATUSES: frozenset[str] = frozenset(
    {
        DECISION_STATUS_CANDIDATE,
        DECISION_STATUS_TIED,
        DECISION_STATUS_PENDING_REVIEW,
        DECISION_STATUS_DEFERRED,
    }
)

# Forbidden labels (case-insensitive check) — must never appear in
# EXP-04 outputs as a final / winner claim.
FORBIDDEN_DECISION_LABELS: frozenset[str] = frozenset(
    {"BEST", "OPTIMAL", "WINNER", "SUPERIOR", "RECOMMENDED", "FINAL"}
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ScenarioMatrixValidationError(ValueError):
    """Raised when the EXP-04 scenario matrix fails validation."""


class ImputationValueError(ValueError):
    """Raised when imputation values are missing or out of range."""


class ScenarioPipelineBuildError(ValueError):
    """Raised when a scenario pipeline cannot be built."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _library_versions() -> dict[str, str]:
    """Snapshot versions of libraries EXP-04 depends on."""
    import numpy
    import pandas
    import pyarrow
    import scipy
    import sklearn

    return {
        "numpy": numpy.__version__,
        "pandas": pandas.__version__,
        "scipy": scipy.__version__,
        "scikit-learn": sklearn.__version__,
        "pyarrow": pyarrow.__version__,
    }


def _platform_info() -> dict[str, str]:
    """Snapshot Python / OS environment."""
    return {
        "python": platform_module.python_version(),
        "system": platform_module.system(),
        "release": platform_module.release(),
        "machine": platform_module.machine(),
    }


def compute_labels_hash(labels: np.ndarray) -> str:
    """Compute deterministic SHA-256 over an integer label vector.

    Parameters
    ----------
    labels : numpy.ndarray
        Integer cluster labels.

    Returns
    -------
    str
        Hex SHA-256 digest of the int64-cast label array.

    Notes
    -----
    This is used as a determinism check: same scenario + same seed
    MUST produce identical cluster labels, hence identical
    ``labels_hash``. K-Means with ``random_state=42`` and ``n_init``
    pinned to a single value (or with deterministic tie-breaking
    when n_init>1) is fully reproducible on a given library
    version.
    """
    arr = np.asarray(labels, dtype=np.int64).tobytes()
    return hashlib.sha256(arr).hexdigest()


def _safe_float(value: Any) -> float | None:
    """Convert a value to float, returning None for NaN / Inf / None."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


# ---------------------------------------------------------------------------
# Scenario dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScenarioSpec:
    """Specification of a single EXP-04 Family B preprocessing scenario."""

    scenario_id: str
    config_id: str
    role: str
    transformation: str
    scaling: str

    def validate(self) -> None:
        """Validate this scenario spec.

        Raises
        ------
        ScenarioMatrixValidationError
            If any field is invalid.
        """
        if self.scenario_id not in EXP04_SCENARIO_IDS:
            raise ScenarioMatrixValidationError(
                f"Unknown scenario_id {self.scenario_id!r}; expected one of {EXP04_SCENARIO_IDS}."
            )
        if self.config_id not in EXP04_CONFIG_IDS:
            raise ScenarioMatrixValidationError(
                f"Unknown config_id {self.config_id!r}; expected one of {EXP04_CONFIG_IDS}."
            )
        if self.transformation not in SUPPORTED_TRANSFORMATIONS:
            raise ScenarioMatrixValidationError(
                f"Unsupported transformation {self.transformation!r}; "
                f"expected one of {sorted(SUPPORTED_TRANSFORMATIONS)}."
            )
        if self.scaling not in SUPPORTED_SCALINGS:
            raise ScenarioMatrixValidationError(
                f"Unsupported scaling {self.scaling!r}; "
                f"expected one of {sorted(SUPPORTED_SCALINGS)}."
            )


@dataclass
class ScenarioRepeatRecord:
    """Result of a single (scenario × repeat) run."""

    scenario_id: str
    config_id: str
    role: str
    repeat_index: int

    feature_set: str
    feature_set_sha256: str

    transformation: str
    scaling: str
    imputation: str

    algorithm: str
    n_clusters: int
    random_seed: int
    hyperparameters: dict[str, Any]

    status: str
    failure_reason: str | None

    silhouette: float | None
    silhouette_status: str
    davies_bouldin: float | None
    davies_bouldin_status: str
    calinski_harabasz: float | None
    calinski_harabasz_status: str
    wcss: float | None
    wcss_status: str

    runtime_seconds: float
    labels_hash: str | None
    n_clusters_realized: int | None

    input_sha256: str
    customer_metadata_sha256: str
    config_sha256: str

    library_versions: dict[str, str]
    platform_info: dict[str, str]


@dataclass
class ScenarioAggregateRecord:
    """Per-scenario aggregate across n_repeat repeats."""

    scenario_id: str
    config_id: str
    role: str
    feature_set: str
    transformation: str
    scaling: str
    imputation: str
    algorithm: str
    n_clusters: int

    silhouette: float | None
    davies_bouldin: float | None
    calinski_harabasz: float | None
    wcss: float | None

    runtime_mean_seconds: float | None
    runtime_std_seconds: float | None

    labels_hash: str | None
    determinism_verified: bool
    n_successful_repeats: int
    n_total_repeats: int

    decision_status: str
    evidence_note: str


@dataclass
class SensitivitySweepResult:
    """Result of the full EXP-04 Family B sensitivity sweep."""

    records: list[ScenarioRepeatRecord]
    aggregates: list[ScenarioAggregateRecord]
    feature_set: str
    feature_set_sha256: str
    algorithm: str
    n_clusters: int
    seed: int
    n_repeat: int
    input_sha256: str
    customer_metadata_sha256: str
    config_sha256: str
    library_versions: dict[str, str]
    platform_info: dict[str, str]


# ---------------------------------------------------------------------------
# Scenario matrix validator
# ---------------------------------------------------------------------------


class ScenarioMatrixValidator:
    """Validate that the EXP-04 scenario matrix matches Plan R2.

    The expected matrix is six scenarios ``EXP04-S01..S06`` with
    unique scenario IDs, unique config IDs, and each
    (transformation, scaling) pair belonging to the supported set.

    Parameters
    ----------
    scenarios : list of :class:`ScenarioSpec`
        Scenario matrix to validate.
    """

    def __init__(self, scenarios: list[ScenarioSpec]) -> None:
        self.scenarios = scenarios

    def validate(self) -> None:
        """Validate scenario matrix.

        Raises
        ------
        ScenarioMatrixValidationError
            On any structural mismatch with Plan R2.
        """
        if len(self.scenarios) != 6:
            raise ScenarioMatrixValidationError(
                f"EXP-04 scenario matrix must contain exactly 6 scenarios; "
                f"got {len(self.scenarios)}."
            )

        ids = [s.scenario_id for s in self.scenarios]
        if len(set(ids)) != 6:
            raise ScenarioMatrixValidationError(f"EXP-04 scenario IDs must be unique; got {ids}.")

        configs = [s.config_id for s in self.scenarios]
        if len(set(configs)) != 6:
            raise ScenarioMatrixValidationError(f"EXP-04 config_ids must be unique; got {configs}.")

        # Required IDs in the required order.
        expected_ids = list(EXP04_SCENARIO_IDS)
        if ids != expected_ids:
            raise ScenarioMatrixValidationError(
                f"EXP-04 scenario_ids must equal {expected_ids} in order; " f"got {ids}."
            )

        expected_configs = list(EXP04_CONFIG_IDS)
        if configs != expected_configs:
            raise ScenarioMatrixValidationError(
                f"EXP-04 config_ids must equal {expected_configs} in order; " f"got {configs}."
            )

        for spec in self.scenarios:
            spec.validate()

        # Per-row sanity: role must be a non-empty string.
        for spec in self.scenarios:
            if not isinstance(spec.role, str) or not spec.role:
                raise ScenarioMatrixValidationError(
                    f"Scenario {spec.scenario_id}: role must be a non-empty string."
                )


# ---------------------------------------------------------------------------
# Imputation applier (CONTROLLED_REFERENCE_IMPUTATION)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ImputationSpec:
    """Specification for CONTROLLED_REFERENCE_IMPUTATION.

    Mirrors the FE-06 C7 fitted imputer. EXP-04 does NOT introduce
    new imputation methods. The fitted values are fixed and reused
    verbatim across all six scenarios.
    """

    method: str
    fitted_values: dict[str, float]
    applied_features: tuple[str, ...]

    def validate(self) -> None:
        """Validate the imputation spec.

        Raises
        ------
        ImputationValueError
            If method is not "median" or any fitted value is missing
            for an applied feature.
        """
        if self.method != "median":
            raise ImputationValueError(
                f"EXP-04 imputation method must be 'median'; got {self.method!r}."
            )
        for feature in self.applied_features:
            if feature not in self.fitted_values:
                raise ImputationValueError(f"Fitted median value missing for feature {feature!r}.")
            value = self.fitted_values[feature]
            if not isinstance(value, (int, float)):
                raise ImputationValueError(
                    f"Fitted median value for {feature!r} must be numeric; "
                    f"got {type(value).__name__}."
                )
            if math.isnan(float(value)) or math.isinf(float(value)):
                raise ImputationValueError(
                    f"Fitted median value for {feature!r} must be finite; " f"got {value!r}."
                )


class ImputationApplier:
    """Apply CONTROLLED_REFERENCE_IMPUTATION to a candidate matrix.

    The applier performs an in-memory fill using the FE-06 C7 fitted
    median values verbatim. It does NOT recompute medians from the
    current data. The source DataFrame is NOT mutated; a copy is
    returned.

    Parameters
    ----------
    spec : :class:`ImputationSpec`
        Imputation specification (method, fitted values, applied features).
    """

    def __init__(self, spec: ImputationSpec) -> None:
        spec.validate()
        self.spec = spec

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return a NEW DataFrame with NaNs in applied features filled.

        Parameters
        ----------
        df : pandas.DataFrame
            Source matrix (e.g., FE-05 ``customer_candidates.parquet``).
            MUST NOT be mutated.

        Returns
        -------
        pandas.DataFrame
            A copy of ``df`` with NaNs in the applied features filled
            by the CONTROLLED_REFERENCE_IMPUTATION fitted median.
        """
        out = df.copy(deep=True)
        for feature in self.spec.applied_features:
            if feature not in out.columns:
                # No NaNs to fill for features not present; skip silently.
                continue
            median = float(self.spec.fitted_values[feature])
            before_nan = int(out[feature].isna().sum())
            if before_nan > 0:
                out[feature] = out[feature].fillna(median)
        return out


# ---------------------------------------------------------------------------
# Scenario pipeline builder (in-memory only)
# ---------------------------------------------------------------------------


@dataclass
class ScenarioPipeline:
    """A fitted per-scenario transformation+scaling pipeline.

    The pipeline is fit in-memory on the imputed matrix and is NOT
    persisted to disk. EXP-04 holds one instance per scenario for
    the lifetime of the run, but never writes it to
    ``data/processed/``.
    """

    scenario_id: str
    transformation: str
    scaling: str
    transformation_step: Any  # sklearn transformer or "passthrough"
    scaling_step: Any  # sklearn transformer or "passthrough"

    def transform(self, X: np.ndarray) -> np.ndarray:
        """Apply transformation then scaling to a numeric matrix."""
        if self.transformation_step is not None:
            X = self.transformation_step.transform(X)
        if self.scaling_step is not None:
            X = self.scaling_step.transform(X)
        return X


class ScenarioPipelineBuilder:
    """Build scenario-specific (transformation + scaling) pipelines.

    The builder never mutates the input DataFrame. Pipelines are
    fit on a copy of the data and held in memory only.

    Parameters
    ----------
    feature_order : list of str
        Ordered list of feature columns the pipeline must operate on.
    """

    def __init__(self, feature_order: list[str]) -> None:
        if not feature_order:
            raise ScenarioPipelineBuildError("feature_order must be non-empty.")
        self.feature_order = list(feature_order)

    def fit(self, spec: ScenarioSpec, df_imputed: pd.DataFrame) -> ScenarioPipeline:
        """Fit a (transformation + scaling) pipeline on ``df_imputed``.

        Parameters
        ----------
        spec : :class:`ScenarioSpec`
            Scenario specification.
        df_imputed : pandas.DataFrame
            Imputed candidate matrix. MUST contain the columns in
            ``feature_order`` in the same order. NOT mutated.

        Returns
        -------
        ScenarioPipeline
            Fitted scenario-specific pipeline (in-memory only).
        """
        spec.validate()

        # Select features in the canonical order. df_imputed is not
        # mutated; .to_numpy() reads.
        missing = [c for c in self.feature_order if c not in df_imputed.columns]
        if missing:
            raise ScenarioPipelineBuildError(
                f"Scenario {spec.scenario_id}: df_imputed missing columns {missing}."
            )
        X = df_imputed[self.feature_order].to_numpy(dtype=np.float64, copy=True)

        # Build transformation step
        transformation_step = self._build_transformation(spec.transformation)
        if transformation_step is not None:
            X = transformation_step.fit_transform(X)

        # Build scaling step
        scaling_step = self._build_scaling(spec.scaling)
        if scaling_step is not None:
            X = scaling_step.fit_transform(X)

        return ScenarioPipeline(
            scenario_id=spec.scenario_id,
            transformation=spec.transformation,
            scaling=spec.scaling,
            transformation_step=transformation_step,
            scaling_step=scaling_step,
        )

    # ----- private -----

    @staticmethod
    def _build_transformation(name: str) -> Any:
        """Return a sklearn transformer or None for 'none'."""
        if name == TRANSFORMATION_NONE:
            return None
        if name == TRANSFORMATION_YEO_JOHNSON:
            from sklearn.preprocessing import PowerTransformer

            return PowerTransformer(method="yeo-johnson", standardize=False)
        raise ScenarioPipelineBuildError(
            f"Unsupported transformation {name!r}; expected one of {sorted(SUPPORTED_TRANSFORMATIONS)}."
        )

    @staticmethod
    def _build_scaling(name: str) -> Any:
        """Return a sklearn scaler or None for 'none'."""
        if name == SCALING_NONE:
            return None
        if name == SCALING_STANDARD:
            from sklearn.preprocessing import StandardScaler

            return StandardScaler()
        if name == SCALING_MINMAX:
            from sklearn.preprocessing import MinMaxScaler

            return MinMaxScaler()
        if name == SCALING_ROBUST:
            from sklearn.preprocessing import RobustScaler

            return RobustScaler()
        raise ScenarioPipelineBuildError(
            f"Unsupported scaling {name!r}; expected one of {sorted(SUPPORTED_SCALINGS)}."
        )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


@dataclass
class _AggregateBuilder:
    """Internal helper to compute aggregate statistics deterministically."""

    repeat_records: list[ScenarioRepeatRecord] = field(default_factory=list)


class PreprocessingFeatureSensitivityRunner:
    """Run EXP-04 Family B (preprocessing sensitivity) sweep.

    The runner is deterministic: with the same scenario + same
    K-Means hyperparameters + same seed, repeated fits MUST produce
    identical labels_hash and metric values. Wall-clock runtime may
    vary across repeats.

    Parameters
    ----------
    framework_cfg : :class:`FrameworkConfig`
        ML-01 framework configuration (clustering.yaml).
    exp04_config : dict
        Parsed EXP-04 YAML configuration.
    framework_config_text : str, optional
        Raw text of ``configs/clustering.yaml`` used to compute
        ``config_sha256`` for provenance.
    """

    def __init__(
        self,
        framework_cfg: FrameworkConfig,
        exp04_config: dict[str, Any],
        framework_config_text: str | None = None,
        exp04_config_text: str | None = None,
    ) -> None:
        self.framework_cfg = framework_cfg
        self.exp04_config = exp04_config
        self.framework_config_text = framework_config_text
        self.exp04_config_text = exp04_config_text
        self.framework_config_sha256 = (
            compute_text_sha256(framework_config_text) if framework_config_text else None
        )
        self.exp04_config_sha256 = (
            compute_text_sha256(exp04_config_text) if exp04_config_text else None
        )

    # ----- Public API -----

    def build_scenarios(self) -> list[ScenarioSpec]:
        """Build and validate the EXP-04 scenario matrix from YAML.

        Returns
        -------
        list of :class:`ScenarioSpec`
            Validated scenario matrix in canonical order
            (``EXP04-S01`` to ``EXP04-S06``).
        """
        exp04_section = self.exp04_config.get("exp04", {})
        scenarios_cfg = exp04_section.get("scenarios", [])
        if not isinstance(scenarios_cfg, list):
            raise ScenarioMatrixValidationError("exp04.scenarios must be a list of scenario dicts.")
        specs: list[ScenarioSpec] = []
        for s in scenarios_cfg:
            try:
                specs.append(
                    ScenarioSpec(
                        scenario_id=str(s["id"]),
                        config_id=str(s["config_id"]),
                        role=str(s.get("role", "")),
                        transformation=str(s["transformation"]),
                        scaling=str(s["scaling"]),
                    )
                )
            except KeyError as exc:
                raise ScenarioMatrixValidationError(
                    f"exp04.scenarios entry missing key {exc!s}; entry={s!r}."
                ) from exc

        ScenarioMatrixValidator(specs).validate()
        return specs

    def build_imputation(self) -> ImputationSpec:
        """Build CONTROLLED_REFERENCE_IMPUTATION from YAML.

        Returns
        -------
        :class:`ImputationSpec`
            Validated imputation spec (median + FE-06 C7 fitted values).
        """
        imp_cfg = self.exp04_config.get("exp04", {}).get("imputation", {})
        method = imp_cfg.get("method")
        fitted = imp_cfg.get("fitted_values", {})
        applied = tuple(imp_cfg.get("applied_features", ()))
        return ImputationSpec(
            method=str(method),
            fitted_values={k: float(v) for k, v in fitted.items()},
            applied_features=applied,
        )

    def algorithm_hyperparameters(self) -> dict[str, Any]:
        """Return the CONTROLLED_REFERENCE_HYPERPARAMETERS for K-Means."""
        algo_cfg = self.exp04_config.get("exp04", {}).get("algorithm", {})
        hp = algo_cfg.get("hyperparameters", {})
        return dict(hp)

    def feature_order(self) -> list[str]:
        """Return the canonical feature order for EXP-04."""
        return list(
            self.exp04_config.get("exp04", {}).get("feature_set", {}).get("feature_order", [])
        )

    def repeat_count(self) -> int:
        """Return the number of repeated executions per scenario."""
        return int(
            self.exp04_config.get("exp04", {}).get("repeated_execution", {}).get("n_repeat", 5)
        )

    def seed(self) -> int:
        """Return the seed for REPRODUCIBILITY_VERIFICATION."""
        return int(self.exp04_config.get("exp04", {}).get("repeated_execution", {}).get("seed", 42))

    def run(
        self,
        candidates_df: pd.DataFrame,
        customer_metadata_df: pd.DataFrame | None,
        *,
        candidates_sha256: str,
        metadata_sha256: str,
    ) -> SensitivitySweepResult:
        """Run the EXP-04 Family B sweep.

        Parameters
        ----------
        candidates_df : pandas.DataFrame
            FE-05 candidate matrix (e.g.,
            ``customer_candidates.parquet``). MUST be unmodified on
            disk. NOT mutated in memory either — the runner takes a
            defensive copy via :class:`ImputationApplier`.
        customer_metadata_df : pandas.DataFrame, optional
            Customer metadata carrying ``CustomerID``.
        candidates_sha256 : str
            SHA-256 of the source candidate file (must match YAML).
        metadata_sha256 : str
            SHA-256 of the customer metadata file (must match YAML).

        Returns
        -------
        :class:`SensitivitySweepResult`
            Aggregated EXP-04 result with per-repeat and per-scenario
            records.
        """
        scenarios = self.build_scenarios()
        imputation = self.build_imputation()
        algo_hp = self.algorithm_hyperparameters()
        feat_order = self.feature_order()
        n_repeat = self.repeat_count()
        seed = self.seed()

        # Verify SHA-256 against YAML expectations.
        ds_cfg = self.exp04_config.get("exp04", {}).get("dataset", {})
        expected_candidates = ds_cfg.get("customer_candidates_sha256")
        if expected_candidates and expected_candidates != candidates_sha256:
            raise ScenarioMatrixValidationError(
                f"customer_candidates.parquet SHA-256 mismatch. "
                f"Expected {expected_candidates!r}, got {candidates_sha256!r}."
            )
        expected_metadata = ds_cfg.get("customer_metadata_sha256")
        if expected_metadata and expected_metadata != metadata_sha256:
            raise ScenarioMatrixValidationError(
                f"customer_metadata.parquet SHA-256 mismatch. "
                f"Expected {expected_metadata!r}, got {metadata_sha256!r}."
            )

        feature_set_name = str(
            self.exp04_config.get("exp04", {}).get("feature_set", {}).get("name", "rfm_extended")
        )

        # Impute once (CONTROLLED_REFERENCE_IMPUTATION), then each
        # scenario fits its own transformation + scaling on a copy of
        # the imputed matrix.
        applier = ImputationApplier(imputation)
        imputed_df = applier.apply(candidates_df)

        # Filter columns to feature order; build the matrix view for
        # scenario pipelines.
        missing = [c for c in feat_order if c not in imputed_df.columns]
        if missing:
            raise ScenarioPipelineBuildError(
                f"Imputed matrix missing expected feature columns: {missing}."
            )
        imputed_view = imputed_df[feat_order].copy(deep=True)

        pipeline_builder = ScenarioPipelineBuilder(feat_order)

        all_repeat_records: list[ScenarioRepeatRecord] = []
        aggregates: list[ScenarioAggregateRecord] = []

        library_versions = _library_versions()
        platform_info = _platform_info()

        algo_name = str(
            self.exp04_config.get("exp04", {}).get("algorithm", {}).get("name", "kmeans")
        )
        n_clusters = int(algo_hp.get("n_clusters", 4))

        for spec in scenarios:
            pipeline = pipeline_builder.fit(spec, imputed_view)

            # Build the per-scenario matrix in-memory. NEVER mutated
            # on disk.
            X_scenario = pipeline.transform(imputed_view.to_numpy(dtype=np.float64, copy=True))
            matrix_df = pd.DataFrame(X_scenario, columns=feat_order, copy=True)

            repeat_records = self._run_repeats(
                spec=spec,
                matrix_df=matrix_df,
                customer_metadata_df=customer_metadata_df,
                algo_name=algo_name,
                algo_hp=algo_hp,
                seed=seed,
                n_repeat=n_repeat,
                candidates_sha256=candidates_sha256,
                metadata_sha256=metadata_sha256,
                config_sha256=self.framework_config_sha256 or "",
                feature_set=feature_set_name,
                feature_set_sha256=candidates_sha256,
                imputation_method=imputation.method,
                library_versions=library_versions,
                platform_info=platform_info,
            )
            all_repeat_records.extend(repeat_records)
            aggregates.append(self._aggregate(spec, repeat_records))

        return SensitivitySweepResult(
            records=all_repeat_records,
            aggregates=aggregates,
            feature_set=feature_set_name,
            feature_set_sha256=candidates_sha256,
            algorithm=algo_name,
            n_clusters=n_clusters,
            seed=seed,
            n_repeat=n_repeat,
            input_sha256=candidates_sha256,
            customer_metadata_sha256=metadata_sha256,
            config_sha256=self.framework_config_sha256 or "",
            library_versions=library_versions,
            platform_info=platform_info,
        )

    # ----- Internal helpers -----

    def _run_repeats(
        self,
        *,
        spec: ScenarioSpec,
        matrix_df: pd.DataFrame,
        customer_metadata_df: pd.DataFrame | None,
        algo_name: str,
        algo_hp: dict[str, Any],
        seed: int,
        n_repeat: int,
        candidates_sha256: str,
        metadata_sha256: str,
        config_sha256: str,
        feature_set: str,
        feature_set_sha256: str,
        imputation_method: str,
        library_versions: dict[str, str],
        platform_info: dict[str, str],
    ) -> list[ScenarioRepeatRecord]:
        """Run ``n_repeat`` deterministic fits for a single scenario."""
        records: list[ScenarioRepeatRecord] = []
        experiment_id = f"EXP04-{spec.config_id}-{spec.scenario_id}"

        for repeat_index in range(n_repeat):
            exp_spec = ExperimentSpec(
                experiment_id=f"{experiment_id}-rep{repeat_index:02d}",
                algorithm=algo_name,
                hyperparameters=dict(algo_hp),
                seed_override=seed,
            )
            runner = ExperimentRunner(
                self.framework_cfg,
                exp_spec,
                config_source=None,
                config_text=self.framework_config_text,
            )
            try:
                result = runner.run(
                    matrix_df,
                    customer_metadata_df,
                    input_sha256=candidates_sha256,
                    input_path=None,
                    metadata_path=None,
                    output_dir=None,
                )
            except Exception as exc:  # noqa: BLE001
                # Defensive: runner.run should never raise (it catches
                # algorithm errors and turns them into FAILED results),
                # but record defensively to keep the sweep robust.
                records.append(
                    ScenarioRepeatRecord(
                        scenario_id=spec.scenario_id,
                        config_id=spec.config_id,
                        role=spec.role,
                        repeat_index=repeat_index,
                        feature_set=feature_set,
                        feature_set_sha256=feature_set_sha256,
                        transformation=spec.transformation,
                        scaling=spec.scaling,
                        imputation=imputation_method,
                        algorithm=algo_name,
                        n_clusters=int(algo_hp.get("n_clusters", 4)),
                        random_seed=seed,
                        hyperparameters=dict(algo_hp),
                        status="FAILED",
                        failure_reason=f"{type(exc).__name__}: {exc}",
                        silhouette=None,
                        silhouette_status="MISSING",
                        davies_bouldin=None,
                        davies_bouldin_status="MISSING",
                        calinski_harabasz=None,
                        calinski_harabasz_status="MISSING",
                        wcss=None,
                        wcss_status="MISSING",
                        runtime_seconds=0.0,
                        labels_hash=None,
                        n_clusters_realized=None,
                        input_sha256=candidates_sha256,
                        customer_metadata_sha256=metadata_sha256,
                        config_sha256=config_sha256,
                        library_versions=library_versions,
                        platform_info=platform_info,
                    )
                )
                continue

            if (
                result.status != "SUCCESS"
                or result.cluster_result is None
                or result.cluster_result.cluster_labels is None
            ):
                records.append(
                    ScenarioRepeatRecord(
                        scenario_id=spec.scenario_id,
                        config_id=spec.config_id,
                        role=spec.role,
                        repeat_index=repeat_index,
                        feature_set=feature_set,
                        feature_set_sha256=feature_set_sha256,
                        transformation=spec.transformation,
                        scaling=spec.scaling,
                        imputation=imputation_method,
                        algorithm=algo_name,
                        n_clusters=int(algo_hp.get("n_clusters", 4)),
                        random_seed=seed,
                        hyperparameters=dict(algo_hp),
                        status="FAILED",
                        failure_reason=(
                            (result.error or {}).get("message") if result.error else "unknown"
                        ),
                        silhouette=None,
                        silhouette_status="MISSING",
                        davies_bouldin=None,
                        davies_bouldin_status="MISSING",
                        calinski_harabasz=None,
                        calinski_harabasz_status="MISSING",
                        wcss=None,
                        wcss_status="MISSING",
                        runtime_seconds=float(result.execution_time),
                        labels_hash=None,
                        n_clusters_realized=None,
                        input_sha256=candidates_sha256,
                        customer_metadata_sha256=metadata_sha256,
                        config_sha256=config_sha256,
                        library_versions=library_versions,
                        platform_info=platform_info,
                    )
                )
                continue

            cluster_result = result.cluster_result
            labels = cluster_result.cluster_labels

            # Compute metrics (silhouette / DBI / CH / WCSS) via the
            # EXP-01 metrics layer.
            X_for_metrics = matrix_df.to_numpy(dtype=np.float64, copy=False)
            cluster_result = attach_metrics_with_status(
                cluster_result,
                X_for_metrics,
                exclude_noise=True,
                noise_label=-1,
                runtime_stats=compute_runtime_stats([float(result.execution_time)]),
            )

            metrics = cluster_result.metrics
            extra = metrics.extra

            records.append(
                ScenarioRepeatRecord(
                    scenario_id=spec.scenario_id,
                    config_id=spec.config_id,
                    role=spec.role,
                    repeat_index=repeat_index,
                    feature_set=feature_set,
                    feature_set_sha256=feature_set_sha256,
                    transformation=spec.transformation,
                    scaling=spec.scaling,
                    imputation=imputation_method,
                    algorithm=algo_name,
                    n_clusters=int(algo_hp.get("n_clusters", 4)),
                    random_seed=seed,
                    hyperparameters=dict(algo_hp),
                    status="SUCCESS",
                    failure_reason=None,
                    silhouette=_safe_float(metrics.silhouette),
                    silhouette_status=extra.get("silhouette_status", "MISSING"),
                    davies_bouldin=_safe_float(metrics.davies_bouldin),
                    davies_bouldin_status=extra.get("davies_bouldin_status", "MISSING"),
                    calinski_harabasz=_safe_float(metrics.calinski_harabasz),
                    calinski_harabasz_status=extra.get("calinski_harabasz_status", "MISSING"),
                    wcss=_safe_float(metrics.wcss),
                    wcss_status=extra.get("wcss_status", "MISSING"),
                    runtime_seconds=float(result.execution_time),
                    labels_hash=compute_labels_hash(labels),
                    n_clusters_realized=(
                        int(cluster_result.n_clusters)
                        if cluster_result.n_clusters is not None
                        else None
                    ),
                    input_sha256=candidates_sha256,
                    customer_metadata_sha256=metadata_sha256,
                    config_sha256=config_sha256,
                    library_versions=library_versions,
                    platform_info=platform_info,
                )
            )

        return records

    @staticmethod
    def _aggregate(
        spec: ScenarioSpec, records: list[ScenarioRepeatRecord]
    ) -> ScenarioAggregateRecord:
        """Aggregate per-repeat records into one record per scenario."""
        successful = [r for r in records if r.status == "SUCCESS"]

        if not successful:
            return ScenarioAggregateRecord(
                scenario_id=spec.scenario_id,
                config_id=spec.config_id,
                role=spec.role,
                feature_set=records[0].feature_set if records else "",
                transformation=spec.transformation,
                scaling=spec.scaling,
                imputation=records[0].imputation if records else "",
                algorithm=records[0].algorithm if records else "",
                n_clusters=records[0].n_clusters if records else 0,
                silhouette=None,
                davies_bouldin=None,
                calinski_harabasz=None,
                wcss=None,
                runtime_mean_seconds=None,
                runtime_std_seconds=None,
                labels_hash=None,
                determinism_verified=False,
                n_successful_repeats=0,
                n_total_repeats=len(records),
                decision_status=DECISION_STATUS_PENDING_REVIEW,
                evidence_note="All repeats failed; cannot compute aggregate.",
            )

        # Primary metric values from the first successful repeat
        # (with VERIFIED identity across all successful repeats).
        first = successful[0]
        labels_hashes = {r.labels_hash for r in successful if r.labels_hash is not None}
        sil_values = {r.silhouette for r in successful if r.silhouette is not None}
        dbi_values = {r.davies_bouldin for r in successful if r.davies_bouldin is not None}
        ch_values = {r.calinski_harabasz for r in successful if r.calinski_harabasz is not None}
        wcss_values = {r.wcss for r in successful if r.wcss is not None}
        runtimes = [float(r.runtime_seconds) for r in successful]

        determinism_verified = (
            len(labels_hashes) == 1
            and len(sil_values) <= 1
            and len(dbi_values) <= 1
            and len(ch_values) <= 1
            and len(wcss_values) <= 1
        )

        runtime_stats = compute_runtime_stats(runtimes)
        runtime_mean = _safe_float(runtime_stats.get("mean_seconds"))
        runtime_std = _safe_float(runtime_stats.get("std_seconds"))

        if determinism_verified:
            decision_status = DECISION_STATUS_CANDIDATE
            evidence_note = (
                "All successful repeats produced identical labels_hash and metric values; "
                "REPRODUCIBILITY_VERIFICATION passed. NOT stability analysis."
            )
        else:
            decision_status = DECISION_STATUS_PENDING_REVIEW
            evidence_parts: list[str] = []
            if len(labels_hashes) > 1:
                evidence_parts.append(f"labels_hash varied across {len(labels_hashes)} values")
            if len(sil_values) > 1:
                evidence_parts.append(f"silhouette varied across {len(sil_values)} values")
            if len(dbi_values) > 1:
                evidence_parts.append(f"DBI varied across {len(dbi_values)} values")
            if len(ch_values) > 1:
                evidence_parts.append(f"CH varied across {len(ch_values)} values")
            if len(wcss_values) > 1:
                evidence_parts.append(f"WCSS varied across {len(wcss_values)} values")
            evidence_note = "Determinism verification FAILED: " + "; ".join(evidence_parts) + "."

        return ScenarioAggregateRecord(
            scenario_id=spec.scenario_id,
            config_id=spec.config_id,
            role=spec.role,
            feature_set=first.feature_set,
            transformation=spec.transformation,
            scaling=spec.scaling,
            imputation=first.imputation,
            algorithm=first.algorithm,
            n_clusters=first.n_clusters,
            silhouette=first.silhouette,
            davies_bouldin=first.davies_bouldin,
            calinski_harabasz=first.calinski_harabasz,
            wcss=first.wcss,
            runtime_mean_seconds=runtime_mean,
            runtime_std_seconds=runtime_std,
            labels_hash=first.labels_hash,
            determinism_verified=determinism_verified,
            n_successful_repeats=len(successful),
            n_total_repeats=len(records),
            decision_status=decision_status,
            evidence_note=evidence_note,
        )
