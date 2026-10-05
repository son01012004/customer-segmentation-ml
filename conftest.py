"""Repository-level pytest configuration.

Ensures the ``src/`` directory is on ``sys.path`` so tests can import
``customer_segmentation.*`` without requiring the caller to set
``PYTHONPATH=src`` manually.

This mirrors the CI configuration in ``.github/workflows/tests.yml``
(which sets ``PYTHONPATH: src``).
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent
_SRC = _REPO_ROOT / "src"

if _SRC.exists() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
