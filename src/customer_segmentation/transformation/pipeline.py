"""End-to-end sklearn `Pipeline` for feature transformation.

TODO
----
- Implement `build_transformation_pipeline(config) -> sklearn.pipeline.Pipeline`.
- Combine skewness correction + scaling + (optional) feature selection.
"""

from __future__ import annotations

from typing import Any

__all__: list[str] = []


def build_transformation_pipeline(config: dict | None = None) -> Any:
    """Build a sklearn `Pipeline` for the feature transformation stage.

    Parameters
    ----------
    config : dict or None
        Transformation configuration. ``None`` uses documented defaults.

    Returns
    -------
    sklearn.pipeline.Pipeline
        Configured but unfitted pipeline.

    Notes
    -----
    Placeholder. The pipeline is constructed from `transform.skewness`
    and `transform.scaling` once they are implemented.
    """
    # TODO: implement pipeline assembly.
    raise NotImplementedError("build_transformation_pipeline is not implemented yet.")
