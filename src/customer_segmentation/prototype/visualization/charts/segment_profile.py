"""Segment profile table for DEV-08 Prototype Visualization.

This module renders a per-segment profile view from a
:class:`SegmentationManifest`. It is the **prototype layer** (DEV-08) and
does not modify research artefacts or introduce ranking / recommendation
language.

Output
------
- **Text table** (string): one block per segment containing
  ``segment_id``, ``count``, ``percentage``, ``is_noise``,
  ``percentage_base`` + the list of ``CharacteristicEntry`` rows
  associated with that segment.

Hard rules
----------
- Only fields present in the existing manifest contract are read.
- Missing / unavailable values are rendered as the configured
  placeholder (``--`` by default) — never silently replaced with zero.
- Noise rows (``is_noise=True``, ``segment_id == -1``) follow the
  existing contract: percentage may be ``--`` when
  ``percentage_base == "n_samples_used_for_compute"`` (denominator
  excludes noise rows).
- Characteristics with ``segment_id == -1`` (legacy / noise
  characteristics) are kept with the noise block when present.
- The mandatory disclaimer is appended at the end of the table.
- No banned word (best / winner / optimal / recommended / ranking /
  champion / loyal / high-value / at-risk / vip / churn) is emitted
  outside the disclaimer.
- No composite score, ranking, or recommendation is computed.
"""

from __future__ import annotations

import json
import textwrap
from typing import TYPE_CHECKING, Any, Final

from customer_segmentation.prototype.visualization.exceptions import (
    VisualizationError,
)
from customer_segmentation.prototype.visualization.scope import (
    DEFAULT_DISCLAIMER_TEXT,
)

if TYPE_CHECKING:
    from customer_segmentation.prototype.segmentation.manifest import (
        CharacteristicEntry,
        SegmentationManifest,
        SegmentSize,
    )


__all__ = [
    "format_segment_profile_table",
    "format_characteristic_entry",
    "collect_segment_characteristics",
]


# Default width for the description column in the characteristic sub-table.
_DESCRIPTION_WIDTH: Final[int] = 48

# Sentinel for "no characteristics" rows in a segment block.
_NO_CHARACTERISTICS_PLACEHOLDER: Final[str] = "-- (no characteristics available)"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fmt_derived_stats(stats: dict[str, Any]) -> str:
    """Return a compact one-line rendering of a ``derived_stats`` dict.

    The dict is rendered as ``key=value`` pairs separated by ``;``. Lists
    and dicts are JSON-encoded (compact) so the output stays on one line.
    """
    if not stats:
        return "--"
    parts: list[str] = []
    for k, v in stats.items():
        if isinstance(v, (list, dict)):
            parts.append(f"{k}={json.dumps(v, ensure_ascii=False, sort_keys=True)}")
        elif v is None:
            parts.append(f"{k}=--")
        else:
            parts.append(f"{k}={v!s}")
    return "; ".join(parts)


def format_characteristic_entry(
    characteristic: CharacteristicEntry,
    *,
    description_width: int = _DESCRIPTION_WIDTH,
    missing_value_placeholder: str = "--",
) -> str:
    """Return a printable rendering of a single :class:`CharacteristicEntry`.

    The output is a single multi-line block with one field per line so
    long descriptions and stat payloads do not break table alignment.
    """
    if (
        not isinstance(characteristic.characteristic_id, str)
        or not characteristic.characteristic_id
    ):
        # Defensive: the manifest __post_init__ already rejects this, but
        # the visualization layer must never crash on bad input.
        char_id_str = missing_value_placeholder
    else:
        char_id_str = characteristic.characteristic_id

    desc = characteristic.description or missing_value_placeholder
    desc_wrapped = textwrap.fill(
        desc,
        width=description_width,
        initial_indent="    ",
        subsequent_indent="    ",
        replace_whitespace=True,
        drop_whitespace=True,
    )

    source_features_str = (
        ",".join(characteristic.source_features)
        if characteristic.source_features
        else missing_value_placeholder
    )
    derived_stats_str = _fmt_derived_stats(characteristic.derived_stats)

    lines = [
        f"    characteristic_id: {char_id_str}",
        "    description:",
        desc_wrapped,
        f"    source_features: {source_features_str}",
        f"    derived_stats: {derived_stats_str}",
    ]
    return "\n".join(lines)


def collect_segment_characteristics(
    characteristics: list[CharacteristicEntry] | SegmentationManifest,
    segment_id: int,
) -> list[CharacteristicEntry]:
    """Return the list of characteristics whose ``segment_id`` matches.

    Handles both a raw list of :class:`CharacteristicEntry` and a
    :class:`SegmentationManifest` (uses its ``characteristics`` field).
    """
    if hasattr(characteristics, "characteristics"):
        chars: list[CharacteristicEntry] = list(characteristics.characteristics)  # type: ignore[union-attr]
    else:
        chars = list(characteristics)
    return [c for c in chars if int(c.segment_id) == int(segment_id)]


# ---------------------------------------------------------------------------
# Text table formatter
# ---------------------------------------------------------------------------


def format_segment_profile_table(
    manifest,
    *,
    include_noise: bool = True,
    disclaimer: str = DEFAULT_DISCLAIMER_TEXT,
    missing_value_placeholder: str = "--",
    description_width: int = _DESCRIPTION_WIDTH,
    characteristic_separator: str = "\n\n",
) -> str:
    """Return a printable per-segment profile table.

    Parameters
    ----------
    manifest : SegmentationManifest or list[SegmentSize]
        If a :class:`SegmentationManifest` is passed, all metadata
        (segment_sizes, characteristics, n_samples_input,
        n_samples_used_for_compute, n_segments, algorithm, algorithm_family,
        noise_count, noise_ratio, noise_policy_used,
        preprocessing_warning) is read from it.

        If a raw list of :class:`SegmentSize` is passed, only the segment
        sizes are shown. The caller must then also pass the characteristics
        explicitly via the ``manifest`` argument's ``characteristics`` if
        available; otherwise the segment blocks contain only the size
        fields. Use a :class:`SegmentationManifest` whenever possible.
    include_noise : bool, default True
        Whether to include the noise block (``segment_id == -1``) in the
        output. Default is True because the table is a raw display of
        manifest data.
    disclaimer : str
        Disclaimer text appended at the end. Must contain the banned
        substrings.
    missing_value_placeholder : str
        Placeholder for unavailable values (e.g. percentage when
        ``percentage_base == "n_samples_used_for_compute"`` for noise).
    description_width : int, default 48
        Maximum width for the description text in each characteristic
        block (used by :func:`format_characteristic_entry`).
    characteristic_separator : str, default ``"\\n\\n"``
        Separator between successive characteristic blocks within a
        single segment.

    Returns
    -------
    str
        Multi-line plain-text table.

    Raises
    ------
    VisualizationError
        When ``manifest`` resolves to an empty list of segment sizes
        (the table would have nothing to show).

    Notes
    -----
    - Percentages are taken directly from each ``SegmentSize.percentage``.
      When the percentage is not meaningful (e.g. noise row under
      ``percentage_base == "n_samples_used_for_compute"``) the
      placeholder is shown.
    - Characteristics with ``segment_id == -1`` are kept with the
      noise block when ``include_noise=True``.
    - The disclaimer is appended verbatim; it contains the banned
      substrings so the output remains clean per the display scan.
    """
    # Resolve manifest, segment_sizes, characteristics from input.
    if hasattr(manifest, "segment_sizes") and hasattr(manifest, "characteristics"):
        _seg_sizes: list[SegmentSize] = list(manifest.segment_sizes)  # type: ignore[union-attr]
        _chars: list[CharacteristicEntry] = list(manifest.characteristics)  # type: ignore[union-attr]
        _n_input: int | None = getattr(manifest, "n_samples_input", None)  # type: ignore[union-attr]
        _n_used: int | None = getattr(manifest, "n_samples_used_for_compute", None)  # type: ignore[union-attr]
        _n_segments: int | None = getattr(manifest, "n_segments", None)  # type: ignore[union-attr]
        _algorithm: str | None = getattr(manifest, "algorithm", None)  # type: ignore[union-attr]
        _algorithm_family: str | None = getattr(manifest, "algorithm_family", None)  # type: ignore[union-attr]
        _noise_count: int | None = getattr(manifest, "noise_count", None)  # type: ignore[union-attr]
        _noise_ratio: float | None = getattr(manifest, "noise_ratio", None)  # type: ignore[union-attr]
        _noise_policy: str | None = getattr(manifest, "noise_policy_used", None)  # type: ignore[union-attr]
        _segmentation_id: str | None = getattr(manifest, "segmentation_id", None)  # type: ignore[union-attr]
        _preprocessing_warning: str = str(
            getattr(manifest, "preprocessing_warning", "") or ""
        )  # type: ignore[union-attr]
    else:
        # Raw list of SegmentSize only — characteristics unavailable.
        _seg_sizes = list(manifest)
        _chars = []
        _n_input = None
        _n_used = None
        _n_segments = None
        _algorithm = None
        _algorithm_family = None
        _noise_count = None
        _noise_ratio = None
        _noise_policy = None
        _segmentation_id = None
        _preprocessing_warning = ""

    if not _seg_sizes:
        raise VisualizationError(
            "manifest has no segment_sizes; cannot render segment profile table."
        )

    lines: list[str] = []

    # --- Header --------------------------------------------------------
    lines.append("# Segment Profile")
    lines.append("# " + "=" * 78)
    if _segmentation_id is not None:
        lines.append(f"# segmentation_id     : {_segmentation_id}")
    if _algorithm is not None:
        lines.append(f"# algorithm           : {_algorithm}")
    if _algorithm_family is not None:
        lines.append(f"# algorithm_family    : {_algorithm_family}")
    if _n_input is not None:
        lines.append(f"# n_samples_input     : {_n_input}")
    if _n_used is not None:
        lines.append(f"# n_samples_used_for_compute: {_n_used}")
    if _n_segments is not None:
        lines.append(f"# n_segments          : {_n_segments}")
    if _noise_count is not None:
        lines.append(f"# noise_count         : {_noise_count}")
    if _noise_ratio is not None:
        lines.append(f"# noise_ratio         : {_noise_ratio:.4f}")
    if _noise_policy is not None:
        lines.append(f"# noise_policy_used   : {_noise_policy}")
    if _preprocessing_warning:
        lines.append("# preprocessing_warning:")
        wrapped_warning = textwrap.fill(
            _preprocessing_warning,
            width=74,
            initial_indent="#   ",
            subsequent_indent="#   ",
        )
        lines.append(wrapped_warning)
    lines.append("# " + "-" * 78)
    lines.append("")

    # --- Per-segment blocks -------------------------------------------
    # Order: non-noise segments first (preserving their declared order),
    # then noise block at the end if present and include_noise=True.
    non_noise = [s for s in _seg_sizes if not s.is_noise]
    noise_rows = [s for s in _seg_sizes if s.is_noise]

    for idx, s in enumerate(non_noise):
        _render_segment_block(
            lines,
            s,
            chars=_chars,
            missing_value_placeholder=missing_value_placeholder,
            description_width=description_width,
            characteristic_separator=characteristic_separator,
        )
        if idx < len(non_noise) - 1 or noise_rows:
            lines.append("")

    if noise_rows and include_noise:
        for s in noise_rows:
            _render_segment_block(
                lines,
                s,
                chars=_chars,
                missing_value_placeholder=missing_value_placeholder,
                description_width=description_width,
                characteristic_separator=characteristic_separator,
            )

    lines.append("")
    lines.append("# " + "-" * 78)
    lines.append(f"Disclaimer: {disclaimer}")
    return "\n".join(lines)


def _render_segment_block(
    lines: list[str],
    segment: SegmentSize,
    *,
    chars: list[CharacteristicEntry],
    missing_value_placeholder: str,
    description_width: int,
    characteristic_separator: str,
) -> None:
    """Append a single segment block to ``lines`` (in-place)."""
    seg_id = int(segment.segment_id)
    count = int(segment.count)
    pct = float(segment.percentage)
    pct_base = str(segment.percentage_base)
    is_noise = bool(segment.is_noise)

    label = "Noise" if is_noise else f"Segment {seg_id}"
    lines.append(f"# {label}")
    lines.append("# " + "-" * 78)
    lines.append(f"# segment_id       : {seg_id}")
    lines.append(f"# count            : {count}")
    if is_noise and pct_base == "n_samples_used_for_compute":
        # The percentage is not meaningful for the noise row under
        # the n_samples_used_for_compute base — surface that explicitly.
        lines.append(
            f"# pct              : {missing_value_placeholder}"
            f" (not meaningful: percentage_base excludes noise rows)"
        )
    else:
        lines.append(f"# pct              : {pct:.1f}")
    lines.append(f"# percentage_base  : {pct_base}")
    lines.append(f"# is_noise         : {is_noise}")

    seg_chars = [c for c in chars if int(c.segment_id) == seg_id]
    if seg_chars:
        lines.append(f"# characteristics ({len(seg_chars)}):")
        char_blocks = [
            format_characteristic_entry(
                c,
                description_width=description_width,
                missing_value_placeholder=missing_value_placeholder,
            )
            for c in seg_chars
        ]
        lines.append(characteristic_separator.join(char_blocks))
    else:
        lines.append(f"# characteristics   : {_NO_CHARACTERISTICS_PLACEHOLDER}")
