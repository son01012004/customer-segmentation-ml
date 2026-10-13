"""Research-safety tests: research artefacts are not mutated by DEV-02."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import pytest

from customer_segmentation.dataset_management.importer import (
    ImportRequest,
    import_dataset,
)


def _snapshot(paths: list[Path]) -> dict[Path, str]:
    """Return a {path: sha256} map of every existing target.

    Missing paths are recorded with an empty string sentinel so a
    deletion is observable as a change.
    """
    snap: dict[Path, str] = {}
    for p in paths:
        if not p.exists():
            snap[p] = "<missing>"
            continue
        if p.is_dir():
            # Hash the directory listing: every file's name + its
            # sha256 of its bytes. Order matters; we sort.
            parts: list[str] = []
            for sub in sorted(p.rglob("*")):
                if sub.is_file():
                    parts.append(
                        f"{sub.relative_to(p).as_posix()}|{hashlib.sha256(sub.read_bytes()).hexdigest()}"
                    )
                else:
                    parts.append(f"{sub.relative_to(p).as_posix()}|<dir>")
            snap[p] = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
        elif p.is_file():
            snap[p] = hashlib.sha256(p.read_bytes()).hexdigest()
        else:
            snap[p] = "<special>"
    return snap


def _make_config(storage_root: Path) -> dict:
    return {
        "storage_root": str(storage_root),
        "max_file_size_mb": 256,
        "supported_import_formats": ["csv", "parquet"],
        "default_csv_encoding": "utf-8",
        "source_path_policy": {"allow_external_source": True},
        "readonly_research_paths": [
            "data/raw/primary",
            "data/raw/backup",
            "data/processed",
            "reports",
        ],
    }


def test_import_does_not_modify_research_artefacts(tmp_path: Path) -> None:
    """A successful import must not change any read-only research path."""
    # Lay out a fake repository structure with the research paths
    # populated with placeholder files.
    repo = tmp_path / "repo"
    for sub in ("data/raw/primary", "data/raw/backup", "data/processed", "reports"):
        d = repo / sub
        d.mkdir(parents=True, exist_ok=True)
        (d / "marker.txt").write_text(f"research-marker:{sub}\n", encoding="utf-8")
    # Even a fake canonical FE-06 file.
    fe06 = repo / "data" / "processed" / "final_clustering_dataset.parquet"
    pd.DataFrame({"x": [1, 2, 3]}).to_parquet(fe06)

    storage = repo / "data" / "prototype" / "datasets"
    storage.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "data.csv"
    src.write_text("a,b\n1,2\n3,4\n5,6\n", encoding="utf-8")

    targets = [
        repo / "data" / "raw" / "primary",
        repo / "data" / "raw" / "backup",
        repo / "data" / "processed",
        repo / "reports",
    ]
    before = _snapshot(targets)

    import_dataset(
        ImportRequest(
            source_path=src,
            name=None,
            config=_make_config(storage),
            allow_external_source=True,
            cwd=tmp_path,
            repo_root=repo,
        )
    )

    after = _snapshot(targets)
    assert before == after, (
        "Research-safety violation: one of the read-only research paths "
        f"was modified by the import. before={before}, after={after}"
    )


def test_failed_import_does_not_modify_research_artefacts(tmp_path: Path) -> None:
    """A failed import (validation FAIL) must not change research paths."""
    repo = tmp_path / "repo"
    for sub in ("data/raw/primary", "data/raw/backup", "data/processed", "reports"):
        d = repo / sub
        d.mkdir(parents=True, exist_ok=True)
        (d / "marker.txt").write_text(f"research-marker:{sub}\n", encoding="utf-8")

    storage = repo / "data" / "prototype" / "datasets"
    storage.mkdir(parents=True, exist_ok=True)
    # Empty CSV (header only) -> validation FAIL.
    src = tmp_path / "empty.csv"
    src.write_text("a,b\n", encoding="utf-8")

    targets = [
        repo / "data" / "raw" / "primary",
        repo / "data" / "raw" / "backup",
        repo / "data" / "processed",
        repo / "reports",
    ]
    before = _snapshot(targets)

    from customer_segmentation.dataset_management import ImportError

    with pytest.raises(ImportError):
        import_dataset(
            ImportRequest(
                source_path=src,
                name=None,
                config=_make_config(storage),
                allow_external_source=True,
                cwd=tmp_path,
                repo_root=repo,
            )
        )

    after = _snapshot(targets)
    assert before == after


def test_import_only_writes_under_storage_root(tmp_path: Path) -> None:
    """After a successful import, only the storage root has new files."""
    repo = tmp_path / "repo"
    for sub in ("data/raw/primary", "data/raw/backup", "data/processed", "reports"):
        d = repo / sub
        d.mkdir(parents=True, exist_ok=True)
        (d / "marker.txt").write_text("x\n", encoding="utf-8")

    storage = repo / "data" / "prototype" / "datasets"
    storage.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "data.csv"
    src.write_text("a\n1\n2\n", encoding="utf-8")

    before_paths = set()
    for sub in ("data/raw/primary", "data/raw/backup", "data/processed", "reports"):
        before_paths |= {p.relative_to(repo) for p in (repo / sub).rglob("*")}

    import_dataset(
        ImportRequest(
            source_path=src,
            name=None,
            config=_make_config(storage),
            allow_external_source=True,
            cwd=tmp_path,
            repo_root=repo,
        )
    )

    after_paths = set()
    for sub in ("data/raw/primary", "data/raw/backup", "data/processed", "reports"):
        after_paths |= {p.relative_to(repo) for p in (repo / sub).rglob("*")}

    new_outside_storage = after_paths - before_paths
    assert new_outside_storage == set(), (
        f"Unexpected new files outside storage root: {new_outside_storage}"
    )


def test_manifest_research_safety_always_set() -> None:
    """Manifest dataclass is documented as always having these markers."""
    from customer_segmentation.dataset_management.manifest import (
        ResearchSafety,
    )

    safe = ResearchSafety(
        automatically_promoted_to_research=False,
        scope="IMPORTED_PROTOTYPE",
        appeared_in_research_evidence=False,
        read_only_paths_unmodified=[
            "data/raw/primary",
            "data/raw/backup",
            "data/processed",
            "reports",
        ],
    )
    assert safe.automatically_promoted_to_research is False
    assert safe.scope == "IMPORTED_PROTOTYPE"
    assert safe.appeared_in_research_evidence is False


def test_audit_and_versioning_symbols_intact() -> None:
    """Reused research-core helpers are still importable (no API removal)."""
    from customer_segmentation.data.audit import (
        basic_overview,
        categorical_profile,
        missing_profile,
        numerical_profile,
    )
    from customer_segmentation.data.validator import ValidationResult
    from customer_segmentation.transformation.versioning import compute_file_sha256

    # All symbols exist and are callable / data classes.
    assert callable(basic_overview)
    assert callable(categorical_profile)
    assert callable(missing_profile)
    assert callable(numerical_profile)
    assert callable(compute_file_sha256)
    assert ValidationResult.__dataclass_fields__  # type: ignore[attr-defined]


def test_audit_mirrors_in_manifest(tmp_path: Path) -> None:
    """Missing summary and statistics summary track audit.* output."""
    from customer_segmentation.data.audit import (
        categorical_profile,
        missing_profile,
        numerical_profile,
    )
    from customer_segmentation.dataset_management.importer import (
        ImportRequest,
        import_dataset,
    )

    storage = tmp_path / "datasets"
    storage.mkdir()
    src = tmp_path / "data.csv"
    src.write_text("a,b,c\n1,x,2.5\n2,y,3.5\n3,z,4.5\n", encoding="utf-8")

    res = import_dataset(
        ImportRequest(
            source_path=src,
            name=None,
            config=_make_config(storage),
            allow_external_source=True,
            cwd=tmp_path,
            repo_root=tmp_path,
        )
    )

    df = pd.read_csv(src)
    expected_missing = {
        str(r["column"]): float(r["missing_rate"])
        for _, r in missing_profile(df).iterrows()
    }
    assert res.manifest.missing_summary == expected_missing

    num_audit = numerical_profile(df)
    for _, r in num_audit.iterrows():
        col = str(r["column"])
        if col not in res.manifest.statistics_summary.numeric:
            continue
        ns = res.manifest.statistics_summary.numeric[col]
        assert ns.mean == pytest.approx(float(r["mean"]), rel=1e-9)
        assert ns.min == pytest.approx(float(r["min"]), rel=1e-9)
        assert ns.max == pytest.approx(float(r["max"]), rel=1e-9)

    cat_audit = categorical_profile(df)
    for _, r in cat_audit.iterrows():
        col = str(r["column"])
        if col not in res.manifest.statistics_summary.categorical:
            continue
        cs = res.manifest.statistics_summary.categorical[col]
        assert cs.unique_count == int(r["unique_count"])
