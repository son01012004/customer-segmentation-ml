"""Feature scaling utilities.

TODO
----
- Implement `scale_features(df, method) -> (X_scaled, scaler)`.
- Methods: standard | robust | minmax | none.
- Return the fitted scaler so it can be applied to held-out data later.
"""

from __future__ import annotations

from typing import Literal

import pandas as pd

__all__: list[str] = []

ScalerKind = Literal["standard", "robust", "minmax", "none"]


def scale_features(
    df: pd.DataFrame,
    method: ScalerKind = "standard",
) -> tuple[pd.DataFrame, object]:
    """Scale numeric features using the requested scaler.

    Parameters
    ----------
    df : pandas.DataFrame
        Customer-level feature matrix.
    method : {"standard", "robust", "minmax", "none"}
        Scaler to use.

    Returns
    -------
    X_scaled : pandas.DataFrame
        Scaled feature matrix.
    scaler : object
        Fitted sklearn-compatible scaler (or ``None`` if ``method == "none"``).

    Notes
    -----
    Placeholder. Implementation will be added in the transformation stage.
    """
    # TODO: implement feature scaling.
    raise NotImplementedError("scale_features is not implemented yet.")
