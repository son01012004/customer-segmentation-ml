"""CP-04 input provenance.

CP-04 reuses analysis units from CP-01/CP-02 (identical to CP-03),
plus evidence from CP-01/CP-02/CP-03 artifacts.

Analysis units
---------------

CP-04 inherits the same 10 analysis units (5 algorithms × 2 conditions)
as CP-01 / CP-02 / CP-03. Only the 5 EXP-01 working-default units
have per-customer labels for segment profiling.

Evidence sources
---------------

CP-04 does NOT recompute cluster statistics or distinguishing
indicators. It aggregates evidence from:

- ``reports/profiling/cp01/cp01_cluster_size_table.csv`` — customer count,
  percentage, relative size per (unit, cluster).
- ``reports/profiling/cp02/cp02_feature_profile_table.csv`` — per-cluster
  feature statistics (mean, median, P25, P75, ...).
- ``reports/profiling/cp02/cp02_relative_comparison.csv`` — relative
  difference vs OVERALL median.
- ``reports/profiling/cp02/cp02_behavioral_interpretation.csv`` — direction
  (HIGHER / LOWER / COMPARABLE) per (unit, cluster, feature).
- ``reports/profiling/cp03/cp03_segment_comparison_matrix.csv`` — combined
  cluster-level stats + OVERALL + IQR overlap with population.
- ``reports/profiling/cp03/cp03_distinguishing_features.csv`` — per-(unit,
  feature) effect_range, IQR overlap, classification.
- ``reports/profiling/cp03/cp03_overlap_analysis.csv`` — pairwise IQR overlap
  between clusters.

Hard constraints (AGENTS.md §2):

- Read-only against all source artifacts.
- No algorithm ranking / "best algorithm".
- No segment naming unless evidence supports it.
- No Marketing recommendation.
- No rerun of experiments.
- DBSCAN noise is NOT a customer segment.
- EXP-03 working-selected units = ``NOT_AVAILABLE``.
- K-Medoids OUT OF SCOPE (per ADR-0003).
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

# Path to source artifacts.
CP01_SIZE_TABLE = Path("reports/profiling/cp01/cp01_cluster_size_table.csv")
CP02_FEATURE_PROFILE = Path("reports/profiling/cp02/cp02_feature_profile_table.csv")
CP02_RELATIVE = Path("reports/profiling/cp02/cp02_relative_comparison.csv")
CP02_BEHAVIORAL = Path("reports/profiling/cp02/cp02_behavioral_interpretation.csv")
CP02_UNIT_PROV = Path("reports/profiling/cp02/cp02_unit_provenance.csv")
CP03_COMPARISON = Path("reports/profiling/cp03/cp03_segment_comparison_matrix.csv")
CP03_DISTINGUISHING = Path("reports/profiling/cp03/cp03_distinguishing_features.csv")
CP03_OVERLAP = Path("reports/profiling/cp03/cp03_overlap_analysis.csv")
CP03_UNIT_PROV = Path("reports/profiling/cp03/cp03_unit_provenance.csv")


@dataclass(frozen=True)
class Cp04AnalysisUnit:
    """A self-contained analysis unit for CP-04.

    Wraps provenance metadata and the loaded evidence DataFrames
    from CP-01 / CP-02 / CP-03.
    """

    unit_id: str
    algorithm: str
    source_experiment: str
    configuration_id: str
    configuration_status: str
    labels_persisted: bool
    n_customers_eligible: int

    # Loaded evidence DataFrames.
    # For EXP-03 units (labels_persisted=False): these are empty/None.
    cluster_sizes: pd.DataFrame = field(repr=False, default_factory=pd.DataFrame)
    feature_profiles: pd.DataFrame = field(repr=False, default_factory=pd.DataFrame)
    relative_comparison: pd.DataFrame = field(repr=False, default_factory=pd.DataFrame)
    behavioral_interp: pd.DataFrame = field(repr=False, default_factory=pd.DataFrame)
    cp03_comparison: pd.DataFrame = field(repr=False, default_factory=pd.DataFrame)
    cp03_distinguishing: pd.DataFrame = field(repr=False, default_factory=pd.DataFrame)
    cp03_overlap: pd.DataFrame = field(repr=False, default_factory=pd.DataFrame)


def _load_cp01_sizes(path: Path, unit_id: str) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    return df[df["unit_id"] == unit_id].copy()


def _load_cp02_feature_profiles(path: Path, unit_id: str) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    return df[df["unit_id"] == unit_id].copy()


def _load_cp02_relative(path: Path, unit_id: str) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    return df[df["unit_id"] == unit_id].copy()


def _load_cp02_behavioral(path: Path, unit_id: str) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    return df[df["unit_id"] == unit_id].copy()


def _load_cp03_comparison(path: Path, unit_id: str) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    return df[df["unit_id"] == unit_id].copy()


def _load_cp03_distinguishing(path: Path, unit_id: str) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    return df[df["unit_id"] == unit_id].copy()


def _load_cp03_overlap(path: Path, unit_id: str) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    return df[df["unit_id"] == unit_id].copy()


def build_cp04_analysis_units(repo_root: Path) -> list[Cp04AnalysisUnit]:
    """Build CP-04 analysis units from CP-02 provenance + CP-01/02/03 artifacts.

    Returns a list of :class:`Cp04AnalysisUnit`, one per algorithm × condition.
    Only the 5 EXP-01 units carry actual evidence DataFrames. EXP-03 units
    return empty DataFrames and are marked ``labels_persisted=False``.

    CP-04 does NOT recompute cluster statistics. All evidence is read
    directly from the CP-01/02/03 CSV artifacts.
    """
    cp02_prov_path = repo_root / CP02_UNIT_PROV
    if not cp02_prov_path.exists():
        raise FileNotFoundError(f"CP-02 provenance not found: {cp02_prov_path}")

    cp02_prov = pd.read_csv(cp02_prov_path)
    cp01_path = repo_root / CP01_SIZE_TABLE
    cp02_fp_path = repo_root / CP02_FEATURE_PROFILE
    cp02_rel_path = repo_root / CP02_RELATIVE
    cp02_beh_path = repo_root / CP02_BEHAVIORAL
    cp03_cmp_path = repo_root / CP03_COMPARISON
    cp03_dis_path = repo_root / CP03_DISTINGUISHING
    cp03_ov_path = repo_root / CP03_OVERLAP

    units: list[Cp04AnalysisUnit] = []
    for _, row in cp02_prov.iterrows():
        uid = str(row["unit_id"])
        unit = Cp04AnalysisUnit(
            unit_id=uid,
            algorithm=str(row["algorithm"]),
            source_experiment=str(row["source_experiment"]),
            configuration_id=str(row["configuration_id"]),
            configuration_status=str(row["configuration_status"]),
            labels_persisted=bool(row["labels_persisted"]),
            n_customers_eligible=int(row["n_customers_eligible"]),
            cluster_sizes=_load_cp01_sizes(cp01_path, uid),
            feature_profiles=_load_cp02_feature_profiles(cp02_fp_path, uid),
            relative_comparison=_load_cp02_relative(cp02_rel_path, uid),
            behavioral_interp=_load_cp02_behavioral(cp02_beh_path, uid),
            cp03_comparison=_load_cp03_comparison(cp03_cmp_path, uid),
            cp03_distinguishing=_load_cp03_distinguishing(cp03_dis_path, uid),
            cp03_overlap=_load_cp03_overlap(cp03_ov_path, uid),
        )
        units.append(unit)
    return units


def _artifact_sha256(path: Path) -> str | None:
    """Return SHA-256 of a file, or None if missing."""
    if not path.exists():
        return None
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def get_cp04_artifact_shas(repo_root: Path) -> Mapping[str, str | None]:
    """Return SHA-256 for all CP-01/02/03 artifacts used by CP-04."""
    base = repo_root
    return {
        "cp01_cluster_size_table": _artifact_sha256(base / CP01_SIZE_TABLE),
        "cp02_feature_profile": _artifact_sha256(base / CP02_FEATURE_PROFILE),
        "cp02_relative_comparison": _artifact_sha256(base / CP02_RELATIVE),
        "cp02_behavioral_interpretation": _artifact_sha256(base / CP02_BEHAVIORAL),
        "cp02_unit_provenance": _artifact_sha256(base / CP02_UNIT_PROV),
        "cp03_segment_comparison_matrix": _artifact_sha256(base / CP03_COMPARISON),
        "cp03_distinguishing_features": _artifact_sha256(base / CP03_DISTINGUISHING),
        "cp03_overlap_analysis": _artifact_sha256(base / CP03_OVERLAP),
        "cp03_unit_provenance": _artifact_sha256(base / CP03_UNIT_PROV),
    }


__all__ = [
    "Cp04AnalysisUnit",
    "build_cp04_analysis_units",
    "get_cp04_artifact_shas",
    "CP01_SIZE_TABLE",
    "CP02_FEATURE_PROFILE",
    "CP02_RELATIVE",
    "CP02_BEHAVIORAL",
    "CP02_UNIT_PROV",
    "CP03_COMPARISON",
    "CP03_DISTINGUISHING",
    "CP03_OVERLAP",
    "CP03_UNIT_PROV",
]
