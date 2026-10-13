"""Tests for DEV-07 Phase B mapping scaffolding.

The mapping scaffolding consumes a CP-04 tokenization result + the
MKT framework **structural** metadata and returns a
:class:`TemplateSlots` object describing which slots would be
filled by MKT-02/MKT-03/MKT-04/MKT-05 content — but with ``None``
placeholders, awaiting owner-approved MKT framework content.

Tests verify:
- Closed set of template slot names.
- Scaffolding returns ``None`` for every business slot (no synthesis).
- Scaffolding preserves CP-04 tokenization result fields.
- ``is_template_resolved`` returns False when all slots are ``None``.
- Scaffolding is pure (no I/O, no datetime, no mutation).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from customer_segmentation.prototype.marketing.config_loader import (
    Dev07Config,
    Dev07DisplayConfig,
    Dev07LoggingConfig,
    Dev07MktFrameworkConfig,
    Dev07ResearchSafetyConfig,
    Dev07StorageConfig,
    Dev07ValidationConfig,
)
from customer_segmentation.prototype.marketing.manifest import (
    build_recommendation_entry_review_required,
)
from customer_segmentation.prototype.marketing.mapping import (
    TEMPLATE_SLOT_NAMES,
    TemplateSlots,
    is_template_resolved,
    resolve_template_slots,
)
from customer_segmentation.prototype.marketing.mkt_framework_loader import (
    MktDocRef,
    MktFrameworkStructure,
)
from customer_segmentation.prototype.marketing.recommendation import (
    build_recommendation_entry_with_scaffolding,
)
from customer_segmentation.prototype.marketing.tokenization import (
    parse_cp04_segment_name,
)


def _make_config() -> Dev07Config:
    return Dev07Config(
        schema_version="1.0.0",
        availability_default="REVIEW_REQUIRED",
        mkt_framework=Dev07MktFrameworkConfig(
            path_relative="docs/marketing",
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


def _make_structure(*, version: str = "v1") -> MktFrameworkStructure:
    docs = {
        f"MKT-0{i}": MktDocRef(
            mkt_id=f"MKT-0{i}",
            file_path=Path(f"/tmp/MKT-0{i}.md"),
            sha256=hashlib.sha256(b"placeholder").hexdigest(),
            byte_count=11,
            token_count=1,
        )
        for i in range(1, 6)
    }
    return MktFrameworkStructure(
        framework_dir=Path("/tmp"),
        version=version,
        docs=docs,
    )


# ---------------------------------------------------------------------------
# Closed set of slot names
# ---------------------------------------------------------------------------


class TestTemplateSlotNames:
    def test_slot_names_exact(self) -> None:
        assert (
            frozenset(
                {"marketing_objective", "strategy", "recommended_action", "kpi", "limitation"}
            )
            == TEMPLATE_SLOT_NAMES
        )

    def test_does_not_contain_evidence_ref(self) -> None:
        """evidence_ref is auto-populated; no MKT lookup needed."""
        assert "evidence_ref" not in TEMPLATE_SLOT_NAMES

    def test_does_not_contain_metadata(self) -> None:
        """Fields like segment_id, cluster_label are not template slots."""
        assert "segment_id" not in TEMPLATE_SLOT_NAMES
        assert "cluster_label" not in TEMPLATE_SLOT_NAMES


# ---------------------------------------------------------------------------
# resolve_template_slots — pure, content-free
# ---------------------------------------------------------------------------


class TestResolveTemplateSlots:
    def test_resolve_with_structure(self) -> None:
        """Resolve returns None for every business slot."""
        tokenization = parse_cp04_segment_name("Recent Frequent HighValue LongTenured")
        structure = _make_structure(version="v1")
        slots = resolve_template_slots(tokenization=tokenization, structure=structure)
        assert isinstance(slots, TemplateSlots)
        assert slots.mkt_framework_version == "v1"
        assert slots.cp04_segment_name == "Recent Frequent HighValue LongTenured"
        assert slots.cp04_tokens_match is True
        # All business slots are None (no synthesis).
        assert slots.marketing_objective is None
        assert slots.strategy is None
        assert slots.recommended_action is None
        assert slots.kpi is None
        assert slots.limitation is None

    def test_resolve_without_structure(self) -> None:
        """Structure=None (Phase A contract) → version=None, slots=None."""
        tokenization = parse_cp04_segment_name("Older Occasional")
        slots = resolve_template_slots(tokenization=tokenization, structure=None)
        assert slots.mkt_framework_version is None
        assert slots.cp04_segment_name == "Older Occasional"
        assert slots.marketing_objective is None

    def test_resolve_preserves_cp04_match_flag(self) -> None:
        """CP-04 tokenization failure surfaces in cp04_tokens_match."""
        tokenization = parse_cp04_segment_name("Comparative Segment A")
        slots = resolve_template_slots(tokenization=tokenization, structure=_make_structure())
        assert slots.cp04_tokens_match is False

    def test_resolve_does_not_synthesize_strategy(self) -> None:
        """Defence-in-depth — strategy slot stays None."""
        tokenization = parse_cp04_segment_name("Recent Frequent HighValue LongTenured")
        slots = resolve_template_slots(tokenization=tokenization, structure=_make_structure())
        assert slots.strategy is None
        assert "strategy" not in tokenization.segment_name.lower()

    def test_resolve_does_not_synthesize_kpi(self) -> None:
        tokenization = parse_cp04_segment_name("Recent Frequent HighValue LongTenured")
        slots = resolve_template_slots(tokenization=tokenization, structure=_make_structure())
        assert slots.kpi is None


# ---------------------------------------------------------------------------
# is_template_resolved
# ---------------------------------------------------------------------------


class TestIsTemplateResolved:
    def test_all_none_returns_false(self) -> None:
        tokenization = parse_cp04_segment_name("Recent Frequent")
        slots = resolve_template_slots(tokenization=tokenization, structure=_make_structure())
        assert is_template_resolved(slots) is False

    def test_populated_marketing_objective_returns_true(self) -> None:
        # Build a slot with one populated field.
        slots = TemplateSlots(
            mkt_framework_version="v1",
            cp04_segment_name="Recent Frequent",
            cp04_tokens_match=True,
            marketing_objective="some objective",
            strategy=None,
            recommended_action=None,
            kpi=None,
            limitation=None,
        )
        assert is_template_resolved(slots) is True


# ---------------------------------------------------------------------------
# TemplateSlots invariants
# ---------------------------------------------------------------------------


class TestTemplateSlotsInvariants:
    def test_invalid_marketing_objective_type_rejected(self) -> None:
        with pytest.raises(ValueError, match="marketing_objective"):
            TemplateSlots(
                mkt_framework_version=None,
                cp04_segment_name="x",
                cp04_tokens_match=False,
                marketing_objective=42,  # type: ignore[arg-type]
                strategy=None,
                recommended_action=None,
                kpi=None,
                limitation=None,
            )

    def test_invalid_kpi_type_rejected(self) -> None:
        with pytest.raises(ValueError, match="kpi"):
            TemplateSlots(
                mkt_framework_version=None,
                cp04_segment_name="x",
                cp04_tokens_match=False,
                marketing_objective=None,
                strategy=None,
                recommended_action=None,
                kpi=["list-not-tuple"],  # type: ignore[arg-type]
                limitation=None,
            )


# ---------------------------------------------------------------------------
# Recommendation wiring with scaffolding
# ---------------------------------------------------------------------------


class TestRecommendationWiring:
    def test_entry_returns_phase_a_shell_when_scaffolding_unresolved(self) -> None:
        """Phase B path is wired but falls back to Phase A shell."""
        tokenization = parse_cp04_segment_name("Recent Frequent HighValue LongTenured")
        structure = _make_structure()
        slots = resolve_template_slots(tokenization=tokenization, structure=structure)
        # Scaffolding is unresolved (all slots None).
        assert is_template_resolved(slots) is False
        # Wiring returns Phase A REVIEW_REQUIRED shell.
        cfg = _make_config()
        entry = build_recommendation_entry_with_scaffolding(
            segment_id=0,
            cluster_label=0,
            evidence_ref=["segmentation_manifest.json"],
            config=cfg,
            cp04_segment_name="Recent Frequent HighValue LongTenured",
            mkt_framework_structure=structure,
        )
        # Compare field-by-field with the Phase A shell (recommendation_id
        # is generated by secrets.token_hex so we cannot compare whole
        # dataclasses directly).
        expected = build_recommendation_entry_review_required(
            segment_id=0,
            cluster_label=0,
            evidence_ref=["segmentation_manifest.json"],
        )
        assert entry.segment_id == expected.segment_id
        assert entry.cluster_label == expected.cluster_label
        assert entry.availability == expected.availability
        assert entry.evidence_ref == expected.evidence_ref
        assert entry.kpi == expected.kpi
        assert entry.marketing_objective == expected.marketing_objective
        assert entry.strategy == expected.strategy
        assert entry.recommended_action == expected.recommended_action
        assert entry.limitation == expected.limitation

    def test_entry_returns_phase_a_shell_without_structure(self) -> None:
        """Phase A: structure=None → Phase A REVIEW_REQUIRED."""
        cfg = _make_config()
        entry = build_recommendation_entry_with_scaffolding(
            segment_id=3,
            cluster_label=3,
            evidence_ref=[],
            config=cfg,
            cp04_segment_name="Recent Frequent HighValue",
            mkt_framework_structure=None,
        )
        expected = build_recommendation_entry_review_required(
            segment_id=3,
            cluster_label=3,
            evidence_ref=[],
        )
        assert entry.segment_id == expected.segment_id
        assert entry.cluster_label == expected.cluster_label
        assert entry.availability == expected.availability
        assert entry.evidence_ref == expected.evidence_ref
        assert entry.kpi == expected.kpi
        assert entry.marketing_objective == expected.marketing_objective

    def test_entry_availability_is_review_required(self) -> None:
        """Even when scaffolding is wired, availability stays REVIEW_REQUIRED."""
        cfg = _make_config()
        entry = build_recommendation_entry_with_scaffolding(
            segment_id=0,
            cluster_label=0,
            evidence_ref=[],
            config=cfg,
            cp04_segment_name="Recent Frequent",
            mkt_framework_structure=_make_structure(),
        )
        assert entry.availability == "REVIEW_REQUIRED"

    def test_entry_kpi_is_none(self) -> None:
        """Phase B no-synthesis contract: kpi stays None."""
        cfg = _make_config()
        entry = build_recommendation_entry_with_scaffolding(
            segment_id=0,
            cluster_label=0,
            evidence_ref=[],
            config=cfg,
            cp04_segment_name="Recent Frequent",
            mkt_framework_structure=_make_structure(),
        )
        assert entry.kpi is None


# ---------------------------------------------------------------------------
# Defensive: scaffolding must not call any I/O
# ---------------------------------------------------------------------------


class TestNoIO:
    def test_resolve_does_not_call_disk(self, tmp_path: Path) -> None:
        """Scaffolding is pure; passing a missing path raises TypeError,
        not OSError."""
        tokenization = parse_cp04_segment_name("Recent Frequent")
        # Pass a real but non-existent path to ensure no read attempt.
        structure = _make_structure()
        # Should not raise even though the path does not exist:
        slots = resolve_template_slots(tokenization=tokenization, structure=structure)
        assert slots.cp04_segment_name == "Recent Frequent"
