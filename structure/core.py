"""Swing structure, S/R, trendlines, Fibonacci, market stages, candle patterns."""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from engine.config import NEAR_PCT, SWING_N
from engine.types import Stage


def swing_highs(high: pd.Series, n: int = SWING_N) -> pd.Series:
    win = high.rolling(2 * n + 1, center=True, min_periods=2 * n + 1).max()
    return (high == win) & high.notna()


def swing_lows(low: pd.Series, n: int = SWING_N) -> pd.Series:
    win = low.rolling(2 * n + 1, center=True, min_periods=2 * n + 1).min()
    return (low == win) & low.notna()


def last_pivots(df: pd.DataFrame, kind: str, count: int = 8, n: int = SWING_N) -> list[tuple[int, float]]:
    """Return chronological (iloc, price) pivots. Confirmed only (no forming bar)."""
    if kind == "high":
        mask = df["swing_high"] if "swing_high" in df.columns else swing_highs(df["high"], n)
        price = df["high"]
    else:
        mask = df["swing_low"] if "swing_low" in df.columns else swing_lows(df["low"], n)
        price = df["low"]
    idxs = np.flatnonzero(mask.to_numpy())
    # last confirmed swing needs n bars to the right; drop any in the last n bars
    cutoff = len(df) - n - 1
    idxs = idxs[idxs <= cutoff]
    out = [(int(i), float(price.iloc[i])) for i in idxs]
    return out[-count:]


def hh_hl(df: pd.DataFrame) -> tuple[bool, bool]:
    highs = last_pivots(df, "high", 3)
    lows = last_pivots(df, "low", 3)
    is_hh = len(highs) >= 2 and highs[-1][1] > highs[-2][1]
    is_hl = len(lows) >= 2 and lows[-1][1] > lows[-2][1]
    return is_hh, is_hl


def lh_ll(df: pd.DataFrame) -> tuple[bool, bool]:
    highs = last_pivots(df, "high", 3)
    lows = last_pivots(df, "low", 3)
    is_lh = len(highs) >= 2 and highs[-1][1] < highs[-2][1]
    is_ll = len(lows) >= 2 and lows[-1][1] < lows[-2][1]
    return is_lh, is_ll


def nearest_level(price: float, levels: list[float], pct: float = NEAR_PCT) -> Optional[float]:
    if not levels:
        return None
    best = min(levels, key=lambda x: abs(x - price) / price if price else 1e9)
    if price and abs(best - price) / price <= pct:
        return best
    return None


def support_resistance(df: pd.DataFrame, lookback: int = 80) -> tuple[list[float], list[float]]:
    sl = df.iloc[-lookback:] if len(df) > lookback else df
    lows = [p for _, p in last_pivots(sl, "low", 12)]
    highs = [p for _, p in last_pivots(sl, "high", 12)]
    return _cluster(lows), _cluster(highs)


def _cluster(levels: list[float], tol: float = 0.008) -> list[float]:
    if not levels:
        return []
    levels = sorted(levels)
    groups: list[list[float]] = [[levels[0]]]
    for x in levels[1:]:
        if abs(x - groups[-1][-1]) / groups[-1][-1] <= tol:
            groups[-1].append(x)
        else:
            groups.append([x])
    return [float(np.mean(g)) for g in groups]


def trendline_from_pivots(pivots: list[tuple[int, float]], at_index: int) -> Optional[float]:
    """Linear extrapolation of last 2–3 pivots to at_index."""
    if len(pivots) < 2:
        return None
    pts = pivots[-3:] if len(pivots) >= 3 else pivots[-2:]
    xs = np.array([p[0] for p in pts], dtype=float)
    ys = np.array([p[1] for p in pts], dtype=float)
    slope, intercept = np.polyfit(xs, ys, 1)
    return float(slope * at_index + intercept)


def fib_retracement(swing_low: float, swing_high: float, direction: str) -> dict[str, float]:
    """direction='up' means impulse was up; retrace from high toward low."""
    diff = swing_high - swing_low
    if diff <= 0:
        return {}
    ratios = (0.236, 0.382, 0.5, 0.618, 0.786)
    if direction == "up":
        return {str(r): swing_high - diff * r for r in ratios}
    return {str(r): swing_low + diff * r for r in ratios}


def last_impulse(df: pd.DataFrame) -> Optional[tuple[float, float, str]]:
    highs = last_pivots(df, "high", 4)
    lows = last_pivots(df, "low", 4)
    if not highs or not lows:
        return None
    last_h, last_l = highs[-1], lows[-1]
    if last_h[0] > last_l[0]:
        return last_l[1], last_h[1], "up"
    return last_l[1], last_h[1], "down"


def sma200_slope_up(df: pd.DataFrame, look: int = 20) -> Optional[bool]:
    if "sma200" not in df.columns or len(df) < 200 + look:
        return None
    a = float(df["sma200"].iloc[-1])
    b = float(df["sma200"].iloc[-1 - look])
    if np.isnan(a) or np.isnan(b):
        return None
    return a > b


def market_stage(daily: pd.DataFrame) -> Stage:
    if daily is None or len(daily) < 220 or "sma200" not in daily.columns:
        return Stage.UNKNOWN
    close = float(daily["close"].iloc[-1])
    sma = float(daily["sma200"].iloc[-1])
    if np.isnan(sma):
        return Stage.UNKNOWN
    slope = sma200_slope_up(daily, 20)
    is_hh, is_hl = hh_hl(daily)
    is_lh, is_ll = lh_ll(daily)
    flat = slope is None or abs(float(daily["sma200"].iloc[-1]) - float(daily["sma200"].iloc[-21])) / sma < 0.015
    if close > sma and slope and is_hh and is_hl:
        return Stage.ADVANCING
    if close < sma and slope is False and is_lh and is_ll:
        return Stage.DECLINING
    if flat and close > sma * 0.97:
        # long prior rally → distribution; long prior drop → accumulation
        past = daily["close"].iloc[-120] if len(daily) >= 120 else daily["close"].iloc[0]
        if close > float(past):
            return Stage.DISTRIBUTION
        return Stage.ACCUMULATION
    if close > sma:
        return Stage.ADVANCING if slope else Stage.ACCUMULATION
    return Stage.DECLINING if slope is False else Stage.DISTRIBUTION


def weekly_bias(weekly: pd.DataFrame) -> Optional[int]:
    """+1 bull, -1 bear, 0 mixed."""
    if weekly is None or len(weekly) < 30:
        return None
    is_hh, is_hl = hh_hl(weekly)
    is_lh, is_ll = lh_ll(weekly)
    sma = weekly["sma50"].iloc[-1] if "sma50" in weekly.columns else np.nan
    close = float(weekly["close"].iloc[-1])
    if is_hh and is_hl and (np.isnan(sma) or close > sma):
        return 1
    if is_lh and is_ll and (np.isnan(sma) or close < sma):
        return -1
    return 0


def candle_features(df: pd.DataFrame, i: int = -1) -> dict:
    row = df.iloc[i]
    prev = df.iloc[i - 1] if len(df) >= abs(i) + 1 or (i < 0 and len(df) >= 2) else None
    o, h, l, c = float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])
    rng = max(h - l, 1e-12)
    body = abs(c - o)
    upper = h - max(o, c)
    lower = min(o, c) - l
    close_loc = (c - l) / rng
    hammer = upper <= body * 0.25 and lower >= body * 2.0 and close_loc >= 0.75 and body > 0
    star = lower <= body * 0.25 and upper >= body * 2.0 and close_loc <= 0.25 and body > 0
    bull_eng = False
    bear_eng = False
    if prev is not None:
        po, pc = float(prev["open"]), float(prev["close"])
        pbody = abs(pc - po)
        bull_eng = pc < po and c > o and o <= pc and c >= po and body >= pbody
        bear_eng = pc > po and c < o and o >= pc and c <= po and body >= pbody
    return {
        "hammer": hammer,
        "shooting_star": star,
        "bull_engulf": bull_eng,
        "bear_engulf": bear_eng,
        "bullish": c > o,
        "bearish": c < o,
        "close_loc": close_loc,
        "body": body,
        "range": rng,
    }


def volume_ok(df: pd.DataFrame, i: int = -1) -> bool:
    row = df.iloc[i]
    vs = row.get("vol_sma", np.nan)
    if pd.isna(vs) or vs <= 0:
        return False
    return float(row["volume"]) > float(vs)


def add_structure(df: pd.DataFrame, n: int = SWING_N) -> pd.DataFrame:
    out = df.copy()
    out["swing_high"] = swing_highs(out["high"], n)
    out["swing_low"] = swing_lows(out["low"], n)
    return out


def broken_above(df: pd.DataFrame, level: float, i: int = -1) -> bool:
    return float(df["close"].iloc[i]) > level and float(df["close"].iloc[i - 1]) <= level


def broken_below(df: pd.DataFrame, level: float, i: int = -1) -> bool:
    return float(df["close"].iloc[i]) < level and float(df["close"].iloc[i - 1]) >= level
