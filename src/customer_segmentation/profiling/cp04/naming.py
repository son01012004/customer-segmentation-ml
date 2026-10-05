"""CP-04 segment naming framework.

Naming principles (from task brief §10-§12):
1. Names are short, evidence-based, and interpretable.
2. Names must traceable to feature evidence.
3. No over-inference (e.g., do not call a cluster "loyal" without
   evidence of repeat behaviour; do not call a cluster "high-value"
   without evidence of elevated Monetary).
4. Names are interpretive labels, NOT ground truth.
5. If evidence does NOT support a meaningful name: use a neutral
   descriptive label (e.g., "Comparative Segment A") with rationale
   explaining why.

Naming framework
------------------

The name is constructed from directional tiers derived from the
CP-03 segment comparison matrix + CP-02 behavioural interpretation.

Core tiers (RFM, always present):
  - RECENCY_TIER: "Recent" (Recency direction=LOWER) |
                   "Older" (Recency direction=HIGHER) |
                   "Mixed" (Recency direction=COMPARABLE or NA)
  - FREQUENCY_TIER: "Frequent" (Frequency direction=HIGHER) |
                     "Occasional" (Frequency direction=LOWER) |
                     "Mixed" (COMPARABLE or NA)
  - MONETARY_TIER: "HighValue" (Monetary direction=HIGHER) |
                   "LowValue" (Monetary direction=LOWER) |
                   "Mixed" (COMPARABLE or NA)

Behavioral modifiers (added when HIGH_DIFFERENCE_OBSERVED and
direction supports a distinct behavioural interpretation):
  - LONG_TENURED: TenureDays direction=HIGHER
  - ACTIVE: ActiveDays direction=HIGHER (HIGH_CORRELATION with
    Frequency 0.97; added only when direction differs from
    Frequency direction — e.g., Frequency=LOWER but ActiveDays=HIGHER)
  - BULK: TotalQuantity direction=HIGHER and Monetary direction=HIGHER
    (large purchases, high item count)
  - IRREGULAR: PurchaseIntervalStd direction=HIGHER (high cadence
    variability; purchase timing unpredictable)

Naming construction rules:
  1. Combine RECENCY_TIER + FREQUENCY_TIER as the core name.
  2. Add MONETARY_TIER if Monetary direction is different from
     Frequency direction (e.g., Frequent HighValue vs Frequent LowValue).
  3. Add behavioural modifier if it adds distinctiveness that the
     core name does not already convey.
  4. Keep total name to ≤ 4 words.
  5. For LOW_DIFFERENCE_OBSERVED or HIGH_OVERLAP clusters:
     use "Comparative Segment A/B/C" with explanation.
  6. For NOT_ASSESSABLE features: do NOT use them in naming.

Special cases:
  - Frequency and Monetary both LOW: name may omit monetary tier
    (low-frequency + low-monetary is already implied).
  - Frequency HIGH but Monetary LOW: "Frequent LowValue" is valid.
  - MONETARY tier added ONLY when it adds distinctiveness.

DBSCAN noise:
  - Noise is NOT a customer segment.
  - Do NOT name noise as "Lost", "Inactive", "Churned", etc.
  - Only the dominant non-noise cluster (n ≥ 20) may receive a
    descriptive name if CP-03 shows distinguishing features.
  - Clusters with n < 20 may receive a minimal label with
    "n=<N> customers" annotation.

EXP-03:
  - NOT_AVAILABLE; no naming performed.

Hard constraints (AGENTS.md §2):
- No marketing terms ("loyal", "at-risk", "vip", "champion", etc.)
  unless the data directly supports the behavioural interpretation.
- No over-inference.
- CancellationRate / ReturnRate (NOT_ASSESSABLE) must NOT be used
  in naming.
- AverageQuantity / BasketSize (HIGH_OVERLAP, redundant) must NOT
  be used as independent naming evidence.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from customer_segmentation.profiling.cp03.comparison import (
    Cp03ComparisonRow,
)
from customer_segmentation.profiling.cp03.difference_analysis import (
    Cp03DistinguishingRow,
)
from customer_segmentation.profiling.cp04.provenance import Cp04AnalysisUnit

# Features that may be used in naming (excluding NOT_ASSESSABLE and
# redundant features).
NAMING_FEATURES = (
    "Recency",
    "Frequency",
    "Monetary",
    "TotalQuantity",
    "TenureDays",
    "ActiveDays",
    "PurchaseIntervalMean",
    "PurchaseIntervalStd",
)

# Behavioral modifier thresholds: feature must be HIGH_DIFFERENCE_OBSERVED
# in the distinguishing table AND direction=HIGHER.
# IRREGULAR uses PurchaseIntervalStd direction=HIGHER (not P25/P75 overlap).


@dataclass(frozen=True)
class SegmentName:
    """The computed name for one cluster."""

    unit_id: str
    algorithm: str
    source_experiment: str
    cluster_id: int
    cluster_label: str
    customer_count: int
    pct_of_assigned: float

    name: str
    recency_tier: str
    frequency_tier: str
    monetary_tier: str
    behavioral_modifier: str | None
    is_noise: bool
    is_not_available: bool
    naming_rationale: str
    supporting_evidence: str
    naming_status: str  # NAMED | COMPARATIVE | NOT_AVAILABLE | NOISE


def _get_cluster_directions(
    cmp_rows: Sequence[Cp03ComparisonRow],
) -> Mapping[str, str]:
    """Return feature → direction mapping from CP-03 comparison rows."""
    return {r.feature: r.direction for r in cmp_rows if r.feature in NAMING_FEATURES}


def _get_feature_rel_diff(cmp_rows: Sequence[Cp03ComparisonRow], feature: str) -> float | None:
    """Return rel_diff_median_pct for a feature, or None."""
    for r in cmp_rows:
        if r.feature == feature:
            return float(r.rel_diff_median_pct) if np.isfinite(r.rel_diff_median_pct) else None
    return None


def _get_distinguishing_classification(
    dist_rows: Sequence[Cp03DistinguishingRow], feature: str
) -> str | None:
    for r in dist_rows:
        if r.feature == feature:
            return r.classification
    return None


def _build_recency_tier(direction: str) -> str:
    if direction == "LOWER":
        return "Recent"
    if direction == "HIGHER":
        return "Older"
    return "Mixed"


def _build_frequency_tier(direction: str) -> str:
    if direction == "LOWER":
        return "Occasional"
    if direction == "HIGHER":
        return "Frequent"
    return "Mixed"


def _build_monetary_tier(direction: str) -> str:
    if direction == "LOWER":
        return "LowValue"
    if direction == "HIGHER":
        return "HighValue"
    return "Mixed"


def _build_behavioral_modifier(
    directions: Mapping[str, str],
    distinguishing: Mapping[str, str],
    recency_tier: str,
    frequency_tier: str,
) -> str | None:
    """Build a behavioural modifier string if evidence supports it.

    Rules:
    - LONG_TENURED: TenureDays direction=HIGHER AND
      TenureDays is HIGH_DIFFERENCE_OBSERVED in CP-03.
    - IRREGULAR: PurchaseIntervalStd direction=HIGHER AND
      PurchaseIntervalStd is HIGH_DIFFERENCE_OBSERVED.
      Note: HIGH PurchaseIntervalStd means HIGH variability in
      purchase cadence — cadence is less predictable.
    - BULK: TotalQuantity direction=HIGHER AND Monetary direction=HIGHER
      AND both HIGH_DIFFERENCE_OBSERVED. This indicates large
      purchases (many items per transaction).
    - ACTIVE: ActiveDays direction=HIGHER AND
      ActiveDays is HIGH_DIFFERENCE_OBSERVED AND
      Frequency direction != ActiveDays direction.
      (If both are HIGH, Frequency already implies active; ACTIVE
      modifier is only added when ActiveDays adds independent info.)

    Returns the first applicable modifier, or None.
    """
    tenure_dir = directions.get("TenureDays", "NA")
    tenure_cls = distinguishing.get("TenureDays", "NA")
    if tenure_dir == "HIGHER" and tenure_cls == "HIGH_DIFFERENCE_OBSERVED":
        return "LongTenured"

    pi_std_dir = directions.get("PurchaseIntervalStd", "NA")
    pi_std_cls = distinguishing.get("PurchaseIntervalStd", "NA")
    if pi_std_dir == "HIGHER" and pi_std_cls == "HIGH_DIFFERENCE_OBSERVED":
        return "IrregularCadence"

    tq_dir = directions.get("TotalQuantity", "NA")
    tq_cls = distinguishing.get("TotalQuantity", "NA")
    mon_dir = directions.get("Monetary", "NA")
    mon_cls = distinguishing.get("Monetary", "NA")
    if (
        tq_dir == "HIGHER"
        and tq_cls == "HIGH_DIFFERENCE_OBSERVED"
        and mon_dir == "HIGHER"
        and mon_cls == "HIGH_DIFFERENCE_OBSERVED"
    ):
        return "Bulk"

    active_dir = directions.get("ActiveDays", "NA")
    active_cls = distinguishing.get("ActiveDays", "NA")
    freq_dir = directions.get("Frequency", "NA")
    if (
        active_dir == "HIGHER"
        and active_cls == "HIGH_DIFFERENCE_OBSERVED"
        and freq_dir != active_dir
    ):
        return "Active"

    return None


def _build_name_parts(
    recency_tier: str,
    frequency_tier: str,
    monetary_tier: str,
    modifier: str | None,
) -> list[str]:
    """Assemble name parts into a display name.

    Construction:
    1. RECENCY_TIER (always first)
    2. FREQUENCY_TIER (always second)
    3. MONETARY_TIER if distinct from frequency (e.g., Frequent HighValue
       vs Frequent LowValue — only added if different from what
       frequency already implies)
    4. behavioural modifier (last)

    Skip monetary if it is the same direction as frequency and the
    cluster is not clearly "high-value" in absolute terms.
    For example: if Frequency=LOWER and Monetary=LOWER, "Occasional LowValue"
    is more informative than just "Occasional"; if Frequency=HIGHER and
    Monetary=HIGHER, "Frequent HighValue" is more informative.
    If Frequency=HIGHER and Monetary=LOWER, both tiers are included.
    """
    parts = [recency_tier, frequency_tier]

    # Add monetary tier if it adds distinctiveness:
    # - Include if Monetary direction != Frequency direction.
    # - Include if both are HIGH (strong high-value signal).
    freq_val = (
        1 if frequency_tier in ("Frequent",) else (-1 if frequency_tier == "Occasional" else 0)
    )
    mon_val = 1 if monetary_tier == "HighValue" else (-1 if monetary_tier == "LowValue" else 0)
    if mon_val != 0 and (mon_val != freq_val or (mon_val == 1 and freq_val == 1)):
        parts.append(monetary_tier)

    if modifier:
        parts.append(modifier)

    return parts


def compute_segment_name(
    unit: Cp04AnalysisUnit,
    cluster_id: int,
    cluster_label: str,
    customer_count: int,
    pct_of_assigned: float,
) -> SegmentName:
    """Compute the segment name and supporting evidence for one cluster.

    This function reads from the unit's pre-loaded CP-03 comparison and
    distinguishing DataFrames. For EXP-03 units (labels_persisted=False),
    returns a NOT_AVAILABLE name.
    """
    if not unit.labels_persisted:
        return SegmentName(
            unit_id=unit.unit_id,
            algorithm=unit.algorithm,
            source_experiment=unit.source_experiment,
            cluster_id=-999,
            cluster_label="N/A",
            customer_count=0,
            pct_of_assigned=0.0,
            name="NOT_AVAILABLE — customer-level labels not persisted by EXP-03",
            recency_tier="NOT_AVAILABLE",
            frequency_tier="NOT_AVAILABLE",
            monetary_tier="NOT_AVAILABLE",
            behavioral_modifier=None,
            is_noise=False,
            is_not_available=True,
            naming_rationale=(
                "EXP-03 working-selected per-customer cluster labels are "
                "NOT persisted (per EV03-HP-01). CP-04 cannot construct "
                "segment profiles for EXP-03 units without labels."
            ),
            supporting_evidence="N/A",
            naming_status="NOT_AVAILABLE",
        )

    # Filter comparison rows for this cluster.
    cmp = unit.cp03_comparison
    dist = unit.cp03_distinguishing

    if cmp.empty:
        # No comparison data.
        return SegmentName(
            unit_id=unit.unit_id,
            algorithm=unit.algorithm,
            source_experiment=unit.source_experiment,
            cluster_id=cluster_id,
            cluster_label=cluster_label,
            customer_count=customer_count,
            pct_of_assigned=pct_of_assigned,
            name="COMPARATIVE — insufficient evidence for descriptive name",
            recency_tier="COMPARATIVE",
            frequency_tier="COMPARATIVE",
            monetary_tier="COMPARATIVE",
            behavioral_modifier=None,
            is_noise=False,
            is_not_available=False,
            naming_rationale=(
                "No CP-03 comparison data available for this unit/cluster. "
                "Cannot construct descriptive segment name."
            ),
            supporting_evidence="No comparison rows found.",
            naming_status="COMPARATIVE",
        )

    # For DBSCAN noise (cluster_id == -1): do NOT name as segment.
    if cluster_id == -1:
        return SegmentName(
            unit_id=unit.unit_id,
            algorithm=unit.algorithm,
            source_experiment=unit.source_experiment,
            cluster_id=-1,
            cluster_label="-1",
            customer_count=customer_count,
            pct_of_assigned=pct_of_assigned,
            name="NOISE — not a customer segment (DBSCAN label=-1)",
            recency_tier="NOISE",
            frequency_tier="NOISE",
            monetary_tier="NOISE",
            behavioral_modifier=None,
            is_noise=True,
            is_not_available=False,
            naming_rationale=(
                "DBSCAN ClusterLabel=-1 is noise, not a customer segment. "
                "Per AGENTS.md §2 and CP-01 design, noise is excluded "
                "from segment profiling and naming."
            ),
            supporting_evidence=(
                f"Noise bucket: {customer_count} customers = " f"{pct_of_assigned:.2f}% of total"
            ),
            naming_status="NOISE",
        )

    # Get comparison rows for this cluster.
    cluster_cmp = cmp[cmp["cluster_id"] == cluster_id]
    cluster_dist = dist[dist["feature"].isin(NAMING_FEATURES)]

    if cluster_cmp.empty:
        return SegmentName(
            unit_id=unit.unit_id,
            algorithm=unit.algorithm,
            source_experiment=unit.source_experiment,
            cluster_id=cluster_id,
            cluster_label=cluster_label,
            customer_count=customer_count,
            pct_of_assigned=pct_of_assigned,
            name=f"Comparative {cluster_label}",
            recency_tier="COMPARATIVE",
            frequency_tier="COMPARATIVE",
            monetary_tier="COMPARATIVE",
            behavioral_modifier=None,
            is_noise=False,
            is_not_available=False,
            naming_rationale=(
                f"No comparison rows found for cluster {cluster_label} in " f"unit {unit.unit_id}."
            ),
            supporting_evidence="No data rows.",
            naming_status="COMPARATIVE",
        )

    # Build direction mapping.
    directions = _get_cluster_directions(cluster_cmp.itertuples())

    # Build distinguishing classification mapping.
    distinguishing: dict[str, str] = {}
    for _, row in cluster_dist.iterrows():
        distinguishing[str(row["feature"])] = str(row["classification"])

    # Get core tiers.
    recency_dir = directions.get("Recency", "NA")
    freq_dir = directions.get("Frequency", "NA")
    mon_dir = directions.get("Monetary", "NA")

    recency_tier = _build_recency_tier(recency_dir)
    frequency_tier = _build_frequency_tier(freq_dir)
    monetary_tier = _build_monetary_tier(mon_dir)

    # Build behavioural modifier.
    modifier = _build_behavioral_modifier(
        directions=directions,
        distinguishing=distinguishing,
        recency_tier=recency_tier,
        frequency_tier=frequency_tier,
    )

    # Assemble name.
    name_parts = _build_name_parts(recency_tier, frequency_tier, monetary_tier, modifier)
    name = " ".join(name_parts)

    # Build supporting evidence string.
    evidence_parts: list[str] = []
    for feat in ("Recency", "Frequency", "Monetary", "TotalQuantity", "TenureDays"):
        d = directions.get(feat, "NA")
        if d not in ("NA",):
            rel = _get_feature_rel_diff(cluster_cmp.itertuples(), feat)
            if rel is not None:
                evidence_parts.append(f"{feat}={d} ({rel:+.0f}%)")
            else:
                evidence_parts.append(f"{feat}={d}")

    supporting_evidence = "; ".join(evidence_parts)

    # Build naming rationale.
    rationale_parts: list[str] = []
    rationale_parts.append(f"Name '{name}' is based on the following observed evidence:")
    rationale_parts.append(f"  Recency: {recency_dir} ({recency_tier})")
    rationale_parts.append(f"  Frequency: {freq_dir} ({frequency_tier})")
    rationale_parts.append(f"  Monetary: {mon_dir} ({monetary_tier})")
    if modifier:
        rationale_parts.append(f"  Behavioural modifier: {modifier}")
    else:
        rationale_parts.append(
            "  No additional behavioural modifier (no HIGH_DIFFERENCE_OBSERVED "
            "TenureDays / PurchaseIntervalStd / TotalQuantity+Monetary pattern)."
        )

    # Add limitation note if relevant.
    if recency_dir == "COMPARABLE":
        rationale_parts.append(
            "  NOTE: Recency is COMPARABLE — recency tier is descriptive "
            "but the cluster's purchase recency is close to the population median."
        )
    if mon_dir == "COMPARABLE":
        rationale_parts.append(
            "  NOTE: Monetary is COMPARABLE — monetary tier is descriptive "
            "but the cluster's spending is close to the population median."
        )
    if (
        distinguishing.get("PurchaseIntervalStd") == "HIGH_DIFFERENCE_OBSERVED"
        and directions.get("PurchaseIntervalStd") == "HIGHER"
    ):
        rationale_parts.append(
            "  NOTE: IrregularCadence modifier: PurchaseIntervalStd "
            "is HIGHER — the gap between purchases is more variable, "
            "meaning purchase cadence is less predictable."
        )

    naming_rationale = "\n".join(rationale_parts)

    return SegmentName(
        unit_id=unit.unit_id,
        algorithm=unit.algorithm,
        source_experiment=unit.source_experiment,
        cluster_id=cluster_id,
        cluster_label=cluster_label,
        customer_count=customer_count,
        pct_of_assigned=pct_of_assigned,
        name=name,
        recency_tier=recency_tier,
        frequency_tier=frequency_tier,
        monetary_tier=monetary_tier,
        behavioral_modifier=modifier,
        is_noise=False,
        is_not_available=False,
        naming_rationale=naming_rationale,
        supporting_evidence=supporting_evidence,
        naming_status="NAMED",
    )


def compute_all_segment_names(
    units: Sequence[Cp04AnalysisUnit],
) -> list[SegmentName]:
    """Compute segment names for all valid clusters across all units."""
    names: list[SegmentName] = []
    for unit in units:
        if not unit.labels_persisted:
            # EXP-03 unit — single NOT_AVAILABLE row.
            names.append(
                compute_segment_name(
                    unit=unit,
                    cluster_id=-999,
                    cluster_label="N/A",
                    customer_count=0,
                    pct_of_assigned=0.0,
                )
            )
            continue

        # Get cluster IDs and sizes from the cluster_sizes DataFrame.
        sizes = unit.cluster_sizes
        if sizes.empty:
            continue

        # Non-noise clusters.
        non_noise = sizes[~sizes["is_noise"]].copy()
        for _, row in non_noise.iterrows():
            cl_id = int(row["cluster_id"])
            cl_label = f"C{cl_id}"
            n = int(row["customer_count"])
            pct = float(row["pct_of_assigned"])
            names.append(
                compute_segment_name(
                    unit=unit,
                    cluster_id=cl_id,
                    cluster_label=cl_label,
                    customer_count=n,
                    pct_of_assigned=pct,
                )
            )

        # Noise row (DBSCAN only).
        noise_rows = sizes[sizes["is_noise"]]
        if not noise_rows.empty:
            nr = noise_rows.iloc[0]
            names.append(
                compute_segment_name(
                    unit=unit,
                    cluster_id=-1,
                    cluster_label="-1",
                    customer_count=int(nr["customer_count"]),
                    pct_of_assigned=float(nr["pct_of_total"]),
                )
            )
    return names


__all__ = [
    "SegmentName",
    "compute_segment_name",
    "compute_all_segment_names",
    "NAMING_FEATURES",
]
