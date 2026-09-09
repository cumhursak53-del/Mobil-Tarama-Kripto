"""PDF formasyon geometrisi — Bulkowski/klasik TA."""
from __future__ import annotations

from typing import Optional

import pandas as pd

from structure.core import last_pivots, volume_ok


def _rel(a: float, b: float, tol: float = 0.015) -> bool:
    return abs(a - b) / max(abs(b), 1e-12) <= tol


def detect_head_shoulders(df: pd.DataFrame) -> Optional[dict]:
    highs = last_pivots(df, "high", 6)
    lows = last_pivots(df, "low", 6)
    if len(highs) < 3 or len(lows) < 2:
        return None
    l, h, r = highs[-3], highs[-2], highs[-1]
    if not (h[1] > l[1] and h[1] > r[1] and _rel(l[1], r[1], 0.04)):
        return None
    shoulder_h = abs(h[1] - (l[1] + r[1]) / 2) / h[1]
    if shoulder_h > 0.08:
        return None
    troughs = [p for p in lows if l[0] < p[0] < r[0]]
    if len(troughs) < 2:
        return None
    neck = (troughs[0][1] + troughs[-1][1]) / 2.0
    height = h[1] - neck
    return {"type": "obo", "neck": neck, "invalidation": h[1], "target": neck - height, "side": "SELL"}


def detect_inverse_hs(df: pd.DataFrame) -> Optional[dict]:
    lows = last_pivots(df, "low", 6)
    highs = last_pivots(df, "high", 6)
    if len(lows) < 3 or len(highs) < 2:
        return None
    l, h, r = lows[-3], lows[-2], lows[-1]
    if not (h[1] < l[1] and h[1] < r[1] and _rel(l[1], r[1], 0.04)):
        return None
    peaks = [p for p in highs if l[0] < p[0] < r[0]]
    if len(peaks) < 2:
        return None
    neck = (peaks[0][1] + peaks[-1][1]) / 2.0
    height = neck - h[1]
    return {"type": "tobo", "neck": neck, "invalidation": h[1], "target": neck + height, "side": "BUY"}


def detect_double_bottom(df: pd.DataFrame) -> Optional[dict]:
    lows = last_pivots(df, "low", 5)
    highs = last_pivots(df, "high", 5)
    if len(lows) < 2 or len(highs) < 1:
        return None
    a, b = lows[-2], lows[-1]
    if not _rel(a[1], b[1], 0.012) or b[0] - a[0] < 8:
        return None
    row_b = df.iloc[b[0]]
    body = abs(float(row_b["close"]) - float(row_b["open"]))
    lower_wick = min(float(row_b["open"]), float(row_b["close"])) - float(row_b["low"])
    if body > 0 and lower_wick < body * 0.45:
        return None
    neck_cands = [p for p in highs if a[0] < p[0] < b[0]]
    if not neck_cands:
        return None
    neck = max(neck_cands, key=lambda x: x[1])[1]
    return {
        "type": "double_bottom",
        "neck": neck,
        "invalidation": min(a[1], b[1]) * 0.995,
        "target": neck + (neck - min(a[1], b[1])),
        "side": "BUY",
    }


def detect_double_top(df: pd.DataFrame) -> Optional[dict]:
    highs = last_pivots(df, "high", 5)
    lows = last_pivots(df, "low", 5)
    if len(highs) < 2 or len(lows) < 1:
        return None
    a, b = highs[-2], highs[-1]
    if not _rel(a[1], b[1], 0.012) or b[0] - a[0] < 8:
        return None
    row_b = df.iloc[b[0]]
    body = abs(float(row_b["close"]) - float(row_b["open"]))
    upper_wick = float(row_b["high"]) - max(float(row_b["open"]), float(row_b["close"]))
    if body > 0 and upper_wick < body * 0.45:
        return None
    neck_cands = [p for p in lows if a[0] < p[0] < b[0]]
    if not neck_cands:
        return None
    neck = min(neck_cands, key=lambda x: x[1])[1]
    return {
        "type": "double_top",
        "neck": neck,
        "invalidation": max(a[1], b[1]) * 1.005,
        "target": neck - (max(a[1], b[1]) - neck),
        "side": "SELL",
    }


def detect_rectangle(df: pd.DataFrame, min_touches: int = 4) -> Optional[dict]:
    highs = last_pivots(df, "high", 8)
    lows = last_pivots(df, "low", 8)
    if len(highs) < 2 or len(lows) < 2:
        return None
    top = sum(p[1] for p in highs[-2:]) / 2.0
    bot = sum(p[1] for p in lows[-2:]) / 2.0
    if not _rel(highs[-1][1], highs[-2][1], 0.012) or not _rel(lows[-1][1], lows[-2][1], 0.012):
        return None
    height = top - bot
    if height / bot < 0.015:
        return None
    touches = sum(1 for p in highs[-4:] if _rel(p[1], top, 0.015)) + sum(1 for p in lows[-4:] if _rel(p[1], bot, 0.015))
    if touches < min_touches:
        return None
    return {"type": "rectangle", "top": top, "bot": bot, "height": height}


def detect_flag(df: pd.DataFrame, atr_mult: float = 2.0) -> Optional[dict]:
    if len(df) < 30 or "atr" not in df.columns:
        return None
    atr = float(df["atr"].iloc[-1])
    for pole_len in (5, 6, 7, 8):
        if len(df) < pole_len + 8:
            continue
        pole = df["close"].iloc[-8 - pole_len:-8]
        cons = df.iloc[-8:]
        pole_move = abs(float(pole.iloc[-1]) - float(pole.iloc[0]))
        if pole_move < atr * atr_mult:
            continue
        cons_w = (float(cons["high"].max()) - float(cons["low"].min())) / float(cons["close"].iloc[-1])
        if cons_w > 0.04 or cons_w > pole_move / float(pole.iloc[0]) * 0.5:
            continue
        direction = "up" if float(pole.iloc[-1]) > float(pole.iloc[0]) else "down"
        return {
            "type": "flag",
            "direction": direction,
            "pole_move": pole_move,
            "cons_high": float(cons["high"].max()),
            "cons_low": float(cons["low"].min()),
        }
    return None
