"""Comparison of multiple evaluation manifests.

Per DEV-05 plan §9, ``compare_evaluations`` partitions a list of
evaluation manifests into groups based on a shared
:class:`CompatibilityKey` (5 fields: dataset_id, preprocessed_id,
ml_dataset_sha256, feature_set_sha256, preprocessing_config_sha256).
Within a group, per-metric values are surfaced side-by-side. Across
groups, an incompatibility reason is reported.

The comparison module is RESEARCH-SAFE: it NEVER emits "best",
"winner", "ranking", "recommended", "optimal", "composite_score" or
"aggregate". The single allowed occurrence of those substrings is
inside the mandatory disclaimer phrase (R-EVAL-08 / R-EVAL-15).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from customer_segmentation.prototype.evaluation.manifest import (
    EvaluationManifest,
    read_evaluation_manifest,
)
from customer_segmentation.prototype.evaluation.scope import METRIC_NAMES

__all__ = [
    "CompatibilityKey",
    "ComparisonGroup",
    "ComparisonReport",
    "IncompatibilityReason",
    "compare_evaluations",
    "DEFAULT_COMPARISON_DISCLAIMER",
]


# Mandatory disclaimer (negation form; the only allowed occurrence of
# ranking / recommendation / winner in DEV-05 output).
DEFAULT_COMPARISON_DISCLAIMER: Final[str] = (
    "no ranking, recommendation, or winner annotation is emitted"
)


@dataclass(frozen=True)
class CompatibilityKey:
    """The 5 fields that must match for two evaluations to be compared.

    Same dataset, same preprocessed artifact (so same ML Dataset file),
    same feature space, same preprocessing config → evaluation values
    are interpretively comparable.
    """

    dataset_id: str
    preprocessed_id: str
    ml_dataset_sha256: str
    feature_set_sha256: str
    preprocessing_config_sha256: str
    metric_set: tuple[str, ...]

    def as_tuple(self) -> tuple:
        return (
            self.dataset_id,
            self.preprocessed_id,
            self.ml_dataset_sha256,
            self.feature_set_sha256,
            self.preprocessing_config_sha256,
            self.metric_set,
        )

    def __hash__(self) -> int:
        return hash(self.as_tuple())


def _extract_key(m: EvaluationManifest) -> CompatibilityKey:
    return CompatibilityKey(
        dataset_id=m.dataset_id,
        preprocessed_id=m.preprocessed_id,
        ml_dataset_sha256=m.ml_dataset_sha256,
        feature_set_sha256=m.feature_set_sha256,
        preprocessing_config_sha256=m.preprocessing_config_sha256,
        metric_set=tuple(m.metric_set),
    )


@dataclass(frozen=True)
class IncompatibilityReason:
    """Why a manifest could not be grouped with another."""

    evaluation_id: str
    field_name: str
    stored_value: str
    compared_value: str


@dataclass(frozen=True)
class ComparisonGroup:
    """A group of evaluations that share the same CompatibilityKey."""

    compatibility_key: CompatibilityKey
    evaluations: list[EvaluationManifest]
    metric_set: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_singleton(self) -> bool:
        return len(self.evaluations) == 1


@dataclass(frozen=True)
class ComparisonReport:
    """Output of ``compare_evaluations``."""

    schema_version: str
    compared_at_utc: str
    groups: list[ComparisonGroup]
    incompatibility_reasons: list[IncompatibilityReason]
    disclaimer: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "compared_at_utc": self.compared_at_utc,
            "groups": [
                {
                    "compatibility_key": {
                        "dataset_id": g.compatibility_key.dataset_id,
                        "preprocessed_id": g.compatibility_key.preprocessed_id,
                        "ml_dataset_sha256": g.compatibility_key.ml_dataset_sha256,
                        "feature_set_sha256": g.compatibility_key.feature_set_sha256,
                        "preprocessing_config_sha256": g.compatibility_key.preprocessing_config_sha256,
                        "metric_set": list(g.compatibility_key.metric_set),
                    },
                    "evaluations": [
                        {
                            "evaluation_id": m.evaluation_id,
                            "clustering_id": m.clustering_id,
                            "algorithm": m.algorithm,
                            "algorithm_family": m.algorithm_family,
                            "seed": m.seed,
                            "seed_policy": m.seed_policy,
                            "n_samples_input": m.n_samples_input,
                            "n_samples_used_for_compute": m.n_samples_used_for_compute,
                            "noise_count": m.noise_count,
                            "noise_ratio": m.noise_ratio,
                            "noise_policy_used": m.noise_policy_used,
                            "metrics": {
                                name: {
                                    "value": m.metrics.entries[name].value,
                                    "status": m.metrics.entries[name].status,
                                    "reason": m.metrics.entries[name].reason,
                                }
                                for name in METRIC_NAMES
                            },
                        }
                        for m in g.evaluations
                    ],
                }
                for g in self.groups
            ],
            "incompatibility_reasons": [
                {
                    "evaluation_id": r.evaluation_id,
                    "field_name": r.field_name,
                    "stored_value": r.stored_value,
                    "compared_value": r.compared_value,
                }
                for r in self.incompatibility_reasons
            ],
            "disclaimer": self.disclaimer,
        }


def compare_evaluations(
    manifest_paths: list[Path],
    *,
    disclaimer: str = DEFAULT_COMPARISON_DISCLAIMER,
) -> ComparisonReport:
    """Partition ``manifest_paths`` by compatibility and group metrics.

    Each manifest is loaded and grouped by its :class:`CompatibilityKey`.
    If a manifest's key matches no other manifest, it forms a
    singleton group. ``incompatibility_reasons`` is populated only when
    manifests could not be grouped with a reference (e.g. the second
    manifest in a 2-manifest list).

    Parameters
    ----------
    manifest_paths : list[Path]
        Paths to ``evaluation_manifest.json`` files.
    disclaimer : str
        Mandatory disclaimer text (default
        :data:`DEFAULT_COMPARISON_DISCLAIMER`).
    """
    manifests: list[EvaluationManifest] = []
    for p in manifest_paths:
        manifests.append(read_evaluation_manifest(Path(p)))

    groups_dict: dict[CompatibilityKey, list[EvaluationManifest]] = {}
    for m in manifests:
        k = _extract_key(m)
        groups_dict.setdefault(k, []).append(m)

    groups: list[ComparisonGroup] = []
    for k, ms in groups_dict.items():
        groups.append(
            ComparisonGroup(
                compatibility_key=k,
                evaluations=list(ms),
                metric_set=tuple(k.metric_set),
            )
        )

    # Incompatibility: a manifest is "incompatible" with another only
    # when we have at least 2 manifests in the input and they differ on
    # a field. We only emit reasons for the first reference key.
    incompat: list[IncompatibilityReason] = []
    if len(manifests) >= 2:
        ref = _extract_key(manifests[0])
        for m in manifests[1:]:
            k = _extract_key(m)
            if k == ref:
                continue
            for fname, fvalue in (
                ("dataset_id", k.dataset_id),
                ("preprocessed_id", k.preprocessed_id),
                ("ml_dataset_sha256", k.ml_dataset_sha256),
                ("feature_set_sha256", k.feature_set_sha256),
                ("preprocessing_config_sha256", k.preprocessing_config_sha256),
            ):
                ref_val = getattr(ref, fname)
                if fvalue != ref_val:
                    incompat.append(
                        IncompatibilityReason(
                            evaluation_id=m.evaluation_id,
                            field_name=fname,
                            stored_value=str(fvalue),
                            compared_value=str(ref_val),
                        )
                    )

    return ComparisonReport(
        schema_version="1.0.0",
        compared_at_utc="",
        groups=groups,
        incompatibility_reasons=incompat,
        disclaimer=disclaimer,
    )
