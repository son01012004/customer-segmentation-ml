"""CP-04 orchestrator.

The orchestrator:

1. Builds CP-04 analysis units from CP-02 provenance + CP-01/02/03
   artefacts (read-only).
2. Computes segment names (CP-04 naming framework).
3. Builds segment profiles for every (unit, cluster) — including
   noise buckets and EXP-03 NOT_AVAILABLE rows.
4. Writes CSV / JSON / Markdown artefacts.
5. Reuses CP-01 / CP-02 / CP-03 charts (no new visualisation).

Hard constraints recorded at the package level
(``src/customer_segmentation/profiling/cp04/__init__.py``).

Read-only against source artefacts:
- CP-01 cluster size table (read)
- CP-02 feature profile + relative comparison + behavioural
  interpretation + unit provenance (read)
- CP-03 segment comparison matrix + distinguishing features + IQR
  overlap + unit provenance (read)
- EXP-01 cluster_labels_*.parquet (NOT touched)
- EXP-03 selected configurations (NOT touched)
- data/processed/customer_candidates.parquet (NOT touched)
- data/processed/customer_metadata.parquet (NOT touched)
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from customer_segmentation.profiling.cp01.provenance import (
    ALGORITHMS,
)
from customer_segmentation.profiling.cp04.naming import (
    SegmentName,
    compute_all_segment_names,
)
from customer_segmentation.profiling.cp04.profile_builder import (
    SegmentProfile,
    build_all_segment_profiles,
    evidence_rows_to_dicts,
    segment_profiles_to_summary_dicts,
)
from customer_segmentation.profiling.cp04.provenance import (
    CP01_SIZE_TABLE,
    CP02_BEHAVIORAL,
    CP02_FEATURE_PROFILE,
    CP02_RELATIVE,
    CP02_UNIT_PROV,
    CP03_COMPARISON,
    CP03_DISTINGUISHING,
    CP03_OVERLAP,
    CP03_UNIT_PROV,
    build_cp04_analysis_units,
    get_cp04_artifact_shas,
)
from customer_segmentation.profiling.cp04.report import (
    Cp04ReportContext,
    build_cp04_markdown,
)

DEFAULT_OUTPUT_DIR = Path("reports/profiling/cp04")


def _file_sha256(path: Path) -> str | None:
    """Return the SHA-256 hex digest of a file, or None if missing."""
    if not path.exists():
        return None
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


class Cp04Runner:
    """Configuration for one CP-04 run."""

    def __init__(
        self,
        repo_root: Path,
        output_dir: Path = DEFAULT_OUTPUT_DIR,
        include_exp03: bool = True,
        cp01_size_table_path: Path | None = None,
        cp02_output_dir: Path | None = None,
        cp03_output_dir: Path | None = None,
        cp01_report_path: Path | None = None,
        cp02_report_path: Path | None = None,
        cp03_report_path: Path | None = None,
    ) -> None:
        self.repo_root = repo_root
        self.output_dir = output_dir
        self.include_exp03 = include_exp03
        self.cp01_size_table_path = cp01_size_table_path or (repo_root / CP01_SIZE_TABLE)
        self.cp02_output_dir = cp02_output_dir or (repo_root / DEFAULT_OUTPUT_DIR.parent / "cp02")
        self.cp03_output_dir = cp03_output_dir or (repo_root / DEFAULT_OUTPUT_DIR.parent / "cp03")
        self.cp01_report_path = cp01_report_path or (
            self.cp01_size_table_path.parent / "cp01_report.md"
        )
        self.cp02_report_path = cp02_report_path or (self.cp02_output_dir / "cp02_report.md")
        self.cp03_report_path = cp03_report_path or (self.cp03_output_dir / "cp03_report.md")

    def run(self) -> Mapping[str, Any]:
        """Execute CP-04 and return the run-summary as a dict.

        Side effects:
        - writes ``cp04_segment_profiles.csv``
        - writes ``cp04_segment_naming.csv``
        - writes ``cp04_segment_evidence.csv``
        - writes ``cp04_unit_provenance.csv``
        - writes ``cp04_cp01_consistency.csv``
        - writes ``cp04_runner_manifest.json``
        - writes ``cp04_report.md``
        """
        # 1. Build CP-04 analysis units (reuses CP-01/02/03 artefacts).
        units = build_cp04_analysis_units(self.repo_root)
        if not self.include_exp03:
            units = [u for u in units if u.source_experiment != "EXP-03"]

        # 2. Compute segment names (CP-04 naming framework).
        segment_names = compute_all_segment_names(units)

        # 3. Build segment profiles.
        profiles = build_all_segment_profiles(units)

        # 4. Sanity: every SegmentName must correspond to a SegmentProfile.
        self._validate_consistency(segment_names, profiles)

        # 5. CSVs.
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 5a. Segment summary table (one row per cluster).
        summary_rows = segment_profiles_to_summary_dicts(profiles)
        summary_df = pd.DataFrame(summary_rows)
        if not summary_df.empty:
            summary_df = summary_df.sort_values(["unit_id", "cluster_id"]).reset_index(drop=True)
        summary_path = self.output_dir / "cp04_segment_profiles.csv"
        summary_df.to_csv(summary_path, index=False)

        # 5b. Naming table (one row per cluster; key fields for
        # quick lookup of "name + rationale + tier + supporting evidence").
        naming_rows = [
            {
                "unit_id": p.unit_id,
                "algorithm": p.algorithm,
                "source_experiment": p.source_experiment,
                "cluster_id": p.cluster_id,
                "cluster_label": p.cluster_label,
                "is_noise": p.is_noise,
                "is_not_available": p.is_not_available,
                "customer_count": p.customer_count,
                "pct_of_total": p.pct_of_total,
                "segment_name": p.segment_name,
                "recency_tier": p.recency_tier,
                "frequency_tier": p.frequency_tier,
                "monetary_tier": p.monetary_tier,
                "behavioral_modifier": p.behavioral_modifier,
                "naming_status": p.naming_status,
                "supporting_evidence": _format_supporting_evidence(p),
                "naming_rationale": p.naming_rationale,
            }
            for p in profiles
        ]
        naming_df = pd.DataFrame(naming_rows)
        if not naming_df.empty:
            naming_df = naming_df.sort_values(["unit_id", "cluster_id"]).reset_index(drop=True)
        naming_path = self.output_dir / "cp04_segment_naming.csv"
        naming_df.to_csv(naming_path, index=False)

        # 5c. Long-format evidence table (one row per profile × feature).
        evidence_df = evidence_rows_to_dicts(profiles)
        evidence_path = self.output_dir / "cp04_segment_evidence.csv"
        evidence_df.to_csv(evidence_path, index=False)

        # 5d. Unit provenance (mirror CP-02/CP-03).
        prov_df = pd.DataFrame(
            [
                {
                    "unit_id": u.unit_id,
                    "algorithm": u.algorithm,
                    "source_experiment": u.source_experiment,
                    "configuration_id": u.configuration_id,
                    "configuration_status": u.configuration_status,
                    "labels_persisted": u.labels_persisted,
                    "n_customers_eligible": u.n_customers_eligible,
                }
                for u in units
            ]
        )
        prov_path = self.output_dir / "cp04_unit_provenance.csv"
        prov_df.to_csv(prov_path, index=False)

        # 5e. CP-01 consistency check.
        consistency_df = self._build_consistency_table(profiles)
        consistency_path = self.output_dir / "cp04_cp01_consistency.csv"
        consistency_df.to_csv(consistency_path, index=False)

        # 6. Build report.
        artifact_paths = self._collect_chart_artifacts(units)
        shas = get_cp04_artifact_shas(self.repo_root)
        report_ctx = Cp04ReportContext(
            units=units,
            profiles=profiles,
            artifacts=artifact_paths,
            analysis_units_total=len(units),
            units_with_labels=sum(1 for u in units if u.labels_persisted),
            units_without_labels=sum(1 for u in units if not u.labels_persisted),
            cp01_report_path=str(self.cp01_report_path),
            cp02_report_path=str(self.cp02_report_path),
            cp03_report_path=str(self.cp03_report_path),
            input_artifact_shas=shas,
        )
        report_path = self.output_dir / "cp04_report.md"
        build_cp04_markdown(report_ctx, report_path)

        # 7. Manifest.
        manifest = {
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "output_dir": str(self.output_dir),
            "include_exp03": bool(self.include_exp03),
            "algorithms": list(ALGORITHMS),
            "analysis_units_total": report_ctx.analysis_units_total,
            "units_with_labels": report_ctx.units_with_labels,
            "units_without_labels": report_ctx.units_without_labels,
            "outputs": {
                "segment_profiles_csv": str(summary_path),
                "segment_naming_csv": str(naming_path),
                "segment_evidence_csv": str(evidence_path),
                "unit_provenance_csv": str(prov_path),
                "cp01_consistency_csv": str(consistency_path),
                "report_md": str(report_path),
            },
            "input_sources": {
                "cp01_cluster_size_table": str(self.cp01_size_table_path),
                "cp01_cluster_size_table_sha256": _file_sha256(self.cp01_size_table_path),
                "cp02_unit_provenance": str(self.repo_root / CP02_UNIT_PROV),
                "cp02_unit_provenance_sha256": _file_sha256(self.repo_root / CP02_UNIT_PROV),
                "cp02_feature_profile": str(self.repo_root / CP02_FEATURE_PROFILE),
                "cp02_feature_profile_sha256": _file_sha256(self.repo_root / CP02_FEATURE_PROFILE),
                "cp02_relative_comparison": str(self.repo_root / CP02_RELATIVE),
                "cp02_relative_comparison_sha256": _file_sha256(self.repo_root / CP02_RELATIVE),
                "cp02_behavioral_interpretation": str(self.repo_root / CP02_BEHAVIORAL),
                "cp02_behavioral_interpretation_sha256": _file_sha256(
                    self.repo_root / CP02_BEHAVIORAL
                ),
                "cp03_segment_comparison_matrix": str(self.repo_root / CP03_COMPARISON),
                "cp03_segment_comparison_matrix_sha256": _file_sha256(
                    self.repo_root / CP03_COMPARISON
                ),
                "cp03_distinguishing_features": str(self.repo_root / CP03_DISTINGUISHING),
                "cp03_distinguishing_features_sha256": _file_sha256(
                    self.repo_root / CP03_DISTINGUISHING
                ),
                "cp03_overlap_analysis": str(self.repo_root / CP03_OVERLAP),
                "cp03_overlap_analysis_sha256": _file_sha256(self.repo_root / CP03_OVERLAP),
                "cp03_unit_provenance": str(self.repo_root / CP03_UNIT_PROV),
                "cp03_unit_provenance_sha256": _file_sha256(self.repo_root / CP03_UNIT_PROV),
                "cp01_report": str(self.cp01_report_path),
                "cp02_report": str(self.cp02_report_path),
                "cp03_report": str(self.cp03_report_path),
            },
            "feature_set": list(
                __import__(
                    "customer_segmentation.profiling.cp02.provenance",
                    fromlist=["FEATURE_COLUMNS"],
                ).FEATURE_COLUMNS
            ),
            "feature_source": (
                "RAW interpretable values from data/processed/customer_candidates.parquet "
                "(FE-05 output) — accessed via CP-02 outputs. NOT Yeo-Johnson / "
                "RobustScaler values."
            ),
            "methodology_gate": (
                "AGENTS.md §2 — no marketing recommendation, no algorithm ranking, "
                "no over-inference. DBSCAN noise separated, EXP-03 NOT_AVAILABLE, "
                "CancellationRate/ReturnRate (NOT_ASSESSABLE) NOT used as primary "
                "naming evidence, AverageQuantity/BasketSize redundancy handled. "
                "K-Medoids OUT OF SCOPE (per ADR-0003)."
            ),
            "summary_stats": self._summary_stats(profiles),
        }
        manifest_path = self.output_dir / "cp04_runner_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return {
            "segment_profiles_csv": str(summary_path),
            "segment_naming_csv": str(naming_path),
            "segment_evidence_csv": str(evidence_path),
            "unit_provenance_csv": str(prov_path),
            "cp01_consistency_csv": str(consistency_path),
            "report_md": str(report_path),
            "manifest_json": str(manifest_path),
            "analysis_units_total": report_ctx.analysis_units_total,
            "units_with_labels": report_ctx.units_with_labels,
            "units_without_labels": report_ctx.units_without_labels,
        }

    # ------------------ helpers ------------------

    def _build_consistency_table(self, profiles: list[SegmentProfile]) -> pd.DataFrame:
        """Build the CP-01 ↔ CP-04 consistency table.

        For each (unit, cluster_id) in CP-04 profiles, compare:
        - ``cp04_cluster_customer_count`` = count from CP-04 segment profile.
        - ``cp01_cluster_customer_count`` = count from CP-01 size table.
        """
        size_csv_path = self.cp01_size_table_path
        if not size_csv_path.exists():
            return pd.DataFrame(
                columns=[
                    "unit_id",
                    "algorithm",
                    "cluster_id",
                    "is_noise",
                    "cp04_cluster_customer_count",
                    "cp01_cluster_customer_count",
                    "match",
                    "diff",
                ]
            )
        cp01_df = pd.read_csv(size_csv_path)
        rows: list[dict[str, Any]] = []
        for p in profiles:
            cp04_count = int(p.customer_count)
            # For NOT_AVAILABLE rows (EXP-03), skip the consistency
            # check entirely — they don't have CP-01 data.
            if p.is_not_available:
                continue
            cp01_row = cp01_df.loc[
                (cp01_df["unit_id"] == p.unit_id) & (cp01_df["cluster_id"] == int(p.cluster_id))
            ]
            if cp01_row.empty:
                cp01_count: int | None = None
                match = False
                diff: int | None = None
            else:
                cp01_count = int(cp01_row.iloc[0]["customer_count"])
                match = cp04_count == cp01_count
                diff = cp04_count - cp01_count
            rows.append(
                {
                    "unit_id": p.unit_id,
                    "algorithm": p.algorithm,
                    "cluster_id": int(p.cluster_id),
                    "is_noise": bool(p.is_noise),
                    "cp04_cluster_customer_count": cp04_count,
                    "cp01_cluster_customer_count": cp01_count,
                    "match": bool(match),
                    "diff": diff,
                }
            )
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values(["unit_id", "cluster_id"]).reset_index(drop=True)
        return df

    def _validate_consistency(
        self,
        segment_names: list[SegmentName],
        profiles: list[SegmentProfile],
    ) -> None:
        """Light sanity check: same number of profiles as names; each
        (unit, cluster_id) appears exactly once."""
        if len(segment_names) != len(profiles):
            raise RuntimeError(
                "Mismatch between segment names and segment profiles: "
                f"{len(segment_names)} names vs {len(profiles)} profiles."
            )
        seen: set[tuple[str, int]] = set()
        for p in profiles:
            key = (p.unit_id, int(p.cluster_id))
            if key in seen:
                raise RuntimeError(f"Duplicate (unit_id, cluster_id) in profiles: {key}")
            seen.add(key)

    def _collect_chart_artifacts(self, units: list) -> dict[str, list[str]]:
        """Collect CP-01/02/03 chart paths for the report.

        Returns a mapping ``unit_id -> [relative paths]``. CP-04 doesn't
        produce its own charts; it reuses charts from earlier profiling
        stages.
        """
        artifacts: dict[str, list[str]] = {}
        cp01_dir = self.cp01_size_table_path.parent / "figures"
        cp02_dir = self.cp02_output_dir / "figures"
        cp03_dir = self.cp03_output_dir / "figures"
        for u in units:
            if not u.labels_persisted:
                continue
            uid = u.unit_id
            chart_paths: list[str] = []
            if cp01_dir.exists():
                for p in sorted(cp01_dir.glob("cp01_*")):
                    if uid.replace(" ", "_") in p.name:
                        chart_paths.append(
                            str(p.relative_to(self.output_dir))
                            if p.is_relative_to(self.output_dir)
                            else f"../cp01/figures/{p.name}"
                        )
            if cp02_dir.exists():
                for p in sorted(cp02_dir.glob("cp02_*")):
                    if uid.replace(" ", "_") in p.name:
                        chart_paths.append(f"../cp02/figures/{p.name}")
            if cp03_dir.exists():
                for p in sorted(cp03_dir.glob("cp03_*")):
                    if uid.replace(" ", "_") in p.name:
                        chart_paths.append(f"../cp03/figures/{p.name}")
            if chart_paths:
                artifacts[uid] = chart_paths
        return artifacts

    def _summary_stats(self, profiles: list[SegmentProfile]) -> dict[str, Any]:
        """Aggregate descriptive stats over the run."""
        n_total = len(profiles)
        n_noise = sum(1 for p in profiles if p.is_noise)
        n_not_available = sum(1 for p in profiles if p.is_not_available)
        n_named = sum(
            1
            for p in profiles
            if p.naming_status == "NAMED" and not p.is_noise and not p.is_not_available
        )
        n_comparative = sum(1 for p in profiles if p.naming_status == "COMPARATIVE")
        naming_status_distribution: dict[str, int] = {
            "NAMED": n_named,
            "COMPARATIVE": n_comparative,
            "NOT_AVAILABLE": n_not_available,
            "NOISE": n_noise,
        }
        # Per-algorithm naming count (only NAMED clusters).
        per_algorithm_named: dict[str, int] = {}
        for p in profiles:
            if p.naming_status == "NAMED" and not p.is_noise:
                per_algorithm_named[p.algorithm] = per_algorithm_named.get(p.algorithm, 0) + 1
        return {
            "total_profiles": n_total,
            "naming_status_distribution": naming_status_distribution,
            "per_algorithm_named": per_algorithm_named,
        }


def run_cp04(
    repo_root: Path | None = None,
    output_dir: Path | None = None,
    include_exp03: bool = True,
) -> Mapping[str, Any]:
    """Convenience entry-point mirroring the package-level API."""
    if repo_root is None:
        repo_root = Path.cwd()
    if output_dir is None:
        output_dir = repo_root / DEFAULT_OUTPUT_DIR
    return Cp04Runner(
        repo_root=repo_root,
        output_dir=output_dir,
        include_exp03=include_exp03,
    ).run()


def _format_supporting_evidence(profile: SegmentProfile) -> str:
    """Format the supporting evidence string for the naming CSV."""
    parts: list[str] = []
    for feat in ("Recency", "Frequency", "Monetary"):
        for fs in profile.feature_summaries:
            if fs.feature == feat:
                if fs.direction == "NA" or fs.direction == "ZERO_REFERENCE":
                    continue
                if np.isfinite(fs.rel_diff_median_pct):
                    parts.append(f"{feat}={fs.direction} ({fs.rel_diff_median_pct:+.0f}%)")
                else:
                    parts.append(f"{feat}={fs.direction}")
                break
    return "; ".join(parts)


__all__ = ["Cp04Runner", "run_cp04", "DEFAULT_OUTPUT_DIR"]
