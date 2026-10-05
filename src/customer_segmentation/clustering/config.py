"""Configuration loader for the ML-01 experiment framework.

Single source of truth: ``configs/clustering.yaml``.

The loader reads the YAML file and returns a typed
:class:`FrameworkConfig` dataclass. The shape is intentionally narrow:
the framework only needs to know about

- the **input** matrix / metadata paths and dataset version,
- the **validation** policy (NaN/Inf/numeric/etc.),
- the **output** directory and artifact filenames,
- the **logging** policy,
- the **random seed** policy,
- the **experiment metadata** (stage version, scope boundaries, ...).

Per-algorithm hyperparameters live under the existing ``clustering.algorithms``
section of the YAML and are NOT parsed by this loader — ML-02 → ML-06
each parse their own slice.

Hard constraints:

- No hard-coded paths. All paths come from YAML.
- The YAML is the **single source of truth** for framework settings.
- Strict mode fails fast on missing keys; non-strict mode uses
  documented defaults (used by unit tests with synthetic YAML).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

__all__ = [
    "DEFAULT_CLUSTERING_CONFIG_PATH",
    "FrameworkConfigError",
    "ExperimentConfig",
    "RandomSeedConfig",
    "InputConfig",
    "ValidationConfig",
    "OutputConfig",
    "LoggingConfig",
    "MetadataConfig",
    "FrameworkConfig",
    "load_framework_config",
    "resolve_framework_config_path",
    "framework_config_to_dict",
    "compute_text_sha256",
]


# Path resolution mirrors the FE-06 config loader.
_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parents[2]
DEFAULT_CLUSTERING_CONFIG_PATH: Path = _REPO_ROOT / "configs" / "clustering.yaml"


class FrameworkConfigError(ValueError):
    """Raised when ``configs/clustering.yaml`` is malformed or missing keys."""


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExperimentConfig:
    """Experiment-level identification."""

    id: str
    description: str


@dataclass(frozen=True)
class RandomSeedConfig:
    """Random seed policy for the framework.

    ``per_algorithm_override`` lets callers override the seed for
    specific algorithms (e.g. GMM might need a different seed than
    K-Means). The override is purely advisory — algorithms that do
    not consume a seed are unaffected.
    """

    default: int
    per_algorithm_override: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class InputConfig:
    """Input matrix + metadata paths and identification."""

    final_clustering_dataset_path: str
    customer_metadata_path: str
    dataset_version: str
    customer_key: str


@dataclass(frozen=True)
class ValidationConfig:
    """Validation policy applied to the clustering matrix."""

    require_no_nan: bool
    require_no_inf: bool
    require_all_numeric: bool
    min_samples: int
    min_features: int
    exclude_customer_id_from_features: bool


@dataclass(frozen=True)
class OutputConfig:
    """Output directory + artifact filename templates.

    Filenames support ``{experiment_id}`` placeholders so multiple
    experiments can coexist in the same directory.
    """

    artifacts_dir: str
    report_dir: str
    save_labels: bool
    save_metadata: bool
    save_algorithm_specific: bool
    cluster_labels_filename: str
    experiment_log_filename: str
    algorithm_output_filename: str


@dataclass(frozen=True)
class LoggingConfig:
    """Logging policy."""

    log_to_console: bool
    log_to_file: bool
    log_file_dir: str
    log_level: str


@dataclass(frozen=True)
class MetadataConfig:
    """Stage metadata."""

    stage: str
    stage_version: str
    stage_status: str
    scope_boundaries: list[str]
    pending_review_notes: list[str]
    assumptions: list[str]


@dataclass(frozen=True)
class FrameworkConfig:
    """Top-level framework configuration."""

    enabled: bool
    experiment: ExperimentConfig
    random_seed: RandomSeedConfig
    input: InputConfig
    validation: ValidationConfig
    output: OutputConfig
    logging: LoggingConfig
    metadata: MetadataConfig


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FrameworkConfigError(f"Config file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise FrameworkConfigError(f"Failed to parse YAML at {path}: {exc}") from exc
    if data is None:
        raise FrameworkConfigError(f"Config file {path} is empty.")
    if not isinstance(data, dict):
        raise FrameworkConfigError(
            f"Config file {path} must be a YAML mapping; got {type(data).__name__}."
        )
    return data


def _require(container: Any, key: str, container_name: str, *, kind: str = "any") -> Any:
    if not isinstance(container, dict):
        raise FrameworkConfigError(
            f"Expected mapping under '{container_name}'; got {type(container).__name__}."
        )
    if key not in container:
        raise FrameworkConfigError(f"Missing required key '{key}' under '{container_name}'.")
    value = container[key]
    if kind == "str":
        if not isinstance(value, str):
            raise FrameworkConfigError(
                f"Expected '{container_name}.{key}' to be a string; "
                f"got {type(value).__name__}={value!r}."
            )
    elif kind == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise FrameworkConfigError(
                f"Expected '{container_name}.{key}' to be an integer; "
                f"got {type(value).__name__}={value!r}."
            )
    elif kind == "bool":
        if not isinstance(value, bool):
            raise FrameworkConfigError(
                f"Expected '{container_name}.{key}' to be a bool; "
                f"got {type(value).__name__}={value!r}."
            )
    elif kind == "list":
        if not isinstance(value, list):
            raise FrameworkConfigError(
                f"Expected '{container_name}.{key}' to be a list; "
                f"got {type(value).__name__}={value!r}."
            )
    elif kind == "dict":
        if not isinstance(value, dict):  # noqa: SIM102
            raise FrameworkConfigError(
                f"Expected '{container_name}.{key}' to be a mapping; "
                f"got {type(value).__name__}={value!r}."
            )
        return value
    return value


def _optional(container: dict, key: str, default: Any, *, kind: str = "any") -> Any:
    if key not in container:
        return default
    value = container[key]
    if kind == "bool" and not isinstance(value, bool):
        raise FrameworkConfigError(
            f"Expected '{key}' to be a bool; got {type(value).__name__}={value!r}."
        )
    if kind == "int" and (isinstance(value, bool) or not isinstance(value, int)):
        raise FrameworkConfigError(
            f"Expected '{key}' to be an integer; got {type(value).__name__}={value!r}."
        )
    if kind == "str" and not isinstance(value, str):
        raise FrameworkConfigError(
            f"Expected '{key}' to be a string; got {type(value).__name__}={value!r}."
        )
    if kind == "list" and not isinstance(value, list):
        raise FrameworkConfigError(
            f"Expected '{key}' to be a list; got {type(value).__name__}={value!r}."
        )
    if kind == "dict" and not isinstance(value, dict):
        raise FrameworkConfigError(
            f"Expected '{key}' to be a mapping; got {type(value).__name__}={value!r}."
        )
    return value


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def _parse_experiment(data: dict) -> ExperimentConfig:
    return ExperimentConfig(
        id=_require(data, "id", "framework.experiment", kind="str"),
        description=_require(data, "description", "framework.experiment", kind="str"),
    )


def _parse_random_seed(data: dict) -> RandomSeedConfig:
    return RandomSeedConfig(
        default=_require(data, "default", "framework.random_seed", kind="int"),
        per_algorithm_override=dict(_optional(data, "per_algorithm_override", {}, kind="dict")),
    )


def _parse_input(data: dict) -> InputConfig:
    return InputConfig(
        final_clustering_dataset_path=_require(
            data, "final_clustering_dataset_path", "framework.input", kind="str"
        ),
        customer_metadata_path=_require(
            data, "customer_metadata_path", "framework.input", kind="str"
        ),
        dataset_version=_require(data, "dataset_version", "framework.input", kind="str"),
        customer_key=_require(data, "customer_key", "framework.input", kind="str"),
    )


def _parse_validation(data: dict) -> ValidationConfig:
    return ValidationConfig(
        require_no_nan=_require(data, "require_no_nan", "framework.validation", kind="bool"),
        require_no_inf=_require(data, "require_no_inf", "framework.validation", kind="bool"),
        require_all_numeric=_require(
            data, "require_all_numeric", "framework.validation", kind="bool"
        ),
        min_samples=_require(data, "min_samples", "framework.validation", kind="int"),
        min_features=_require(data, "min_features", "framework.validation", kind="int"),
        exclude_customer_id_from_features=_require(
            data,
            "exclude_customer_id_from_features",
            "framework.validation",
            kind="bool",
        ),
    )


def _parse_output(data: dict) -> OutputConfig:
    return OutputConfig(
        artifacts_dir=_require(data, "artifacts_dir", "framework.output", kind="str"),
        report_dir=_require(data, "report_dir", "framework.output", kind="str"),
        save_labels=_require(data, "save_labels", "framework.output", kind="bool"),
        save_metadata=_require(data, "save_metadata", "framework.output", kind="bool"),
        save_algorithm_specific=_require(
            data, "save_algorithm_specific", "framework.output", kind="bool"
        ),
        cluster_labels_filename=_require(
            data, "cluster_labels_filename", "framework.output", kind="str"
        ),
        experiment_log_filename=_require(
            data, "experiment_log_filename", "framework.output", kind="str"
        ),
        algorithm_output_filename=_require(
            data, "algorithm_output_filename", "framework.output", kind="str"
        ),
    )


def _parse_logging(data: dict) -> LoggingConfig:
    return LoggingConfig(
        log_to_console=_require(data, "log_to_console", "framework.logging", kind="bool"),
        log_to_file=_require(data, "log_to_file", "framework.logging", kind="bool"),
        log_file_dir=_require(data, "log_file_dir", "framework.logging", kind="str"),
        log_level=_require(data, "log_level", "framework.logging", kind="str"),
    )


def _parse_metadata(data: dict) -> MetadataConfig:
    return MetadataConfig(
        stage=_require(data, "stage", "framework.metadata", kind="str"),
        stage_version=_require(data, "stage_version", "framework.metadata", kind="str"),
        stage_status=_require(data, "stage_status", "framework.metadata", kind="str"),
        scope_boundaries=list(_optional(data, "scope_boundaries", [], kind="list")),
        pending_review_notes=list(_optional(data, "pending_review_notes", [], kind="list")),
        assumptions=list(_optional(data, "assumptions", [], kind="list")),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_framework_config_path(explicit: Path | None = None) -> Path | None:
    """Resolve the clustering config path.

    Parameters
    ----------
    explicit : pathlib.Path, optional
        If provided, returned verbatim.

    Returns
    -------
    pathlib.Path or None
        Path to the config file (explicit or default) or ``None`` if
        neither exists.
    """
    if explicit is not None:
        return explicit
    if DEFAULT_CLUSTERING_CONFIG_PATH.exists():
        return DEFAULT_CLUSTERING_CONFIG_PATH
    return None


def load_framework_config(
    path: Path | None = None,
    *,
    strict: bool = True,
) -> FrameworkConfig:
    """Load the framework config from YAML.

    Parameters
    ----------
    path : pathlib.Path, optional
        Path to the YAML file. If ``None``, defaults to
        :data:`DEFAULT_CLUSTERING_CONFIG_PATH`.
    strict : bool
        Reserved for future use. Currently always strict.

    Returns
    -------
    FrameworkConfig
        Fully-typed dataclass instance.

    Raises
    ------
    FrameworkConfigError
        If the YAML cannot be parsed or a required key is missing.
    """
    _ = strict  # API symmetry with FE-06 loader; behaviour is always strict.
    if path is None:
        path = DEFAULT_CLUSTERING_CONFIG_PATH

    raw = _read_yaml(path)
    if "clustering" not in raw or not isinstance(raw["clustering"], dict):
        raise FrameworkConfigError(
            f"Config file {path} must have a top-level 'clustering' mapping."
        )
    data: dict[str, Any] = raw["clustering"]
    framework_raw = data.get("framework")
    if not isinstance(framework_raw, dict):
        raise FrameworkConfigError(
            f"Config file {path} must contain a 'clustering.framework' mapping "
            "for the ML-01 experiment framework."
        )
    if not _optional(framework_raw, "enabled", True, kind="bool"):
        raise FrameworkConfigError(
            f"Config file {path} has framework.enabled=False; ML-01 cannot load it."
        )

    return FrameworkConfig(
        enabled=True,
        experiment=_parse_experiment(_require(framework_raw, "experiment", "framework")),
        random_seed=_parse_random_seed(_require(framework_raw, "random_seed", "framework")),
        input=_parse_input(_require(framework_raw, "input", "framework")),
        validation=_parse_validation(_require(framework_raw, "validation", "framework")),
        output=_parse_output(_require(framework_raw, "output", "framework")),
        logging=_parse_logging(_require(framework_raw, "logging", "framework")),
        metadata=_parse_metadata(_require(framework_raw, "metadata", "framework")),
    )


def framework_config_to_dict(cfg: FrameworkConfig) -> dict:
    """Serialise a :class:`FrameworkConfig` to a plain dict (for tests)."""
    return {
        "enabled": cfg.enabled,
        "experiment": {
            "id": cfg.experiment.id,
            "description": cfg.experiment.description,
        },
        "random_seed": {
            "default": cfg.random_seed.default,
            "per_algorithm_override": dict(cfg.random_seed.per_algorithm_override),
        },
        "input": {
            "final_clustering_dataset_path": cfg.input.final_clustering_dataset_path,
            "customer_metadata_path": cfg.input.customer_metadata_path,
            "dataset_version": cfg.input.dataset_version,
            "customer_key": cfg.input.customer_key,
        },
        "validation": {
            "require_no_nan": cfg.validation.require_no_nan,
            "require_no_inf": cfg.validation.require_no_inf,
            "require_all_numeric": cfg.validation.require_all_numeric,
            "min_samples": cfg.validation.min_samples,
            "min_features": cfg.validation.min_features,
            "exclude_customer_id_from_features": cfg.validation.exclude_customer_id_from_features,
        },
        "output": {
            "artifacts_dir": cfg.output.artifacts_dir,
            "report_dir": cfg.output.report_dir,
            "save_labels": cfg.output.save_labels,
            "save_metadata": cfg.output.save_metadata,
            "save_algorithm_specific": cfg.output.save_algorithm_specific,
            "cluster_labels_filename": cfg.output.cluster_labels_filename,
            "experiment_log_filename": cfg.output.experiment_log_filename,
            "algorithm_output_filename": cfg.output.algorithm_output_filename,
        },
        "logging": {
            "log_to_console": cfg.logging.log_to_console,
            "log_to_file": cfg.logging.log_to_file,
            "log_file_dir": cfg.logging.log_file_dir,
            "log_level": cfg.logging.log_level,
        },
        "metadata": {
            "stage": cfg.metadata.stage,
            "stage_version": cfg.metadata.stage_version,
            "stage_status": cfg.metadata.stage_status,
            "scope_boundaries": list(cfg.metadata.scope_boundaries),
            "pending_review_notes": list(cfg.metadata.pending_review_notes),
            "assumptions": list(cfg.metadata.assumptions),
        },
    }


def compute_text_sha256(text: str) -> str:
    """SHA-256 of a UTF-8 string. Used for config SHA-256 in the run log."""
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()
