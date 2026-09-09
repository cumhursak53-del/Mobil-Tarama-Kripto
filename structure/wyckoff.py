"""Wyckoff hacim imzalari — spring / upthrust."""
from __future__ import annotations

import pandas as pd

from structure.core import support_resistance, volume_ok


def wyckoff_spring(df: pd.DataFrame, lookback: int = 30) -> bool:
    """Accumulation spring: destek alti fitil, kapanis destek ustu, hacim spike."""
    if df is None or len(df) < lookback + 5:
        return False
    window = df.iloc[-lookback:]
    supports, _ = support_resistance(window.iloc[:-3])
    if not supports:
        return False
    sup = supports[-1]
    last = df.iloc[-1]
    prev = df.iloc[-2]
    low, close, vol = float(last["low"]), float(last["close"]), float(last["volume"])
    vol_sma = float(last.get("vol_sma") or df["volume"].iloc[-20:].mean())
    broke = low < sup * 0.997 and close > sup
    reclaim = float(prev["close"]) <= sup * 1.002
    vol_spike = vol > vol_sma * 1.15
    return broke and reclaim and vol_spike and volume_ok(df)


def wyckoff_upthrust(df: pd.DataFrame, lookback: int = 30) -> bool:
    """Distribution upthrust: direnc ustu fitil, kapanis altinda, hacim spike."""
    if df is None or len(df) < lookback + 5:
        return False
    window = df.iloc[-lookback:]
    _, resistances = support_resistance(window.iloc[:-3])
    if not resistances:
        return False
    res = resistances[-1]
    last = df.iloc[-1]
    prev = df.iloc[-2]
    high, close, vol = float(last["high"]), float(last["close"]), float(last["volume"])
    vol_sma = float(last.get("vol_sma") or df["volume"].iloc[-20:].mean())
    broke = high > res * 1.003 and close < res
    reject = float(prev["close"]) >= res * 0.998
    vol_spike = vol > vol_sma * 1.15
    return broke and reject and vol_spike and volume_ok(df)
