"""Render geriye donuk giris: python bot_engine.py -> MTF canli piyasa motoru."""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

from engine.config import SCAN_SYMBOLS
from engine.paper import run_paper

if __name__ == "__main__":
    n = int(os.environ.get("SCAN_SYMBOLS", str(SCAN_SYMBOLS)))
    run_paper(n)
