"""CP-05 runner — orchestrate all 6 evaluation axes + Final Segment Definition."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from customer_segmentation.profiling.cp05.business_relevance import (
    business_relevance_results_to_rows,
    evaluate_business_relevance,
)
from customer_segmentation.profiling.cp05.consistency import (
    consistency_results_to_rows,
    evaluate_consistency,
)
from customer_segmentation.profiling.cp05.distinctiveness import (
    distinctiveness_results_to_rows,
    evaluate_distinctiveness,
)
from customer_segmentation.profiling.cp05.final_definition import (
    build_final_segment_definition,
    final_segment_definitions_to_rows,
)
from customer_segmentation.profiling.cp05.interpretability import (
    evaluate_interpretability,
    interpretability_results_to_rows,
)
from customer_segmentation.profiling.cp05.provenance import (
    Cp04EvidenceBundle,
    build_cp05_analysis_units,
    load_cp04_evidence_for_unit,
)
from customer_segmentation.profiling.cp05.report import (
    Cp05ReportContext,
    build_cp05_markdown,
)
from customer_segmentation.profiling.cp05.size_evaluation import (
    evaluate_size,
    size_results_to_rows,
)
from customer_segmentation.profiling.cp05.stability import (
    evaluate_stability,
    stability_results_to_rows,
)

LOGGER = logging.getLogger(__name__)

DEFAULT_OUTPUT_DIR = Path("reports/profiling/cp05")
DEFAULT_CP04_OUTPUT_DIR = Path("reports/profiling/cp04")
DEFAULT_CP01_OUTPUT_DIR = Path("reports/profiling/cp01")
DEFAULT_CP02_OUTPUT_DIR = Path("reports/profiling/cp02")
DEFAULT_CP03_OUTPUT_DIR = Path("reports/profiling/cp03")
DEFAULT_EXP05_OUTPUT_DIR = Path("reports/exp05")


@dataclass
class Cp05RunResult:
    """Output của CP-05 run."""

    output_dir: Path
    n_units: int
    n_definitions: int
    sha_manifest: dict[str, str]


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _list_input_paths(
    cp01_dir: Path,
    cp02_dir: Path,
    cp03_dir: Path,
    cp04_dir: Path,
    exp05_dir: Path | None,
) -> list[Path]:
    paths: list[Path] = []
    for d in (cp01_dir, cp02_dir, cp03_dir, cp04_dir):
        if d.exists():
            for p in sorted(d.glob("*.csv")):
                paths.append(p)
            for p in sorted(d.glob("*.json")):
                paths.append(p)
            for p in sorted(d.glob("*.md")):
                paths.append(p)
    if exp05_dir is not None and exp05_dir.exists():
        for p in sorted(exp05_dir.glob("*.csv")):
            paths.append(p)
    return paths


def _sha_manifest(input_paths: Iterable[Path], output_files: Iterable[Path]) -> dict[str, str]:
    manifest: dict[str, str] = {}
    for p in input_paths:
        if p.exists():
            manifest[f"INPUT::{p}"] = _sha256_file(p)
    for p in output_files:
        if p.exists():
            manifest[f"OUTPUT::{p}"] = _sha256_file(p)
    return manifest


class Cp05Runner:
    """Top-level orchestrator."""

    def __init__(
        self,
        output_dir: Path = DEFAULT_OUTPUT_DIR,
        *,
        cp04_dir: Path = DEFAULT_CP04_OUTPUT_DIR,
        cp01_dir: Path = DEFAULT_CP01_OUTPUT_DIR,
        cp02_dir: Path = DEFAULT_CP02_OUTPUT_DIR,
        cp03_dir: Path = DEFAULT_CP03_OUTPUT_DIR,
        exp05_dir: Path | None = DEFAULT_EXP05_OUTPUT_DIR,
        include_exp03: bool = True,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.cp04_dir = Path(cp04_dir)
        self.cp01_dir = Path(cp01_dir)
        self.cp02_dir = Path(cp02_dir)
        self.cp03_dir = Path(cp03_dir)
        self.exp05_dir = Path(exp05_dir) if exp05_dir is not None else None
        self.include_exp03 = include_exp03

    def run(self) -> Cp05RunResult:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        LOGGER.info("CP-05 starting. output_dir=%s", self.output_dir)

        # 1. Load analysis units.
        units = build_cp05_analysis_units(self.cp04_dir / "cp04_unit_provenance.csv")
        if not self.include_exp03:
            units = [u for u in units if u.source_experiment == "EXP-01"]

        # 2. Per-unit evaluation.
        all_defs: list = []
        all_distinct: list = []
        all_interp: list = []
        all_cons: list = []
        all_size: list = []
        all_stab: list = []
        all_biz: list = []

        for unit in units:
            LOGGER.info("Processing unit: %s", unit.unit_id)
            bundle: Cp04EvidenceBundle = load_cp04_evidence_for_unit(
                unit,
                cp01_dir=self.cp01_dir,
                cp02_dir=self.cp02_dir,
                cp03_dir=self.cp03_dir,
                cp04_dir=self.cp04_dir,
            )

            distinct = evaluate_distinctiveness(bundle)
            interp = evaluate_interpretability(bundle)
            cons = evaluate_consistency(bundle)
            size = evaluate_size(bundle)
            stab = evaluate_stability(bundle, exp05_dir=self.exp05_dir)
            biz = evaluate_business_relevance(bundle)

            defs = build_final_segment_definition(
                unit,
                bundle,
                distinctiveness_results=distinct,
                interpretability_results=interp,
                consistency_results=cons,
                size_results=size,
                stability_results=stab,
                business_relevance_results=biz,
            )

            all_defs.extend(defs)
            all_distinct.extend(distinct)
            all_interp.extend(interp)
            all_cons.extend(cons)
            all_size.extend(size)
            all_stab.extend(stab)
            all_biz.extend(biz)

        # 3. Write artifacts.
        defs_df = pd.DataFrame(final_segment_definitions_to_rows(all_defs))
        defs_df = defs_df.sort_values(["unit_id", "cluster_id"]).reset_index(drop=True)
        defs_path = self.output_dir / "cp05_final_segment_definition.csv"
        defs_df.to_csv(defs_path, index=False)

        for name, results, to_rows in [
            ("cp05_distinctiveness_evaluation.csv", all_distinct, distinctiveness_results_to_rows),
            ("cp05_interpretability_evaluation.csv", all_interp, interpretability_results_to_rows),
            ("cp05_behavioral_consistency_evaluation.csv", all_cons, consistency_results_to_rows),
            ("cp05_segment_size_evaluation.csv", all_size, size_results_to_rows),
            ("cp05_stability_evaluation.csv", all_stab, stability_results_to_rows),
            ("cp05_business_relevance_evaluation.csv", all_biz, business_relevance_results_to_rows),
        ]:
            df = pd.DataFrame(to_rows(results))
            df = df.sort_values(["unit_id", "cluster_id"]).reset_index(drop=True)
            df.to_csv(self.output_dir / name, index=False)

        # Unit provenance.
        prov_rows = []
        for u in units:
            prov_rows.append(
                {
                    "unit_id": u.unit_id,
                    "algorithm": u.algorithm,
                    "source_experiment": u.source_experiment,
                    "configuration_status": u.configuration_status,
                    "labels_persisted": u.labels_persisted,
                    "n_customers_eligible": u.n_customers_eligible,
                }
            )
        pd.DataFrame(prov_rows).to_csv(self.output_dir / "cp05_unit_provenance.csv", index=False)

        # 4. Report (Vietnamese).
        ctx = Cp05ReportContext(
            final_definitions=all_defs,
            units=units,
            sha_manifest={},  # populated below
        )
        report_md = build_cp05_markdown(ctx)
        (self.output_dir / "cp05_report.md").write_text(report_md, encoding="utf-8")

        # 5. Manifest.
        input_paths = _list_input_paths(
            self.cp01_dir, self.cp02_dir, self.cp03_dir, self.cp04_dir, self.exp05_dir
        )
        output_files = sorted(self.output_dir.glob("*.csv")) + [self.output_dir / "cp05_report.md"]
        manifest = _sha_manifest(input_paths, output_files)
        manifest_payload = {
            "input_shas": {
                k[len("INPUT::") :]: v for k, v in manifest.items() if k.startswith("INPUT::")
            },
            "output_shas": {
                k[len("OUTPUT::") :]: v for k, v in manifest.items() if k.startswith("OUTPUT::")
            },
            "n_units": len(units),
            "n_definitions": len(all_defs),
        }
        (self.output_dir / "cp05_runner_manifest.json").write_text(
            json.dumps(manifest_payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # 6. Re-write report with full SHA manifest.
        ctx2 = Cp05ReportContext(
            final_definitions=all_defs,
            units=units,
            sha_manifest={
                **{k[len("INPUT::") :]: v for k, v in manifest.items() if k.startswith("INPUT::")},
                **{
                    k[len("OUTPUT::") :]: v for k, v in manifest.items() if k.startswith("OUTPUT::")
                },
            },
        )
        report_md2 = build_cp05_markdown(ctx2)
        (self.output_dir / "cp05_report.md").write_text(report_md2, encoding="utf-8")

        # 7. Re-verify output SHAs after second write.
        for out in [self.output_dir / "cp05_report.md"]:
            manifest_payload["output_shas"][str(out)] = _sha256_file(out)
        (self.output_dir / "cp05_runner_manifest.json").write_text(
            json.dumps(manifest_payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        LOGGER.info(
            "CP-05 complete. units=%d, definitions=%d, outputs=%s",
            len(units),
            len(all_defs),
            self.output_dir,
        )
        return Cp05RunResult(
            output_dir=self.output_dir,
            n_units=len(units),
            n_definitions=len(all_defs),
            sha_manifest=manifest,
        )


def run_cp05(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    include_exp03: bool = True,
) -> Cp05RunResult:
    """Functional entrypoint."""
    runner = Cp05Runner(
        output_dir=output_dir,
        include_exp03=include_exp03,
    )
    return runner.run()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="CP-05 runner")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--no-exp03", action="store_true")
    args = parser.parse_args()
    result = run_cp05(
        output_dir=Path(args.output_dir),
        include_exp03=not args.no_exp03,
    )
    print(f"CP-05 complete. units={result.n_units}, definitions={result.n_definitions}")


if __name__ == "__main__":
    main()
