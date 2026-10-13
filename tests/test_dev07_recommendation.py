"""Tests for DEV-07 per-segment recommendation entry builder.

Covers ``build_recommendation_entry`` and
``build_recommendations_from_segmentation``. Phase A: every entry is a
``REVIEW_REQUIRED`` shell with template fields set to
``PENDING_MKT_FRAMEWORK`` and ``kpi=None``.
"""

from __future__ import annotations

from customer_segmentation.prototype.marketing.config_loader import (
    Dev07Config,
    Dev07DisplayConfig,
    Dev07LoggingConfig,
    Dev07MktFrameworkConfig,
    Dev07ResearchSafetyConfig,
    Dev07StorageConfig,
    Dev07ValidationConfig,
)
from customer_segmentation.prototype.marketing.recommendation import (
    build_recommendation_entry,
    build_recommendations_from_segmentation,
)
from customer_segmentation.prototype.marketing.scope import (
    AVAILABILITY_STATUSES,
    DEFAULT_AVAILABILITY,
    MARKETING_LIMITATION_TEXT,
    MARKETING_PENDING_PLACEHOLDER,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_full_config() -> Dev07Config:
    return Dev07Config(
        schema_version="1.0.0",
        availability_default=DEFAULT_AVAILABILITY,
        mkt_framework=Dev07MktFrameworkConfig(
            path_relative="docs/marketing",
            # Canonical aggregate form per ADR-0008 (Option A).
            version_pattern=r"^MKT-01\.\.05__v\d+(?:\.\d+)*$",
        ),
        display=Dev07DisplayConfig(
            percentage_decimals=2,
            missing_value_placeholder="--",
            csv_missing_value="",
            disclaimer_text="descriptive only",
        ),
        storage=Dev07StorageConfig(
            output_dir_relative="marketing",
            emit_manifest_json=True,
            emit_recommendations_csv=False,
            emit_recommendations_jsonl=False,
        ),
        logging=Dev07LoggingConfig(
            level="INFO",
            format="%(message)s",
            log_dir_relative="data/prototype/datasets",
            emit_to_console=True,
        ),
        research_safety=Dev07ResearchSafetyConfig(
            readonly_paths=["data/raw/primary"],
            never_promote_to_research=True,
            marketing_scope="MARKETING_PROTOTYPE",
        ),
        validation=Dev07ValidationConfig(
            forbid_internal_metrics_as_kpi=True,
            forbid_marketing_terminology=True,
            require_no_duplicate_segment_id=True,
            exclude_dbscan_noise=True,
        ),
    )


def _make_segmentation_data(
    segment_sizes: list[dict] | None = None,
    *,
    include_inputs: bool = True,
) -> dict:
    """Build a minimal DEV-06 manifest data dict for builder tests."""
    if segment_sizes is None:
        segment_sizes = [
            {"segment_id": 0, "count": 100, "percentage": 0.5, "is_noise": False},
            {"segment_id": 1, "count": 100, "percentage": 0.5, "is_noise": False},
        ]
    data: dict = {
        "schema_version": "1.0.0",
        "segmentation_id": "seg_" + "0" * 24,
        "segment_sizes": segment_sizes,
    }
    if include_inputs:
        data["input_segmentation_manifest"] = "segmentation_manifest.json"
        data["input_cluster_labels"] = "cluster_labels.parquet"
        data["input_ml_dataset"] = "ml_dataset.parquet"
        data["input_evaluation_manifest"] = None
    return data


# ---------------------------------------------------------------------------
# build_recommendation_entry — single segment
# ---------------------------------------------------------------------------


class TestBuildRecommendationEntry:
    def test_basic_entry(self) -> None:
        cfg = _make_full_config()
        e = build_recommendation_entry(
            segment_id=3,
            cluster_label=3,
            evidence_ref=["segmentation_manifest.json"],
            config=cfg,
        )
        assert e.segment_id == 3
        assert e.cluster_label == 3
        assert e.availability == DEFAULT_AVAILABILITY
        assert e.availability in AVAILABILITY_STATUSES
        assert e.marketing_objective == MARKETING_PENDING_PLACEHOLDER
        assert e.strategy == MARKETING_PENDING_PLACEHOLDER
        assert e.recommended_action == MARKETING_PENDING_PLACEHOLDER
        assert e.kpi is None
        assert e.limitation == MARKETING_LIMITATION_TEXT
        assert e.evidence_ref == ["segmentation_manifest.json"]

    def test_recommendation_id_format(self) -> None:
        cfg = _make_full_config()
        e = build_recommendation_entry(
            segment_id=7,
            cluster_label=7,
            evidence_ref=[],
            config=cfg,
        )
        assert e.recommendation_id.startswith("mkt_seg_7_")
        # 16 hex chars trailing.
        assert len(e.recommendation_id.split("_")[-1]) == 16

    def test_evidence_ref_copied_not_aliased(self) -> None:
        cfg = _make_full_config()
        refs = ["path/a", "path/b"]
        e = build_recommendation_entry(
            segment_id=0,
            cluster_label=0,
            evidence_ref=refs,
            config=cfg,
        )
        # Mutating the source list should NOT mutate the entry's list.
        refs.append("path/c")
        assert len(e.evidence_ref) == 2

    def test_interpretation_readiness_carry_over(self) -> None:
        cfg = _make_full_config()
        e = build_recommendation_entry(
            segment_id=1,
            cluster_label=1,
            evidence_ref=[],
            config=cfg,
            interpretation_readiness="CONDITIONAL",
            is_interpretation_ready=False,
        )
        assert e.interpretation_readiness == "CONDITIONAL"
        assert e.is_interpretation_ready is False

    def test_interpretation_ready_default_none(self) -> None:
        cfg = _make_full_config()
        e = build_recommendation_entry(
            segment_id=2,
            cluster_label=2,
            evidence_ref=[],
            config=cfg,
        )
        assert e.interpretation_readiness is None
        assert e.is_interpretation_ready is None

    def test_zero_segment_id_accepted(self) -> None:
        cfg = _make_full_config()
        e = build_recommendation_entry(
            segment_id=0,
            cluster_label=0,
            evidence_ref=[],
            config=cfg,
        )
        assert e.segment_id == 0

    def test_distinct_segment_ids_produce_distinct_recommendation_ids(self) -> None:
        cfg = _make_full_config()
        e1 = build_recommendation_entry(segment_id=1, cluster_label=1, evidence_ref=[], config=cfg)
        e2 = build_recommendation_entry(segment_id=2, cluster_label=2, evidence_ref=[], config=cfg)
        # Both must embed their segment_id (suffix portion differs only in
        # the segment_id prefix); distinct ids overall.
        assert e1.recommendation_id != e2.recommendation_id
        assert "1_" in e1.recommendation_id
        assert "2_" in e2.recommendation_id

    def test_phase_a_does_not_invent_strategy(self) -> None:
        """Per AGENTS.md §2.1: do NOT invent strategy / KPI / action."""
        cfg = _make_full_config()
        e = build_recommendation_entry(
            segment_id=0,
            cluster_label=0,
            evidence_ref=[],
            config=cfg,
        )
        # All three template fields must be the explicit placeholder, not
        # arbitrary business-sounding text.
        assert e.marketing_objective == MARKETING_PENDING_PLACEHOLDER
        assert e.strategy == MARKETING_PENDING_PLACEHOLDER
        assert e.recommended_action == MARKETING_PENDING_PLACEHOLDER

    def test_kpi_none_phase_a(self) -> None:
        cfg = _make_full_config()
        e = build_recommendation_entry(
            segment_id=0,
            cluster_label=0,
            evidence_ref=[],
            config=cfg,
        )
        # FR-MKT-05: KPI blocklist auto-respected by leaving kpi=None.
        assert e.kpi is None


# ---------------------------------------------------------------------------
# build_recommendations_from_segmentation — full builder
# ---------------------------------------------------------------------------


class TestBuildRecommendationsFromSegmentation:
    def test_basic_two_segments(self) -> None:
        cfg = _make_full_config()
        data = _make_segmentation_data()
        entries = build_recommendations_from_segmentation(
            segmentation_manifest_data=data,
            config=cfg,
        )
        assert len(entries) == 2
        seg_ids = sorted(e.segment_id for e in entries)
        assert seg_ids == [0, 1]

    def test_dbscan_noise_excluded(self) -> None:
        cfg = _make_full_config()
        data = _make_segmentation_data(
            segment_sizes=[
                {"segment_id": 0, "count": 100, "is_noise": False},
                {"segment_id": 1, "count": 100, "is_noise": False},
                {"segment_id": -1, "count": 50, "is_noise": True},
            ]
        )
        entries = build_recommendations_from_segmentation(
            segmentation_manifest_data=data,
            config=cfg,
        )
        assert len(entries) == 2
        for e in entries:
            assert e.segment_id >= 0
            assert e.segment_id != -1

    def test_only_noise_returns_empty(self) -> None:
        cfg = _make_full_config()
        data = _make_segmentation_data(
            segment_sizes=[
                {"segment_id": -1, "count": 50, "is_noise": True},
                {"segment_id": -1, "count": 30, "is_noise": True},
            ]
        )
        entries = build_recommendations_from_segmentation(
            segmentation_manifest_data=data,
            config=cfg,
        )
        assert entries == []

    def test_all_entries_review_required(self) -> None:
        cfg = _make_full_config()
        data = _make_segmentation_data()
        entries = build_recommendations_from_segmentation(
            segmentation_manifest_data=data,
            config=cfg,
        )
        for e in entries:
            assert e.availability == DEFAULT_AVAILABILITY

    def test_all_kpis_none(self) -> None:
        cfg = _make_full_config()
        data = _make_segmentation_data()
        entries = build_recommendations_from_segmentation(
            segmentation_manifest_data=data,
            config=cfg,
        )
        for e in entries:
            assert e.kpi is None

    def test_evidence_ref_includes_segmentation_manifest(self) -> None:
        cfg = _make_full_config()
        data = _make_segmentation_data()
        entries = build_recommendations_from_segmentation(
            segmentation_manifest_data=data,
            config=cfg,
        )
        # Per builder: evidence_ref is auto-populated from input_* fields.
        assert any("segmentation_manifest.json" in r for e in entries for r in e.evidence_ref)

    def test_evidence_ref_includes_cluster_labels(self) -> None:
        cfg = _make_full_config()
        data = _make_segmentation_data()
        entries = build_recommendations_from_segmentation(
            segmentation_manifest_data=data,
            config=cfg,
        )
        assert any("cluster_labels.parquet" in r for e in entries for r in e.evidence_ref)

    def test_evidence_ref_includes_ml_dataset(self) -> None:
        cfg = _make_full_config()
        data = _make_segmentation_data()
        entries = build_recommendations_from_segmentation(
            segmentation_manifest_data=data,
            config=cfg,
        )
        assert any("ml_dataset.parquet" in r for e in entries for r in e.evidence_ref)

    def test_evidence_ref_handles_missing_inputs(self) -> None:
        """If input_* fields are absent, evidence_ref is empty (no crash)."""
        cfg = _make_full_config()
        data = _make_segmentation_data(include_inputs=False)
        entries = build_recommendations_from_segmentation(
            segmentation_manifest_data=data,
            config=cfg,
        )
        for e in entries:
            assert e.evidence_ref == []

    def test_cluster_label_default(self) -> None:
        """When 'cluster_label' field absent, default to segment_id."""
        cfg = _make_full_config()
        data = _make_segmentation_data(
            segment_sizes=[
                {"segment_id": 5, "count": 50, "is_noise": False},
            ]
        )
        entries = build_recommendations_from_segmentation(
            segmentation_manifest_data=data,
            config=cfg,
        )
        assert len(entries) == 1
        assert entries[0].cluster_label == 5  # == segment_id

    def test_cluster_label_explicit(self) -> None:
        cfg = _make_full_config()
        data = _make_segmentation_data(
            segment_sizes=[
                {"segment_id": 0, "cluster_label": 7, "count": 50, "is_noise": False},
            ]
        )
        entries = build_recommendations_from_segmentation(
            segmentation_manifest_data=data,
            config=cfg,
        )
        assert entries[0].cluster_label == 7

    def test_segment_sizes_missing_returns_empty(self) -> None:
        cfg = _make_full_config()
        data: dict = {"schema_version": "1.0.0"}
        entries = build_recommendations_from_segmentation(
            segmentation_manifest_data=data,
            config=cfg,
        )
        assert entries == []

    def test_segment_sizes_non_dict_entries_skipped(self) -> None:
        cfg = _make_full_config()
        data = {
            "schema_version": "1.0.0",
            "segment_sizes": [
                {"segment_id": 0, "is_noise": False},
                "not-a-dict",
                {"segment_id": 1, "is_noise": False},
                None,
            ],
        }
        entries = build_recommendations_from_segmentation(
            segmentation_manifest_data=data,
            config=cfg,
        )
        # 2 valid dict entries; non-dict entries skipped silently.
        assert len(entries) == 2

    def test_is_noise_flag_excludes(self) -> None:
        """is_noise=True (even with segment_id >= 0) excludes the segment."""
        cfg = _make_full_config()
        data = _make_segmentation_data(
            segment_sizes=[
                {"segment_id": 0, "is_noise": False},
                {"segment_id": 1, "is_noise": True},  # exclude via flag
            ]
        )
        entries = build_recommendations_from_segmentation(
            segmentation_manifest_data=data,
            config=cfg,
        )
        assert len(entries) == 1
        assert entries[0].segment_id == 0

    def test_segment_id_minus_one_excluded(self) -> None:
        """segment_id=-1 is excluded even if is_noise flag missing."""
        cfg = _make_full_config()
        data = _make_segmentation_data(
            segment_sizes=[
                {"segment_id": -1, "count": 50},  # no is_noise flag, but -1
            ]
        )
        entries = build_recommendations_from_segmentation(
            segmentation_manifest_data=data,
            config=cfg,
        )
        assert entries == []

    def test_recommendations_unique_segment_id(self) -> None:
        cfg = _make_full_config()
        data = _make_segmentation_data(
            segment_sizes=[
                {"segment_id": 0, "is_noise": False},
                {"segment_id": 1, "is_noise": False},
                {"segment_id": 2, "is_noise": False},
            ]
        )
        entries = build_recommendations_from_segmentation(
            segmentation_manifest_data=data,
            config=cfg,
        )
        seg_ids = [e.segment_id for e in entries]
        assert len(seg_ids) == len(set(seg_ids))

    def test_input_evaluation_manifest_included_when_set(self) -> None:
        cfg = _make_full_config()
        data = _make_segmentation_data()
        data["input_evaluation_manifest"] = "evaluation_manifest.json"
        entries = build_recommendations_from_segmentation(
            segmentation_manifest_data=data,
            config=cfg,
        )
        assert any("evaluation_manifest.json" in r for e in entries for r in e.evidence_ref)

    def test_no_phase_b_template_resolution(self) -> None:
        """Phase A: never resolve from non-existent MKT templates."""
        cfg = _make_full_config()
        # Even with rich config (e.g., hypothetical mkt_framework), the
        # Phase A behaviour is REVIEW_REQUIRED placeholder.
        data = _make_segmentation_data()
        entries = build_recommendations_from_segmentation(
            segmentation_manifest_data=data,
            config=cfg,
        )
        for e in entries:
            # No creative templating; only the canonical placeholder.
            assert e.marketing_objective == MARKETING_PENDING_PLACEHOLDER
            assert e.strategy == MARKETING_PENDING_PLACEHOLDER
            assert e.recommended_action == MARKETING_PENDING_PLACEHOLDER


# ---------------------------------------------------------------------------
# Sanity: list of recommendations passed to manifest builder is invariant
# ---------------------------------------------------------------------------


def test_builder_output_passes_manifest_invariants() -> None:
    """Entries produced by the builder are immediately valid for the manifest."""
    from customer_segmentation.prototype.marketing.manifest import (
        MarketingValidationReport,
        build_marketing_manifest,
    )

    cfg = _make_full_config()
    data = _make_segmentation_data()
    entries = build_recommendations_from_segmentation(
        segmentation_manifest_data=data,
        config=cfg,
    )

    # Build a manifest with these entries — must not raise.
    manifest = build_marketing_manifest(
        marketing_id="mkt_" + "0" * 24,
        segmentation_id="seg_" + "0" * 24,
        clustering_id="cl_" + "1" * 24,
        preprocessed_id="pp_test",
        dataset_id="ds_test",
        source_framework_version=None,
        mkt_framework_found=False,
        ml_dataset_sha256="a" * 64,
        feature_set_sha256="b" * 64,
        preprocessing_config_sha256="c" * 64,
        segmentation_manifest_sha256="d" * 64,
        n_segments_input=2,
        n_segments_with_recommendation=len(entries),
        n_segments_noise=0,
        n_segments_not_available=0,
        noise_policy_used="n/a",
        recommendations=entries,
        environment={
            "python": "3.11",
            "platform": "Linux",
            "release": "7.0",
            "machine": "x86_64",
            "key_libraries": {},
        },
        config_sha256="e" * 64,
        log_file="",
        validation_report=MarketingValidationReport(all_passed=True),
        readonly_paths=["data/raw/primary"],
        input_segmentation_manifest="segmentation_manifest.json",
    )
    assert len(manifest.recommendations) == 2
    for e in manifest.recommendations:
        assert e.availability == DEFAULT_AVAILABILITY
        assert e.kpi is None
