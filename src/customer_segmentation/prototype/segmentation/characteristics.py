"""Per-segment characteristics derivation for DEV-06 (4-rule engine).

Per OQ-SEG-CHAR-01, DEV-06 supports exactly **4** characteristic rules
(reduced set; the 2 dropped rules are profile-quality indicators, not
customer characteristics):

- ``mean_high_<feature>`` — segment mean > dataset_mean + z_threshold *
  dataset_std.
- ``mean_low_<feature>`` — segment mean < dataset_mean - z_threshold *
  dataset_std.
- ``median_above_dataset_median_<feature>`` — segment median >
  dataset median.
- ``top_category_<feature>_<value>`` — for categorical features, the
  most-frequent category in the segment.

Hard rules
----------
- The 4 rule templates are closed (per OQ-SEG-CHAR-01). No other
  characteristic is generated.
- Each characteristic is descriptive only. No business labels
  ("Champions", "Loyal", "VIP", "high-value", "at-risk", "best",
  "optimal", "winner", "recommended") are emitted (R-DEV-06-19).
- ``z_threshold`` controls the strictness of ``mean_high_/mean_low_``.
  Default = 1.0 (one standard deviation from the dataset mean).
- Categorical ``top_category`` only emits when ``topk_categories`` is
  present in the profile and non-empty.
- Empty / missing data: the corresponding rule is silently skipped
  (no characteristic emitted for that segment × feature).
"""

from __future__ import annotations

import re
from typing import Any

from customer_segmentation.prototype.segmentation.manifest import (
    CharacteristicEntry,
    FeatureProfile,
)

__all__ = [
    "DEFAULT_Z_THRESHOLD",
    "CharacteristicDerivationError",
    "derive_segment_characteristics",
    "RULE_MEAN_HIGH",
    "RULE_MEAN_LOW",
    "RULE_MEDIAN_ABOVE",
    "RULE_TOP_CATEGORY",
]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_Z_THRESHOLD: float = 1.0

# Rule template names (the literal template strings, e.g. "mean_high_<feature>").
RULE_MEAN_HIGH: str = "mean_high_<feature>"
RULE_MEAN_LOW: str = "mean_low_<feature>"
RULE_MEDIAN_ABOVE: str = "median_above_dataset_median_<feature>"
RULE_TOP_CATEGORY: str = "top_category_<feature>_<value>"

# Regex for ``<feature>`` substitution: identifier-like.
_FEATURE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
# Regex for ``<value>`` substitution: any non-empty string.
_VALUE_RE = re.compile(r"^.+$")


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class CharacteristicDerivationError(ValueError):
    """Raised on characteristic derivation failure."""


# ---------------------------------------------------------------------------
# Derive
# ---------------------------------------------------------------------------


def _safe_feature_name(name: str) -> str:
    """Validate and return a feature name safe for use in characteristic_id."""
    if not _FEATURE_RE.match(name):
        raise CharacteristicDerivationError(f"feature name {name!r} is not a valid identifier.")
    return name


def _safe_category_value(value: Any) -> str:
    """Validate and return a category value safe for use in characteristic_id."""
    s = str(value)
    if not _VALUE_RE.match(s):
        raise CharacteristicDerivationError(
            f"category value {value!r} cannot be encoded in characteristic_id."
        )
    # The id-portion must not contain spaces or special chars
    # (the value is appended after the underscore).
    # We allow any non-empty string and rely on CharacteristicEntry
    # to reject the rest at the regex level.
    return s


def derive_segment_characteristics(
    *,
    profiles: list[FeatureProfile],
    dataset_stats: dict[str, dict[str, float]],
    z_threshold: float = DEFAULT_Z_THRESHOLD,
) -> list[CharacteristicEntry]:
    """Derive per-segment characteristics from a list of profiles.

    Parameters
    ----------
    profiles : list[FeatureProfile]
        Per-segment feature profiles (output of
        :func:`customer_segmentation.prototype.segmentation.profile.compute_feature_profiles`).
    dataset_stats : dict[str, dict[str, float]]
        Dataset-wide statistics with keys ``"mean"``, ``"median"``,
        ``"std"`` per feature. Missing features silently skip
        mean/median rules.
    z_threshold : float, optional
        Strictness for ``mean_high_/mean_low_`` rules (default 1.0).

    Returns
    -------
    list[CharacteristicEntry]
        Empty list if no rule fires.
    """
    if z_threshold < 0:
        raise CharacteristicDerivationError(f"z_threshold MUST be >= 0; got {z_threshold!r}.")
    out: list[CharacteristicEntry] = []
    for p in profiles:
        try:
            feat = _safe_feature_name(p.feature_name)
        except CharacteristicDerivationError:
            # Skip features that cannot be safely encoded.
            continue
        ds = dataset_stats.get(p.feature_name, {})
        seg_mean = p.statistics.get("mean")
        seg_median = p.statistics.get("median")
        ds_mean = ds.get("mean")
        ds_median = ds.get("median")
        ds_std = ds.get("std")
        # Record the source segment_id so the on-disk JSON can be
        # nested by segment_id per plan §4.2. Per OQ-SEG-NOISE-01,
        # noise (segment_id == -1) is excluded upstream by
        # ``compute_feature_profiles`` when ``exclude_noise=True``
        # (default), so any entry reaching this point has a
        # non-noise segment_id.
        segment_id = int(p.segment_id)
        # mean_high
        if seg_mean is not None and ds_mean is not None and ds_std is not None:
            threshold_high = ds_mean + z_threshold * ds_std
            if seg_mean > threshold_high:
                out.append(
                    CharacteristicEntry(
                        characteristic_id=f"{RULE_MEAN_HIGH.replace('<feature>', feat)}",
                        description=(
                            f"Mean of {feat} in this segment is above the "
                            f"dataset mean by more than {z_threshold:g} std."
                        ),
                        source_features=[feat],
                        derived_stats={
                            "rule": "mean_high",
                            "actual": float(seg_mean),
                            "dataset_mean": float(ds_mean),
                            "dataset_std": float(ds_std),
                            "threshold": float(threshold_high),
                            "z_threshold": float(z_threshold),
                        },
                        segment_id=segment_id,
                    )
                )
        # mean_low
        if seg_mean is not None and ds_mean is not None and ds_std is not None:
            threshold_low = ds_mean - z_threshold * ds_std
            if seg_mean < threshold_low:
                out.append(
                    CharacteristicEntry(
                        characteristic_id=f"{RULE_MEAN_LOW.replace('<feature>', feat)}",
                        description=(
                            f"Mean of {feat} in this segment is below the "
                            f"dataset mean by more than {z_threshold:g} std."
                        ),
                        source_features=[feat],
                        derived_stats={
                            "rule": "mean_low",
                            "actual": float(seg_mean),
                            "dataset_mean": float(ds_mean),
                            "dataset_std": float(ds_std),
                            "threshold": float(threshold_low),
                            "z_threshold": float(z_threshold),
                        },
                        segment_id=segment_id,
                    )
                )
        # median_above_dataset_median
        if seg_median is not None and ds_median is not None and seg_median > ds_median:
            out.append(
                CharacteristicEntry(
                    characteristic_id=f"{RULE_MEDIAN_ABOVE.replace('<feature>', feat)}",
                    description=(
                        f"Median of {feat} in this segment is above " f"the dataset median."
                    ),
                    source_features=[feat],
                    derived_stats={
                        "rule": "median_above_dataset_median",
                        "actual": float(seg_median),
                        "dataset_median": float(ds_median),
                    },
                    segment_id=segment_id,
                )
            )
        # top_category (categorical only)
        topk = p.statistics.get("topk_categories")
        if isinstance(topk, list) and len(topk) > 0:
            top_category, top_count = topk[0]
            try:
                cat_value = _safe_category_value(top_category)
            except CharacteristicDerivationError:
                cat_value = None
            if cat_value is not None:
                cid = RULE_TOP_CATEGORY.replace("<feature>", feat).replace("<value>", cat_value)
                # Manually validate against the regex; if it doesn't
                # match, skip silently (defence).
                if re.match(
                    r"^top_category_[A-Za-z0-9_]+_.+$",
                    cid,
                ):
                    out.append(
                        CharacteristicEntry(
                            characteristic_id=cid,
                            description=(
                                f"Top category in {feat} for this segment " f"is {cat_value!r}."
                            ),
                            source_features=[feat],
                            derived_stats={
                                "rule": "top_category",
                                "category": cat_value,
                                "count": int(top_count),
                            },
                            segment_id=segment_id,
                        )
                    )
    return out
