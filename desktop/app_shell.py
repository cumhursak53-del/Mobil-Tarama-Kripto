from __future__ import annotations

import asyncio
import os
import sys

import flet as ft

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from desktop.components.cards import status_chip
from desktop.pages.home import build as build_home
from desktop.pages.islem_analizi import build as build_islem
from desktop.pages.lab import build as build_lab
from desktop.pages.patlama import build as build_patlama
from desktop.pages.smc import build as build_smc
from desktop.pages.strateji import build as build_strateji
from desktop.services.engine_client import engine_reachable
from desktop.services.ollama_client import check_ollama
from desktop.theme import ACCENT, BG, GRADIENT, SURFACE, TEXT, TEXT_MUTED, apply_page_theme
from shared.ui_data import REFRESH_SEC_OPTIONS, engine_status, load_data

NAV_ITEMS = [
    ("Dashboard", ft.Icons.DASHBOARD_OUTLINED, ft.Icons.DASHBOARD),
    ("Islem Analizi", ft.Icons.ANALYTICS_OUTLINED, ft.Icons.ANALYTICS),
    ("Patlama", ft.Icons.ROCKET_LAUNCH_OUTLINED, ft.Icons.ROCKET_LAUNCH),
    ("SMC", ft.Icons.CANDLESTICK_CHART_OUTLINED, ft.Icons.CANDLESTICK_CHART),
    ("Lab", ft.Icons.SCIENCE_OUTLINED, ft.Icons.SCIENCE),
    ("Strateji", ft.Icons.AUTO_AWESOME_OUTLINED, ft.Icons.AUTO_AWESOME),
]


class KrpitoApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.auto_refresh = True
        self.refresh_sec = 60
        self._nav_index = 0
        self._version = 0
        self.content_area = ft.Container(expand=True, padding=20)
        self.motor_chip = ft.Container()
        self.ollama_chip = ft.Container()
        self.caption = ft.Text("", size=11, color=TEXT_MUTED)

    def build(self) -> None:
        apply_page_theme(self.page)

        nav_destinations = [
            ft.NavigationRailDestination(icon=icon, selected_icon=sel, label=label)
            for label, icon, sel in NAV_ITEMS
        ]
        self.rail = ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=88,
            min_extended_width=180,
            bgcolor=SURFACE,
            indicator_color=f"{ACCENT}44",
            destinations=nav_destinations,
            on_change=self._on_nav,
        )

        refresh_dd = ft.Dropdown(
            value=str(self.refresh_sec),
            width=100,
            options=[ft.dropdown.Option(str(x)) for x in REFRESH_SEC_OPTIONS],
            on_select=self._on_refresh_interval,
        )
        auto_sw = ft.Switch(value=self.auto_refresh, on_change=self._on_auto_toggle, active_color=ACCENT)

        top_bar = ft.Container(
            content=ft.Row(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.CURRENCY_BITCOIN, color=ACCENT, size=28),
                            ft.Column(
                                [
                                    ft.Text("Krpito MTF", size=18, weight=ft.FontWeight.BOLD, color=TEXT),
                                    ft.Text("Local · Ollama · Paper Trading", size=11, color=TEXT_MUTED),
                                ],
                                spacing=0,
                            ),
                        ],
                        spacing=10,
                    ),
                    ft.Container(expand=True),
                    self.motor_chip,
                    self.ollama_chip,
                    ft.Row(
                        [
                            ft.Text("Otomatik", size=11, color=TEXT_MUTED),
                            auto_sw,
                            refresh_dd,
                            ft.IconButton(
                                icon=ft.Icons.REFRESH,
                                tooltip="Yenile",
                                icon_color=ACCENT,
                                on_click=self._manual_refresh,
                            ),
                        ],
                        spacing=4,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            gradient=GRADIENT,
            padding=ft.Padding.symmetric(horizontal=20, vertical=14),
        )

        self.page.add(
            ft.Column(
                [
                    top_bar,
                    ft.Row(
                        [
                            self.rail,
                            ft.VerticalDivider(width=1, color=ft.Colors.TRANSPARENT),
                            ft.Column(
                                [
                                    self.content_area,
                                    ft.Container(content=self.caption, padding=ft.Padding.only(left=20, bottom=8)),
                                ],
                                expand=True,
                            ),
                        ],
                        expand=True,
                    ),
                ],
                expand=True,
                spacing=0,
            )
        )
        self._render_page(0)
        self.page.run_task(self._refresh_loop)

    def _update_status(self) -> None:
        data = load_data(force_version=self._version)
        eng_label, eng_key, eng_desc = engine_status(data)
        motor_ok = engine_reachable() and eng_key == "ok"
        ollama_ok, ollama_msg, _ = check_ollama()
        self.motor_chip.content = status_chip(f"Motor: {eng_label}", ok=motor_ok)
        self.ollama_chip.content = status_chip("Ollama", ok=ollama_ok, detail=ollama_msg.split("(")[0].strip()[:20])
        self.caption.value = f"{eng_desc} · Son veri: {data.get('updated_at', '-')}"

    def _render_page(self, index: int) -> None:
        self._nav_index = index
        self._update_status()
        builders = [
            build_home,
            build_islem,
            build_patlama,
            lambda: build_smc(self.page),
            build_lab,
            build_strateji,
        ]
        self.content_area.content = builders[index]()
        self.page.update()

    def _on_nav(self, e: ft.ControlEvent) -> None:
        self._render_page(int(e.control.selected_index))

    def _on_auto_toggle(self, e: ft.ControlEvent) -> None:
        self.auto_refresh = bool(e.control.value)

    def _on_refresh_interval(self, e: ft.ControlEvent) -> None:
        try:
            self.refresh_sec = int(e.control.value)
        except (TypeError, ValueError):
            self.refresh_sec = 60

    def _manual_refresh(self, _e: ft.ControlEvent | None = None) -> None:
        self._version += 1
        self._render_page(self._nav_index)

    async def _refresh_loop(self) -> None:
        while True:
            await asyncio.sleep(max(5, self.refresh_sec))
            if self.auto_refresh:
                self._version += 1
                self._render_page(self._nav_index)
