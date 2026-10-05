"""CP-04 segment profile builder.

For each (unit, cluster) with persisted labels, this module constructs a
rich **SegmentProfile** that aggregates evidence from CP-01 (size),
CP-02 (feature statistics), CP-02 (relative comparison), CP-03
(comparison matrix), and CP-04 (naming).

The SegmentProfile is a frozen dataclass containing:

- Provenance fields (unit, algorithm, cluster).
- Size fields (customer count, pct of total).
- Naming fields (segment name, tiers, modifier, rationale, evidence).
- Top HIGHER / LOWER / COMPARABLE features (per CP-02 direction).
- Feature summary table (median, P25, P75, rel_diff_pct, direction).
- IQR overlap summary (mean, min, max with OVERALL).
- Distinguishing classification per feature.
- Behavioural summary narrative.

Hard constraints (AGENTS.md §2):
- Read-only against all source artefacts.
- No marketing terms, no over-inference.
- DBSCAN noise excluded from Customer Profile.
- EXP-03 units → NOT_AVAILABLE.
- Feature names must be evidence-based.
- No cross-algorithm mapping of Cluster IDs.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from customer_segmentation.profiling.cp04.naming import (
    SegmentName,
    compute_all_segment_names,
)
from customer_segmentation.profiling.cp04.provenance import Cp04AnalysisUnit


@dataclass(frozen=True)
class FeatureSummary:
    """One row of the per-cluster feature summary table."""

    feature: str
    median: float
    p25: float
    p75: float
    overall_median: float
    rel_diff_median_pct: float
    direction: str  # HIGHER / LOWER / COMPARABLE / ZERO_REFERENCE / NA
    classification: str  # HIGH / MODERATE / LOW_DIFFERENCE_OBSERVED / HIGH_OVERLAP / NOT_ASSESSABLE


@dataclass(frozen=True)
class IqrOverlapSummary:
    """IQR overlap statistics for one cluster vs OVERALL."""

    mean_overlap: float
    min_overlap: float
    max_overlap: float


@dataclass(frozen=True)
class SegmentProfile:
    """The complete profile for one cluster."""

    # Provenance.
    unit_id: str
    algorithm: str
    source_experiment: str
    cluster_id: int
    cluster_label: str
    is_noise: bool
    is_not_available: bool

    # Size.
    customer_count: int
    pct_of_total: float  # % of all customers in unit (incl. noise for DBSCAN)

    # Naming.
    segment_name: str
    recency_tier: str
    frequency_tier: str
    monetary_tier: str
    behavioral_modifier: str | None
    naming_rationale: str
    naming_status: str  # NAMED / COMPARATIVE / NOT_AVAILABLE / NOISE

    # Top distinguishing features.
    top_higher_features: tuple[str, ...]  # Features where direction=HIGHER
    top_lower_features: tuple[str, ...]  # Features where direction=LOWER
    top_comparable_features: tuple[str, ...]  # direction=COMPARABLE

    # Feature summary table (all 14 features).
    feature_summaries: tuple[FeatureSummary, ...]

    # IQR overlap summary.
    iqr_overlap_summary: IqrOverlapSummary | None

    # Behavioural narrative (text summary).
    behavioral_summary: str = field(default="")


def _build_feature_summaries(unit: Cp04AnalysisUnit, cluster_id: int) -> list[FeatureSummary]:
    """Build the per-cluster feature summary table from CP-03 comparison."""
    cmp_df = unit.cp03_comparison
    dist_df = unit.cp03_distinguishing

    if cmp_df.empty:
        return []

    cluster_cmp = cmp_df[cmp_df["cluster_id"] == cluster_id]
    summaries: list[FeatureSummary] = []
    for _, row in cluster_cmp.iterrows():
        feature = str(row["feature"])
        med = float(row["median"]) if np.isfinite(float(row["median"])) else np.nan
        p25 = float(row["p25"]) if np.isfinite(float(row["p25"])) else np.nan
        p75 = float(row["p75"]) if np.isfinite(float(row["p75"])) else np.nan
        overall_med = (
            float(row["overall_median"]) if np.isfinite(float(row["overall_median"])) else np.nan
        )
        rel = (
            float(row["rel_diff_median_pct"])
            if np.isfinite(float(row["rel_diff_median_pct"]))
            else np.nan
        )
        # Normalize NaN direction to "NA" (CP-02 uses NaN for
        # PurchaseIntervalStd clusters where std is undefined; CP-03
        # reads NaN as a string "nan" which would break downstream
        # assertions, so we normalize).
        direction_raw = row["direction"]
        if (
            direction_raw is None
            or (isinstance(direction_raw, float) and np.isnan(direction_raw))
            or (isinstance(direction_raw, str) and direction_raw.lower() == "nan")
        ):
            direction = "NA"
        else:
            direction = str(direction_raw)
        # Get distinguishing classification.
        dist_row = dist_df[dist_df["feature"] == feature]
        if not dist_row.empty:
            cls_raw = dist_row.iloc[0]["classification"]
            if (
                cls_raw is None
                or (isinstance(cls_raw, float) and np.isnan(cls_raw))
                or (isinstance(cls_raw, str) and cls_raw.lower() == "nan")
            ):
                classification = "NOT_ASSESSABLE"
            else:
                classification = str(cls_raw)
        else:
            classification = "NOT_ASSESSABLE"
        summaries.append(
            FeatureSummary(
                feature=feature,
                median=med,
                p25=p25,
                p75=p75,
                overall_median=overall_med,
                rel_diff_median_pct=rel,
                direction=direction,
                classification=classification,
            )
        )
    return summaries


def _build_iqr_summary(unit: Cp04AnalysisUnit, cluster_id: int) -> IqrOverlapSummary | None:
    """Build IQR overlap summary for one cluster."""
    cmp_df = unit.cp03_comparison
    if cmp_df.empty:
        return None
    cluster_cmp = cmp_df[cmp_df["cluster_id"] == cluster_id]
    if "iqr_overlap_with_population" not in cluster_cmp.columns:
        return None
    overlaps = cluster_cmp["iqr_overlap_with_population"].dropna()
    if overlaps.empty:
        return None
    vals = overlaps.values
    finite = vals[np.isfinite(vals)]
    if finite.size == 0:
        return None
    return IqrOverlapSummary(
        mean_overlap=float(np.nanmean(finite)),
        min_overlap=float(np.nanmin(finite)),
        max_overlap=float(np.nanmax(finite)),
    )


def _build_behavioral_summary(profile: SegmentProfile) -> str:
    """Build a short behavioural narrative text from the profile."""
    if profile.is_noise:
        return (
            "This DBSCAN noise bucket contains customers not assigned to any "
            "dense cluster. Noise is NOT a customer segment and does not "
            "receive a segment profile."
        )
    if profile.is_not_available:
        return (
            "Segment profile not available: EXP-03 working-selected "
            "per-customer labels are NOT persisted."
        )

    lines: list[str] = []
    recency = profile.recency_tier
    freq = profile.frequency_tier
    mon = profile.monetary_tier
    mod = profile.behavioral_modifier

    lines.append(
        f"Segment '{profile.segment_name}' "
        f"({profile.customer_count:,} customers, "
        f"{profile.pct_of_total:.2f}% of unit population):"
    )
    lines.append("")
    lines.append(f"  Recency tier: {recency}")
    lines.append(f"  Frequency tier: {freq}")
    lines.append(f"  Monetary tier: {mon}")
    if mod:
        lines.append(f"  Behavioural modifier: {mod}")
    lines.append("")
    if profile.top_higher_features:
        lines.append(
            "  Features with HIGHER median than overall population: "
            + ", ".join(profile.top_higher_features)
        )
    if profile.top_lower_features:
        lines.append(
            "  Features with LOWER median than overall population: "
            + ", ".join(profile.top_lower_features)
        )
    if profile.top_comparable_features:
        lines.append(
            "  Features COMPARABLE to overall population: "
            + ", ".join(profile.top_comparable_features)
        )
    lines.append("")
    iqr = profile.iqr_overlap_summary
    if iqr is not None:
        lines.append(
            "  IQR overlap with overall population: "
            f"mean={iqr.mean_overlap:.2f}, "
            f"min={iqr.min_overlap:.2f}, "
            f"max={iqr.max_overlap:.2f}"
        )
    lines.append("")
    lines.append("  Naming rationale:")
    lines.append(profile.naming_rationale)
    return "\n".join(lines)


def _build_segment_profile(
    unit: Cp04AnalysisUnit,
    segment_name: SegmentName,
) -> SegmentProfile:
    """Build a complete SegmentProfile from a SegmentName and unit evidence."""
    cl_id = segment_name.cluster_id
    is_noise = segment_name.is_noise
    is_na = segment_name.is_not_available

    # Get feature summaries.
    if not is_na and not is_noise:
        feature_summaries = _build_feature_summaries(unit, cl_id)
        iqr_summary = _build_iqr_summary(unit, cl_id)
        # Top features by direction.
        higher_feats = tuple(s.feature for s in feature_summaries if s.direction == "HIGHER")
        lower_feats = tuple(s.feature for s in feature_summaries if s.direction == "LOWER")
        comparable_feats = tuple(
            s.feature for s in feature_summaries if s.direction == "COMPARABLE"
        )
    else:
        feature_summaries = []
        iqr_summary = None
        higher_feats = ()
        lower_feats = ()
        comparable_feats = ()

    # Look up the canonical ``pct_of_total`` (share of all customers
    # in the unit, including noise for DBSCAN) from CP-01 size table.
    # Note: SegmentName.pct_of_assigned is share of non-noise customers
    # which differs for DBSCAN. CP-04 reports pct_of_total to align
    # with CP-01 ``pct_of_total`` for downstream consistency.
    if not is_na and not unit.cluster_sizes.empty:
        sizes = unit.cluster_sizes
        if is_noise:
            row = sizes[(sizes["cluster_id"] == -1) & (sizes["is_noise"] == True)]  # noqa: E712
        else:
            row = sizes[
                (sizes["cluster_id"] == int(cl_id)) & (sizes["is_noise"] == False)  # noqa: E712
            ]
        if not row.empty and "pct_of_total" in row.columns:
            pct_total = float(row.iloc[0]["pct_of_total"])
        else:
            pct_total = float("nan")
    else:
        pct_total = 0.0

    profile = SegmentProfile(
        unit_id=segment_name.unit_id,
        algorithm=segment_name.algorithm,
        source_experiment=segment_name.source_experiment,
        cluster_id=cl_id,
        cluster_label=segment_name.cluster_label,
        is_noise=is_noise,
        is_not_available=is_na,
        customer_count=segment_name.customer_count,
        pct_of_total=pct_total,
        segment_name=segment_name.name,
        recency_tier=segment_name.recency_tier,
        frequency_tier=segment_name.frequency_tier,
        monetary_tier=segment_name.monetary_tier,
        behavioral_modifier=segment_name.behavioral_modifier,
        naming_rationale=segment_name.naming_rationale,
        naming_status=segment_name.naming_status,
        top_higher_features=higher_feats,
        top_lower_features=lower_feats,
        top_comparable_features=comparable_feats,
        feature_summaries=tuple(feature_summaries),
        iqr_overlap_summary=iqr_summary,
        behavioral_summary="",
    )
    # Build narrative after profile is constructed.
    behavioral = _build_behavioral_summary(profile)
    # Reconstruct with the narrative (using object.__setattr__ because frozen).
    object.__setattr__(profile, "behavioral_summary", behavioral)
    return profile


def build_all_segment_profiles(
    units: Sequence[Cp04AnalysisUnit],
) -> list[SegmentProfile]:
    """Build complete segment profiles for all valid clusters.

    One profile per (unit, cluster) — including noise buckets (DBSCAN)
    and NOT_AVAILABLE rows (EXP-03). The list preserves the order from
    :func:`compute_all_segment_names`.
    """
    segment_names = compute_all_segment_names(units)
    # Build a map from (unit_id, cluster_id) → unit for lookup.
    unit_map: dict[tuple[str, int], Cp04AnalysisUnit] = {}
    for u in units:
        if u.labels_persisted and not u.cluster_sizes.empty:
            for _, sz in u.cluster_sizes.iterrows():
                unit_map[(u.unit_id, int(sz["cluster_id"]))] = u
        else:
            unit_map[(u.unit_id, -999)] = u

    profiles: list[SegmentProfile] = []
    for sn in segment_names:
        key = (sn.unit_id, sn.cluster_id)
        unit = unit_map.get(key)
        if unit is None:
            continue
        profile = _build_segment_profile(unit, sn)
        profiles.append(profile)
    return profiles


def segment_profiles_to_dicts(
    profiles: Sequence[SegmentProfile],
) -> list[dict[str, Any]]:
    """Serialise segment profiles to plain dicts for CSV output.

    The output schema is one row per (profile, feature_summary) —
    i.e., a long-format table where each row contains both the cluster
    metadata and one feature's summary. This makes downstream
    filtering by cluster straightforward.

    For profiles with empty feature summaries (NOT_AVAILABLE, NOISE),
    a single row with ``feature = "N/A"`` is emitted.
    """
    rows: list[dict[str, Any]] = []
    for p in profiles:
        if not p.feature_summaries:
            rows.append(
                {
                    "unit_id": p.unit_id,
                    "algorithm": p.algorithm,
                    "source_experiment": p.source_experiment,
                    "cluster_id": p.cluster_id,
                    "cluster_label": p.cluster_label,
                    "is_noise": p.is_noise,
                    "is_not_available": p.is_not_available,
                    "customer_count": p.customer_count,
                    "pct_of_total": p.pct_of_total,
                    "segment_name": p.segment_name,
                    "recency_tier": p.recency_tier,
                    "frequency_tier": p.frequency_tier,
                    "monetary_tier": p.monetary_tier,
                    "behavioral_modifier": p.behavioral_modifier,
                    "naming_rationale": p.naming_rationale,
                    "naming_status": p.naming_status,
                    "top_higher_features": "|".join(p.top_higher_features),
                    "top_lower_features": "|".join(p.top_lower_features),
                    "top_comparable_features": "|".join(p.top_comparable_features),
                    "iqr_mean_overlap": (
                        p.iqr_overlap_summary.mean_overlap
                        if p.iqr_overlap_summary is not None
                        else None
                    ),
                    "iqr_min_overlap": (
                        p.iqr_overlap_summary.min_overlap
                        if p.iqr_overlap_summary is not None
                        else None
                    ),
                    "iqr_max_overlap": (
                        p.iqr_overlap_summary.max_overlap
                        if p.iqr_overlap_summary is not None
                        else None
                    ),
                    "feature": "N/A",
                    "feature_median": None,
                    "feature_p25": None,
                    "feature_p75": None,
                    "feature_overall_median": None,
                    "feature_rel_diff_median_pct": None,
                    "feature_direction": "N/A",
                    "feature_classification": "N/A",
                    "behavioral_summary": p.behavioral_summary,
                }
            )
            continue
        for f in p.feature_summaries:
            rows.append(
                {
                    "unit_id": p.unit_id,
                    "algorithm": p.algorithm,
                    "source_experiment": p.source_experiment,
                    "cluster_id": p.cluster_id,
                    "cluster_label": p.cluster_label,
                    "is_noise": p.is_noise,
                    "is_not_available": p.is_not_available,
                    "customer_count": p.customer_count,
                    "pct_of_total": p.pct_of_total,
                    "segment_name": p.segment_name,
                    "recency_tier": p.recency_tier,
                    "frequency_tier": p.frequency_tier,
                    "monetary_tier": p.monetary_tier,
                    "behavioral_modifier": p.behavioral_modifier,
                    "naming_rationale": p.naming_rationale,
                    "naming_status": p.naming_status,
                    "top_higher_features": "|".join(p.top_higher_features),
                    "top_lower_features": "|".join(p.top_lower_features),
                    "top_comparable_features": "|".join(p.top_comparable_features),
                    "iqr_mean_overlap": (
                        p.iqr_overlap_summary.mean_overlap
                        if p.iqr_overlap_summary is not None
                        else None
                    ),
                    "iqr_min_overlap": (
                        p.iqr_overlap_summary.min_overlap
                        if p.iqr_overlap_summary is not None
                        else None
                    ),
                    "iqr_max_overlap": (
                        p.iqr_overlap_summary.max_overlap
                        if p.iqr_overlap_summary is not None
                        else None
                    ),
                    "feature": f.feature,
                    "feature_median": f.median,
                    "feature_p25": f.p25,
                    "feature_p75": f.p75,
                    "feature_overall_median": f.overall_median,
                    "feature_rel_diff_median_pct": f.rel_diff_median_pct,
                    "feature_direction": f.direction,
                    "feature_classification": f.classification,
                    "behavioral_summary": p.behavioral_summary,
                }
            )
    return rows


def segment_profiles_to_summary_dicts(
    profiles: Sequence[SegmentProfile],
) -> list[dict[str, Any]]:
    """Serialise segment profiles to a one-row-per-cluster summary table.

    This is the canonical segment-profile CSV — one row per
    (analysis_unit, cluster). The behavioural narrative is included
    as a single text column. Feature-level detail is not duplicated;
    readers who need per-feature statistics should consult
    ``cp04_segment_evidence.csv``.
    """
    rows: list[dict[str, Any]] = []
    for p in profiles:
        iqr = p.iqr_overlap_summary
        rows.append(
            {
                "unit_id": p.unit_id,
                "algorithm": p.algorithm,
                "source_experiment": p.source_experiment,
                "cluster_id": p.cluster_id,
                "cluster_label": p.cluster_label,
                "is_noise": p.is_noise,
                "is_not_available": p.is_not_available,
                "customer_count": p.customer_count,
                "pct_of_total": p.pct_of_total,
                "segment_name": p.segment_name,
                "recency_tier": p.recency_tier,
                "frequency_tier": p.frequency_tier,
                "monetary_tier": p.monetary_tier,
                "behavioral_modifier": p.behavioral_modifier,
                "naming_rationale": p.naming_rationale,
                "naming_status": p.naming_status,
                "top_higher_features": "|".join(p.top_higher_features),
                "top_lower_features": "|".join(p.top_lower_features),
                "top_comparable_features": "|".join(p.top_comparable_features),
                "iqr_mean_overlap": iqr.mean_overlap if iqr else None,
                "iqr_min_overlap": iqr.min_overlap if iqr else None,
                "iqr_max_overlap": iqr.max_overlap if iqr else None,
                "behavioral_summary": p.behavioral_summary,
            }
        )
    return rows


def evidence_rows_to_dicts(
    profiles: Sequence[SegmentProfile],
) -> pd.DataFrame:
    """Return a long-format per-feature evidence table (one row per profile × feature).

    Includes columns:
    - profile-level provenance (unit_id, algorithm, cluster_id, segment_name, ...)
    - per-feature values (median, P25, P75, overall_median, rel_diff_pct,
      direction, classification)
    """
    rows = segment_profiles_to_dicts(profiles)
    return pd.DataFrame(rows)


__all__ = [
    "FeatureSummary",
    "IqrOverlapSummary",
    "SegmentProfile",
    "build_all_segment_profiles",
    "segment_profiles_to_dicts",
    "segment_profiles_to_summary_dicts",
    "evidence_rows_to_dicts",
]
