from __future__ import annotations

import flet as ft
import pandas as pd

from desktop.components.cards import empty_state
from desktop.theme import ACCENT, BORDER, CARD, GREEN, RED, TEXT, TEXT_MUTED, border_all


def _cell_text(val, col_name: str) -> ft.Text:
    s = str(val)[:100]
    color = TEXT
    lower = col_name.lower()
    if "pnl" in lower or "roe" in lower:
        try:
            num = float(str(val).replace(",", "").replace("$", "").replace("+", ""))
            if num > 0:
                color = GREEN
            elif num < 0:
                color = RED
        except (TypeError, ValueError):
            pass
    if col_name in ("Gecti",) and s == "Evet":
        color = GREEN
    return ft.Text(s, size=11, color=color)


def dataframe_table(
    df: pd.DataFrame,
    *,
    max_rows: int | None = 150,
    height: int = 420,
    empty_title: str = "Kayit yok",
    empty_message: str = "Motor calisiyorsa birkaç dakika bekleyin veya local motoru baslatin.",
) -> ft.Control:
    if df is None or df.empty:
        return empty_state(empty_title, empty_message, icon=ft.Icons.TABLE_ROWS_OUTLINED)
    view = df if max_rows is None else df.head(max_rows)
    cols = [
        ft.DataColumn(ft.Text(str(c), size=12, weight=ft.FontWeight.BOLD, color=TEXT_MUTED))
        for c in view.columns
    ]
    rows = []
    for _, row in view.iterrows():
        cells = [
            ft.DataCell(_cell_text(v, str(c)))
            for c, v in zip(view.columns, row.tolist())
        ]
        rows.append(ft.DataRow(cells=cells))
    return ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(f"{len(view)} kayit", size=11, color=TEXT_MUTED),
                        ft.Text(
                            "Limit yok" if max_rows is None else f"Gosterilen max {max_rows}",
                            size=11,
                            color=TEXT_MUTED,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.DataTable(
                    columns=cols,
                    rows=rows,
                    heading_row_height=40,
                    data_row_min_height=44,
                    data_row_max_height=56,
                    border=border_all(BORDER),
                    heading_row_color=f"{ACCENT}22",
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
        ),
        height=height,
        border_radius=12,
        padding=8,
        bgcolor=CARD,
        border=border_all(BORDER),
    )
