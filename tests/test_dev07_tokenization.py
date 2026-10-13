"""Tests for CP-04 §4.1-§4.3 segment name tokenization parser.

The parser is a pure function; tests verify that:
- Closed sets of tier / modifier tokens are exactly as CP-04 §4.1
  and §4.2 specify.
- Parsing recognises every documented RFM tier × tier × optional
  monetary tier × optional modifier combination.
- ``Mixed Mixed`` (CP-04 §5.3 sample) parses cleanly.
- Names with non-CP-04 tokens (e.g. ``"Comparative Segment A"``)
  surface unmatched tokens and return ``tier_match=False``.
- Empty / non-string inputs are handled defensively.
"""

from __future__ import annotations

import pytest

from customer_segmentation.prototype.marketing.tokenization import (
    ALL_VALID_TOKENS,
    BEHAVIOURAL_MODIFIERS,
    FREQUENCY_TIERS,
    MONETARY_TIERS,
    RECENCY_TIERS,
    CP04TokenizationResult,
    parse_cp04_segment_name,
)

# ---------------------------------------------------------------------------
# Closed-set sanity
# ---------------------------------------------------------------------------


class TestClosedSets:
    def test_recency_tiers_exact(self) -> None:
        assert frozenset({"Recent", "Older", "Mixed"}) == RECENCY_TIERS

    def test_frequency_tiers_exact(self) -> None:
        assert frozenset({"Frequent", "Occasional", "Mixed"}) == FREQUENCY_TIERS

    def test_monetary_tiers_exact(self) -> None:
        assert frozenset({"HighValue", "LowValue", "Mixed"}) == MONETARY_TIERS

    def test_modifiers_exact(self) -> None:
        assert (
            frozenset({"LongTenured", "IrregularCadence", "Bulk", "Active"})
            == BEHAVIOURAL_MODIFIERS
        )

    def test_all_valid_tokens_is_union(self) -> None:
        assert ALL_VALID_TOKENS == (
            RECENCY_TIERS | FREQUENCY_TIERS | MONETARY_TIERS | BEHAVIOURAL_MODIFIERS
        )


# ---------------------------------------------------------------------------
# CP-04 §4.3 canonical patterns (CP-04 §5.3 sample names)
# ---------------------------------------------------------------------------


class TestCanonicalParse:
    def test_kmin_self_c0(self) -> None:
        """K-Means EXP-01 C0 sample: Recent Frequent HighValue LongTenured."""
        r = parse_cp04_segment_name("Recent Frequent HighValue LongTenured")
        assert r.recency_tier == "Recent"
        assert r.frequency_tier == "Frequent"
        assert r.monetary_tier == "HighValue"
        assert r.modifiers == ("LongTenured",)
        assert r.unmatched_tokens == ()
        assert r.tier_match is True

    def test_kmin_c1(self) -> None:
        r = parse_cp04_segment_name("Older Occasional")
        assert r.recency_tier == "Older"
        assert r.frequency_tier == "Occasional"
        assert r.monetary_tier is None
        assert r.modifiers == ()
        assert r.tier_match is True

    def test_kmin_c2(self) -> None:
        """Same as C0 — Recent Frequent HighValue LongTenured."""
        r = parse_cp04_segment_name("Recent Frequent HighValue LongTenured")
        assert r.tier_match is True

    def test_kmin_c3(self) -> None:
        r = parse_cp04_segment_name("Recent Frequent HighValue LongTenured")
        assert r.tier_match is True

    def test_dbscan_c1_dominant(self) -> None:
        """DBSCAN C1 dominant non-noise: Mixed Mixed (per CP-04 §5.3)."""
        r = parse_cp04_segment_name("Mixed Mixed")
        assert r.recency_tier == "Mixed"
        assert r.frequency_tier == "Mixed"
        assert r.monetary_tier is None
        assert r.modifiers == ()
        assert r.tier_match is True

    def test_dbscan_bulk(self) -> None:
        """DBSCAN sample: Recent Frequent HighValue Bulk."""
        r = parse_cp04_segment_name("Recent Frequent HighValue Bulk")
        assert r.modifiers == ("Bulk",)
        assert r.tier_match is True

    def test_recency_only_older(self) -> None:
        r = parse_cp04_segment_name("Older")
        # No frequency tier → not a valid NAMED segment per §4.3.
        assert r.recency_tier == "Older"
        assert r.frequency_tier is None
        assert r.tier_match is False

    def test_recency_freq_only(self) -> None:
        r = parse_cp04_segment_name("Older Occasional")
        assert r.recency_tier == "Older"
        assert r.frequency_tier == "Occasional"
        assert r.tier_match is True


# ---------------------------------------------------------------------------
# Modifiers
# ---------------------------------------------------------------------------


class TestModifiers:
    def test_long_tenured(self) -> None:
        r = parse_cp04_segment_name("Recent Frequent LongTenured")
        assert "LongTenured" in r.modifiers

    def test_irregular_cadence(self) -> None:
        r = parse_cp04_segment_name("Older Occasional IrregularCadence")
        assert "IrregularCadence" in r.modifiers

    def test_bulk(self) -> None:
        r = parse_cp04_segment_name("Recent Frequent HighValue Bulk")
        assert "Bulk" in r.modifiers

    def test_active(self) -> None:
        r = parse_cp04_segment_name("Recent Frequent Active")
        assert "Active" in r.modifiers


# ---------------------------------------------------------------------------
# Failure cases
# ---------------------------------------------------------------------------


class TestFailures:
    def test_empty_string(self) -> None:
        r = parse_cp04_segment_name("")
        assert r.segment_name == ""
        assert r.tier_match is False
        assert r.unmatched_tokens == ()

    def test_whitespace_only(self) -> None:
        r = parse_cp04_segment_name("   \t  ")
        assert r.tier_match is False

    def test_comparative_fallback(self) -> None:
        """CP-04 §4.3 fallback: 'Comparative Segment A' / 'B' / 'C'."""
        r = parse_cp04_segment_name("Comparative Segment A")
        assert r.tier_match is False
        assert r.unmatched_tokens == ("Comparative", "Segment", "A")
        assert r.recency_tier is None
        assert r.frequency_tier is None

    def test_not_available_placeholder(self) -> None:
        """CP-04 §5.3 NAMING_PENDING / NOT_AVAILABLE → no tier match."""
        r = parse_cp04_segment_name("NOT_AVAILABLE")
        assert r.tier_match is False
        assert r.unmatched_tokens == ("NOT_AVAILABLE",)

    def test_noise_placeholder(self) -> None:
        """DBSCAN noise name = 'NOISE' per CP-04 §5.3."""
        r = parse_cp04_segment_name("NOISE")
        assert r.tier_match is False
        assert r.unmatched_tokens == ("NOISE",)

    def test_garbage_name(self) -> None:
        r = parse_cp04_segment_name("Foo Bar Baz")
        assert r.tier_match is False
        assert r.unmatched_tokens == ("Foo", "Bar", "Baz")

    def test_partial_match(self) -> None:
        """One tier present, the other missing → tier_match=False."""
        r = parse_cp04_segment_name("Recent HighValue")
        assert r.recency_tier == "Recent"
        assert r.frequency_tier is None
        assert r.monetary_tier == "HighValue"
        assert r.tier_match is False


# ---------------------------------------------------------------------------
# Defensive
# ---------------------------------------------------------------------------


class TestDefensive:
    def test_extra_whitespace_stripped(self) -> None:
        r = parse_cp04_segment_name("   Recent    Frequent   HighValue   ")
        assert r.segment_name == "Recent Frequent HighValue"
        assert r.tier_match is True

    def test_modifier_only_no_tier(self) -> None:
        r = parse_cp04_segment_name("LongTenured")
        assert r.recency_tier is None
        assert r.tier_match is False

    def test_invalid_tier_in_dataclass_raises(self) -> None:
        """Constructor rejects invalid tier values."""
        with pytest.raises(ValueError, match="recency_tier"):
            CP04TokenizationResult(
                segment_name="x",
                recency_tier="Invalid",
                frequency_tier=None,
                monetary_tier=None,
                modifiers=(),
                unmatched_tokens=(),
                tier_match=False,
            )

    def test_invalid_modifier_in_dataclass_raises(self) -> None:
        with pytest.raises(ValueError, match="modifier"):
            CP04TokenizationResult(
                segment_name="x",
                recency_tier=None,
                frequency_tier=None,
                monetary_tier=None,
                modifiers=("NotAModifier",),
                unmatched_tokens=(),
                tier_match=False,
            )

    def test_does_not_mutate_input(self) -> None:
        original = "Recent Frequent HighValue LongTenured"
        parse_cp04_segment_name(original)
        assert original == "Recent Frequent HighValue LongTenured"
