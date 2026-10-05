"""The :class:`ExperimentResultRepository` — top-level EVA-01 container.

The repository holds the unified, normalized rows from EPIC-07 and
exposes methods to:

- Collect rows from EPIC-07 source artifacts.
- Validate the schema and detect anomalies.
- Build summary tables (per-experiment, per-algorithm, per-K).
- Serialise the standardized dataset (parquet + CSV).
- Emit a Markdown summary report.
- Persist the validation report alongside the data.

Hard constraints (AGENTS.md §2):

- No ranking, no "best/winner/optimal/recommended/final" labels.
- No mutation of EPIC-07 artifacts.
- No new dependencies.
- Schema is locked in :mod:`schema`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from customer_segmentation.evaluation.experiment_results import collectors
from customer_segmentation.evaluation.experiment_results.schema import (
    ALLOWED_DECISION_STATUSES,
    FIELD_TYPES,
    FORBIDDEN_DECISION_LABELS,
    MISSING,
    STANDARD_COLUMNS,
)
from customer_segmentation.evaluation.experiment_results.summary import (
    build_algorithm_summary,
    build_experiment_summary,
    build_k_summary,
    summary_tables_to_markdown,
)
from customer_segmentation.evaluation.experiment_results.validation import (
    ValidationReport,
    validate_repository,
    validation_report_to_json,
)

__all__ = [
    "ExperimentResultRepository",
    "build_repository_from_reports",
]


# Default locations used by ``build_repository_from_reports``.
DEFAULT_REPORTS_DIR: Path = Path("reports")
DEFAULT_OUTPUT_DIR: Path = Path("reports/evaluation")


@dataclass
class RepositorySnapshot:
    """Bundled payload of all outputs derived from a repository.

    Groups the standardised dataset, the validation report, the
    summary tables, and the Markdown summary report so callers can
    persist them in one call.
    """

    rows: list[dict[str, Any]]
    dataset: pd.DataFrame
    validation_report: ValidationReport
    experiment_summary: pd.DataFrame
    algorithm_summary: pd.DataFrame
    k_summary: pd.DataFrame
    markdown_report: str


class ExperimentResultRepository:
    """In-memory container for the unified experiment result dataset.

    Lifecycle:

    1. Construct via :meth:`build` or :meth:`build_from_reports_dir`.
    2. Optionally run :meth:`validate` to detect anomalies.
    3. Call :meth:`summary` to build summary tables.
    4. Call :meth:`to_parquet` / :meth:`to_csv` / :meth:`write_outputs`
       to persist.
    """

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        if not isinstance(rows, list):
            raise TypeError(f"rows must be a list of dicts, got {type(rows).__name__}.")
        self.rows: list[dict[str, Any]] = rows
        self._dataset_cache: pd.DataFrame | None = None
        self._validation_report: ValidationReport | None = None

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    @classmethod
    def build(
        cls,
        *,
        exp01_rows: list[dict[str, Any]],
        exp02_rows: list[dict[str, Any]],
        exp03_rows: list[dict[str, Any]],
        exp04_rows: list[dict[str, Any]],
        exp05_rows: list[dict[str, Any]],
    ) -> ExperimentResultRepository:
        """Build a repository from pre-collected per-experiment row lists.

        Useful for tests where each collector's output is supplied
        independently.
        """
        rows = exp01_rows + exp02_rows + exp03_rows + exp04_rows + exp05_rows
        return cls(rows=rows)

    @classmethod
    def build_from_reports_dir(
        cls,
        reports_dir: Path | str,
        *,
        experiments: tuple[str, ...] = ("EXP-01", "EXP-02", "EXP-03", "EXP-04", "EXP-05"),
    ) -> ExperimentResultRepository:
        """Build the repository by reading EPIC-07 artifacts from disk.

        Parameters
        ----------
        reports_dir : path-like
            Path to the ``reports/`` directory (containing ``exp01/`` ...
            ``exp05/``).
        experiments : tuple of str, optional
            Subset of source experiments to include. Default: all five.

        Returns
        -------
        ExperimentResultRepository
            A populated repository instance.
        """
        reports_dir = Path(reports_dir)
        exp01_rows: list[dict[str, Any]] = []
        exp02_rows: list[dict[str, Any]] = []
        exp03_rows: list[dict[str, Any]] = []
        exp04_rows: list[dict[str, Any]] = []
        exp05_rows: list[dict[str, Any]] = []

        if "EXP-01" in experiments:
            exp01_rows = collectors.collect_exp01(reports_dir / "exp01")
        if "EXP-02" in experiments:
            exp02_rows = collectors.collect_exp02(reports_dir / "exp02")
        if "EXP-03" in experiments:
            exp03_rows = collectors.collect_exp03(reports_dir / "exp03")
        if "EXP-04" in experiments:
            exp04_rows = collectors.collect_exp04(reports_dir / "exp04")
        if "EXP-05" in experiments:
            exp05_rows = collectors.collect_exp05(reports_dir / "exp05")

        return cls.build(
            exp01_rows=exp01_rows,
            exp02_rows=exp02_rows,
            exp03_rows=exp03_rows,
            exp04_rows=exp04_rows,
            exp05_rows=exp05_rows,
        )

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def n_rows(self) -> int:
        """Total number of rows in the repository."""
        return len(self.rows)

    @property
    def n_rows_by_experiment(self) -> dict[str, int]:
        """Count rows per source experiment."""
        out: dict[str, int] = {}
        for r in self.rows:
            key = str(r.get("source_experiment", MISSING))
            out[key] = out.get(key, 0) + 1
        return out

    @property
    def dataset(self) -> pd.DataFrame:
        """Return the dataset as a pandas DataFrame (cached)."""
        if self._dataset_cache is None:
            self._dataset_cache = _to_dataframe(self.rows)
        return self._dataset_cache

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> ValidationReport:
        """Run schema validation and anomaly detection.

        Returns a :class:`ValidationReport` summarising row statuses,
        duplicate detection, condition inconsistency, and field coverage.
        """
        if self._validation_report is None:
            self._validation_report = validate_repository(self.rows)
        return self._validation_report

    # ------------------------------------------------------------------
    # Summary tables
    # ------------------------------------------------------------------

    def summary(self) -> dict[str, pd.DataFrame]:
        """Build summary tables (per-experiment, per-algorithm, per-K)."""
        df = self.dataset
        return {
            "experiment_summary": build_experiment_summary(df),
            "algorithm_summary": build_algorithm_summary(df),
            "k_summary": build_k_summary(df),
        }

    def summary_markdown(self) -> str:
        """Return the Markdown summary report for the repository."""
        df = self.dataset
        tables = self.summary()
        validation_report = self.validate()
        return summary_tables_to_markdown(
            dataset=df,
            tables=tables,
            validation_report=validation_report,
        )

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_parquet(self, output_dir: Path | str) -> dict[str, str]:
        """Serialise the standardized dataset to a parquet file.

        Returns
        -------
        dict
            Mapping ``{"parquet": "..."}`` with the destination path.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "eva01_experiment_repository.parquet"
        df = self.dataset
        df.to_parquet(path, index=False)
        return {"parquet": str(path)}

    def to_csv(self, output_dir: Path | str) -> dict[str, str]:
        """Serialise the standardized dataset to a CSV file."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "eva01_experiment_repository.csv"
        df = self.dataset
        df.to_csv(path, index=False)
        return {"csv": str(path)}

    def write_outputs(
        self,
        output_dir: Path | str,
        *,
        also_csv: bool = True,
        also_markdown: bool = True,
        also_validation: bool = True,
        also_summary_csv: bool = True,
    ) -> dict[str, Any]:
        """Persist the full EVA-01 output bundle.

        Writes (by default):

        - ``eva01_experiment_repository.parquet`` — standardized dataset
        - ``eva01_experiment_repository.csv`` — same in CSV form
        - ``eva01_validation_report.json`` — validation / anomaly report
        - ``eva01_summary_experiment.csv`` — per-experiment summary
        - ``eva01_summary_algorithm.csv`` — per-algorithm summary
        - ``eva01_summary_k.csv`` — per-K summary
        - ``eva01_summary.md`` — Markdown summary

        Parameters
        ----------
        output_dir : path-like
            Destination directory. Created if missing.
        also_csv, also_markdown, also_validation, also_summary_csv : bool
            Toggle each artefact independently.

        Returns
        -------
        dict
            Mapping of artefact name → absolute path.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        paths: dict[str, Any] = {}

        # Standardized dataset (parquet + optional CSV)
        paths.update(self.to_parquet(output_dir))
        if also_csv:
            paths.update(self.to_csv(output_dir))

        # Summary tables
        tables = self.summary()
        if also_summary_csv:
            for name, df in tables.items():
                summary_path = output_dir / f"eva01_{name}.csv"
                df.to_csv(summary_path, index=False)
                paths[f"{name}_csv"] = str(summary_path)

        # Validation report
        if also_validation:
            validation_path = output_dir / "eva01_validation_report.json"
            report = self.validate()
            validation_path.write_text(validation_report_to_json(report), encoding="utf-8")
            paths["validation_report_json"] = str(validation_path)

        # Markdown summary
        if also_markdown:
            md_path = output_dir / "eva01_summary.md"
            md_path.write_text(self.summary_markdown(), encoding="utf-8")
            paths["markdown_summary"] = str(md_path)

        return paths

    # ------------------------------------------------------------------
    # Snapshot helper
    # ------------------------------------------------------------------

    def snapshot(self) -> RepositorySnapshot:
        """Return a :class:`RepositorySnapshot` bundling all outputs."""
        return RepositorySnapshot(
            rows=list(self.rows),
            dataset=self.dataset.copy(),
            validation_report=self.validate(),
            **self.summary(),
            markdown_report=self.summary_markdown(),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Convert a list of row dicts to a typed pandas DataFrame.

    The DataFrame is built with the standardised schema in
    :data:`STANDARD_COLUMNS`. Columns not present in a row are
    filled with the literal ``MISSING`` string (matching the
    sentinel used by the validators).

    The dtypes are then coerced according to :data:`FIELD_TYPES`.
    Float / Int64 columns may contain ``MISSING`` strings where
    the value was not recorded.
    """
    if not rows:
        df = pd.DataFrame(columns=list(STANDARD_COLUMNS))
    else:
        df = pd.DataFrame(rows)
        # Reorder to STANDARD_COLUMNS; fill missing columns.
        for col in STANDARD_COLUMNS:
            if col not in df.columns:
                df[col] = MISSING
        df = df.loc[:, list(STANDARD_COLUMNS)]

    # Dtype coercion. We use Int64 / Float64 (pandas nullable) so that
    # ``MISSING`` strings can survive the round-trip without forcing
    # the whole column to ``object``. Missing-valued cells are coerced
    # to pandas.NA.
    for col, dtype in FIELD_TYPES.items():
        if col not in df.columns:
            continue
        try:
            if dtype in ("Int64", "Float64"):
                # Coerce MISSING / NaN to NA
                df[col] = pd.to_numeric(df[col], errors="coerce").astype(dtype)
            elif dtype == "str":
                # String columns keep their ``MISSING`` literal.
                df[col] = df[col].astype("object").where(df[col].notna(), MISSING)
        except (TypeError, ValueError):
            # Fallback: leave the column as-is if coercion fails.
            continue
    return df


def build_repository_from_reports(
    reports_dir: Path | str = DEFAULT_REPORTS_DIR,
    *,
    experiments: tuple[str, ...] = ("EXP-01", "EXP-02", "EXP-03", "EXP-04", "EXP-05"),
) -> ExperimentResultRepository:
    """Convenience wrapper for :meth:`ExperimentResultRepository.build_from_reports_dir`.

    Equivalent to calling the classmethod directly but with a shorter
    signature for one-shot use.
    """
    return ExperimentResultRepository.build_from_reports_dir(
        reports_dir,
        experiments=experiments,
    )


# ---------------------------------------------------------------------------
# Decision-status sanity check (defensive; should never trigger)
# ---------------------------------------------------------------------------


def assert_decision_status_taxonomy(rows: list[dict[str, Any]]) -> list[str]:
    """Return any decision_status values that are NOT in the allowed taxonomy.

    EVA-01 does NOT add new decision statuses; it only inherits them
    from the source experiments. This helper exists for the test suite
    to confirm that no collector accidentally leaks a forbidden label.
    """
    bad: list[str] = []
    for r in rows:
        ds = r.get("decision_status", "")
        if isinstance(ds, str) and ds and ds != MISSING:
            if ds not in ALLOWED_DECISION_STATUSES:
                bad.append(ds)
            if ds in FORBIDDEN_DECISION_LABELS:
                bad.append(ds)
    return sorted(set(bad))


def now_utc_iso() -> str:
    """Return the current UTC timestamp in ISO-8601."""
    return datetime.now(UTC).isoformat()
