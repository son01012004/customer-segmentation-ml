"""Tests for DEV-06 characteristics.py (4-rule engine per OQ-SEG-CHAR-01)."""

from __future__ import annotations

import pytest

from customer_segmentation.prototype.segmentation.characteristics import (
    derive_segment_characteristics,
)
from customer_segmentation.prototype.segmentation.manifest import (
    CharacteristicEntry,
    FeatureProfile,
)
from customer_segmentation.prototype.segmentation.scope import (
    ALLOWED_CHARACTERISTIC_RULES,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_profiles() -> list[FeatureProfile]:
    """3 segments × 2 numerical features (Recency, Monetary)."""
    return [
        FeatureProfile(
            segment_id=0, feature_name="Recency", statistics={"mean": 5.0, "median": 4.0}
        ),
        FeatureProfile(
            segment_id=0, feature_name="Monetary", statistics={"mean": 100.0, "median": 95.0}
        ),
        FeatureProfile(
            segment_id=1, feature_name="Recency", statistics={"mean": 15.0, "median": 14.0}
        ),
        FeatureProfile(
            segment_id=1, feature_name="Monetary", statistics={"mean": 200.0, "median": 195.0}
        ),
        FeatureProfile(
            segment_id=2, feature_name="Recency", statistics={"mean": 25.0, "median": 24.0}
        ),
        FeatureProfile(
            segment_id=2, feature_name="Monetary", statistics={"mean": 300.0, "median": 295.0}
        ),
    ]


def _make_dataset_stats() -> dict[str, dict[str, float]]:
    """Dataset-wide stats: Recency mean=15, std=8.16; Monetary mean=200, std=81.6."""
    return {
        "Recency": {"mean": 15.0, "median": 14.0, "std": 8.16496580927726},
        "Monetary": {"mean": 200.0, "median": 195.0, "std": 81.6496580927726},
    }


# ---------------------------------------------------------------------------
# Allowed rule set
# ---------------------------------------------------------------------------


def test_allowed_rules_count_is_four() -> None:
    """Per OQ-SEG-CHAR-01: 4 rules only (reduced set)."""
    assert len(ALLOWED_CHARACTERISTIC_RULES) == 4


def test_allowed_rules_excludes_diversity_and_missing() -> None:
    """The two removed rules MUST NOT be in the allowlist."""
    for forbidden in ("category_diversity_low_<feature>", "missing_share_high_<feature>"):
        assert forbidden not in ALLOWED_CHARACTERISTIC_RULES


def test_allowed_rules_includes_expected_set() -> None:
    expected = {
        "mean_high_<feature>",
        "mean_low_<feature>",
        "median_above_dataset_median_<feature>",
        "top_category_<feature>_<value>",
    }
    assert expected == ALLOWED_CHARACTERISTIC_RULES


# ---------------------------------------------------------------------------
# derive_segment_characteristics — happy path
# ---------------------------------------------------------------------------


def test_derive_returns_list_of_characteristic_entries() -> None:
    profiles = _make_profiles()
    dataset_stats = _make_dataset_stats()
    chars = derive_segment_characteristics(
        profiles=profiles,
        dataset_stats=dataset_stats,
    )
    assert isinstance(chars, list)
    for c in chars:
        assert isinstance(c, CharacteristicEntry)


def test_derive_mean_high_for_high_mean_segment() -> None:
    """segment 2 has Recency mean=25 > 15+1*8.16=23.16 ⇒ mean_high_Recency."""
    profiles = _make_profiles()
    dataset_stats = _make_dataset_stats()
    chars = derive_segment_characteristics(
        profiles=profiles,
        dataset_stats=dataset_stats,
        z_threshold=1.0,
    )
    ids = {c.characteristic_id for c in chars}
    assert "mean_high_Recency" in ids


def test_derive_mean_low_for_low_mean_segment() -> None:
    """segment 0 has Recency mean=5 < 15-1*8.16=6.84 ⇒ mean_low_Recency."""
    profiles = _make_profiles()
    dataset_stats = _make_dataset_stats()
    chars = derive_segment_characteristics(
        profiles=profiles,
        dataset_stats=dataset_stats,
        z_threshold=1.0,
    )
    ids = {c.characteristic_id for c in chars}
    assert "mean_low_Recency" in ids


def test_derive_median_above_dataset_median() -> None:
    """segment 2 has Recency median=24 > 14 ⇒ median_above_dataset_median_Recency."""
    profiles = _make_profiles()
    dataset_stats = _make_dataset_stats()
    chars = derive_segment_characteristics(
        profiles=profiles,
        dataset_stats=dataset_stats,
    )
    ids = {c.characteristic_id for c in chars}
    assert "median_above_dataset_median_Recency" in ids


def test_derive_top_category_emitted_for_categorical_profile() -> None:
    """If a categorical profile has topk_categories, emit top_category_<feature>_<value>."""
    profiles = [
        FeatureProfile(
            segment_id=0,
            feature_name="Country",
            statistics={
                "topk_categories": [("UK", 4), ("NL", 2), ("FR", 1)],
                "value_counts": {"UK": 4, "NL": 2, "FR": 1},
                "other_count": 0,
                "missing_count": 0,
            },
        ),
    ]
    chars = derive_segment_characteristics(
        profiles=profiles,
        dataset_stats={},
    )
    ids = {c.characteristic_id for c in chars}
    assert "top_category_Country_UK" in ids


def test_derive_top_category_no_topk_does_not_emit() -> None:
    """Numerical profiles do NOT emit top_category."""
    profiles = _make_profiles()
    dataset_stats = _make_dataset_stats()
    chars = derive_segment_characteristics(
        profiles=profiles,
        dataset_stats=dataset_stats,
    )
    ids = {c.characteristic_id for c in chars}
    for cid in ids:
        assert not cid.startswith("top_category_")


def test_derive_does_not_emit_disallowed_rules() -> None:
    """No characteristic_id outside the 4 allowed templates."""
    profiles = _make_profiles()
    dataset_stats = _make_dataset_stats()
    chars = derive_segment_characteristics(
        profiles=profiles,
        dataset_stats=dataset_stats,
    )
    for c in chars:
        # All ids must match the regex template.
        import re

        assert re.match(
            r"^(mean_high_[A-Za-z0-9_]+|mean_low_[A-Za-z0-9_]+"
            r"|median_above_dataset_median_[A-Za-z0-9_]+"
            r"|top_category_[A-Za-z0-9_]+_.+)$",
            c.characteristic_id,
        ), f"Disallowed characteristic_id: {c.characteristic_id!r}"


# ---------------------------------------------------------------------------
# z_threshold behavior
# ---------------------------------------------------------------------------


def test_z_threshold_zero_marks_all_above_mean() -> None:
    """z_threshold=0: any segment with mean > dataset mean → mean_high."""
    profiles = _make_profiles()
    dataset_stats = _make_dataset_stats()
    chars = derive_segment_characteristics(
        profiles=profiles,
        dataset_stats=dataset_stats,
        z_threshold=0.0,
    )
    ids = {c.characteristic_id for c in chars}
    # segment 2 (mean=25) > 15 ⇒ mean_high_Recency.
    assert "mean_high_Recency" in ids
    # segment 0 (mean=5) < 15 ⇒ mean_low_Recency.
    assert "mean_low_Recency" in ids


def test_z_threshold_high_marks_no_one() -> None:
    """z_threshold=1000: nobody is far enough from dataset mean."""
    profiles = _make_profiles()
    dataset_stats = _make_dataset_stats()
    chars = derive_segment_characteristics(
        profiles=profiles,
        dataset_stats=dataset_stats,
        z_threshold=1000.0,
    )
    ids = {c.characteristic_id for c in chars}
    assert "mean_high_Recency" not in ids
    assert "mean_low_Recency" not in ids


# ---------------------------------------------------------------------------
# Missing data / edge cases
# ---------------------------------------------------------------------------


def test_derive_empty_profiles_returns_empty() -> None:
    chars = derive_segment_characteristics(profiles=[], dataset_stats={})
    assert chars == []


def test_derive_segment_with_missing_mean_skips_mean_rules() -> None:
    """If segment mean is None, mean_high/mean_low rules are NOT emitted."""
    profiles = [
        FeatureProfile(
            segment_id=0, feature_name="Recency", statistics={"mean": None, "median": 4.0}
        ),
    ]
    chars = derive_segment_characteristics(
        profiles=profiles,
        dataset_stats={"Recency": {"mean": 15.0, "median": 14.0, "std": 1.0}},
    )
    ids = {c.characteristic_id for c in chars}
    assert "mean_high_Recency" not in ids
    assert "mean_low_Recency" not in ids


def test_derive_dataset_stats_missing_for_feature_skips_mean_rules() -> None:
    """If dataset_stats lacks the feature, no mean-based rule is emitted."""
    profiles = _make_profiles()
    chars = derive_segment_characteristics(
        profiles=profiles,
        dataset_stats={},  # empty
    )
    ids = {c.characteristic_id for c in chars}
    assert "mean_high_Recency" not in ids
    assert "mean_low_Recency" not in ids
    # median rule also requires dataset median.
    assert "median_above_dataset_median_Recency" not in ids


def test_derive_top_category_with_empty_topk_does_not_emit() -> None:
    profiles = [
        FeatureProfile(
            segment_id=0,
            feature_name="Country",
            statistics={
                "topk_categories": [],
                "value_counts": {},
                "other_count": 0,
                "missing_count": 0,
            },
        ),
    ]
    chars = derive_segment_characteristics(
        profiles=profiles,
        dataset_stats={},
    )
    ids = {c.characteristic_id for c in chars}
    assert not any(c.startswith("top_category_") for c in ids)


# ---------------------------------------------------------------------------
# Description + source_features + derived_stats
# ---------------------------------------------------------------------------


def test_characteristic_entry_has_required_fields() -> None:
    profiles = _make_profiles()
    dataset_stats = _make_dataset_stats()
    chars = derive_segment_characteristics(
        profiles=profiles,
        dataset_stats=dataset_stats,
        z_threshold=1.0,
    )
    for c in chars:
        assert c.description
        assert c.source_features
        assert isinstance(c.derived_stats, dict)


def test_derived_stats_contain_threshold_and_actual() -> None:
    """mean_high/mean_low rules record threshold and actual values."""
    profiles = _make_profiles()
    dataset_stats = _make_dataset_stats()
    chars = derive_segment_characteristics(
        profiles=profiles,
        dataset_stats=dataset_stats,
        z_threshold=1.0,
    )
    for c in chars:
        if c.characteristic_id.startswith(("mean_high_", "mean_low_")):
            assert "threshold" in c.derived_stats
            assert "actual" in c.derived_stats
            assert "dataset_mean" in c.derived_stats


def test_no_segment_business_label_emitted() -> None:
    """Per R-DEV-06-19: NO business labels (no 'VIP', 'loyal', etc.)."""
    profiles = _make_profiles()
    dataset_stats = _make_dataset_stats()
    chars = derive_segment_characteristics(
        profiles=profiles,
        dataset_stats=dataset_stats,
    )
    forbidden_substrings = (
        "vip",
        "loyal",
        "champion",
        "at-risk",
        "at_risk",
        "high-value",
        "high_value",
        "winner",
        "best",
        "optimal",
        "recommended",
    )
    for c in chars:
        cid_lower = c.characteristic_id.lower()
        desc_lower = c.description.lower()
        for sub in forbidden_substrings:
            assert sub not in cid_lower, (
                f"characteristic_id {c.characteristic_id!r} contains "
                f"forbidden business term {sub!r}"
            )
            assert sub not in desc_lower, (
                f"description {c.description!r} contains " f"forbidden business term {sub!r}"
            )


# ---------------------------------------------------------------------------
# segment_id propagation on CharacteristicEntry (P1-1 fix)
# ---------------------------------------------------------------------------


def test_characteristic_entry_default_segment_id_is_minus_one() -> None:
    """Default segment_id is -1 (noise sentinel) for backward compat."""
    c = CharacteristicEntry(
        characteristic_id="mean_high_a",
        description="d",
        source_features=["a"],
        derived_stats={},
    )
    assert c.segment_id == -1


def test_characteristic_entry_accepts_segment_id() -> None:
    """Explicit segment_id is preserved."""
    c = CharacteristicEntry(
        characteristic_id="mean_high_a",
        description="d",
        source_features=["a"],
        derived_stats={},
        segment_id=3,
    )
    assert c.segment_id == 3


def test_characteristic_entry_to_dict_includes_segment_id() -> None:
    """to_dict emits segment_id (per plan §4.2 contract)."""
    c = CharacteristicEntry(
        characteristic_id="mean_high_a",
        description="d",
        source_features=["a"],
        derived_stats={"k": "v"},
        segment_id=2,
    )
    d = c.to_dict()
    assert d["segment_id"] == 2
    assert d["characteristic_id"] == "mean_high_a"


def test_characteristic_entry_rejects_negative_segment_id_below_minus_one() -> None:
    """segment_id < -1 is rejected (only -1 reserved for noise)."""
    from customer_segmentation.prototype.segmentation.manifest import (
        SegmentationManifestError,
    )

    with pytest.raises(SegmentationManifestError):
        CharacteristicEntry(
            characteristic_id="mean_high_a",
            description="d",
            source_features=["a"],
            derived_stats={},
            segment_id=-2,
        )


def test_characteristic_entry_rejects_non_int_segment_id() -> None:
    """segment_id MUST be an int."""
    from customer_segmentation.prototype.segmentation.manifest import (
        SegmentationManifestError,
    )

    with pytest.raises(SegmentationManifestError):
        CharacteristicEntry(
            characteristic_id="mean_high_a",
            description="d",
            source_features=["a"],
            derived_stats={},
            segment_id="not-an-int",  # type: ignore[arg-type]
        )


def test_derive_segment_characteristics_propagates_segment_id() -> None:
    """Each emitted CharacteristicEntry carries the source segment_id."""
    profiles = _make_profiles()  # segments 0, 1, 2
    dataset_stats = _make_dataset_stats()
    chars = derive_segment_characteristics(
        profiles=profiles, dataset_stats=dataset_stats, z_threshold=1.0
    )
    assert chars, "expected at least one characteristic"
    seg_ids = {c.segment_id for c in chars}
    # segments 0, 1, 2 may all appear depending on threshold;
    # but every entry must reference one of those (or -1 default
    # from forward-compat — never any other value).
    assert seg_ids <= {0, 1, 2}, f"unexpected segment_ids: {seg_ids}"
