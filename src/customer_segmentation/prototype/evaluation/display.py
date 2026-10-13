"""Display helpers for DEV-05 Prototype Evaluation.

The display module is purely textual — it produces a printable string
table for ``EvaluationMetricsResult`` and a (future) comparison report.
The format is intentionally minimal:

- For each metric, the row is::

      {metric_name:<24} {value_or_placeholder:>12} [{status:<16}] ({reason})

  where ``value_or_placeholder`` is the numeric value formatted to 3
  decimal places for ``VALID_VALUE`` rows, or ``--`` (em-dash) for any
  other status.

- For ``NOT_APPLICABLE`` / ``MISSING`` / ``COMPUTATION_ERROR`` rows, a
  parenthetical reason is appended so readers can see at a glance WHY
  the value is missing.

This module NEVER prints "best" / "winner" / "recommended" / "optimal"
or any "ranking" / "score" / "aggregate" word outside the disclaimer
phrase. R-EVAL-08 / R-EVAL-15 enforcement.
"""

from __future__ import annotations

import textwrap
from typing import Any, Final

from customer_segmentation.prototype.evaluation.manifest import (
    EvaluationMetricEntry,
    EvaluationMetricsResult,
    EvaluationManifest,
)
from customer_segmentation.prototype.evaluation.scope import (
    MetricReason,
    MetricStatus,
)

__all__ = [
    "format_metrics_table",
    "format_manifest_path",
    "BANNED_SUBSTRINGS_OUTSIDE_DISCLAIMER",
    "DEFAULT_DISCLAIMER_TEXT",
    "check_no_banned_substrings",
]


DEFAULT_DISCLAIMER_TEXT: Final[str] = (
    "no ranking, recommendation, or winner annotation is emitted"
)

# Words that MUST NOT appear in DEV-05 display output (R-EVAL-08 / R-EVAL-15).
# The disclaimer is the single allowed occurrence (negation pattern).
BANNED_SUBSTRINGS: Final[tuple[str, ...]] = (
    "best",
    "winner",
    "optimal",
    "recommended",
    "ranking",
    "composite_score",
)


def _format_value(entry: EvaluationMetricEntry) -> str:
    """Format a metric entry's value for display."""
    if entry.value is not None:
        return f"{entry.value:>12.3f}"
    return f"{'--':>12}"


def _format_status_block(entry: EvaluationMetricEntry) -> str:
    """Format the ``[STATUS]`` + reason suffix."""
    status_str = f"[{entry.status}]"
    return f"{status_str:<18} {entry.reason}"


def format_metrics_table(
    result: EvaluationMetricsResult,
    *,
    missing_value_placeholder: str = "--",
) -> str:
    """Return a printable table for the 3-metric result.

    Parameters
    ----------
    result : EvaluationMetricsResult
        Per-metric entries to render.
    missing_value_placeholder : str
        The placeholder string for non-VALID_VALUE rows. Default ``"--"``
        (em-dash), per OQ-EVAL-06 display convention.
    """
    lines: list[str] = []
    lines.append(
        f"{'metric':<24} {'value':>12}   {'status':<16}  reason"
    )
    lines.append("-" * 72)
    for metric_name in ("silhouette", "davies_bouldin", "calinski_harabasz"):
        entry = result.entries[metric_name]
        if entry.status == MetricStatus.VALID_VALUE.value and entry.value is not None:
            value_str = f"{entry.value:>12.3f}"
        else:
            # Right-pad the placeholder to the value column width.
            value_str = f"{missing_value_placeholder:>12}"
        status_str = f"[{entry.status}]"
        lines.append(
            f"{metric_name:<24} {value_str}   {status_str:<16}  {entry.reason}"
        )
    return "\n".join(lines)


def format_manifest_path(
    manifest: EvaluationManifest,
    *,
    path_prefix: str = "",
) -> str:
    """Return a one-line summary of the manifest for CLI display."""
    line = (
        f"evaluation_id={manifest.evaluation_id}  "
        f"algorithm={manifest.algorithm}  "
        f"noise_policy={manifest.noise_policy_used}  "
        f"n_samples_used={manifest.n_samples_used_for_compute}/"
        f"{manifest.n_samples_input}"
    )
    if path_prefix:
        line = f"{path_prefix}  {line}"
    return line


def check_no_banned_substrings(
    text: str,
    *,
    disclaimer: str = DEFAULT_DISCLAIMER_TEXT,
) -> list[str]:
    """Return the list of banned substrings present in ``text``.

    The disclaimer phrase is excluded from the check. Any other
    occurrence of a banned word is reported.

    Uses word-boundary matching (case-insensitive) so substrings like
    "recommended" don't trigger because of the disclaimer text
    containing "recommendation".

    Per R-EVAL-08 / R-EVAL-15.
    """
    import re

    found: list[str] = []
    # Strip the disclaimer phrase (case-insensitive).
    check_text = text
    if disclaimer:
        lower = check_text.lower()
        dl_lower = disclaimer.lower()
        while dl_lower in lower:
            idx = lower.index(dl_lower)
            check_text = check_text[:idx] + check_text[idx + len(dl_lower) :]
            lower = check_text.lower()
    # Use word-boundary regex for accurate detection.
    for banned in BANNED_SUBSTRINGS:
        # \b matches at word boundaries; re.escape protects special chars.
        pattern = r"\b" + re.escape(banned) + r"\b"
        if re.search(pattern, check_text, flags=re.IGNORECASE):
            found.append(banned)
    return found


# Backwards-compatible alias (was the name in the plan).
BANNED_SUBSTRINGS_OUTSIDE_DISCLAIMER: Final[tuple[str, ...]] = BANNED_SUBSTRINGS
