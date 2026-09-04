"""Grafik icin SMC yapı etiketleri."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from structure.core import broken_above, broken_below, last_pivots
from structure.smc import EventKind, SMCAnalysis, Trend


@dataclass
class ChartLabel:
    x: object
    y: float
    text: str
    color: str
    symbol: str = "circle"
    size: int = 10


def structure_chart_labels(
    df: pd.DataFrame,
    analysis: SMCAnalysis,
    *,
    internal_n: int,
    external_n: int,
    lookback: int = 120,
) -> list[ChartLabel]:
    labels: list[ChartLabel] = []
    if df is None or len(df) < 30:
        return labels
    sl = df.iloc[-lookback:]
    x_start = sl.index[0]

    for n, scope, color in (
        (internal_n, "INT", "#64b5f6"),
        (external_n, "EXT", "#ffb74d"),
    ):
        for kind, sym, ycol in (("high", "triangle-down", "high"), ("low", "triangle-up", "low")):
            pivots = last_pivots(df, kind, 6, n=n)
            for idx, price in pivots[-4:]:
                ts = df.index[idx]
                if ts < x_start:
                    continue
                labels.append(
                    ChartLabel(x=ts, y=price, text=scope, color=color, symbol=sym, size=8)
                )

    ext_highs = last_pivots(df, "high", 5, n=external_n)
    ext_lows = last_pivots(df, "low", 5, n=external_n)
    trend = analysis.trend

    if len(ext_highs) >= 2 and broken_above(df, ext_highs[-2][1]):
        ts = df.index[-1]
        ev = _event_label(analysis.external_event, trend, broke_high=True)
        if ev:
            labels.append(ChartLabel(x=ts, y=float(df["high"].iloc[-1]), text=ev, color="#00e676", symbol="star", size=12))
    if len(ext_lows) >= 2 and broken_below(df, ext_lows[-2][1]):
        ts = df.index[-1]
        ev = _event_label(analysis.external_event, trend, broke_high=False)
        if ev:
            labels.append(ChartLabel(x=ts, y=float(df["low"].iloc[-1]), text=ev, color="#ff5252", symbol="star", size=12))

    if analysis.inducement_bull:
        labels.append(ChartLabel(x=df.index[-1], y=float(df["low"].iloc[-1]), text="IND↑", color="#18ffff", symbol="diamond", size=11))
    if analysis.inducement_bear:
        labels.append(ChartLabel(x=df.index[-1], y=float(df["high"].iloc[-1]), text="IND↓", color="#ff4081", symbol="diamond", size=11))
    if analysis.turtle_soup_bull:
        labels.append(ChartLabel(x=df.index[-1], y=float(df["low"].iloc[-1]), text="TS↑", color="#69f0ae", symbol="x", size=10))
    if analysis.turtle_soup_bear:
        labels.append(ChartLabel(x=df.index[-1], y=float(df["high"].iloc[-1]), text="TS↓", color="#ff8a80", symbol="x", size=10))

    return labels


def _event_label(event: EventKind, trend: Trend, *, broke_high: bool) -> str:
    if event == "none":
        return "BOS" if broke_high else "BOS"
    mapping = {
        "bos_bull": "BOS↑",
        "bos_bear": "BOS↓",
        "choch_bull": "CHoCH↑",
        "choch_bear": "CHoCH↓",
    }
    return mapping.get(event, "BOS↑" if broke_high else "BOS↓")
