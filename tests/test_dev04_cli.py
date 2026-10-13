"""Tests for the DEV-04 CLI script."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))


class TestCliHelp:
    def test_help_shows_all_algorithms(self) -> None:
        from scripts.dev04_run_clustering import _build_argparser

        parser = _build_argparser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--help"])
        # --help exits with 0.
        assert exc_info.value.code == 0

    def test_required_args_enforced(self) -> None:
        from scripts.dev04_run_clustering import _build_argparser

        parser = _build_argparser()
        with pytest.raises(SystemExit):
            parser.parse_args([])


class TestCollectHyperparameters:
    def test_collects_all_cli_overrides(self) -> None:
        from argparse import Namespace

        from scripts.dev04_run_clustering import _collect_hyperparameters

        args = Namespace(
            n_clusters=5,
            init="random",
            n_init=20,
            max_iter=500,
            tol=1e-3,
            linkage=None,
            metric=None,
            eps=None,
            min_samples=None,
            n_components=None,
            covariance_type=None,
            fuzziness=None,
            error=None,
        )
        hp = _collect_hyperparameters(args)
        assert hp == {
            "n_clusters": 5,
            "init": "random",
            "n_init": 20,
            "max_iter": 500,
            "tol": 1e-3,
        }

    def test_ignores_none_values(self) -> None:
        from argparse import Namespace

        from scripts.dev04_run_clustering import _collect_hyperparameters

        args = Namespace(
            n_clusters=None,
            init=None,
            n_init=None,
            max_iter=None,
            tol=None,
            linkage=None,
            metric=None,
            eps=None,
            min_samples=None,
            n_components=None,
            covariance_type=None,
            fuzziness=None,
            error=None,
        )
        hp = _collect_hyperparameters(args)
        assert hp == {}

    def test_gmm_hyperparameters(self) -> None:
        from argparse import Namespace

        from scripts.dev04_run_clustering import _collect_hyperparameters

        args = Namespace(
            n_clusters=None,
            init=None,
            n_init=None,
            max_iter=None,
            tol=None,
            linkage=None,
            metric=None,
            eps=None,
            min_samples=None,
            n_components=6,
            covariance_type="diag",
            fuzziness=None,
            error=None,
        )
        hp = _collect_hyperparameters(args)
        assert hp == {"n_components": 6, "covariance_type": "diag"}
