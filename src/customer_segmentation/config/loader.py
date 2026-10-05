"""Project-wide configuration loaders.

Single source of truth
----------------------
For the FE-02 cleaning stage, ``configs/preprocessing.yaml`` is the
**single source of truth** for cleaning rules. This module exposes a
loader (:func:`load_preprocessing_config`) that reads that file and
returns a fully-typed :class:`customer_segmentation.preprocessing.cleaning.PipelineConfig`.

The :class:`PipelineConfig` dataclass itself is defined in
:mod:`customer_segmentation.preprocessing.cleaning`. Keeping the loader
separate from the dataclass means:

- The cleaning module can be imported without a YAML parser (no runtime
  dependency on ``PyYAML``).
- Behaviour tests for the cleaning pipeline can construct
  ``PipelineConfig`` instances directly without going through YAML.
- YAML loading is reserved for the orchestrator (``scripts/run_fe02_cleaning.py``).

Failure modes
-------------
:func:`load_preprocessing_config` raises a typed
:class:`PreprocessingConfigError` when the YAML is malformed or when a
required key is missing. The caller can catch this and surface a clean
error message; it never falls back to a silent default.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from customer_segmentation.preprocessing.cleaning import (
    PipelineConfig,
)
from customer_segmentation.preprocessing.invalid_records import (
    InvalidRecordRules,
)

__all__ = [
    "DEFAULT_PREPROCESSING_CONFIG_PATH",
    "PreprocessingConfigError",
    "find_default_preprocessing_config_path",
    "load_preprocessing_config",
    "preprocessing_config_to_dict",
    "resolve_preprocessing_config_path",
]


# The YAML is the single source of truth for FE-02. We resolve it via
# the repo root (the parent of ``src/customer_segmentation/config/``).
_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parents[2]
DEFAULT_PREPROCESSING_CONFIG_PATH: Path = _REPO_ROOT / "configs" / "preprocessing.yaml"


# Status markers used in the YAML to flag decisions that the cleaning
# pipeline applies but the research methodology has not yet finalised.
STATUS_WORKING_ASSUMPTION = "WORKING_ASSUMPTION"
STATUS_PENDING_MENTOR_REVIEW = "PENDING_MENTOR_REVIEW"
VALID_STATUSES = {STATUS_WORKING_ASSUMPTION, STATUS_PENDING_MENTOR_REVIEW}


class PreprocessingConfigError(ValueError):
    """Raised when ``configs/preprocessing.yaml`` is malformed or missing keys."""


# ---------------------------------------------------------------------------
# Schema: required keys and accepted values
# ---------------------------------------------------------------------------

# These are the keys we look at. Anything else is ignored. ``Pydantic``-
# style validation is overkill here; we lean on the dataclass types.

_REQUIRED_INVALID_RECORD_KEYS: tuple[str, ...] = (
    "drop_missing_invoice_no",
    "drop_missing_customer_id",
    "drop_missing_description",
    "drop_unparseable_invoice_date",
    "drop_zero_quantity",
    "drop_non_positive_unit_price",
    "flag_cancellations",
    "flag_returns",
    "cancellation_prefix",
)

_REQUIRED_TOP_LEVEL_KEYS: tuple[str, ...] = (
    "missing_strategy",
    "missing_columns",
    "duplicate_subset",
    "duplicate_keep",
    "outlier_action",
    "outlier_method",
    "outlier_columns",
    "outlier_iqr_multiplier",
    "outlier_zscore_threshold",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def find_default_preprocessing_config_path() -> Path:
    """Return the canonical path to ``configs/preprocessing.yaml``.

    Returns
    -------
    pathlib.Path
        Absolute path to the default preprocessing configuration file.
    """
    return DEFAULT_PREPROCESSING_CONFIG_PATH


def resolve_preprocessing_config_path(
    explicit: Path | None = None,
    *,
    search_paths: tuple[Path, ...] = (DEFAULT_PREPROCESSING_CONFIG_PATH,),
) -> Path | None:
    """Pick the first existing preprocessing config path.

    Parameters
    ----------
    explicit : pathlib.Path, optional
        If provided, this path is always returned (the caller has made
        an explicit decision). The path is **not** required to exist;
        the caller is expected to handle ``FileNotFoundError`` to give a
        clear error message.
    search_paths : tuple[pathlib.Path, ...]
        Ordered list of fallback paths. The first existing path is
        returned. If none exist, returns ``None``.

    Returns
    -------
    pathlib.Path or None
        Resolved path or ``None`` if neither ``explicit`` nor any
        fallback exists.
    """
    if explicit is not None:
        return explicit
    for p in search_paths:
        if p.exists():
            return p
    return None


def _read_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file as a nested dict. Raises typed errors for IO / parse failures."""
    if not path.exists():
        raise PreprocessingConfigError(f"Preprocessing config file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as exc:  # type: ignore[misc]
        raise PreprocessingConfigError(f"Failed to parse YAML at {path}: {exc}") from exc
    if data is None:
        raise PreprocessingConfigError(f"Preprocessing config file {path} is empty.")
    if not isinstance(data, dict):
        raise PreprocessingConfigError(
            f"Preprocessing config file {path} must be a YAML mapping; got {type(data).__name__}."
        )
    return data


def _require(
    container: dict[str, Any],
    key: str,
    *,
    container_name: str,
) -> Any:
    """Look up `key` in `container`; raise if missing."""
    if key not in container:
        raise PreprocessingConfigError(
            f"Missing required key {key!r} under {container_name!r} in preprocessing config."
        )
    return container[key]


def _require_bool(container: dict[str, Any], key: str, *, container_name: str) -> bool:
    """Look up `key`, expecting a bool. Type-errors with a clear message."""
    value = _require(container, key, container_name=container_name)
    if not isinstance(value, bool):
        raise PreprocessingConfigError(
            f"Expected {key!r} under {container_name!r} to be a boolean; "
            f"got {type(value).__name__}={value!r}."
        )
    return value


def _require_str(container: dict[str, Any], key: str, *, container_name: str) -> str:
    """Look up `key`, expecting a string."""
    value = _require(container, key, container_name=container_name)
    if not isinstance(value, str):
        raise PreprocessingConfigError(
            f"Expected {key!r} under {container_name!r} to be a string; "
            f"got {type(value).__name__}={value!r}."
        )
    return value


def _require_number(container: dict[str, Any], key: str, *, container_name: str) -> float:
    """Look up `key`, expecting an int or float."""
    value = _require(container, key, container_name=container_name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PreprocessingConfigError(
            f"Expected {key!r} under {container_name!r} to be a number; "
            f"got {type(value).__name__}={value!r}."
        )
    return float(value)


def _optional_number(
    container: dict[str, Any],
    key: str,
    *,
    container_name: str,
    default: float,
) -> float:
    if key not in container:
        return default
    return _require_number(container, key, container_name=container_name)


def _require_list(container: dict[str, Any], key: str, *, container_name: str) -> list[Any]:
    """Look up `key`, expecting a list."""
    value = _require(container, key, container_name=container_name)
    if not isinstance(value, list):
        raise PreprocessingConfigError(
            f"Expected {key!r} under {container_name!r} to be a list; "
            f"got {type(value).__name__}={value!r}."
        )
    return value


def _optional_list_of_str(
    container: dict[str, Any],
    key: str,
    *,
    container_name: str,
) -> list[str] | None:
    """Look up `key`, expecting either null or a list of strings."""
    if key not in container:
        return None
    value = container[key]
    if value is None:
        return None
    if not isinstance(value, list):
        raise PreprocessingConfigError(
            f"Expected {key!r} under {container_name!r} to be null or a list; "
            f"got {type(value).__name__}={value!r}."
        )
    for i, item in enumerate(value):
        if not isinstance(item, str):
            raise PreprocessingConfigError(
                f"Expected {key!r}[{i}] under {container_name!r} to be a string; "
                f"got {type(item).__name__}={item!r}."
            )
    return [str(x) for x in value]


def _require_list_of_str(container: dict[str, Any], key: str, *, container_name: str) -> list[str]:
    """Look up `key`, expecting a list of strings."""
    raw = _require_list(container, key, container_name=container_name)
    for i, item in enumerate(raw):
        if not isinstance(item, str):
            raise PreprocessingConfigError(
                f"Expected {key!r}[{i}] under {container_name!r} to be a string; "
                f"got {type(item).__name__}={item!r}."
            )
    return [str(x) for x in raw]


# ---------------------------------------------------------------------------
# Validation sets
# ---------------------------------------------------------------------------


VALID_MISSING_STRATEGIES: frozenset[str] = frozenset(
    {"drop", "impute_zero", "impute_median", "impute_mean", "keep"}
)
VALID_KEEP_MODES: frozenset[str] = frozenset({"first", "last", "none"})
VALID_OUTLIER_ACTIONS: frozenset[str] = frozenset({"clip", "remove", "flag", "none"})
VALID_OUTLIER_METHODS: frozenset[str] = frozenset({"iqr", "zscore", "winsorize"})


# ---------------------------------------------------------------------------
# Status annotation support
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConfigAnnotation:
    """A per-key annotation: status, source, rationale.

    Attributes
    ----------
    status : str
        ``"WORKING_ASSUMPTION"`` or ``"PENDING_MENTOR_REVIEW"``.
    source : str
        The location of the key in the YAML, e.g.
        ``"invalid_records.drop_missing_customer_id"``. Useful for
        error messages.
    rule_id : str or None
        CL-### rule ID if the key corresponds to a cleaning rule.
    rationale : str
        Short human description.
    """

    status: str
    source: str
    rule_id: str | None
    rationale: str

    def __post_init__(self) -> None:
        if self.status not in VALID_STATUSES:
            raise ValueError(f"Unknown status {self.status!r}; valid: {sorted(VALID_STATUSES)}.")


# Annotations that mirror the CL-### table in
# ``reports/fe02/cleaning_report.md``. They are not strictly required for
# pipeline execution; they exist so a downstream consumer (or mentor
# reviewer) can map a YAML key back to the rule ID without re-reading
# the cleaning report.
KEY_ANNOTATIONS: dict[str, ConfigAnnotation] = {
    "invalid_records.drop_missing_customer_id": ConfigAnnotation(
        status=STATUS_WORKING_ASSUMPTION,
        source="invalid_records.drop_missing_customer_id",
        rule_id="CL-01",
        rationale="CustomerID is the customer-level join key.",
    ),
    "invalid_records.drop_missing_description": ConfigAnnotation(
        status=STATUS_WORKING_ASSUMPTION,
        source="invalid_records.drop_missing_description",
        rule_id="CL-03",
        rationale="Small share (~0.27%); RFM does not use Description.",
    ),
    "invalid_records.drop_unparseable_invoice_date": ConfigAnnotation(
        status=STATUS_WORKING_ASSUMPTION,
        source="invalid_records.drop_unparseable_invoice_date",
        rule_id="CL-04",
        rationale="Unparseable dates break Recency computation.",
    ),
    "invalid_records.drop_zero_quantity": ConfigAnnotation(
        status=STATUS_WORKING_ASSUMPTION,
        source="invalid_records.drop_zero_quantity",
        rule_id="CL-05",
        rationale="Zero quantity has no transactional value.",
    ),
    "invalid_records.drop_non_positive_unit_price": ConfigAnnotation(
        status=STATUS_WORKING_ASSUMPTION,
        source="invalid_records.drop_non_positive_unit_price",
        rule_id="CL-07",
        rationale="Non-positive prices have no monetary value.",
    ),
    "invalid_records.flag_cancellations": ConfigAnnotation(
        status=STATUS_PENDING_MENTOR_REVIEW,
        source="invalid_records.flag_cancellations",
        rule_id="CL-08",
        rationale=(
            "C-prefixed cancellations are flagged, not dropped. "
            "Final treatment is decided by the RFM stage (FE-03)."
        ),
    ),
    "invalid_records.flag_returns": ConfigAnnotation(
        status=STATUS_PENDING_MENTOR_REVIEW,
        source="invalid_records.flag_returns",
        rule_id="CL-06",
        rationale=(
            "Negative Quantity is flagged, not dropped. "
            "Final treatment is decided by the RFM stage (FE-03)."
        ),
    ),
    "invalid_records.drop_missing_invoice_no": ConfigAnnotation(
        status=STATUS_WORKING_ASSUMPTION,
        source="invalid_records.drop_missing_invoice_no",
        rule_id="CL-10",
        rationale="Missing InvoiceNo breaks transaction grouping.",
    ),
    "duplicates.drop_duplicates_subset": ConfigAnnotation(
        status=STATUS_WORKING_ASSUMPTION,
        source="duplicates.subset_columns",
        rule_id="CL-09",
        rationale="Exact-row duplicates are pure data-quality issues.",
    ),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_preprocessing_config(
    path: Path | None = None,
    *,
    strict: bool = True,
) -> PipelineConfig:
    """Load ``configs/preprocessing.yaml`` and return a :class:`PipelineConfig`.

    Parameters
    ----------
    path : pathlib.Path, optional
        Explicit path to the YAML file. If ``None``, defaults to
        :data:`DEFAULT_PREPROCESSING_CONFIG_PATH`.
    strict : bool, default True
        If ``True``, every required key in ``_REQUIRED_TOP_LEVEL_KEYS``
        and ``_REQUIRED_INVALID_RECORD_KEYS`` must be present. If
        ``False``, missing keys fall back to the dataclass defaults —
        this mode is intended only for partial YAML overrides during
        experimentation; it is **not** the recommended path.

    Returns
    -------
    PipelineConfig
        Fully-typed dataclass instance ready to pass to
        :func:`customer_segmentation.preprocessing.cleaning.clean_transactions`.

    Raises
    ------
    PreprocessingConfigError
        If the YAML cannot be read, parsed, or does not contain the
        required keys (when ``strict=True``).
    """
    if path is None:
        path = DEFAULT_PREPROCESSING_CONFIG_PATH

    raw = _read_yaml(path)
    if "preprocessing" not in raw or not isinstance(raw["preprocessing"], dict):
        raise PreprocessingConfigError(
            f"Preprocessing config file {path} must have a top-level 'preprocessing' mapping."
        )
    pp: dict[str, Any] = raw["preprocessing"]

    # ------------------------------------------------------------------
    # Invalid-record rules
    # ------------------------------------------------------------------
    invalid_record_section = pp.get("invalid_records", {})
    if not isinstance(invalid_record_section, dict):
        raise PreprocessingConfigError(
            f"Expected 'invalid_records' under 'preprocessing' to be a mapping; "
            f"got {type(invalid_record_section).__name__}."
        )

    if strict:
        for required in _REQUIRED_INVALID_RECORD_KEYS:
            if required not in invalid_record_section:
                raise PreprocessingConfigError(
                    f"Missing required key 'invalid_records.{required}' in {path}."
                )

    invalid_rules_kwargs: dict[str, Any] = {}
    for key in _REQUIRED_INVALID_RECORD_KEYS:
        if key in invalid_record_section:
            if key == "cancellation_prefix":
                invalid_rules_kwargs[key] = _require_str(
                    invalid_record_section,
                    key,
                    container_name="invalid_records",
                )
            else:
                invalid_rules_kwargs[key] = _require_bool(
                    invalid_record_section,
                    key,
                    container_name="invalid_records",
                )
    invalid_rules = InvalidRecordRules(**invalid_rules_kwargs)

    # ------------------------------------------------------------------
    # Top-level pipeline parameters
    # ------------------------------------------------------------------
    def _maybe(label: str) -> Any:
        if label in pp:
            return pp[label]
        if strict:
            raise PreprocessingConfigError(
                f"Missing required key 'preprocessing.{label}' in {path}."
            )
        return None

    missing_strategy = _maybe("missing_strategy")
    if missing_strategy is not None:
        if not isinstance(missing_strategy, str):
            raise PreprocessingConfigError(
                f"'preprocessing.missing_strategy' must be a string; got {type(missing_strategy).__name__}."
            )
        if missing_strategy not in VALID_MISSING_STRATEGIES:
            raise PreprocessingConfigError(
                f"'preprocessing.missing_strategy'={missing_strategy!r} is not a "
                f"recognised strategy. Valid: {sorted(VALID_MISSING_STRATEGIES)}."
            )

    duplicate_keep = pp.get("duplicate_keep")
    if duplicate_keep is not None and duplicate_keep not in VALID_KEEP_MODES:
        raise PreprocessingConfigError(
            f"'preprocessing.duplicate_keep'={duplicate_keep!r} is not a "
            f"recognised keep mode. Valid: {sorted(VALID_KEEP_MODES)}."
        )

    outlier_action = pp.get("outlier_action")
    if outlier_action is not None and outlier_action not in VALID_OUTLIER_ACTIONS:
        raise PreprocessingConfigError(
            f"'preprocessing.outlier_action'={outlier_action!r} is not a "
            f"recognised action. Valid: {sorted(VALID_OUTLIER_ACTIONS)}."
        )

    outlier_method = pp.get("outlier_method")
    if outlier_method is not None and outlier_method not in VALID_OUTLIER_METHODS:
        raise PreprocessingConfigError(
            f"'preprocessing.outlier_method'={outlier_method!r} is not a "
            f"recognised method. Valid: {sorted(VALID_OUTLIER_METHODS)}."
        )

    duplicate_subset = _optional_list_of_str(pp, "duplicate_subset", container_name="preprocessing")
    missing_columns = (
        _require_list_of_str(pp, "missing_columns", container_name="preprocessing")
        if "missing_columns" in pp
        else []
    )
    outlier_columns = (
        _require_list_of_str(pp, "outlier_columns", container_name="preprocessing")
        if "outlier_columns" in pp
        else []
    )

    # Strict-mode requires the string fields; partial mode can skip them.
    def _str_or_none(key: str) -> str | None:
        if key not in pp:
            return None
        v = pp[key]
        if not isinstance(v, str):
            raise PreprocessingConfigError(
                f"'preprocessing.{key}' must be a string; got {type(v).__name__}."
            )
        return v

    missing_strategy = (
        missing_strategy if missing_strategy is not None else _str_or_none("missing_strategy")
    )
    duplicate_keep = (
        duplicate_keep if duplicate_keep is not None else _str_or_none("duplicate_keep")
    )
    outlier_action = (
        outlier_action if outlier_action is not None else _str_or_none("outlier_action")
    )
    outlier_method = (
        outlier_method if outlier_method is not None else _str_or_none("outlier_method")
    )

    outlier_iqr_multiplier = _optional_number(
        pp,
        "outlier_iqr_multiplier",
        container_name="preprocessing",
        default=1.5,
    )
    outlier_zscore_threshold = _optional_number(
        pp,
        "outlier_zscore_threshold",
        container_name="preprocessing",
        default=3.0,
    )

    cfg = PipelineConfig(
        invalid_rules=invalid_rules,
        missing_strategy=missing_strategy if missing_strategy is not None else "keep",
        missing_columns=list(missing_columns),
        duplicate_subset=duplicate_subset,
        duplicate_keep=duplicate_keep if duplicate_keep is not None else "first",
        outlier_action=outlier_action if outlier_action is not None else "none",
        outlier_method=outlier_method if outlier_method is not None else "iqr",
        outlier_columns=list(outlier_columns),
        outlier_iqr_multiplier=outlier_iqr_multiplier,
        outlier_zscore_threshold=outlier_zscore_threshold,
    )

    if not strict:
        # Partial mode: merge in the dataclass defaults for any field
        # the YAML did not specify. ``PipelineConfig`` already exposes
        # sensible defaults in its dataclass, so we simply replace only
        # the fields that were explicitly provided.
        default = PipelineConfig()
        new_kwargs: dict[str, Any] = {}
        for key in (
            "missing_strategy",
            "missing_columns",
            "duplicate_subset",
            "duplicate_keep",
            "outlier_action",
            "outlier_method",
            "outlier_columns",
        ):
            present_in_yaml = key in pp
            if present_in_yaml:
                new_kwargs[key] = getattr(cfg, key)
            else:
                new_kwargs[key] = getattr(default, key)
        cfg = PipelineConfig(
            invalid_rules=cfg.invalid_rules,
            **new_kwargs,
            outlier_iqr_multiplier=cfg.outlier_iqr_multiplier,
            outlier_zscore_threshold=cfg.outlier_zscore_threshold,
        )

    return cfg


# ---------------------------------------------------------------------------
# Serialisation (used by FE-02 cleaning_report.json)
# ---------------------------------------------------------------------------


def preprocessing_config_to_dict(config: PipelineConfig) -> dict[str, Any]:
    """Serialise a :class:`PipelineConfig` to a JSON/YAML-friendly dict.

    This is a convenience used by the FE-02 orchestrator so the resolved
    config can be embedded in ``reports/fe02/cleaning_run.json``. The
    shape mirrors the YAML so reviewers can diff the two directly.

    Parameters
    ----------
    config : PipelineConfig
        Config to serialise.

    Returns
    -------
    dict
        Nested dict whose top-level keys are ``invalid_rules`` and the
        flat keys listed in :class:`PipelineConfig`.
    """
    rules = config.invalid_rules
    return {
        "invalid_rules": {
            "drop_missing_customer_id": rules.drop_missing_customer_id,
            "drop_missing_invoice_no": rules.drop_missing_invoice_no,
            "drop_missing_description": rules.drop_missing_description,
            "drop_unparseable_invoice_date": rules.drop_unparseable_invoice_date,
            "drop_zero_quantity": rules.drop_zero_quantity,
            "drop_non_positive_unit_price": rules.drop_non_positive_unit_price,
            "flag_cancellations": rules.flag_cancellations,
            "flag_returns": rules.flag_returns,
            "cancellation_prefix": rules.cancellation_prefix,
        },
        "missing_strategy": config.missing_strategy,
        "missing_columns": list(config.missing_columns),
        "duplicate_subset": list(config.duplicate_subset) if config.duplicate_subset else None,
        "duplicate_keep": config.duplicate_keep,
        "outlier_action": config.outlier_action,
        "outlier_method": config.outlier_method,
        "outlier_columns": list(config.outlier_columns),
        "outlier_iqr_multiplier": config.outlier_iqr_multiplier,
        "outlier_zscore_threshold": config.outlier_zscore_threshold,
    }
