"""Plotly grafik PNG export (Gemini vision icin)."""
from __future__ import annotations

import plotly.graph_objects as go


def fig_to_png_bytes(fig: go.Figure, *, width: int = 1280, height: int = 720) -> bytes | None:
    try:
        return fig.to_image(format="png", width=width, height=height, scale=2)
    except Exception:
        return None
