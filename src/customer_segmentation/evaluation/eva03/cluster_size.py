"""Cluster size variation analysis (EVA-03).

For each (block, algorithm) the EXP-05 evidence records
per-cluster customer counts (cluster_label → customer count) per run.
This module extracts the per-cluster Min / Max / Range / Mean / Std
across runs, which is one form of "cluster size variation" evidence.

Hard constraints (AGENTS.md §2):

- NO composite score.
- NO ordering / weighting across clusters.
- Per-cluster evidence only; per-algorithm aggregation is descriptive.
- Each algorithm reported independently.
"""

from __future__ import annotations

from statistics import pstdev
from typing import Any

import pandas as pd

# ``load_exp05_reproducibility_results_csv`` is defined at the bottom
# of this module; we defer the resolution to keep the public import
# surface tidy.

__all__ = ["analyze_cluster_size_variation", "load_exp05_reproducibility_results_csv"]


def _safe_load_csv(path: Any) -> pd.DataFrame:
    """Read a CSV; return empty DataFrame if missing."""
    try:
        return pd.read_csv(path)
    except (FileNotFoundError, OSError, pd.errors.EmptyDataError):
        return pd.DataFrame()


def analyze_cluster_size_variation(
    exp05_reports_dir: Any,
) -> pd.DataFrame:
    """Build a per-(block, algorithm, cluster) cluster-size summary.

    Parameters
    ----------
    exp05_reports_dir : path-like
        Path to ``reports/exp05`` (containing the per-block result CSVs).
    label_decoder : callable, optional
        Reserved for future use (e.g. mapping raw cluster IDs via
        Hungarian). Not used by the default implementation.

    Returns
    -------
    pd.DataFrame
        Columns: ``block, algorithm, cluster_id, n_runs_with_cluster,
        customer_count_min, customer_count_max, customer_count_range,
        customer_count_mean, customer_count_std, source_artifact``.
    """
    rows: list[dict[str, Any]] = []

    # Build (run_id, cluster_id -> count) by reading the per-block CSVs.
    sources = {
        "R": (
            exp05_reports_dir,
            "exp05_reproducibility_results.csv",
        ),
        "S": (
            exp05_reports_dir,
            "exp05_seed_sweep_results.csv",
        ),
        "N": (
            exp05_reports_dir,
            "exp05_noise_perturbation_results.csv",
        ),
    }
    for block, (path, fname) in sources.items():
        df = _safe_load_csv(f"{path}/{fname}")
        if df.empty:
            continue
        # The CSV has a ``cluster_sizes`` JSON column.
        if "cluster_sizes" not in df.columns:
            continue
        for _, r in df.iterrows():
            algo = str(r.get("algorithm"))
            run_id = str(r.get("run_id"))
            sigma = r.get("sigma")
            sigma_val = (
                float(sigma) if pd.notna(sigma) else None
            )
            perturbation_seed = r.get("perturbation_seed")
            pseed_val = (
                int(perturbation_seed) if pd.notna(perturbation_seed) else None
            )
            raw_cs = r.get("cluster_sizes")
            try:
                cs = (
                    eval(raw_cs)
                    if isinstance(raw_cs, str) and raw_cs.startswith("{")
                    else {}
                )
            except Exception:
                continue
            for cluster_id, count in cs.items():
                rows.append(
                    {
                        "block": block,
                        "algorithm": algo,
                        "run_id": run_id,
                        "cluster_id": str(cluster_id),
                        "sigma": sigma_val,
                        "perturbation_seed": pseed_val,
                        "customer_count": int(count),
                        "source_artifact": fname,
                    }
                )

    detail_df = pd.DataFrame(rows)
    if detail_df.empty:
        return detail_df

    # Group by (block, algorithm, cluster_id) to compute min/max/range/...
    grouped = detail_df.groupby(
        ["block", "algorithm", "cluster_id", "source_artifact"]
    )

    summary_rows: list[dict[str, Any]] = []
    for (block, algo, cluster_id, src), grp in grouped:
        values = grp["customer_count"].astype(int).tolist()
        summary_rows.append(
            {
                "block": block,
                "algorithm": algo,
                "cluster_id": cluster_id,
                "n_runs_with_cluster": int(len(values)),
                "customer_count_min": int(min(values)),
                "customer_count_max": int(max(values)),
                "customer_count_range": int(max(values) - min(values)),
                "customer_count_mean": float(sum(values) / len(values)),
                "customer_count_std": (
                    float(pstdev(values)) if len(values) > 1 else 0.0
                ),
                "source_artifact": src,
            }
        )
    return pd.DataFrame(summary_rows)


def load_exp05_reproducibility_results_csv(path: Any) -> pd.DataFrame:
    """Load Block R (or any of R/S/N) ``*_results.csv`` from disk."""
    return pd.read_csv(path)
