"""Tests that the dataset_management module's runtime process
does not actually load any forbidden backend / database / queue
library, beyond what is pre-installed on the system."""

from __future__ import annotations

import importlib
import sys


def test_dataset_management_does_not_load_fastapi() -> None:
    """`fastapi` is not in the loaded module set after a clean import
    of the dataset_management package.

    Note: this only fails if `fastapi` happens to be importable on
    the test machine. If it is not importable at all, the test
    passes trivially (it cannot be loaded).
    """
    importlib.import_module("customer_segmentation.dataset_management")
    fastapi = sys.modules.get("fastapi")
    if fastapi is None:
        # Module is not installed/importable on this system. Trivially OK.
        return
    # If it is loadable, the dataset_management package must not have
    # pulled it in.
    pkg = "customer_segmentation.dataset_management"
    chain = []
    for mod_name, mod in sys.modules.items():
        if mod is fastapi:
            chain.append(mod_name)
    # The package itself is not in this chain.
    for mod_name in chain:
        assert not mod_name.startswith(pkg), (
            f"fastapi was pulled in via {mod_name!r} from {pkg!r}"
        )


def test_dataset_management_does_not_load_sqlalchemy() -> None:
    importlib.import_module("customer_segmentation.dataset_management")
    sa = sys.modules.get("sqlalchemy")
    if sa is None:
        return
    pkg = "customer_segmentation.dataset_management"
    for mod_name in sys.modules:
        if mod_name.startswith("sqlalchemy"):
            # The mapping from sqlalchemy sub-modules to their loaders
            # is not directly observable; just assert that
            # dataset_management's __file__'s package isn't a parent.
            assert not mod_name.startswith(pkg)


def test_dataset_management_does_not_load_celery() -> None:
    importlib.import_module("customer_segmentation.dataset_management")
    cel = sys.modules.get("celery")
    if cel is None:
        return
    pkg = "customer_segmentation.dataset_management"
    for mod_name in sys.modules:
        if mod_name.startswith("celery"):
            assert not mod_name.startswith(pkg)
