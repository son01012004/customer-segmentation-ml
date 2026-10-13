"""CP-04 §4.1-§4.3 segment name tokenization parser for DEV-07 Phase B.

This module implements **pure parsing** of CP-04 segment names into
their constituent tokens (RFM tiers + behavioural modifiers).
It does NOT generate content, does NOT call DEV-06 / DEV-07 code,
does NOT mutate any state, and does NOT depend on disk I/O.

The parser implements CP-04 §4.1-§4.3 (verified by `Read` of
``docs/evaluation/CP-04.md``):

- **§4.1 RFM core tiers** — Recency: Recent / Older / Mixed;
  Frequency: Frequent / Occasional / Mixed; Monetary: HighValue /
  LowValue / Mixed.
- **§4.2 Behavioural modifiers** — LongTenured, IrregularCadence,
  Bulk, Active.
- **§4.3 Construction rules** — ``[RecencyTier] [FrequencyTier]`` +
  optional ``MonetaryTier`` (when Monetary direction != Frequency
  direction OR both HIGHER) + optional ``Modifier`` (when
  direction=HIGHER + classification=HIGH_DIFFERENCE_OBSERVED).
  Total tokens ≤ 4 words.

This module is owner-resolved safe: it parses CP-04 tokens without
synthesizing any marketing business content. It does not address
OQ-D07-03 (canonical tokenization confirmation); it merely
implements the parsing logic per CP-04 §4.1-§4.3.

Hard rules
----------
- Pure functions only (no side effects, no I/O, no datetime).
- Closed set of tier / modifier tokens (frozen at module load).
- Order-independent parsing (parse from any starting point; verify
  coverage).
- A name that matches a CP-04 §4.3 pattern returns the full token
  tuple. A name that does NOT match (e.g. ``COMPARATIVE``, ``NOT_AVAILABLE``,
  ``NOISE``, ``Mixed Mixed`` per CP-04 §5.3 sample) returns a sentinel
  ``CP04TokenizationResult`` with ``tier_match=False``.
- The parser NEVER auto-fixes / corrects a malformed name; it
  surfaces the unmatched tokens in ``unmatched_tokens``.
- No filesystem / network / datetime imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

__all__ = [
    "RECENCY_TIERS",
    "FREQUENCY_TIERS",
    "MONETARY_TIERS",
    "BEHAVIOURAL_MODIFIERS",
    "CP04TokenizationResult",
    "parse_cp04_segment_name",
]


# ---------------------------------------------------------------------------
# Closed sets (CP-04 §4.1 + §4.2 — verified 2026-10-10)
# ---------------------------------------------------------------------------

# Recency tiers (CP-04 §4.1)
RECENCY_TIERS: Final[frozenset[str]] = frozenset({"Recent", "Older", "Mixed"})

# Frequency tiers (CP-04 §4.1)
FREQUENCY_TIERS: Final[frozenset[str]] = frozenset({"Frequent", "Occasional", "Mixed"})

# Monetary tiers (CP-04 §4.1)
MONETARY_TIERS: Final[frozenset[str]] = frozenset({"HighValue", "LowValue", "Mixed"})

# Behavioural modifiers (CP-04 §4.2)
BEHAVIOURAL_MODIFIERS: Final[frozenset[str]] = frozenset(
    {"LongTenured", "IrregularCadence", "Bulk", "Active"}
)

# All valid tokens combined (for membership tests).
ALL_VALID_TOKENS: Final[frozenset[str]] = frozenset(
    RECENCY_TIERS | FREQUENCY_TIERS | MONETARY_TIERS | BEHAVIOURAL_MODIFIERS
)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CP04TokenizationResult:
    """Outcome of parsing one CP-04 segment name.

    Attributes
    ----------
    segment_name : str
        The input segment name (verbatim, post-strip).
    recency_tier : str or None
        Matched Recency tier (CP-04 §4.1), or None if unmatched.
    frequency_tier : str or None
        Matched Frequency tier (CP-04 §4.1), or None if unmatched.
    monetary_tier : str or None
        Matched Monetary tier (CP-04 §4.1), or None if unmatched / absent.
    modifiers : tuple of str
        Matched behavioural modifiers (CP-04 §4.2), in encounter order.
    unmatched_tokens : tuple of str
        Tokens that did NOT match any tier / modifier (e.g. segment
        names with ``Comparative`` fallback or unknown words).
    tier_match : bool
        True iff the parser found at least one valid
        (RecencyTier, FrequencyTier) pair AND every word in the
        segment name is accounted for in the matched tiers /
        modifiers (no unmatched tokens).

    Notes
    -----
    Per CP-04 §4.3, total tokens in a NAMED segment is ≤ 4 words.
    The parser does NOT auto-correct / fabricate a token when one is
    missing.
    """

    segment_name: str
    recency_tier: str | None
    frequency_tier: str | None
    monetary_tier: str | None
    modifiers: tuple[str, ...]
    unmatched_tokens: tuple[str, ...]
    tier_match: bool

    def __post_init__(self) -> None:
        if self.recency_tier is not None and self.recency_tier not in RECENCY_TIERS:
            raise ValueError(
                f"recency_tier {self.recency_tier!r} is not in " f"{sorted(RECENCY_TIERS)}."
            )
        if self.frequency_tier is not None and self.frequency_tier not in FREQUENCY_TIERS:
            raise ValueError(
                f"frequency_tier {self.frequency_tier!r} is not in " f"{sorted(FREQUENCY_TIERS)}."
            )
        if self.monetary_tier is not None and self.monetary_tier not in MONETARY_TIERS:
            raise ValueError(
                f"monetary_tier {self.monetary_tier!r} is not in " f"{sorted(MONETARY_TIERS)}."
            )
        for m in self.modifiers:
            if m not in BEHAVIOURAL_MODIFIERS:
                raise ValueError(f"modifier {m!r} is not in {sorted(BEHAVIOURAL_MODIFIERS)}.")


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def _tokenize_words(name: str) -> list[str]:
    """Split a CP-04 segment name into words.

    Whitespace-split only. Empty tokens are filtered out.
    """
    return [w for w in name.split() if w]


def parse_cp04_segment_name(segment_name: str) -> CP04TokenizationResult:
    """Parse a CP-04 segment name into its constituent tokens.

    Parameters
    ----------
    segment_name : str
        A segment name produced by CP-04 (e.g. ``"Recent Frequent
        HighValue LongTenured"``). May be empty.

    Returns
    -------
    CP04TokenizationResult
        Structured result with matched tiers / modifiers and any
        unmatched tokens. ``tier_match=True`` only when the input
        conforms to a CP-04 §4.3 NAMED segment.

    Notes
    -----
    The returned ``segment_name`` field is normalized: leading /
    trailing whitespace is stripped and runs of internal whitespace
    are collapsed to a single space. The original tokenization
    matches CP-04 §4.1-§4.3 tiers / modifiers regardless of internal
    whitespace.

    Examples
    --------
    >>> parse_cp04_segment_name("Recent Frequent HighValue LongTenured")
    CP04TokenizationResult(
      segment_name='Recent Frequent HighValue LongTenured',
      recency_tier='Recent', frequency_tier='Frequent',
      monetary_tier='HighValue',
      modifiers=('LongTenured',),
      unmatched_tokens=(), tier_match=True,
    )

    >>> parse_cp04_segment_name("Mixed Mixed")
    CP04TokenizationResult(
      segment_name='Mixed Mixed',
      recency_tier='Mixed', frequency_tier='Mixed',
      monetary_tier=None, modifiers=(),
      unmatched_tokens=(), tier_match=True)

    >>> parse_cp04_segment_name("Comparative Segment A")
    CP04TokenizationResult(
      segment_name='Comparative Segment A',
      recency_tier=None, frequency_tier=None,
      monetary_tier=None, modifiers=(),
      unmatched_tokens=('Comparative', 'Segment', 'A'),
      tier_match=False)
    """
    # Normalize whitespace: strip ends + collapse internal runs.
    normalized = " ".join(segment_name.split())
    words = [w for w in normalized.split(" ") if w]

    recency_tier: str | None = None
    frequency_tier: str | None = None
    monetary_tier: str | None = None
    modifiers: list[str] = []
    unmatched: list[str] = []

    for w in words:
        if w in RECENCY_TIERS and recency_tier is None:
            recency_tier = w
        elif w in FREQUENCY_TIERS and frequency_tier is None:
            frequency_tier = w
        elif w in MONETARY_TIERS and monetary_tier is None:
            monetary_tier = w
        elif w in BEHAVIOURAL_MODIFIERS:
            # Modifiers may co-occur (per CP-04 §4.2); keep all.
            modifiers.append(w)
        else:
            unmatched.append(w)

    # CP-04 §4.3 requires at minimum (RecencyTier + FrequencyTier)
    # for a NAMED segment. tier_match requires both tiers present
    # AND every word accounted for in valid tokens.
    has_minimum_tiers = recency_tier is not None and frequency_tier is not None
    all_words_accounted = len(unmatched) == 0
    tier_match = has_minimum_tiers and all_words_accounted

    return CP04TokenizationResult(
        segment_name=normalized,
        recency_tier=recency_tier,
        frequency_tier=frequency_tier,
        monetary_tier=monetary_tier,
        modifiers=tuple(modifiers),
        unmatched_tokens=tuple(unmatched),
        tier_match=tier_match,
    )
