"""CP-04 — Customer Profiles and Segment Naming.

CP-04 chuyển kết quả clustering từ EPIC-07/08 (CP-01/02/03 evidence)
thành Customer Profile có thể diễn giải được, và đặt tên segment dựa
trên observed evidence (RFM tiers + behavioural modifiers).

CP-04 sử dụng trực tiếp evidence surface đã có:

- CP-01 cluster size table.
- CP-02 feature profile + relative comparison + behavioural
  interpretation.
- CP-03 segment comparison matrix + distinguishing features + IQR
  overlap with OVERALL.

CP-04 KHÔNG recompute cluster statistics. Mọi giá trị numeric đều
truy ngược được về CP-01/02/03 source artefacts.

Hard constraints (AGENTS.md §2):
- Read-only đối với tất cả source artefacts.
- KHÔNG ranking algorithm / cluster / "best algorithm".
- KHÔNG đặt tên segment nếu evidence không support semantics đó
  (NO marketing terms: "loyal", "champion", "VIP", "at-risk", ...).
- KHÔNG đưa ra Marketing Recommendation (CP-05 territory).
- KHÔNG gộp cluster labels giữa các algorithm / condition khác nhau.
- KHÔNG rerun EXP-03 để tạo profiles giả.
- DBSCAN noise tách riêng; KHÔNG coi noise là Customer Segment;
  KHÔNG đặt tên cho noise.
- EXP-03 working-selected profiles = ``NOT_AVAILABLE`` (per
  `EV03-HP-01`).
- CancellationRate / ReturnRate (``NOT_ASSESSABLE`` ở CP-03 do
  ZERO_REFERENCE) KHÔNG được dùng làm primary naming evidence.
- AverageQuantity ↔ BasketSize redundant (Pearson = 1.0 per FE-06);
  KHÔNG dùng cả hai như hai evidence độc lập.
- PurchaseIntervalMean / Std có structural NaN; NaN KHÔNG được diễn
  giải như quan sát trực tiếp.
- K-Medoids OUT OF SCOPE (per ADR-0003).
- Sử dụng RAW interpretable feature values từ FE-05 output (qua
  CP-02); KHÔNG dùng Yeo-Johnson + RobustScaler values.

Submodules
----------
- :mod:`customer_segmentation.profiling.cp04.provenance`
    Resolution of analysis units + load CP-01/02/03 evidence.
- :mod:`customer_segmentation.profiling.cp04.naming`
    Segment naming framework (RFM tiers + behavioural modifiers).
- :mod:`customer_segmentation.profiling.cp04.profile_builder`
    Build SegmentProfile objects aggregating CP-01/02/03 evidence.
- :mod:`customer_segmentation.profiling.cp04.report`
    Markdown report builder.
- :mod:`customer_segmentation.profiling.cp04.runner`
    Top-level orchestration.
"""

from customer_segmentation.profiling.cp04.naming import (
    NAMING_FEATURES,
    SegmentName,
    compute_all_segment_names,
    compute_segment_name,
)
from customer_segmentation.profiling.cp04.profile_builder import (
    FeatureSummary,
    IqrOverlapSummary,
    SegmentProfile,
    build_all_segment_profiles,
    evidence_rows_to_dicts,
    segment_profiles_to_dicts,
    segment_profiles_to_summary_dicts,
)
from customer_segmentation.profiling.cp04.provenance import (
    CP01_SIZE_TABLE,
    CP02_BEHAVIORAL,
    CP02_FEATURE_PROFILE,
    CP02_RELATIVE,
    CP02_UNIT_PROV,
    CP03_COMPARISON,
    CP03_DISTINGUISHING,
    CP03_OVERLAP,
    CP03_UNIT_PROV,
    Cp04AnalysisUnit,
    build_cp04_analysis_units,
    get_cp04_artifact_shas,
)
from customer_segmentation.profiling.cp04.report import (
    Cp04ReportContext,
    build_cp04_markdown,
)
from customer_segmentation.profiling.cp04.runner import (
    DEFAULT_OUTPUT_DIR,
    Cp04Runner,
    run_cp04,
)

__all__ = [
    # Runner
    "Cp04Runner",
    "run_cp04",
    "DEFAULT_OUTPUT_DIR",
    # Provenance
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
    # Naming
    "SegmentName",
    "compute_segment_name",
    "compute_all_segment_names",
    "NAMING_FEATURES",
    # Profile builder
    "FeatureSummary",
    "IqrOverlapSummary",
    "SegmentProfile",
    "build_all_segment_profiles",
    "segment_profiles_to_dicts",
    "segment_profiles_to_summary_dicts",
    "evidence_rows_to_dicts",
    # Report
    "Cp04ReportContext",
    "build_cp04_markdown",
]
