"""Top-level orchestration for EVA-03 — Stability & Reproducibility Evaluation.

Hard constraints (AGENTS.md §2 / EPIC-08 boundary):

- Read-only against EXP-05 / EXP-01 / EXP-03 artifacts.
- No mutation of any input artifact.
- No composite stability score.
- No "best/most stable/winner" language.
- No promotion of WORKING_SELECTED to RESEARCH_APPROVED.

Pipeline:

1. Load EXP-05 labels artifact + per-block aggregate CSVs.
2. Load EXP-01 cluster labels + EXP-03 working-selected metadata.
3. Compute per-block analyses (R / S / N + HP comparison + cluster size + Hungarian).
4. Persist CSVs + JSON + Markdown reports under
   ``reports/evaluation/eva03/``.
"""

from __future__ import annotations

import platform
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from customer_segmentation.evaluation.eva03.cluster_size import (
    analyze_cluster_size_variation,
)
from customer_segmentation.evaluation.eva03.hungarian import (
    compute_hungarian_summary,
)
from customer_segmentation.evaluation.eva03.hyperparameter_stability import (
    analyze_hyperparameter_stability,
)
from customer_segmentation.evaluation.eva03.load import (
    load_eva03_config,
    load_exp01_cluster_labels,
    load_exp03_selected_configurations,
    load_exp05_labels_artifact,
    load_exp05_per_block_record_aggregates,
)
from customer_segmentation.evaluation.eva03.perturbation import analyze_block_n
from customer_segmentation.evaluation.eva03.report import (
    build_comparison_report,
    build_reproducibility_report,
    build_run_manifest_dict,
    build_stability_report,
    write_run_manifest_json,
)
from customer_segmentation.evaluation.eva03.reproducibility import analyze_block_r
from customer_segmentation.evaluation.eva03.seed_stability import analyze_block_s

__all__ = [
    "Eva03Config",
    "Eva03Runner",
    "run_eva03",
]


# Default output directory keeps parity with EVA-01 / EVA-02.
DEFAULT_EVA03_DIR: Path = Path("reports/evaluation/eva03")
RUN_MANIFEST_NAME: str = "eva03_run_manifest.json"


@dataclass(frozen=True)
class Eva03Config:
    """Immutable configuration object for EVA-03."""

    config_path: Path = Path("configs/eva03_stability_evaluation.yaml")
    exp05_reports_dir: Path = Path("reports/exp05")
    exp01_reports_dir: Path = Path("reports/exp01")
    output_dir: Path = DEFAULT_EVA03_DIR
    figures_subdir: str = "figures"
    tables_subdir: str = "tables"
    include_hungarian: bool = True
    include_pairwise_tables: bool = True


@dataclass
class Eva03Runner:
    config: Eva03Config = field(default_factory=Eva03Config)

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def _tables_dir(self) -> Path:
        return self.config.output_dir / self.config.tables_subdir

    def _figures_dir(self) -> Path:
        return self.config.output_dir / self.config.figures_subdir

    def _ensure_dirs(self) -> None:
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        self._tables_dir().mkdir(parents=True, exist_ok=True)
        self._figures_dir().mkdir(parents=True, exist_ok=True)

    def _write_csv(self, df: pd.DataFrame, filename: str) -> Path:
        path = self._tables_dir() / filename
        df.to_csv(path, index=False)
        return path

    def _relative_to_repo(self, path: Path) -> str:
        try:
            cwd = Path.cwd().resolve()
            return str(path.resolve().relative_to(cwd))
        except ValueError:
            return str(path)

    # ------------------------------------------------------------------
    # Pipeline
    # ------------------------------------------------------------------

    def run(self) -> Mapping[str, object]:
        self._ensure_dirs()
        generated_at = datetime.now(UTC).isoformat()

        cfg = load_eva03_config(self.config.config_path)
        exp05 = cfg["eva03"]

        # ---- 1. Load inputs (read-only) ----
        labels_path = (
            Path(self.config.exp05_reports_dir) / "exp05_cluster_labels.parquet"
        )
        labels_df = load_exp05_labels_artifact(labels_path)
        aggregates = load_exp05_per_block_record_aggregates(
            self.config.exp05_reports_dir
        )

        # SHA of the labels artifact for traceability (informational).
        import hashlib

        h = hashlib.sha256()
        h.update(labels_path.read_bytes())
        labels_artifact_sha = h.hexdigest()

        # ---- 2. Block R — reproducibility ----
        block_r_result = analyze_block_r(
            labels_df, include_hungarian=self.config.include_hungarian
        )
        block_r_summary = block_r_result["summary"]
        block_r_per_pair_df = pd.DataFrame(
            [
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
                for r in block_r_result["per_pair"]
            ]
        )

        # ---- 3. Block S — seed stability ----
        block_s_result = analyze_block_s(labels_df)
        block_s_summary = block_s_result["summary"]
        block_s_per_pair = block_s_result["per_pair"]

        # ---- 4. Block N — perturbation robustness ----
        block_n_result = analyze_block_n(labels_df)
        block_n_per_pair = block_n_result["per_pair"]
        block_n_baseline = block_n_result["baseline"]

        # Block N summary by (algorithm, sigma).
        bn_grouped_rows: list[dict[str, object]] = []
        if not block_n_per_pair.empty:
            for (algo, sigma_a), grp in block_n_per_pair.groupby(
                ["algorithm", "sigma_a"]
            ):
                for _metric in ("ari", "ami", "nmi"):
                    pass
                ari_vals = grp["ari"].tolist()
                ami_vals = grp["ami"].tolist()
                nmi_vals = grp["nmi"].tolist()
                bn_grouped_rows.append(
                    {
                        "algorithm": algo,
                        "sigma": sigma_a,
                        "n_pairs": int(len(ari_vals)),
                        "ari_mean": float(np.mean(ari_vals)) if ari_vals else float("nan"),
                        "ari_std": float(np.std(ari_vals)) if ari_vals else 0.0,
                        "ari_min": float(np.min(ari_vals)) if ari_vals else float("nan"),
                        "ari_max": float(np.max(ari_vals)) if ari_vals else float("nan"),
                        "ami_mean": float(np.mean(ami_vals)) if ami_vals else float("nan"),
                        "nmi_mean": float(np.mean(nmi_vals)) if nmi_vals else float("nan"),
                        "decision_status": block_n_result["decision_status"].get(
                            algo, "PERTURBATION_ROBUSTNESS_EVIDENCE_ANALYZED"
                        ),
                    }
                )
        block_n_sigma_summary = pd.DataFrame(bn_grouped_rows)

        # ---- 5. EXP-01 vs EXP-03 working-selected ----
        exp01_summary = pd.read_csv(
            Path(self.config.exp01_reports_dir) / "exp01_baseline_summary.csv"
        )
        exp03_selected = load_exp03_selected_configurations(
            Path("reports/exp03/exp03_selected_configurations.csv")
        )
        hp_result = analyze_hyperparameter_stability(
            exp01_summary, exp03_selected
        )

        # ---- 6. Cluster size variation ----
        cluster_size_variation = analyze_cluster_size_variation(
            self.config.exp05_reports_dir
        )

        # ---- 7. Hungarian alignment summary (descriptive) ----
        hungarian_df = compute_hungarian_summary(
            labels_df, pair_selector="first_two"
        )

        # ---- 8. Persist CSVs ----
        table_paths: list[Path] = []
        table_paths.append(
            self._write_csv(block_r_summary, "eva03_block_r_summary.csv")
        )
        if not block_r_per_pair_df.empty:
            table_paths.append(
                self._write_csv(
                    block_r_per_pair_df, "eva03_block_r_pairwise.csv"
                )
            )
        if not block_s_summary.empty:
            table_paths.append(
                self._write_csv(block_s_summary, "eva03_block_s_summary.csv")
            )
        if not block_s_per_pair.empty:
            table_paths.append(
                self._write_csv(block_s_per_pair, "eva03_block_s_pairwise.csv")
            )
        if not block_s_result["cluster_size_variation"].empty:
            table_paths.append(
                self._write_csv(
                    block_s_result["cluster_size_variation"],
                    "eva03_block_s_cluster_size_variation.csv",
                )
            )
        if not block_n_sigma_summary.empty:
            table_paths.append(
                self._write_csv(
                    block_n_sigma_summary, "eva03_block_n_summary.csv"
                )
            )
        if not block_n_per_pair.empty:
            table_paths.append(
                self._write_csv(
                    block_n_per_pair, "eva03_block_n_pairwise.csv"
                )
            )
        if not block_n_baseline.empty:
            table_paths.append(
                self._write_csv(
                    block_n_baseline, "eva03_block_n_sigma0_baseline.csv"
                )
            )
        if not block_n_result["cluster_size_variation"].empty:
            table_paths.append(
                self._write_csv(
                    block_n_result["cluster_size_variation"],
                    "eva03_block_n_cluster_size_variation.csv",
                )
            )
        if not hp_result["per_algorithm"].empty:
            table_paths.append(
                self._write_csv(
                    hp_result["per_algorithm"],
                    "eva03_exp01_vs_exp03_metadata.csv",
                )
            )
        if not cluster_size_variation.empty:
            table_paths.append(
                self._write_csv(
                    cluster_size_variation, "eva03_cluster_size_variation.csv"
                )
            )
        if not hungarian_df.empty:
            table_paths.append(
                self._write_csv(
                    hungarian_df, "eva03_hungarian_alignments.csv"
                )
            )

        # ---- 9. Markdown reports ----
        from customer_segmentation.evaluation.eva03.types import HungarianAssignment

        hungarians_block_r: list[HungarianAssignment] = list(
            block_r_result["hungarian"]
        )

        reproducibility_md = build_reproducibility_report(
            block_r_summary=block_r_summary,
            per_pair_rows=block_r_result["per_pair"],
            hungarians=hungarians_block_r,
            input_sha256=labels_artifact_sha,
            generated_at=generated_at,
        )
        reproducibility_path = (
            self.config.output_dir / exp05["output"]["reports"]["reproducibility"]
        )
        reproducibility_path.write_text(reproducibility_md, encoding="utf-8")

        stability_md = build_stability_report(
            block_s_summary=block_s_summary,
            block_s_per_pair=block_s_per_pair,
            cluster_size_variation=block_s_result["cluster_size_variation"],
            generated_at=generated_at,
        )
        stability_path = (
            self.config.output_dir / exp05["output"]["reports"]["stability"]
        )
        stability_path.write_text(stability_md, encoding="utf-8")

        comparison_md = build_comparison_report(
            block_n_matrices_summary=block_n_sigma_summary,
            block_n_baseline=block_n_baseline,
            hyperparameter_comparison=hp_result["per_algorithm"],
            cluster_size_variation_n=block_n_result["cluster_size_variation"],
            hungarian_alignments=hungarian_df,
            input_sha256=labels_artifact_sha,
            generated_at=generated_at,
            pending_review_notes=exp05["pending_review_notes"],
            limitations=hp_result["limitations"],
        )
        comparison_path = (
            self.config.output_dir / exp05["output"]["reports"]["comparison"]
        )
        comparison_path.write_text(comparison_md, encoding="utf-8")

        # ---- 10. Run manifest ----
        manifest = build_run_manifest_dict(
            generated_at=generated_at,
            n_rows_in_repo=int(len(labels_df)),
            input_sha256=labels_artifact_sha,
            table_paths=[self._relative_to_repo(p) for p in table_paths],
            figure_paths=[],
            block_r_decisions=block_r_result["decision_status"],
            block_s_decisions=block_s_result["decision_status"],
            block_n_decisions=block_n_result["decision_status"],
            hyperparameter_decisions=hp_result["decision_status"],
            pending_review_notes=exp05["pending_review_notes"],
            scope_boundaries=exp05["scope_boundaries"],
            library_versions=_library_versions(),
            platform_info=_platform_info(),
        )
        write_run_manifest_json(manifest, self.config.output_dir / RUN_MANIFEST_NAME)

        return {
            "generated_at": generated_at,
            "output_dir": str(self.config.output_dir),
            "n_rows_in_repo": int(len(labels_df)),
            "tables": [self._relative_to_repo(p) for p in table_paths],
            "reports": {
                "stability": self._relative_to_repo(stability_path),
                "reproducibility": self._relative_to_repo(reproducibility_path),
                "comparison": self._relative_to_repo(comparison_path),
            },
            "decision_status": {
                "block_r": block_r_result["decision_status"],
                "block_s": block_s_result["decision_status"],
                "block_n": block_n_result["decision_status"],
                "hyperparameter": hp_result["decision_status"],
            },
        }


def _library_versions() -> dict[str, str]:
    try:
        import scipy
    except ImportError:
        scipy_version = "MISSING"
    else:
        scipy_version = scipy.__version__

    try:
        import sklearn
    except ImportError:
        sklearn_version = "MISSING"
    else:
        sklearn_version = sklearn.__version__

    return {
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scipy": scipy_version,
        "scikit-learn": sklearn_version,
    }


def _platform_info() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
    }


def run_eva03(
    *,
    config_path: Path | str = "configs/eva03_stability_evaluation.yaml",
    exp05_reports_dir: Path | str = "reports/exp05",
    exp01_reports_dir: Path | str = "reports/exp01",
    output_dir: Path | str = DEFAULT_EVA03_DIR,
    include_hungarian: bool = True,
) -> Mapping[str, object]:
    """Convenience wrapper around :class:`Eva03Runner`."""
    config = Eva03Config(
        config_path=Path(config_path),
        exp05_reports_dir=Path(exp05_reports_dir),
        exp01_reports_dir=Path(exp01_reports_dir),
        output_dir=Path(output_dir),
        include_hungarian=include_hungarian,
    )
    return Eva03Runner(config=config).run()
