"""CP-05 — Segment Interpretability & Business Relevance Evaluation.

CP-05 đánh giá **khả năng diễn giải** và **khả năng ứng dụng phân tích**
của các Customer Segment hiện có, dựa trên evidence surface đã được
CP-01 → CP-04 (và EXP-05) sản xuất ra.

CP-05 KHÔNG recompute cluster statistics, KHÔNG fit lại model, KHÔNG
ranking algorithm, KHÔNG đặt tên segment mới, KHÔNG marketing
recommendation.

CP-05 sử dụng trực tiếp evidence surface đã có:

- CP-01 cluster size table + noise summary + distribution indicators.
- CP-02 feature profile + relative comparison + behavioural
  interpretation.
- CP-03 segment comparison matrix + distinguishing features + IQR
  overlap with OVERALL.
- CP-04 segment profiles + naming + evidence + naming rationale.
- EXP-05 reproducibility + seed sweep + noise perturbation
  (read-only; KHÔNG compute ARI/AMI).

Hard constraints (AGENTS.md §2):

- Read-only đối với tất cả source artefacts.
- KHÔNG ranking algorithm / cluster / "best algorithm".
- KHÔNG đặt tên segment ngoài CP-04 naming framework.
- KHÔNG marketing recommendation, campaign, action plan.
- KHÔNG suy diễn CLV/LTV/loyalty/churn/purchase probability.
- KHÔNG compute ARI/AMI/NMI/Hungarian.
- KHÔNG gộp cluster labels giữa các algorithm / condition khác nhau.
- KHÔNG rerun EXP-03 để tạo profiles giả.
- DBSCAN noise tách riêng; KHÔNG coi noise là Customer Segment.
- EXP-03 working-selected profiles = ``NOT_AVAILABLE``.
- CancellationRate / ReturnRate (``NOT_ASSESSABLE`` ở CP-03) KHÔNG
  được dùng làm business interpretation evidence.
- AverageQuantity ↔ BasketSize redundant (Pearson = 1.0 per FE-06);
  KHÔNG dùng cả hai như hai evidence độc lập.
- K-Medoids OUT OF SCOPE (per ADR-0003).
- Sử dụng RAW interpretable feature values từ FE-05 output (qua
  CP-02); KHÔNG dùng Yeo-Johnson + RobustScaler values.

Submodules
----------
- :mod:`customer_segmentation.profiling.cp05.provenance`
    Resolution of analysis units + load CP-01/02/03/04/EXP-05 evidence.
- :mod:`customer_segmentation.profiling.cp05.size_evaluation`
    Segment size evaluation (per §8).
- :mod:`customer_segmentation.profiling.cp05.distinctiveness`
    Distinctiveness evaluation (per §5).
- :mod:`customer_segmentation.profiling.cp05.interpretability`
    Interpretability evaluation (per §6).
- :mod:`customer_segmentation.profiling.cp05.consistency`
    Behavioral consistency evaluation (per §7).
- :mod:`customer_segmentation.profiling.cp05.stability`
    Stability evidence evaluation (per §9; KHÔNG compute ARI/AMI).
- :mod:`customer_segmentation.profiling.cp05.business_relevance`
    Business relevance evaluation (per §10).
- :mod:`customer_segmentation.profiling.cp05.final_definition`
    Final Segment Definition builder (per §11).
- :mod:`customer_segmentation.profiling.cp05.report`
    Markdown report builder.
- :mod:`customer_segmentation.profiling.cp05.runner`
    Top-level orchestration.
"""

from customer_segmentation.profiling.cp05.business_relevance import (
    BusinessRelevanceResult,
    evaluate_business_relevance,
)
from customer_segmentation.profiling.cp05.consistency import (
    ConsistencyResult,
    evaluate_consistency,
)
from customer_segmentation.profiling.cp05.distinctiveness import (
    DistinctivenessResult,
    evaluate_distinctiveness,
)
from customer_segmentation.profiling.cp05.final_definition import (
    FinalSegmentDefinition,
    build_final_segment_definition,
)
from customer_segmentation.profiling.cp05.interpretability import (
    InterpretabilityResult,
    evaluate_interpretability,
)
from customer_segmentation.profiling.cp05.provenance import (
    Cp04EvidenceBundle,
    Cp05AnalysisUnit,
    build_cp05_analysis_units,
    get_cp05_artifact_shas,
)
from customer_segmentation.profiling.cp05.report import (
    Cp05ReportContext,
    build_cp05_markdown,
)
from customer_segmentation.profiling.cp05.runner import (
    DEFAULT_OUTPUT_DIR,
    Cp05Runner,
    run_cp05,
)
from customer_segmentation.profiling.cp05.size_evaluation import (
    SizeResult,
    evaluate_size,
)
from customer_segmentation.profiling.cp05.stability import (
    StabilityResult,
    evaluate_stability,
)

__all__ = [
    # Runner
    "Cp05Runner",
    "run_cp05",
    "DEFAULT_OUTPUT_DIR",
    # Provenance
    "Cp05AnalysisUnit",
    "Cp04EvidenceBundle",
    "build_cp05_analysis_units",
    "get_cp05_artifact_shas",
    # Evaluation axes
    "DistinctivenessResult",
    "evaluate_distinctiveness",
    "InterpretabilityResult",
    "evaluate_interpretability",
    "ConsistencyResult",
    "evaluate_consistency",
    "SizeResult",
    "evaluate_size",
    "StabilityResult",
    "evaluate_stability",
    "BusinessRelevanceResult",
    "evaluate_business_relevance",
    # Final definition
    "FinalSegmentDefinition",
    "build_final_segment_definition",
    # Report
    "Cp05ReportContext",
    "build_cp05_markdown",
]
