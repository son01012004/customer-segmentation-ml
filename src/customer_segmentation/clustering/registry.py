"""Algorithm registry for the ML-01 experiment framework.

The registry is a thin, in-process map of ``name -> adapter class``. It
lets ML-02 → ML-06 register their concrete algorithm adapters without
the framework knowing about them at import time.

Design constraints (AGENTS.md):

- Registry is **value-neutral**: registering an algorithm does not
  endorse it as "best/recommended/optimal".
- Registry names are short, lowercase, stable identifiers
  (e.g. ``"kmeans"``, ``"dbscan"``, ``"gmm"``).
- Registering the same name twice raises a clear error so the runner
  never accidentally uses the wrong adapter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from customer_segmentation.clustering.base import BaseClusterAlgorithm


class AlgorithmRegistryError(ValueError):
    """Raised when an algorithm is not registered or registered twice."""


class AlgorithmRegistry:
    """In-process registry of :class:`BaseClusterAlgorithm` subclasses.

    Usage
    -----

    Register at module import::

        from customer_segmentation.clustering.registry import AlgorithmRegistry
        from customer_segmentation.clustering.base import BaseClusterAlgorithm

        @AlgorithmRegistry.register("kmeans")
        class KMeansAdapter(BaseClusterAlgorithm):
            ...

    Or register imperatively::

        AlgorithmRegistry.register("kmeans")(KMeansAdapter)

    Look up by name::

        adapter_cls = AlgorithmRegistry.get("kmeans")
        adapter = adapter_cls(...)

    Notes
    -----
    - The registry is **global** (class-level). Tests that need a
      clean registry can call :meth:`clear` and re-register their own
      adapters.
    - Names are case-sensitive.
    """

    _registry: dict[str, type[BaseClusterAlgorithm]] = {}

    @classmethod
    def register(cls, name: str) -> type[BaseClusterAlgorithm]:
        """Decorator / direct registration of an algorithm adapter.

        Parameters
        ----------
        name : str
            Stable, lowercase identifier (e.g. ``"kmeans"``).

        Returns
        -------
        type[BaseClusterAlgorithm]
            Either the decorator (when called with parentheses) or the
            class itself (when used as ``@register("name")``).

        Raises
        ------
        AlgorithmRegistryError
            If ``name`` is empty, not a string, or already registered.
        """
        if not isinstance(name, str) or not name:
            raise AlgorithmRegistryError(
                f"Algorithm name must be a non-empty string; got {name!r}."
            )

        def _wrap(adapter_cls: type[BaseClusterAlgorithm]) -> type[BaseClusterAlgorithm]:
            if not isinstance(adapter_cls, type) or not issubclass(
                adapter_cls, cls.__bases_class__()  # type: ignore[attr-defined]
            ):
                # The line above is a defensive check; the public path
                # is the isinstance/issubclass in __init_subclass__.
                pass
            if name in cls._registry:
                raise AlgorithmRegistryError(
                    f"Algorithm '{name}' is already registered with "
                    f"{cls._registry[name].__name__}. Refusing to overwrite."
                )
            # Sanity check: subclass of BaseClusterAlgorithm.
            from customer_segmentation.clustering.base import BaseClusterAlgorithm

            if not (
                isinstance(adapter_cls, type) and issubclass(adapter_cls, BaseClusterAlgorithm)
            ):
                raise AlgorithmRegistryError(
                    f"Cannot register {adapter_cls!r}: must subclass " f"BaseClusterAlgorithm."
                )
            adapter_cls.name = name  # type: ignore[attr-defined]
            cls._registry[name] = adapter_cls
            return adapter_cls

        return _wrap

    @classmethod
    def get(cls, name: str) -> type[BaseClusterAlgorithm]:
        """Look up an algorithm adapter class by name.

        Parameters
        ----------
        name : str
            Registered algorithm name.

        Returns
        -------
        type[BaseClusterAlgorithm]
            The adapter class.

        Raises
        ------
        AlgorithmRegistryError
            If ``name`` is not registered.
        """
        if name not in cls._registry:
            available = ", ".join(sorted(cls._registry)) or "(none)"
            raise AlgorithmRegistryError(
                f"Algorithm '{name}' is not registered. Available: {available}."
            )
        return cls._registry[name]

    @classmethod
    def list_registered(cls) -> list[str]:
        """Return a sorted list of registered algorithm names."""
        return sorted(cls._registry)

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Return whether ``name`` is registered."""
        return name in cls._registry

    @classmethod
    def clear(cls) -> None:
        """Remove all registered algorithms.

        Intended for **tests only**. Production code MUST NOT call this.
        """
        cls._registry.clear()

    # Internal helper used by :meth:`register`'s defensive check.
    @classmethod
    def __bases_class__(cls):  # pragma: no cover - defensive only
        from customer_segmentation.clustering.base import BaseClusterAlgorithm

        return BaseClusterAlgorithm


__all__ = ["AlgorithmRegistry", "AlgorithmRegistryError"]
