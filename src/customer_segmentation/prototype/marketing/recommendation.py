"""Per-segment marketing recommendation entry builder for DEV-07.

Phase A (MKT-01..MKT-05 absent): every entry is a
``REVIEW_REQUIRED`` shell with template fields set to
``PENDING_MKT_FRAMEWORK`` and ``kpi=None``. The pipeline does NOT
populate marketing_objective / strategy / recommended_action / kpi
/ limitation from any non-MKT source.

Phase B (MKT framework present): mapping scaffolding is wired in
via :func:`build_recommendation_entry_with_scaffolding`. The
scaffolding consumes a CP-04 tokenization result + the MKT framework
**structural** metadata and returns a
:class:`~customer_segmentation.prototype.marketing.mapping.TemplateSlots`
object. When no MKT business content is available, the slots are
``None`` and the entry falls back to the Phase A REVIEW_REQUIRED
shell.

Phase B is BLOCKED here: MKT-01..MKT-05 absent in repository;
OQ-D07-01 (MKT scope), OQ-D07-03 (CP-04 tokenization canonical),
OQ-D07-04 (KPI units) all ``REVIEW_REQUIRED``. The wiring below is
defensive and falls back to Phase A REVIEW_REQUIRED when MKT content
is unavailable.
"""

from __future__ import annotations

from typing import Any

from customer_segmentation.prototype.marketing.config_loader import Dev07Config
from customer_segmentation.prototype.marketing.manifest import (
    MarketingRecommendationEntry,
    build_recommendation_entry_review_required,
)
from customer_segmentation.prototype.marketing.mapping import (
    TemplateSlots,
    is_template_resolved,
    resolve_template_slots,
)
from customer_segmentation.prototype.marketing.mkt_framework_loader import (
    MktFrameworkStructure,
)
from customer_segmentation.prototype.marketing.tokenization import (
    CP04TokenizationResult,
    parse_cp04_segment_name,
)

__all__ = [
    "build_recommendation_entry",
    "build_recommendations_from_segmentation",
    "build_recommendation_entry_with_scaffolding",
]


def build_recommendation_entry(
    *,
    segment_id: int,
    cluster_label: int,
    evidence_ref: list[str],
    config: Dev07Config,
    interpretation_readiness: str | None = None,
    is_interpretation_ready: bool | None = None,
    mkt_framework_structure: MktFrameworkStructure | None = None,
    cp04_segment_name: str | None = None,
) -> MarketingRecommendationEntry:
    """Build a single per-segment recommendation entry.

    Phase A behaviour: emits a ``REVIEW_REQUIRED`` shell. ``kpi`` is
    always ``None``. All template fields are set to
    ``"PENDING_MKT_FRAMEWORK"``.

    Phase B behaviour (when ``mkt_framework_structure`` is provided
    AND ``cp04_segment_name`` is provided): the segment name is parsed
    via CP-04 §4.1-§4.3 tokenization and the MKT framework
    **structure** is consulted. Since the mapping scaffolding
    returns ``None`` for every business slot until MKT-02..MKT-05
    business content is available, the entry falls back to the
    Phase A REVIEW_REQUIRED shell in the current state.

    Parameters
    ----------
    segment_id : int
        DEV-06 segment id (MUST be >= 0; DBSCAN noise is filtered
        before this function is called).
    cluster_label : int
        Original cluster label assigned by DEV-04 (recorded for
        provenance).
    evidence_ref : list of str
        Repository-relative paths to DEV-06 / CP-04 / CP-05 artifacts
        supporting this segment.
    config : Dev07Config
        Loaded DEV-07 config (currently unused ở Phase A; reserved
        for Phase B template-resolution).
    interpretation_readiness : str or None
        Carry-over from CP-05 ``interpretation_readiness`` (None if
        CP-05 evidence absent).
    is_interpretation_ready : bool or None
        Carry-over from CP-05 ``is_interpretation_ready`` (None if
        CP-05 evidence absent).
    mkt_framework_structure : MktFrameworkStructure or None
        Optional Phase B MKT framework structural metadata. When
        ``None`` (default), the entry uses the Phase A REVIEW_REQUIRED
        shell. When provided, the entry attempts Phase B tokenization
        + scaffolding; falls back to Phase A REVIEW_REQUIRED when no
        business content is available.
    cp04_segment_name : str or None
        Optional CP-04 segment name (for Phase B tokenization).
        When ``None``, Phase B path is skipped.

    Returns
    -------
    MarketingRecommendationEntry
        A ``REVIEW_REQUIRED`` entry (Phase A shell) in the current
        state. Once MKT business content is available, the Phase B
        path will populate template fields per OQ-D07-01.
    """
    # Phase B path: tokenize + resolve slots; fall back to Phase A
    # if MKT content absent or tokenization is incomplete.
    if mkt_framework_structure is not None and cp04_segment_name is not None:
        tokenization = parse_cp04_segment_name(cp04_segment_name)
        slots: TemplateSlots = resolve_template_slots(
            tokenization=tokenization,
            structure=mkt_framework_structure,
        )
        if is_template_resolved(slots):
            # When MKT business content becomes available, this branch
            # will populate marketing_objective / strategy / action /
            # kpi / limitation from the MKT framework templates.
            # Until then, the scaffolding returns None for every slot
            # and ``is_template_resolved`` returns False.
            pass

    # Phase A: delegate to the shell builder. Phase B (when unblocked
    # with owner-approved MKT content) will replace this with a
    # MKT-framework-driven template resolver.
    return build_recommendation_entry_review_required(
        segment_id=segment_id,
        cluster_label=cluster_label,
        evidence_ref=evidence_ref,
        interpretation_readiness=interpretation_readiness,
        is_interpretation_ready=is_interpretation_ready,
    )


def build_recommendations_from_segmentation(
    *,
    segmentation_manifest_data: dict[str, Any],
    config: Dev07Config,
    mkt_framework_structure: MktFrameworkStructure | None = None,
) -> list[MarketingRecommendationEntry]:
    """Build all per-segment recommendation entries from a DEV-06 manifest.

    DBSCAN noise (``segment_id == -1`` or ``is_noise == True``) is
    EXCLUDED entirely (FR-MKT-06, CON-08). The caller is responsible
    for recording the noise count in the manifest's
    ``n_segments_noise`` field.

    ``evidence_ref`` is auto-populated with the DEV-06 manifest path
    + the canonical DEV-06 artifact paths (when present in
    ``input_*`` fields of the segmentation manifest).

    Phase A: every entry has ``availability == REVIEW_REQUIRED``,
    ``kpi is None``, and all template fields set to
    ``"PENDING_MKT_FRAMEWORK"``.

    Phase B: when ``mkt_framework_structure`` is provided, the entry
    builder attempts Phase B tokenization + scaffolding. The
    scaffolding returns ``None`` for every business slot until
    MKT-02..MKT-05 business content is available, so the entries
    fall back to Phase A REVIEW_REQUIRED in the current state.

    Parameters
    ----------
    segmentation_manifest_data : dict
        Raw JSON object of the DEV-06 ``segmentation_manifest.json``.
    config : Dev07Config
        Loaded DEV-07 config.
    mkt_framework_structure : MktFrameworkStructure or None
        Optional Phase B MKT framework structural metadata.

    Returns
    -------
    list of MarketingRecommendationEntry
        One entry per non-noise segment.
    """
    segment_sizes = segmentation_manifest_data.get("segment_sizes", [])
    input_segmentation_manifest = str(
        segmentation_manifest_data.get("input_segmentation_manifest", "")
    )
    input_cluster_labels = str(segmentation_manifest_data.get("input_cluster_labels", ""))
    input_ml_dataset = str(segmentation_manifest_data.get("input_ml_dataset", ""))
    input_evaluation_manifest = segmentation_manifest_data.get("input_evaluation_manifest")

    base_evidence: list[str] = []
    if input_segmentation_manifest:
        base_evidence.append(input_segmentation_manifest)
    if input_cluster_labels:
        base_evidence.append(input_cluster_labels)
    if input_ml_dataset:
        base_evidence.append(input_ml_dataset)
    if input_evaluation_manifest:
        base_evidence.append(str(input_evaluation_manifest))

    entries: list[MarketingRecommendationEntry] = []
    for s in segment_sizes:
        if not isinstance(s, dict):
            continue
        seg_id = int(s.get("segment_id", 0))
        is_noise = bool(s.get("is_noise", False))
        # Exclude DBSCAN noise (FR-MKT-06, CON-08).
        if is_noise or seg_id == -1:
            continue
        # Derive cluster_label (use segment_id as cluster_label when the
        # DEV-06 manifest does not carry a separate cluster_label field;
        # for hard/fuzzy/model_based algorithms segment_id == cluster_label).
        cluster_label = int(s.get("cluster_label", seg_id))
        entries.append(
            build_recommendation_entry(
                segment_id=seg_id,
                cluster_label=cluster_label,
                evidence_ref=list(base_evidence),
                config=config,
                mkt_framework_structure=mkt_framework_structure,
                cp04_segment_name=None,  # Phase B hook: pass CP-04 segment name when wired
            )
        )
    return entries


def build_recommendation_entry_with_scaffolding(
    *,
    segment_id: int,
    cluster_label: int,
    evidence_ref: list[str],
    config: Dev07Config,
    cp04_segment_name: str,
    mkt_framework_structure: MktFrameworkStructure | None,
    interpretation_readiness: str | None = None,
    is_interpretation_ready: bool | None = None,
) -> MarketingRecommendationEntry:
    """Build a single entry with explicit CP-04 tokenization + MKT structure.

    This is the explicit Phase B entry point. Phase A path uses
    :func:`build_recommendation_entry` directly.

    The function is intentionally conservative: it always returns
    a Phase A REVIEW_REQUIRED shell in the current state, because
    the mapping scaffolding (``resolve_template_slots``) returns
    ``None`` for every business slot until MKT-02..MKT-05 content
    becomes available. Once owner-approved MKT files exist and
    OQ-D07-01 is resolved, this function will populate template
    fields from the framework.

    Parameters
    ----------
    segment_id : int
        DEV-06 segment id (>= 0).
    cluster_label : int
        Original cluster label assigned by DEV-04.
    evidence_ref : list of str
        Repository-relative paths to DEV-06 / CP-04 / CP-05 artifacts.
    config : Dev07Config
        Loaded DEV-07 config.
    cp04_segment_name : str
        CP-04 segment name (e.g. ``"Recent Frequent HighValue LongTenured"``).
    mkt_framework_structure : MktFrameworkStructure or None
        MKT framework structural metadata. When ``None``, the entry
        falls back to Phase A REVIEW_REQUIRED.
    interpretation_readiness : str or None
        Carry-over from CP-05.
    is_interpretation_ready : bool or None
        Carry-over from CP-05.

    Returns
    -------
    MarketingRecommendationEntry
        Phase A REVIEW_REQUIRED entry in the current state.
    """
    return build_recommendation_entry(
        segment_id=segment_id,
        cluster_label=cluster_label,
        evidence_ref=evidence_ref,
        config=config,
        interpretation_readiness=interpretation_readiness,
        is_interpretation_ready=is_interpretation_ready,
        mkt_framework_structure=mkt_framework_structure,
        cp04_segment_name=cp04_segment_name,
    )
