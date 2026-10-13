"""Tests for DEV-07 MarketingRecommendationManifest schema, JSON I/O, and invariants."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from customer_segmentation.prototype.marketing.exceptions import (
    MarketingManifestError,
    MarketingScopeError,
)
from customer_segmentation.prototype.marketing.manifest import (
    MarketingRecommendationEntry,
    MarketingRecommendationManifest,
    MarketingValidationReport,
    ResearchSafetyBlock,
    build_marketing_manifest,
    build_recommendation_entry_review_required,
    check_forbidden_marketing_terms,
    manifest_to_dict,
    now_utc_iso,
    read_marketing_manifest,
    write_marketing_manifest,
)
from customer_segmentation.prototype.marketing.scope import (
    MARKETING_LIMITATION_TEXT,
    MARKETING_MANIFEST_SCHEMA_VERSION,
    MARKETING_PENDING_PLACEHOLDER,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(**overrides) -> MarketingRecommendationEntry:
    base = {
        "segment_id": 0,
        "cluster_label": 0,
        "availability": "REVIEW_REQUIRED",
        "recommendation_id": "mkt_seg_0_0000000000000000",
        "marketing_objective": MARKETING_PENDING_PLACEHOLDER,
        "strategy": MARKETING_PENDING_PLACEHOLDER,
        "recommended_action": MARKETING_PENDING_PLACEHOLDER,
        "kpi": None,
        "evidence_ref": ["path/to/seg.json"],
        "limitation": MARKETING_LIMITATION_TEXT,
        "limitation_note": "test",
        "interpretation_readiness": None,
        "is_interpretation_ready": None,
    }
    base.update(overrides)
    return MarketingRecommendationEntry(**base)


def _make_args(**overrides):
    base = {
        "marketing_id": "mkt_" + "0" * 24,
        "segmentation_id": "seg_" + "0" * 24,
        "clustering_id": "cl_" + "1" * 24,
        "preprocessed_id": "pp_x",
        "dataset_id": "ds_x",
        "source_framework_version": None,
        "mkt_framework_found": False,
        "ml_dataset_sha256": "a" * 64,
        "feature_set_sha256": "b" * 64,
        "preprocessing_config_sha256": "c" * 64,
        "segmentation_manifest_sha256": "d" * 64,
        "n_segments_input": 1,
        "n_segments_with_recommendation": 1,
        "n_segments_noise": 0,
        "n_segments_not_available": 0,
        "noise_policy_used": "exclude",
        "recommendations": [_make_entry()],
        "environment": {
            "python": "3.11",
            "platform": "Linux",
            "release": "7.0",
            "machine": "x86_64",
            "key_libraries": {},
        },
        "config_sha256": "e" * 64,
        "log_file": "",
        "validation_report": MarketingValidationReport(all_passed=True, checks=[]),
        "readonly_paths": ["data/raw/primary"],
        "input_segmentation_manifest": "segmentation_manifest.json",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# ResearchSafetyBlock invariants
# ---------------------------------------------------------------------------


def test_research_safety_block_rejects_wrong_scope() -> None:
    with pytest.raises(MarketingScopeError):
        ResearchSafetyBlock(
            automatically_promoted_to_research=False,
            scope="RESEARCH_APPROVED",
            appeared_in_research_evidence=False,
        )


def test_research_safety_block_rejects_promoted_true() -> None:
    with pytest.raises(MarketingScopeError):
        ResearchSafetyBlock(
            automatically_promoted_to_research=True,
            scope="MARKETING_PROTOTYPE",
            appeared_in_research_evidence=False,
        )


def test_research_safety_block_rejects_evidence_true() -> None:
    with pytest.raises(MarketingScopeError):
        ResearchSafetyBlock(
            automatically_promoted_to_research=False,
            scope="MARKETING_PROTOTYPE",
            appeared_in_research_evidence=True,
        )


def test_research_safety_block_accepts_canonical() -> None:
    rs = ResearchSafetyBlock(
        automatically_promoted_to_research=False,
        scope="MARKETING_PROTOTYPE",
        appeared_in_research_evidence=False,
    )
    assert rs.scope == "MARKETING_PROTOTYPE"


# ---------------------------------------------------------------------------
# MarketingRecommendationEntry invariants
# ---------------------------------------------------------------------------


def test_entry_rejects_noise_segment_id() -> None:
    with pytest.raises(MarketingManifestError, match="DBSCAN noise"):
        _make_entry(segment_id=-1)


def test_entry_rejects_invalid_availability() -> None:
    with pytest.raises(MarketingManifestError, match="availability"):
        _make_entry(availability="UNKNOWN")


def test_entry_rejects_bad_recommendation_id() -> None:
    with pytest.raises(MarketingManifestError, match="recommendation_id"):
        _make_entry(recommendation_id="not_matching_pattern")


def test_entry_rejects_blocked_kpi() -> None:
    with pytest.raises(MarketingManifestError, match="internal clustering metric"):
        _make_entry(kpi=["silhouette_score"])


def test_entry_accepts_none_kpi() -> None:
    entry = _make_entry(kpi=None)
    assert entry.kpi is None


def test_entry_rejects_empty_limitation_note() -> None:
    with pytest.raises(MarketingManifestError, match="limitation_note"):
        _make_entry(limitation_note="")


def test_entry_rejects_empty_evidence_ref_entry() -> None:
    with pytest.raises(MarketingManifestError, match="evidence_ref"):
        _make_entry(evidence_ref=[""])


# ---------------------------------------------------------------------------
# Manifest invariants
# ---------------------------------------------------------------------------


def test_manifest_rejects_wrong_schema_version() -> None:
    m = build_marketing_manifest(**_make_args())
    object.__setattr__(m, "schema_version", "0.9.0")
    with pytest.raises(MarketingManifestError, match="schema_version"):
        MarketingRecommendationManifest(**dataclasses.asdict(m))


def test_manifest_rejects_invalid_availability() -> None:
    with pytest.raises(MarketingManifestError, match="availability"):
        build_marketing_manifest(**_make_args(availability="MAYBE"))


def test_manifest_rejects_invalid_noise_policy() -> None:
    with pytest.raises(MarketingManifestError, match="noise_policy_used"):
        build_marketing_manifest(**_make_args(noise_policy_used="maybe"))


def test_manifest_rejects_count_mismatch() -> None:
    """n_segments_with_recommendation must equal len(recommendations)."""
    with pytest.raises(MarketingManifestError, match="n_segments_with_recommendation"):
        build_marketing_manifest(
            **_make_args(n_segments_with_recommendation=2, n_segments_not_available=0)
        )


def test_manifest_rejects_duplicate_segment_id() -> None:
    entries = [_make_entry(segment_id=0), _make_entry(segment_id=0)]
    with pytest.raises(MarketingManifestError, match="UNIQUE"):
        build_marketing_manifest(
            **_make_args(recommendations=entries, n_segments_with_recommendation=2)
        )


def test_manifest_minimal_happy_path() -> None:
    m = build_marketing_manifest(**_make_args())
    assert m.schema_version == MARKETING_MANIFEST_SCHEMA_VERSION
    assert m.availability == "REVIEW_REQUIRED"
    assert m.research_safety.scope == "MARKETING_PROTOTYPE"
    assert m.research_safety.automatically_promoted_to_research is False
    assert m.research_safety.appeared_in_research_evidence is False


# ---------------------------------------------------------------------------
# manifest_to_dict + I/O roundtrip
# ---------------------------------------------------------------------------


def test_manifest_to_dict_serializable_to_json() -> None:
    m = build_marketing_manifest(**_make_args())
    d = manifest_to_dict(m)
    s = json.dumps(d, ensure_ascii=False, indent=2, sort_keys=True)
    assert isinstance(s, str)
    assert "MARKETING_PROTOTYPE" in s


def test_write_and_read_roundtrip(tmp_path: Path) -> None:
    m = build_marketing_manifest(**_make_args())
    p = tmp_path / "mkt" / "marketing_manifest.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    write_marketing_manifest(m, p)
    m2 = read_marketing_manifest(p)
    assert m2.marketing_id == m.marketing_id
    assert m2.availability == m.availability
    assert len(m2.recommendations) == len(m.recommendations)


def test_write_atomic_no_leftover_tmp(tmp_path: Path) -> None:
    m = build_marketing_manifest(**_make_args())
    p = tmp_path / "marketing_manifest.json"
    write_marketing_manifest(m, p)
    assert p.exists()
    assert not (p.with_suffix(p.suffix + ".tmp")).exists()


def test_write_rejects_missing_parent_dir(tmp_path: Path) -> None:
    m = build_marketing_manifest(**_make_args())
    p = tmp_path / "nonexistent" / "marketing_manifest.json"
    with pytest.raises(MarketingManifestError, match="parent"):
        write_marketing_manifest(m, p)


def test_read_missing_file(tmp_path: Path) -> None:
    with pytest.raises(MarketingManifestError, match="not found"):
        read_marketing_manifest(tmp_path / "nope.json")


def test_read_invalid_json(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("{not valid json")
    with pytest.raises(MarketingManifestError, match="parse"):
        read_marketing_manifest(p)


def test_read_rejects_research_safety_promoted_true(tmp_path: Path) -> None:
    m = build_marketing_manifest(**_make_args())
    d = manifest_to_dict(m)
    d["research_safety"]["automatically_promoted_to_research"] = True
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(d))
    with pytest.raises(MarketingScopeError, match="automatically_promoted_to_research"):
        read_marketing_manifest(p)


# ---------------------------------------------------------------------------
# check_forbidden_marketing_terms
# ---------------------------------------------------------------------------


def test_check_forbidden_terms_finds_known() -> None:
    found = check_forbidden_marketing_terms("This is a champion segment.")
    assert "champion" in found


def test_check_forbidden_terms_clean_text() -> None:
    found = check_forbidden_marketing_terms("Just a normal description with no terms.")
    assert found == []


def test_check_forbidden_terms_case_insensitive() -> None:
    found = check_forbidden_marketing_terms("VIP customer")
    assert "vip" in found


# ---------------------------------------------------------------------------
# now_utc_iso
# ---------------------------------------------------------------------------


def test_now_utc_iso_format() -> None:
    s = now_utc_iso()
    assert len(s) == 20
    assert s[4] == "-"
    assert s[10] == "T"
    assert s.endswith("Z")


# ---------------------------------------------------------------------------
# build_recommendation_entry_review_required
# ---------------------------------------------------------------------------


def test_build_recommendation_entry_review_required() -> None:
    e = build_recommendation_entry_review_required(
        segment_id=5, cluster_label=2, evidence_ref=["path"]
    )
    assert e.availability == "REVIEW_REQUIRED"
    assert e.kpi is None
    assert e.marketing_objective == MARKETING_PENDING_PLACEHOLDER
    assert e.strategy == MARKETING_PENDING_PLACEHOLDER
    assert e.recommended_action == MARKETING_PENDING_PLACEHOLDER
    assert e.segment_id == 5
    assert e.cluster_label == 2
    assert e.evidence_ref == ["path"]
    assert e.limitation == MARKETING_LIMITATION_TEXT


def test_build_recommendation_entry_recommendation_id_format() -> None:
    e = build_recommendation_entry_review_required(segment_id=12, cluster_label=12, evidence_ref=[])
    assert e.recommendation_id.startswith("mkt_seg_12_")
    assert len(e.recommendation_id.split("_")[-1]) == 16
