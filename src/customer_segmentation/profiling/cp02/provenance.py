"""CP-02 input provenance resolution.

CP-02 loads:

1. The cluster-label artifacts that CP-01 already uses
   (``reports/exp01/cluster_labels_EXP-01-{algo}_rep4.parquet``) — these
   provide the per-customer ClusterLabel used in EXP-01 working-default.
2. The RAW interpretable customer-level feature matrix from
   ``data/processed/customer_candidates.parquet`` — the 14-feature
   RFM + Extended representation **before** Yeo-Johnson / RobustScaler.

Why raw features (not the transformed matrix)?
- CP-02 describes BEHAVIOUR with values that a reader can interpret
  in business terms (e.g., "Monetary trung bình = 1,200 GBP").
- ``final_clustering_dataset.parquet`` contains Yeo-Johnson +
  RobustScaler values which are not interpretable in business units.
- We deliberately do NOT inverse-transform: the fitted pipeline
  (Yeo-Johnson + RobustScaler) is reversible, but a non-trivial
  inverse step is not part of CP-02 scope. Using the RAW matrix is
  the canonical interpretation surface that FE-05 / FE-06 already
  pinned.

Hard constraints (AGENTS.md §2):
- Read-only against FE-05 / FE-06 / EXP-01 / EXP-03 artifacts.
- DBSCAN noise (ClusterLabel == -1) is NOT profiled as a Customer
  Segment.
- Each analysis unit reads exactly ONE cluster-label artifact + ONE
  raw-feature matrix; nothing is merged across algorithms.
- EXP-03 working-selected labels are NOT persisted (per
  ``EV03-HP-01``); CP-02 reuses the same ``NOT_AVAILABLE`` handling
  as CP-01 — no rerun is performed.
- K-Medoids is OUT OF SCOPE per ADR-0003.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from customer_segmentation.profiling.cp01.provenance import (
    ALGORITHMS,
)
from customer_segmentation.profiling.cp01.provenance import (
    build_analysis_units as cp01_build_analysis_units,
)

# Path to the RAW customer-level feature matrix (pre-transformation).
# This is the canonical interpretation surface for CP-02.
RAW_FEATURES_PATH = Path("data/processed/customer_candidates.parquet")

# The 14 working features, in their canonical FE-05 / FE-06 order.
# This is the working representation locked by the methodology.
# Source: ``docs/research/FE05_Customer_Feature_Engineering.md`` +
# ``docs/research/FE06_Transformation_Final_Dataset.md``.
FEATURE_COLUMNS: tuple[str, ...] = (
    "Recency",
    "Frequency",
    "Monetary",
    "TotalQuantity",
    "AverageQuantity",
    "BasketSize",
    "TenureDays",
    "PurchaseIntervalMean",
    "PurchaseIntervalStd",
    "ActiveDays",
    "AverageInvoiceValue",
    "ProductsPerInvoice",
    "CancellationRate",
    "ReturnRate",
)


@dataclass(frozen=True)
class Cp02AnalysisUnit:
    """A self-contained analysis unit for CP-02.

    Wraps a CP-01 ``AnalysisUnit`` (which carries the persisted
    cluster-label frame) with the joined RAW feature frame so
    downstream modules can compute per-(cluster, feature) statistics
    without reloading the RAW matrix.

    Attributes
    ----------
    unit_id : str
        Stable identifier — same naming convention as CP-01.
    algorithm : str
        Registry algorithm name (kmeans, agglomerative, dbscan, ...).
    source_experiment : str
        "EXP-01" or "EXP-03".
    configuration_id : str
        Source experiment_id.
    configuration_status : str
        Verbatim ``decision_status`` (e.g., ``WORKING_DEFAULT``).
    labels_persisted : bool
        Whether per-customer cluster labels parquet exists.
    cluster_labels_frame : pd.DataFrame
        CustomerID-indexed cluster-label frame (from CP-01 source).
    raw_features_frame : pd.DataFrame
        CustomerID-indexed RAW (pre-transformation) feature frame.
        Always present for CP-02 (needed to compute statistics),
        even when ``labels_persisted is False`` (so report can
        still cite the population reference).
    n_customers_eligible : int
        Total number of unique CustomerIDs considered.
    """

    unit_id: str
    algorithm: str
    source_experiment: str
    configuration_id: str
    configuration_status: str
    labels_persisted: bool
    cluster_labels_frame: pd.DataFrame = field(repr=False)
    raw_features_frame: pd.DataFrame = field(repr=False)
    n_customers_eligible: int = 0

    @property
    def is_persistable(self) -> bool:
        """Whether this unit has labels we can profile (vs EXP-03 metadata-only)."""
        return self.labels_persisted


def load_raw_customer_features(repo_root: Path) -> pd.DataFrame:
    """Load the RAW customer-level feature matrix.

    Returns a DataFrame indexed by ``CustomerID`` with the 14 canonical
    FE-05 features as columns. Missing values are kept as ``NaN`` —
    they are reported per-(cluster, feature) and never silently
    imputed by CP-02.

    Raises
    ------
    FileNotFoundError
        If ``customer_candidates.parquet`` is missing.
    ValueError
        If required feature columns are missing.
    """
    path = repo_root / RAW_FEATURES_PATH
    if not path.exists():
        raise FileNotFoundError(f"RAW features file missing: {path}")
    df = pd.read_parquet(path)
    if "CustomerID" not in df.columns:
        raise ValueError(f"{path} missing CustomerID column")
    missing_features = [c for c in FEATURE_COLUMNS if c not in df.columns]
    if missing_features:
        raise ValueError(f"{path} missing required feature columns: {missing_features}")
    # Keep CustomerID + 14 features; deduplicate defensively.
    keep_cols = ["CustomerID", *FEATURE_COLUMNS]
    df = df.loc[:, keep_cols].copy()
    df = df.drop_duplicates(subset=["CustomerID"], keep="first")
    return df.set_index("CustomerID")


def _join_labels_with_features(labels: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    """Left-join labels onto features by CustomerID.

    Both frames are indexed by CustomerID. The resulting frame
    contains all feature columns + ClusterLabel + IsNoise. CustomerIDs
    present in features but missing from labels are dropped (they are
    not eligible for this analysis unit). CustomerIDs present in
    labels but missing from features are dropped (data inconsistency).

    The result is sorted by CustomerID for determinism.
    """
    if "CustomerID" in labels.columns:
        labels_indexed = labels.set_index("CustomerID")
    else:
        labels_indexed = labels.copy()
    joined = features.join(labels_indexed[["ClusterLabel", "IsNoise"]], how="inner")
    # Drop any row with NaN ClusterLabel
    joined = joined.dropna(subset=["ClusterLabel"])
    joined["ClusterLabel"] = joined["ClusterLabel"].astype(int)
    joined["IsNoise"] = joined["IsNoise"].astype(bool)
    joined = joined.sort_index().reset_index()
    return joined


def build_cp02_analysis_units(repo_root: Path) -> list[Cp02AnalysisUnit]:
    """Build the full set of CP-02 analysis units.

    Reuses CP-01's analysis-unit construction so the analysis units
    stay aligned (same unit_id, same algorithm, same condition).

    For each analysis unit:

    - If labels are persisted: load the cluster-label frame, join
      with the RAW feature frame by CustomerID, build a
      ``Cp02AnalysisUnit`` carrying both frames.
    - If labels are NOT persisted (EXP-03 working-selected): build
      a ``Cp02AnalysisUnit`` with an empty labels frame; downstream
      code will report this unit as ``NOT_AVAILABLE`` for cluster
      profiles, but the RAW feature frame is still attached so the
      runner can record the population reference for the report.

    Returns a list of ``Cp02AnalysisUnit``, one per algorithm × condition.
    """
    raw_features = load_raw_customer_features(repo_root)
    cp01_units = cp01_build_analysis_units(repo_root)
    out: list[Cp02AnalysisUnit] = []
    for u in cp01_units:
        if u.labels_persisted:
            labels_df = u.cluster_labels_frame.copy()
            joined = _join_labels_with_features(labels_df, raw_features)
            n_eligible = int(joined["CustomerID"].nunique())
            out.append(
                Cp02AnalysisUnit(
                    unit_id=u.unit_id,
                    algorithm=u.algorithm,
                    source_experiment=u.source_experiment,
                    configuration_id=u.configuration_id,
                    configuration_status=u.configuration_status,
                    labels_persisted=True,
                    cluster_labels_frame=joined,
                    raw_features_frame=raw_features,
                    n_customers_eligible=n_eligible,
                )
            )
        else:
            placeholder = pd.DataFrame(
                columns=["CustomerID", *FEATURE_COLUMNS, "ClusterLabel", "IsNoise"]
            )
            out.append(
                Cp02AnalysisUnit(
                    unit_id=u.unit_id,
                    algorithm=u.algorithm,
                    source_experiment=u.source_experiment,
                    configuration_id=u.configuration_id,
                    configuration_status=u.configuration_status,
                    labels_persisted=False,
                    cluster_labels_frame=placeholder,
                    raw_features_frame=raw_features,
                    n_customers_eligible=0,
                )
            )
    return out


__all__ = [
    "Cp02AnalysisUnit",
    "build_cp02_analysis_units",
    "load_raw_customer_features",
    "FEATURE_COLUMNS",
    "RAW_FEATURES_PATH",
    "ALGORITHMS",
]
