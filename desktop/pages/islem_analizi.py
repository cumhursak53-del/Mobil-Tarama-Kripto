from __future__ import annotations

import flet as ft

from desktop.components.cards import section_header
from desktop.components.sections import panel_section
from desktop.components.tables import dataframe_table
from shared.ui_data import (
    load_data,
    post_exit_analysis_rows,
    post_exit_watch_rows,
    signal_outcome_rows,
    signal_watch_rows,
)


def build() -> ft.Control:
    data = load_data()
    return ft.Column(
        [
            section_header("Analiz Merkezi", "Sinyal ve islem 24s izleme + otomatik analiz"),
            panel_section(
                "Sinyal analizi",
                dataframe_table(
                    signal_outcome_rows(data.get("signal_outcome_log")),
                    max_rows=None,
                    height=480,
                    empty_title="Sinyal analizi yok",
                ),
            ),
            panel_section(
                "Aktif sinyal izleme",
                dataframe_table(
                    signal_watch_rows(data.get("signal_watchlist")),
                    height=220,
                    empty_title="Izlenen sinyal yok",
                ),
            ),
            panel_section(
                "Islem analizi",
                dataframe_table(post_exit_analysis_rows(data.get("post_exit_log")), height=280, empty_title="Analiz kaydi yok"),
            ),
            panel_section(
                "Aktif islem izleme",
                dataframe_table(post_exit_watch_rows(data.get("post_exit_watchlist")), height=220, empty_title="Izlenen islem yok"),
            ),
        ],
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )
