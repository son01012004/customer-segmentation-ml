"""CP-05 provenance — resolve analysis units + load evidence from CP-01 → CP-04 + EXP-05.

CP-05 KHÔNG tạo analysis unit mới. CP-05 kế thừa trực tiếp 10 analysis
units từ CP-04 ``cp04_unit_provenance.csv`` (5 algorithms × 2
conditions).
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

LOGGER = logging.getLogger(__name__)

DEFAULT_CP04_OUTPUT_DIR = Path("reports/profiling/cp04")
DEFAULT_CP01_OUTPUT_DIR = Path("reports/profiling/cp01")
DEFAULT_CP02_OUTPUT_DIR = Path("reports/profiling/cp02")
DEFAULT_CP03_OUTPUT_DIR = Path("reports/profiling/cp03")
DEFAULT_EXP05_OUTPUT_DIR = Path("reports/exp05")

# Inherited status taxonomy from CP-04.
ALLOWED_CONFIGURATION_STATUSES = frozenset(
    {
        "WORKING_DEFAULT",
        "WORKING_SELECTED",
        "TIED_WORKING_SELECTED",
    }
)


@dataclass(frozen=True)
class Cp05AnalysisUnit:
    """Một analysis unit kế thừa trực tiếp từ CP-04.

    Attributes
    ----------
    unit_id : str
        Ví dụ: ``EXP-01-kmeans-working-default``.
    algorithm : str
        Tên thuật toán (``kmeans`` / ``agglomerative`` / ``dbscan`` /
        ``gmm`` / ``fuzzy_cmeans``).
    source_experiment : str
        ``EXP-01`` hoặc ``EXP-03``.
    configuration_status : str
        Verbatim từ CP-04 (``WORKING_DEFAULT`` /
        ``WORKING_SELECTED`` / ``TIED_WORKING_SELECTED``).
    labels_persisted : bool
        True nếu EXP-01; False nếu EXP-03 (per ``EV03-HP-01``).
    n_customers_eligible : int
        Số customers thuộc analysis unit (4,371 cho EXP-01; 0 cho
        EXP-03).
    """

    unit_id: str
    algorithm: str
    source_experiment: str
    configuration_status: str
    labels_persisted: bool
    n_customers_eligible: int


@dataclass
class Cp04EvidenceBundle:
    """Tập CP-01 → CP-04 evidence đã load cho một analysis unit.

    Attributes
    ----------
    unit : Cp05AnalysisUnit
    size_df : pd.DataFrame
        Cluster-size table từ CP-01 (per-cluster n_customers,
        pct_of_assigned, pct_of_total, relative_size_ratio).
    noise_df : pd.DataFrame | None
        Noise summary từ CP-01 (chỉ DBSCAN có).
    feature_profile_df : pd.DataFrame | None
        Per-(cluster, feature) statistics từ CP-02.
    relative_df : pd.DataFrame | None
        Relative comparison từ CP-02.
    behavioral_df : pd.DataFrame | None
        Behavioral interpretation từ CP-02.
    comparison_df : pd.DataFrame | None
        Segment comparison matrix từ CP-03.
    distinguishing_df : pd.DataFrame | None
        Distinguishing features từ CP-03.
    overlap_df : pd.DataFrame | None
        Pairwise IQR overlap từ CP-03.
    naming_df : pd.DataFrame | None
        Segment naming từ CP-04.
    profile_df : pd.DataFrame | None
        Segment profiles từ CP-04.
    evidence_df : pd.DataFrame | None
        Per-(profile, feature) evidence từ CP-04.
    """

    unit: Cp05AnalysisUnit
    size_df: pd.DataFrame
    noise_df: pd.DataFrame | None
    feature_profile_df: pd.DataFrame | None = None
    relative_df: pd.DataFrame | None = None
    behavioral_df: pd.DataFrame | None = None
    comparison_df: pd.DataFrame | None = None
    distinguishing_df: pd.DataFrame | None = None
    overlap_df: pd.DataFrame | None = None
    naming_df: pd.DataFrame | None = None
    profile_df: pd.DataFrame | None = None
    evidence_df: pd.DataFrame | None = None


def _sha256_file(path: Path) -> str:
    """Compute SHA-256 của một file."""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _read_csv_if_exists(path: Path) -> pd.DataFrame | None:
    """Đọc CSV nếu tồn tại, ngược lại trả về None."""
    if not path.exists():
        return None
    return pd.read_csv(path)


def build_cp05_analysis_units(
    cp04_unit_provenance_csv: Path,
) -> list[Cp05AnalysisUnit]:
    """Build 10 analysis units kế thừa từ CP-04.

    Parameters
    ----------
    cp04_unit_provenance_csv : Path
        Path tới ``cp04_unit_provenance.csv``.

    Returns
    -------
    list[Cp05AnalysisUnit]
        Danh sách 10 analysis units, sorted theo ``unit_id``.

    Raises
    ------
    ValueError
        Nếu thiếu algorithms hoặc có K-Medoids (per ADR-0003).
    """
    df = pd.read_csv(cp04_unit_provenance_csv)
    algorithms = set(df["algorithm"].unique())
    expected = {"kmeans", "agglomerative", "dbscan", "gmm", "fuzzy_cmeans"}
    missing = expected - algorithms
    if missing:
        raise ValueError(f"Missing algorithms in CP-04 provenance: {missing}")
    forbidden = algorithms - expected
    if forbidden:
        raise ValueError(f"Forbidden algorithms detected (K-Medoids? per ADR-0003): {forbidden}")

    units: list[Cp05AnalysisUnit] = []
    for _, row in df.iterrows():
        config_status = str(row["configuration_status"])
        if config_status not in ALLOWED_CONFIGURATION_STATUSES:
            raise ValueError(
                f"Unexpected configuration_status '{config_status}' for unit " f"'{row['unit_id']}'"
            )
        units.append(
            Cp05AnalysisUnit(
                unit_id=str(row["unit_id"]),
                algorithm=str(row["algorithm"]),
                source_experiment=str(row["source_experiment"]),
                configuration_status=config_status,
                labels_persisted=bool(row["labels_persisted"]),
                n_customers_eligible=int(row["n_customers_eligible"]),
            )
        )
    units.sort(key=lambda u: u.unit_id)
    LOGGER.info("CP-05 built %d analysis units", len(units))
    return units


def load_cp04_evidence_for_unit(
    unit: Cp05AnalysisUnit,
    *,
    cp01_dir: Path,
    cp02_dir: Path,
    cp03_dir: Path,
    cp04_dir: Path,
) -> Cp04EvidenceBundle:
    """Load tất cả CP-01 → CP-04 evidence cho một analysis unit.

    KHÔNG mutate source artifacts. CHỈ đọc.

    Parameters
    ----------
    unit : Cp05AnalysisUnit
    cp01_dir, cp02_dir, cp03_dir, cp04_dir : Path
        Thư mục output tương ứng của CP-01 → CP-04.

    Returns
    -------
    Cp04EvidenceBundle
    """
    size_df = _read_csv_if_exists(cp01_dir / "cp01_cluster_size_table.csv")
    if size_df is None:
        raise FileNotFoundError(f"Missing cp01_cluster_size_table.csv in {cp01_dir}")
    size_df = size_df[size_df["unit_id"] == unit.unit_id].copy()

    noise_df = _read_csv_if_exists(cp01_dir / "cp01_noise_summary.csv")
    if noise_df is not None:
        noise_df = noise_df[noise_df["unit_id"] == unit.unit_id].copy()

    def _load_optional(path: Path) -> pd.DataFrame | None:
        df = _read_csv_if_exists(path)
        if df is None:
            return None
        if "unit_id" in df.columns:
            df = df[df["unit_id"] == unit.unit_id].copy()
        return df

    return Cp04EvidenceBundle(
        unit=unit,
        size_df=size_df,
        noise_df=noise_df,
        feature_profile_df=_load_optional(cp02_dir / "cp02_feature_profile_table.csv"),
        relative_df=_load_optional(cp02_dir / "cp02_relative_comparison.csv"),
        behavioral_df=_load_optional(cp02_dir / "cp02_behavioral_interpretation.csv"),
        comparison_df=_load_optional(cp03_dir / "cp03_segment_comparison_matrix.csv"),
        distinguishing_df=_load_optional(cp03_dir / "cp03_distinguishing_features.csv"),
        overlap_df=_load_optional(cp03_dir / "cp03_overlap_analysis.csv"),
        naming_df=_load_optional(cp04_dir / "cp04_segment_naming.csv"),
        profile_df=_load_optional(cp04_dir / "cp04_segment_profiles.csv"),
        evidence_df=_load_optional(cp04_dir / "cp04_segment_evidence.csv"),
    )


def get_cp05_artifact_shas(
    paths: Iterable[Path],
) -> dict[str, str]:
    """Compute SHA-256 cho mỗi file path (read-only manifest helper)."""
    out: dict[str, str] = {}
    for p in paths:
        if not p.exists():
            continue
        out[str(p)] = _sha256_file(p)
    return out
