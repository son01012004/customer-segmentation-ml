"""CP-01 input provenance resolution.

CP-01 consumes cluster-assignment artifacts produced by EPIC-07
(EXP-01 working defaults) and reuses the EXP-03 working-selected
configuration metadata from `exp03_selected_configurations.csv`. Each
input is described as an "analysis unit" with explicit provenance
fields so downstream analysis can be traced back to its source.

Analysis units
--------------

Two per-algorithm × condition slices are constructed:

1. ``EXP-01 working-default`` — the control / baseline condition.
   - One row per algorithm (kmeans, agglomerative, dbscan, gmm,
     fuzzy_cmeans).
   - DBSCAN noise label (-1) is treated separately as ``noise_count``.
   - Per-customer labels parquet exists in ``reports/exp01/`` and is
     loaded directly.
2. ``EXP-03 working-selected`` — the algorithm's working-selected
   configuration produced by EXP-03 Stage C / Stage B.
   - The configuration metadata (K, hyperparameters, decision status)
     is loaded from ``reports/03/exp03_selected_configurations.csv``.
   - PER-CUSTOMER LABELS ARE NOT PERSISTED in EXP-03 (recorded in
     ``EV03-HP-01``); CP-01 reports this as ``labels_persisted: False``
     and marks the size table row as ``NOT_AVAILABLE``. We DO NOT
     recompute labels, in order to:
       (a) honour AGENTS.md §2.1 ("do not invent data");
       (b) honour the user's "Ưu tiên sử dụng artifact đã tồn tại"
           instruction;
       (c) keep CP-01 read-only against the EPIC-07 source.

Each ``AnalysisUnit`` captures:

  - ``unit_id``               — stable identifier used in outputs.
  - ``algorithm``             — registry algorithm name.
  - ``algorithm_family``      — partition / hierarchical / density /
                                model / fuzzy.
  - ``source_experiment``     — EXP-01 or EXP-03.
  - ``configuration_id``      — source `experiment_id`.
  - ``configuration_status``  — verbatim `decision_status` string
                                (`WORKING_SELECTED`, `TIED_WORKING_SELECTED`,
                                ...).
  - ``random_seed``           — seed used for the run, if applicable.
  - ``n_clusters_requested``  — requested K (None for DBSCAN).
  - ``labels_persisted``      — whether per-customer labels parquet exists.
  - ``cluster_labels_frame``  — DataFrame[CustomerID, ClusterLabel, IsNoise]
                                if ``labels_persisted`` else empty.
  - ``n_customers_eligible``  — total customers considered (denominator).
  - ``source_path``           — artifact path.

Hard constraints (AGENTS.md §2):

- No mutation of EXP-01 / EXP-03 source artifacts.
- K-Medoids is OUT OF SCOPE → not present in any unit.
- DBSCAN noise (-1) is loaded as ``IsNoise=True``; it is NOT a segment.
- Each unit reads exactly ONE source artifact; nothing is merged across
  units.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

import pandas as pd

# Where EPIC-07 / EXP-01 / EXP-03 cluster-label artifacts live.
EXP01_DEFAULT_DIR = Path("reports/exp01")
EXP03_SELECTED_CONFIGURATIONS_CSV = Path("reports/exp03/exp03_selected_configurations.csv")
ALGORITHMS = ("kmeans", "agglomerative", "dbscan", "gmm", "fuzzy_cmeans")

ALGORITHM_FAMILY: Mapping[str, str] = {
    "kmeans": "partition",
    "agglomerative": "hierarchical",
    "dbscan": "density",
    "gmm": "model",
    "fuzzy_cmeans": "fuzzy",
}


@dataclass(frozen=True)
class AnalysisUnit:
    """A self-contained analysis unit (one algorithm × one condition).

    Required fields come first; defaulted fields after, so a frozen
    dataclass can be constructed with sensible defaults for the optional
    bookkeeping values.
    """

    unit_id: str
    algorithm: str
    algorithm_family: str
    source_experiment: str
    configuration_id: str
    configuration_status: str
    random_seed: int | None
    n_clusters_requested: int | None
    labels_persisted: bool
    cluster_labels_frame: pd.DataFrame = field(repr=False)
    source_path: Path = field(repr=False)
    n_customers_eligible: int = 0

    def labels_frame(self) -> pd.DataFrame:
        """Return the underlying labels frame (CustomerID-indexed)."""
        return self.cluster_labels_frame


def _load_exp01_unit(algorithm: str, repo_root: Path) -> AnalysisUnit:
    """Load the EXP-01 working-default labels for one algorithm."""
    path = repo_root / EXP01_DEFAULT_DIR / f"cluster_labels_EXP-01-{algorithm}_rep4.parquet"
    if not path.exists():
        raise FileNotFoundError(f"EXP-01 labels file missing: {path}")
    df = pd.read_parquet(path)
    required = {"CustomerID", "ClusterLabel", "IsNoise"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"EXP-01-{algorithm} labels file {path} missing required columns: {sorted(missing)}"
        )
    return AnalysisUnit(
        unit_id=f"EXP-01-{algorithm}-working-default",
        algorithm=algorithm,
        algorithm_family=ALGORITHM_FAMILY.get(algorithm, "unknown"),
        source_experiment="EXP-01",
        configuration_id=f"EXP-01-{algorithm}",
        configuration_status="WORKING_DEFAULT",
        random_seed=42,
        n_clusters_requested=4 if algorithm != "dbscan" else None,
        labels_persisted=True,
        cluster_labels_frame=df,
        n_customers_eligible=int(df["CustomerID"].nunique()),
        source_path=path,
    )


def _load_exp03_unit_metadata_only(algorithm: str, repo_root: Path) -> AnalysisUnit:
    """Load the EXP-03 working-selected *metadata*.

    Cluster sizes are NOT computed here because per-customer labels are
    not persisted by EXP-03 (see ``EV03-HP-01``).
    """
    selected_csv = repo_root / EXP03_SELECTED_CONFIGURATIONS_CSV
    if not selected_csv.exists():
        raise FileNotFoundError(f"EXP-03 selected configurations missing: {selected_csv}")
    configs = pd.read_csv(selected_csv)
    sub = configs[configs["algorithm"] == algorithm].copy()
    if sub.empty:
        raise FileNotFoundError(
            f"No EXP-03 working-selected configuration for algorithm={algorithm}."
        )
    cfg = sub.iloc[0]
    configuration_id = str(cfg["experiment_id"])
    configuration_status = str(cfg["decision_status"])
    hp_str = str(cfg.get("hyperparameters", "{}"))
    try:
        hp = json.loads(hp_str)
    except json.JSONDecodeError:
        hp = {}
    seed_val = hp.get("random_state") if algorithm in {"kmeans", "gmm", "fuzzy_cmeans"} else None
    placeholder = pd.DataFrame(columns=["CustomerID", "ClusterLabel", "IsNoise"])
    return AnalysisUnit(
        unit_id=f"EXP-03-{algorithm}-working-selected",
        algorithm=algorithm,
        algorithm_family=ALGORITHM_FAMILY.get(algorithm, "unknown"),
        source_experiment="EXP-03",
        configuration_id=configuration_id,
        configuration_status=configuration_status,
        random_seed=int(seed_val) if seed_val is not None else None,
        n_clusters_requested=int(cfg["n_clusters"]) if pd.notna(cfg.get("n_clusters")) else None,
        labels_persisted=False,
        cluster_labels_frame=placeholder,
        n_customers_eligible=0,
        source_path=selected_csv,
    )


def build_analysis_units(repo_root: Path) -> list[AnalysisUnit]:
    """Build the full set of analysis units (10 = 5 algorithms × 2 conditions)."""
    units: list[AnalysisUnit] = []
    for algo in ALGORITHMS:
        units.append(_load_exp01_unit(algo, repo_root))
        units.append(_load_exp03_unit_metadata_only(algo, repo_root))
    return units
