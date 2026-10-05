"""Markdown report builders for EVA-03.

Three reports are produced:

1. ``eva03_reproducibility_report.md`` — Block R evidence + per-algorithm
   summary + Hungarian alignment note.
2. ``eva03_stability_report.md`` — Block S evidence (seed stability).
3. ``eva03_comparison_report.md`` — Block N (perturbation) + EXP-01 vs
   EXP-03 working-selected metadata + Hungarian alignment note.

Hard constraints (AGENTS.md §2 / EPIC-08 boundary):

- NO best / winner / optimal / recommended / final claims.
- No composite / weighted stability score.
- Each algorithm reported independently.
- Limitations + PENDING_REVIEW notes explicitly documented.
- One section must list "Methodology decisions not implemented" so a
  reviewer can see exactly where the methodology stops.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from customer_segmentation.evaluation.eva03.types import HungarianAssignment

__all__ = [
    "build_reproducibility_report",
    "build_stability_report",
    "build_comparison_report",
]


# ---------------------------------------------------------------------------
# Common helpers
# ---------------------------------------------------------------------------


def _df_to_markdown(df: pd.DataFrame, *, max_rows: int = 200) -> str:
    """Render a small DataFrame as a markdown table."""
    if df is None or df.empty:
        return "_(no rows)_\n"
    view = df.head(max_rows)
    return view.to_markdown(index=False, floatfmt=".6g") + "\n"


def _perp_blockr_summary(per_pair: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for r in per_pair:
        rows.append(
            {
                "algorithm": r.algorithm,
                "run_id_a": r.run_id_a,
                "run_id_b": r.run_id_b,
                "repeat_index_a": r.repeat_index_a,
                "repeat_index_b": r.repeat_index_b,
                "ari": r.ari,
                "ami": r.ami,
                "nmi": r.nmi,
                "n_customers": r.n_customers,
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Reproducibility Report
# ---------------------------------------------------------------------------


def build_reproducibility_report(
    *,
    block_r_summary: pd.DataFrame,
    per_pair_rows: list[Any],
    hungarians: list[HungarianAssignment],
    config_sha: str | None = None,
    input_sha256: str | None = None,
    generated_at: str | None = None,
) -> str:
    parts: list[str] = []
    parts.append("# EVA-03 — Reproducibility Report\n")
    if generated_at:
        parts.append(f"**Generated:** {generated_at}\n")
    if config_sha:
        parts.append(f"**Config SHA-256:** `{config_sha}`\n")
    if input_sha256:
        parts.append(f"**EXP-05 input SHA-256:** `{input_sha256}`\n")

    parts.append(
        "\n## 1. Scope\n\n"
        "Block R from EXP-05 provides 5 algorithms × n_repeat=5 × seed=42 "
        "(25 runs total). For each algorithm, this report computes "
        "pairwise ARI / AMI / NMI across the 5 repeats and Hungarian "
        "matching for descriptive cluster correspondence. The "
        "expectation under fixed-seed determinism is that every "
        "off-diagonal pair yields ARI = AMI = NMI = 1.0.\n\n"
        "**This is NOT stability analysis** (Block S / Block N "
        "sections handle that). Per AGENTS.md §2 / EPIC-08 boundary, "
        "no 'most reproducible' / 'winner' / 'best reproducibility' "
        "language is used; each algorithm is reported independently.\n"
    )

    parts.append("\n## 2. Per-algorithm summary\n\n")
    parts.append(
        "_Decision status is one of REPRODUCIBILITY_VERIFIED_LABEL_LEVEL "
        "or REPRODUCIBILITY_FAILED_LABEL_LEVEL._\n\n"
    )
    parts.append(_df_to_markdown(block_r_summary))

    parts.append("\n## 3. Off-diagonal pair-wise evidence (Block R)\n\n")
    if per_pair_rows:
        per_pair_df = pd.DataFrame(_perp_blockr_summary(per_pair_rows))
        parts.append(_df_to_markdown(per_pair_df, max_rows=100))
    else:
        parts.append("_(no pair rows)_\n")

    parts.append("\n## 4. Hungarian cluster-label alignment (descriptive)\n\n")
    parts.append(
        "**Hungarian matching is DESCRIPTIVE ONLY.** It records which "
        "cluster labels in run A map to which labels in run B and how "
        "many customers overlap. Hungarian is NOT a stability metric "
        "and is NOT used to rank algorithms or configurations.\n\n"
    )
    if hungarians:
        for h in hungarians:
            parts.append(
                f"### 4.{hungarians.index(h) + 1} `{h.algorithm}` — "
                f"runs `{h.run_id_a}` ↔ `{h.run_id_b}`\n\n"
                "- Total non-noise customers in alignment: "
                f"{h.total_customers}\n"
                "- Matched cluster pairs: {n_pairs}\n".format(
                    n_pairs=len(h.source_labels)
                )
            )
            if h.source_labels:
                small = pd.DataFrame(
                    {
                        "source_label": h.source_labels,
                        "target_label": h.target_labels,
                        "overlap_count": h.overlap_counts,
                        "overlap_fraction": [
                            ovr / max(h.total_customers, 1)
                            for ovr in h.overlap_counts
                        ],
                    }
                )
                parts.append(small.to_markdown(index=False, floatfmt=".6g"))
                parts.append("\n")
    else:
        parts.append("_(no Hungarian pairs produced)_\n")

    parts.append(
        "\n## 5. Methodology notes\n\n"
        "- ARI / AMI / NMI use sklearn defaults "
        "(`adjusted_rand_score`, "
        "`adjusted_mutual_info_score` with `average_method='arithmetic'`, "
        "`normalized_mutual_info_score` with `average_method='arithmetic'`).\n"
        "- All three metrics are permutation-invariant by construction. "
        "Order of cluster labels does not affect them.\n"
        "- DBSCAN noise label (-1) is included in ARI / AMI / NMI "
        "(permutation-invariant). It is excluded from the Hungarian "
        "contingency matrix by design (Hungarian assumes positive "
        "overlap counts).\n"
        "- Verified threshold for Block R: ARI ≥ 1 - 1e-9 ⇒ "
        "`REPRODUCIBILITY_VERIFIED_LABEL_LEVEL`; otherwise "
        "`REPRODUCIBILITY_FAILED_LABEL_LEVEL`. The threshold is "
        "set to absorb IEEE-754 sub-1.0 noise; it does NOT represent "
        "approximate reproducibility.\n"
    )

    parts.append(
        "\n## 6. Methodology limitations\n\n"
        "- Block R contains only one seed (42). Determinism at other "
        "seeds is verified by EXP-05's labels_hash; Block S handles "
        "seed variation explicitly.\n"
        "- Runtime variation across repeats is captured in EXP-05 "
        "outputs but is NOT a reproducibility evidence here (a fast run "
        "may produce identical labels to a slow run).\n"
    )

    parts.append(
        "\n## 7. Interpretation boundary\n\n"
        "Per AGENTS.md §2.5, no algorithm is declared 'most reproducible'. "
        "The data above is the per-algorithm reproducibility evidence. "
        "Cross-algorithm comparison should be deferred to EPIC-08 "
        "interpretation in the RQ3 final analysis.\n"
    )
    return "".join(parts)


# ---------------------------------------------------------------------------
# Seed Stability Report
# ---------------------------------------------------------------------------


def build_stability_report(
    *,
    block_s_summary: pd.DataFrame,
    block_s_per_pair: pd.DataFrame,
    cluster_size_variation: pd.DataFrame,
    generated_at: str | None = None,
    config_sha: str | None = None,
) -> str:
    parts: list[str] = []
    parts.append("# EVA-03 — Seed Stability Report (Block S)\n")
    if generated_at:
        parts.append(f"**Generated:** {generated_at}\n")
    if config_sha:
        parts.append(f"**Config SHA-256:** `{config_sha}`\n")
    parts.append(
        "\n## 1. Scope\n\n"
        "Block S from EXP-05 records K-Means + GMM + Fuzzy C-Means at "
        "5 seeds (42, 7, 123, 2024, 1729), with fixed EXP-01 working "
        "default hyperparameters. Agglomerative and DBSCAN are "
        "deterministic (no seed axis) and are NOT included in Block S.\n\n"
        "For each algorithm, this report computes pairwise ARI / AMI / "
        "NMI across the 5 seeds and the per-cluster size variation "
        "(Min / Max / Range / Mean / Std).\n\n"
        "**Per AGENTS.md §2 / EPIC-08 boundary:** no algorithm is "
        "declared 'most stable'; each algorithm is reported "
        "independently. No composite / weighted stability score.\n"
    )

    parts.append("\n## 2. Per-algorithm summary\n\n")
    parts.append(_df_to_markdown(block_s_summary))
    parts.append(
        "\n_Notes:_\n\n"
        "- ``ari_off_diagonal_unique_count`` is the number of distinct "
        "off-diagonal ARI values; smaller values indicate more homogeneous "
        "agreement across seed pairs.\n"
        "- All metrics are recorded as evidence; the per-pair records are "
        "preserved in the ``tables`` directory.\n"
    )

    parts.append("\n## 3. Per-pair seed similarity (Block S)\n\n")
    parts.append(_df_to_markdown(block_s_per_pair))

    parts.append("\n## 4. Cluster size variation\n\n")
    parts.append(
        "Per-cluster (per algorithm) Min / Max / Range of customer "
        "counts across seeds. DBSCAN noise cluster (when present) is "
        "reported as cluster_id='-1'.\n\n"
    )
    parts.append(_df_to_markdown(cluster_size_variation))

    parts.append(
        "\n## 5. Methodology notes\n\n"
        "- 5 seeds produce C(5,2) = 10 off-diagonal pair comparisons per "
        "algorithm. Statistical tests across seeds (paired t-test / "
        "Wilcoxon) are NOT computed here because the seed variation is "
        "intentional and the sample size (n=5) is too small for "
        "parametric assumptions; this is documented as a methodology "
        "limitation in EV03-ST-01.\n"
        "- Cluster size variation is recorded per-cluster (not per-"
        "algorithm aggregate) so a reader can trace each row back to "
        "its (block, algorithm, cluster) source.\n"
        "- Agglomerative + DBSCAN are deterministic; their "
        "``labels_hash_unique_count`` = 1 in EXP-05. They are excluded "
        "from Block S by design.\n"
    )

    parts.append(
        "\n## 6. Interpretation boundary\n\n"
        "The seed stability evidence in this section describes the "
        "observed variation across 5 seeds for each algorithm. It does "
        "NOT answer the question 'which algorithm is most stable?' "
        "because:\n\n"
        "- The seed set (5 values) is fixed by the EXP-05 plan; sampling "
        "more seeds is deferred to a follow-up artefact if required.\n"
        "- Stability conclusions require mentor approval of the "
        "stability-claim policy before any single metric (ARI / AMI / "
        "NMI) is used as a primary criterion.\n"
    )
    return "".join(parts)


# ---------------------------------------------------------------------------
# Comparison Report (Block N + EXP-01 vs EXP-03 + Hungarian alignment)
# ---------------------------------------------------------------------------


def build_comparison_report(
    *,
    block_n_matrices_summary: pd.DataFrame,
    block_n_baseline: pd.DataFrame,
    hyperparameter_comparison: pd.DataFrame,
    cluster_size_variation_n: pd.DataFrame,
    hungarian_alignments: pd.DataFrame,
    config_sha: str | None = None,
    input_sha256: str | None = None,
    generated_at: str | None = None,
    pending_review_notes: list[Any] | None = None,
    limitations: list[str] | None = None,
) -> str:
    parts: list[str] = []
    parts.append("# EVA-03 — Comparison Report (Block N + EXP-01 vs EXP-03)\n")
    if generated_at:
        parts.append(f"**Generated:** {generated_at}\n")
    if config_sha:
        parts.append(f"**Config SHA-256:** `{config_sha}`\n")
    if input_sha256:
        parts.append(f"**EXP-05 input SHA-256:** `{input_sha256}`\n")

    parts.append(
        "\n## 1. Scope\n\n"
        "This report covers TWO separate evidence streams:\n\n"
        "1. **Block N — Feature Perturbation Robustness.** "
        "Per-algorithm pairwise ARI / AMI / NMI across "
        "(sigma × perturbation_seed) runs, plus the sigma=0 baseline "
        "sanity check (verified at the labels_hash level by EXP-05).\n"
        "2. **EXP-01 vs EXP-03 working-selected metadata comparison.** "
        "Metric-based descriptive comparison; label-level comparison "
        "is NOT computable from the existing evidence (see §6).\n\n"
        "**Per AGENTS.md §2 / EPIC-08 boundary:** no algorithm is "
        "declared 'most robust'; no 'best algorithm' / 'winner' / "
        "'recommended' claims; no composite / weighted robustness "
        "score; perturbation variation is NOT called 'reproducibility'.\n"
    )

    parts.append("\n## 2. Block N — Per-algorithm pairwise summary\n\n")
    parts.append(
        "_Decision status: SIGMA_ZERO_BASELINE_MATCH_LABEL_LEVEL when "
        "the sigma=0 sanity check confirms the algorithm's deterministic "
        "pattern; PERTURBATION_ROBUSTNESS_EVIDENCE_ANALYZED otherwise._\n\n"
    )
    parts.append(_df_to_markdown(block_n_matrices_summary))

    parts.append("\n## 3. Block N — sigma=0 baseline vs sigma > 0 runs\n\n")
    parts.append(_df_to_markdown(block_n_baseline))

    parts.append("\n## 4. Block N — Cluster size variation by (algorithm, sigma)\n\n")
    parts.append(_df_to_markdown(cluster_size_variation_n))

    parts.append("\n## 5. EXP-01 default vs EXP-03 working-selected (metric-based)\n\n")
    parts.append(_df_to_markdown(hyperparameter_comparison))

    parts.append("\n## 6. Label-level comparison is NOT computable\n\n")
    parts.append(
        "EXP-03 working-selected cluster labels are NOT persisted in the "
        "current EXP-05 artifact. Therefore, **no label-level "
        "(ARI / AMI / NMI) comparison between EXP-01 default and EXP-03 "
        "working-selected is computable** from the existing evidence. "
        "If label-level comparison becomes a requirement, the EXP-03 "
        "working-selected labels must be added to the EXP-05 artifact "
        "or recorded in a follow-up artefact. This is documented as the "
        "methodology decision EV03-HP-01 (TECHNICALLY_LIMITED).\n"
    )

    parts.append("\n## 7. Hungarian cluster-label alignments (descriptive)\n\n")
    parts.append(
        "**Hungarian matching is DESCRIPTIVE ONLY** — it provides per-"
        "cluster correspondence (which cluster in run A maps to which "
        "in run B) and is NOT a stability / robustness / quality metric. "
        "It is not used to rank algorithms.\n\n"
    )
    parts.append(_df_to_markdown(hungarian_alignments, max_rows=200))

    parts.append(
        "\n## 8. Methodology notes\n\n"
        "- Block N sigma=0 sanity check is verified at the EXP-05 "
        "labels_hash level (``SIGMA_ZERO_BASELINE_MATCH``). EVA-03 does "
        "not recompute the sanity check; it confirms the EXP-05 record.\n"
        "- Block N with sigma > 0 may or may not change cluster labels. "
        "Whether labels change is an empirical observation; EVA-03 reports "
        "the observed change without implying a robustness claim.\n"
        "- EXP-01 vs EXP-03 is metric-based; the difference in metric "
        "values is recorded but no 'better / worse' / 'preferred' language "
        "is used.\n"
    )

    parts.append("\n## 9. Methodology limitations\n\n")
    if limitations:
        for i, note in enumerate(limitations, start=1):
            parts.append(f"{i}. {note}\n")
    else:
        parts.append("_(no additional limitations recorded)_\n")

    if pending_review_notes:
        parts.append("\n## 10. Methodology decisions (PENDING_REVIEW)\n\n")
        for note in pending_review_notes:
            parts.append(
                f"- **{note.get('id', 'EV03-?')}** — "
                f"{note.get('decision', '')} "
                f"(status = {note.get('status', 'PENDING_REVIEW')})\n"
            )

    parts.append(
        "\n## 11. Interpretation boundary\n\n"
        "Per AGENTS.md §2.5 / §2.6 / §2.9:\n\n"
        "- No algorithm is declared 'most robust' / 'most reproducible' / "
        "'most stable' / 'best'.\n"
        "- No composite stability / robustness score is computed.\n"
        "- WORKING_SELECTED is NOT promoted to RESEARCH_APPROVED.\n"
        "- Cross-algorithm ranking is FORBIDDEN.\n"
        "- Perturbation variation is NOT called 'reproducibility' "
        "(the two concepts are reported separately).\n"
    )
    return "".join(parts)


# ---------------------------------------------------------------------------
# Run Manifest
# ---------------------------------------------------------------------------


def build_run_manifest_dict(
    *,
    generated_at: str,
    n_rows_in_repo: int,
    input_sha256: str | None,
    table_paths: list[str],
    figure_paths: list[str],
    block_r_decisions: dict[str, str],
    block_s_decisions: dict[str, str],
    block_n_decisions: dict[str, str],
    hyperparameter_decisions: dict[str, str],
    pending_review_notes: list[Any],
    scope_boundaries: list[str],
    library_versions: dict[str, str] | None,
    platform_info: dict[str, str] | None,
) -> dict[str, Any]:
    """Build the run manifest dictionary for EVA-03."""
    return {
        "generated_at": generated_at,
        "name": "EVA-03 Stability & Reproducibility Evaluation",
        "n_rows_in_artifact": int(n_rows_in_repo),
        "input_sha256": input_sha256,
        "tables": list(table_paths),
        "figures": list(figure_paths),
        "decision_status_options": sorted(
            set(
                list(block_r_decisions.values())
                + list(block_s_decisions.values())
                + list(block_n_decisions.values())
                + list(hyperparameter_decisions.values())
            )
        ),
        "forbidden_terms": [
            "best",
            "winner",
            "optimal",
            "recommended",
            "final",
            "approved",
            "superior",
        ],
        "decision_status_by_block": {
            "block_r": block_r_decisions,
            "block_s": block_s_decisions,
            "block_n": block_n_decisions,
            "hyperparameter": hyperparameter_decisions,
        },
        "pending_review_notes": [note.__dict__ if hasattr(note, "__dict__") else note for note in pending_review_notes],
        "scope_boundaries": list(scope_boundaries),
        "library_versions": library_versions or {},
        "platform_info": platform_info or {},
    }


def write_run_manifest_json(manifest: dict[str, Any], path: Any) -> None:
    """Write the run manifest JSON."""
    import pathlib

    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(path).write_text(
        json.dumps(manifest, indent=2, default=str),
        encoding="utf-8",
    )
