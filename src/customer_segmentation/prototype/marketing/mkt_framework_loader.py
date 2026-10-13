"""MKT framework loader for DEV-07 Prototype Marketing.

Phase A (MKT-01..MKT-05 absent):

- :func:`load_mkt_framework` returns ``None`` and reports
  ``mkt_framework_found=False``.
- The pipeline emits ``availability=REVIEW_REQUIRED`` for every
  recommendation.
- This module does NOT silently fabricate a MKT framework; it does
  NOT parse non-existent files; it does NOT raise on absent path.

Phase B (MKT framework present):

- :func:`load_mkt_framework` reads the framework directory
  (``configs/dev07_marketing.yaml::mkt_framework.path_relative``)
  and returns a :class:`MktFrameworkRef` carrying the discovered
  version string and per-file references.
- The version string matches the config's
  ``mkt_framework.version_pattern`` regex.
- Phase B extension: :func:`load_mkt_framework_structure` returns
  an optional :class:`MktFrameworkStructure` carrying per-doc
  structural metadata (file existence + per-doc sha256 + token
  length). It does NOT parse business content (objective / strategy /
  action / KPI / limitation templates are NOT extracted). Owner
  approval + MKT framework design is required before any business
  template extraction is attempted (OQ-D07-01).

Diagnostics
-----------
- When the framework directory is missing or has < 5 MKT docs, a
  ``DEBUG`` log records the reason; loader returns ``None`` (Phase
  A contract preserved).
- When the framework is present but the version extracted from the
  filename does not match the configured pattern (a known P1 issue
  flagged in audit §4.1; canonical-form decision pending ADR-0008),
  a ``WARNING`` log records the constructed aggregate form and the
  pattern that rejected it. Loader still returns ``None`` to keep
  the Phase A contract.

Hard rules
----------
- Read-only on disk; does not write or modify anything.
- No "best", "winner", "optimal", "recommended" outside the
  framework-discovery disclaimer.
- Phase B structure loader does NOT parse business content from MKT
  files. It only reads file metadata (sha256, token count, presence).
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from customer_segmentation.prototype.marketing.config_loader import Dev07Config
from customer_segmentation.prototype.marketing.exceptions import (
    MarketingConfigError,
)

__all__ = [
    "MktFrameworkRef",
    "MktDocRef",
    "MktFrameworkStructure",
    "load_mkt_framework",
    "load_mkt_framework_structure",
    "framework_version_string",
]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MKT_DOC_NAMES: Final[tuple[str, ...]] = (
    "MKT-01_framework_overview",
    "MKT-02_objective_templates",
    "MKT-03_strategy_action_templates",
    "MKT-04_kpi_definitions",
    "MKT-05_limitation_framework",
)

# Stdlib logger for diagnostics. We do NOT use the project
# ``logging_config`` here to avoid a circular import: the loader is
# imported by ``pipeline`` which configures logging at runtime, but
# the loader itself may be called from tests before logging is
# configured. Stdlib logging is safe regardless of configuration
# state (messages are no-ops if no handler is attached).
_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Reference
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MktFrameworkRef:
    """Reference to a discovered MKT framework directory.

    Attributes
    ----------
    framework_dir : pathlib.Path
        Path to the discovered MKT framework directory.
    version : str
        Framework version string (matched against
        ``configs/dev07_marketing.yaml::mkt_framework.version_pattern``).
    files : list of str
        Repository-relative paths to the MKT-01..05 files found.
    """

    framework_dir: Path
    version: str
    files: list[str]


@dataclass(frozen=True)
class MktDocRef:
    """Structural reference to a single MKT-NN file (Phase B).

    Carries structural metadata only. Business content (objective /
    strategy / KPI definitions) is NOT extracted here.
    """

    mkt_id: str  # e.g. "MKT-01"
    file_path: Path  # absolute path on disk
    sha256: str  # sha256 hex of file bytes
    byte_count: int  # raw file size in bytes
    token_count: int  # whitespace-split token count

    def __post_init__(self) -> None:
        if not self.mkt_id.startswith("MKT-"):
            raise ValueError(f"mkt_id {self.mkt_id!r} must start with 'MKT-'.")
        if not isinstance(self.sha256, str) or len(self.sha256) != 64:
            raise ValueError(f"sha256 must be a 64-character hex string; got {self.sha256!r}.")
        if self.byte_count < 0:
            raise ValueError(f"byte_count MUST be >= 0; got {self.byte_count!r}.")
        if self.token_count < 0:
            raise ValueError(f"token_count MUST be >= 0; got {self.token_count!r}.")


@dataclass(frozen=True)
class MktFrameworkStructure:
    """Structural metadata for a discovered MKT framework (Phase B).

    The structure is intentionally **content-free**: it carries
    per-doc presence + sha256 + size, but does NOT extract any
    marketing business content (objective / strategy / action /
    KPI / limitation). Owner approval + MKT framework design is
    required before business template extraction is attempted
    (OQ-D07-01).
    """

    framework_dir: Path
    version: str
    docs: dict[str, MktDocRef] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Enforce closed set of MKT doc ids.
        expected = {f"MKT-0{i}" for i in range(1, 6)}
        actual = set(self.docs.keys())
        if actual != expected:
            missing = expected - actual
            extra = actual - expected
            raise ValueError(
                f"MktFrameworkStructure.docs must contain exactly MKT-01..05; "
                f"missing={sorted(missing)}, extra={sorted(extra)}."
            )

    @property
    def is_complete(self) -> bool:
        """Return True iff all 5 MKT-NN files are present."""
        return len(self.docs) == 5


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def load_mkt_framework(
    config: Dev07Config,
    repo_root: Path | None = None,
) -> MktFrameworkRef | None:
    """Discover the MKT framework under the configured path.

    Parameters
    ----------
    config : Dev07Config
        Loaded DEV-07 config (uses ``mkt_framework.path_relative`` and
        ``mkt_framework.version_pattern``).
    repo_root : pathlib.Path or None
        Repository root for resolving ``path_relative``. If None, use
        the parent of :data:`DEFAULT_DEV07_CONFIG_PATH`.

    Returns
    -------
    MktFrameworkRef or None
        Reference to the framework directory if all five MKT-0X files
        are present; ``None`` if any are missing (Phase A behaviour).
    """
    if repo_root is None:
        from customer_segmentation.prototype.marketing.config_loader import (
            DEFAULT_DEV07_CONFIG_PATH,
        )

        repo_root = DEFAULT_DEV07_CONFIG_PATH.parent.parent

    framework_dir = repo_root / config.mkt_framework.path_relative
    if not framework_dir.is_dir():
        _LOGGER.debug(
            "MKT framework directory not found at %s; treating as absent (Phase A).",
            framework_dir,
        )
        return None

    pattern = re.compile(config.mkt_framework.version_pattern)
    # Find files matching MKT-NN_*.md naming convention.
    found_files: list[Path] = []
    for child in sorted(framework_dir.iterdir()):
        if not child.is_file():
            continue
        if not child.name.lower().endswith(".md"):
            continue
        if not child.name.startswith("MKT-"):
            continue
        found_files.append(child)

    if len(found_files) < len(_MKT_DOC_NAMES):
        _LOGGER.debug(
            "MKT framework directory %s present but only %d/%d MKT docs found; "
            "treating as absent (Phase A).",
            framework_dir,
            len(found_files),
            len(_MKT_DOC_NAMES),
        )
        return None

    # Extract version from the first MKT-01 file name (e.g. "MKT-01__v1.md").
    version = _extract_version(found_files[0], pattern)
    if version is None:
        # Diagnostic: framework directory exists, all 5 docs present,
        # but version extraction failed. This is the silent-failure
        # case flagged in DEV-07 audit §4.1. We log the reason and
        # the constructed aggregate form so the operator can see why
        # the pattern did not match (e.g. config pattern is per-file
        # shape while loader constructs aggregate form). The
        # canonical-form decision is pending owner approval per
        # ADR-0008.
        constructed = f"MKT-01..05__{_extract_version_debug_stem(found_files[0])}"
        _LOGGER.warning(
            "MKT framework found at %s but version extraction failed. "
            "The configured pattern %r did not match the constructed "
            "aggregate version string %r. See ADR-0008 (Accepted) "
            "for the canonical-form decision (Option A: aggregate "
            "MKT-01..05__vN). Loader returns None (Phase A contract "
            "preserved).",
            framework_dir,
            config.mkt_framework.version_pattern,
            constructed,
        )
        return None

    rel_files = [
        str(p.relative_to(repo_root)) if repo_root in p.parents else str(p) for p in found_files
    ]
    return MktFrameworkRef(
        framework_dir=framework_dir,
        version=version,
        files=rel_files,
    )


def load_mkt_framework_structure(
    config: Dev07Config,
    repo_root: Path | None = None,
) -> MktFrameworkStructure | None:
    """Load structural metadata for a discovered MKT framework (Phase B).

    Returns an :class:`MktFrameworkStructure` carrying per-doc
    structural metadata (sha256 + size + token count), or ``None``
    if the framework is absent (mirrors :func:`load_mkt_framework`
    Phase A contract).

    The structure is **content-free**: no business template
    extraction is attempted. This is intentional — owner approval
    + MKT framework design is required before business content is
    extracted (OQ-D07-01).

    Parameters
    ----------
    config : Dev07Config
        Loaded DEV-07 config.
    repo_root : pathlib.Path or None
        Repository root for resolving ``path_relative``.

    Returns
    -------
    MktFrameworkStructure or None
        Structural metadata if all 5 MKT-NN files are present;
        ``None`` otherwise.
    """
    ref = load_mkt_framework(config, repo_root=repo_root)
    if ref is None:
        return None

    # Build per-doc structural metadata.
    docs: dict[str, MktDocRef] = {}
    for f in sorted(ref.framework_dir.iterdir()):
        if not f.is_file():
            continue
        if not f.name.lower().endswith(".md"):
            continue
        if not f.name.startswith("MKT-"):
            continue
        # Derive MKT id from filename prefix (e.g. "MKT-01__v1.md" → "MKT-01").
        m = re.match(r"^(MKT-0[1-5])(?:__|_)v\d+(?:\.\d+)*", f.name)
        if m is None:
            _LOGGER.debug("Skipping file %s: cannot derive MKT id from filename.", f.name)
            continue
        mkt_id = m.group(1)
        try:
            raw = f.read_bytes()
        except OSError as exc:
            _LOGGER.warning("Failed to read MKT file %s: %s", f, exc)
            continue
        sha256 = hashlib.sha256(raw).hexdigest()
        byte_count = len(raw)
        token_count = len(raw.decode("utf-8", errors="replace").split())
        docs[mkt_id] = MktDocRef(
            mkt_id=mkt_id,
            file_path=f,
            sha256=sha256,
            byte_count=byte_count,
            token_count=token_count,
        )

    if len(docs) != 5:
        # Some docs failed to load; treat framework as incomplete.
        _LOGGER.warning(
            "MKT framework structure incomplete; only %d/5 docs loaded.",
            len(docs),
        )
        return None

    return MktFrameworkStructure(
        framework_dir=ref.framework_dir,
        version=ref.version,
        docs=docs,
    )


def _extract_version(path: Path, pattern: re.Pattern[str]) -> str | None:
    """Extract the version string from a MKT file name.

    Accepts naming conventions:
    - ``MKT-01__v1.md`` → ``v1``
    - ``MKT-01_v1.md`` → ``v1``
    - ``MKT-01_v1.2.md`` → ``v1.2``

    The extracted version is then wrapped to ``"MKT-01..05__vN"`` form
    at the caller level (this function only returns the bare ``vN``).
    """
    stem = path.stem  # e.g. "MKT-01__v1"
    m = re.search(r"__?(v\d+(?:\.\d+)*)$", stem)
    if m is None:
        _LOGGER.debug(
            "Could not extract version from %s stem %r (no __vN or _vN suffix).",
            path.name,
            stem,
        )
        return None
    version = m.group(1)
    # Reject if the entire constructed version string would not match
    # the configured pattern.
    if not pattern.match(f"MKT-01..05__{version}"):
        # Diagnostic: emit debug log with the constructed aggregate form
        # so operators can see why the pattern did not match. This is
        # the silent-failure case flagged in audit §4.1; the canonical
        # aggregate vs per-file decision is pending ADR-0008.
        _LOGGER.debug(
            "MKT version pattern mismatch: pattern=%r did not match "
            "constructed aggregate form %r (extracted from %s).",
            pattern.pattern,
            f"MKT-01..05__{version}",
            path.name,
        )
        return None
    return version


def _extract_version_debug_stem(path: Path) -> str:
    """Return the bare version string for diagnostic logging.

    Used only for the warning emitted when ``_extract_version`` returns
    ``None``. Returns ``"<no-version>"`` if the filename has no
    recognisable version suffix.
    """
    m = re.search(r"__?(v\d+(?:\.\d+)*)$", path.stem)
    return m.group(1) if m is not None else "<no-version>"


def framework_version_string(ref: MktFrameworkRef) -> str:
    """Return the canonical ``"MKT-01..05__vN"`` version string for a ref."""
    return f"MKT-01..05__{ref.version}"
