"""Pytest config for the GIS visualization demo dataset tests.

Inserts the project root and the ``scripts/`` directory into ``sys.path`` so
that the future generator (``scripts/generate_demo_data.py``) and any
shared utilities (``scripts/gis_common.py``) become importable from tests
once they exist.

Project root resolution:
    tests/conftest.py  ->  parents[0] = tests/
                          parents[1] = project root (e.g. .../GIS可视化)
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

for _p in (PROJECT_ROOT, SCRIPTS_DIR):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)
