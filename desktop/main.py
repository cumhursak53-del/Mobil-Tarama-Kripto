"""Krpito MTF masaustu giris noktasi (Flet)."""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("KRPITO_MODE", "desktop")

from engine.env_loader import bootstrap_env

bootstrap_env()

import flet as ft

from desktop.app_shell import KrpitoApp


def main(page: ft.Page) -> None:
    app = KrpitoApp(page)
    app.build()


if __name__ == "__main__":
    ft.run(main)
