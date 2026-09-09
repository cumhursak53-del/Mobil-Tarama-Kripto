from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from engine.config import MIN_SL_ATR_MULT, MIN_SL_PCT, NEAR_PCT
from engine.types import EntryMode, Signal, Side, TpMode
from structure.core import last_pivots


def sl_from_swing(df: pd.DataFrame, side: Side, atr_buf: float = 0.15) -> Optional[float]:
    atr = float(df["atr"].iloc[-1]) if "atr" in df.columns and pd.notna(df["atr"].iloc[-1]) else float(df["close"].iloc[-1]) * 0.01
    if side == Side.BUY:
        lows = last_pivots(df, "low", 3)
        if not lows:
            return float(df["low"].iloc[-2]) - atr * atr_buf
        return min(lows[-1][1], float(df["low"].iloc[-1])) - atr * atr_buf
    highs = last_pivots(df, "high", 3)
    if not highs:
        return float(df["high"].iloc[-2]) + atr * atr_buf
    return max(highs[-1][1], float(df["high"].iloc[-1])) + atr * atr_buf


def tp_r(entry: float, sl: float, side: Side, r: float = 2.0) -> float:
    dist = abs(entry - sl)
    if side == Side.BUY:
        return entry + dist * r
    return entry - dist * r


def _min_sl_distance(entry: float, atr: float) -> float:
    return max(entry * MIN_SL_PCT, atr * MIN_SL_ATR_MULT)


def _normalize_sl_tp(
    entry: float,
    sl_price: float,
    tp_price: Optional[float],
    side: Side,
    atr: float,
    tp_r_val: float,
) -> tuple[float, Optional[float]]:
    """SL/TP yonunu ve minimum mesafeyi zorunlu kil."""
    min_dist = _min_sl_distance(entry, atr)
    if side == Side.BUY:
        if sl_price >= entry or entry - sl_price < min_dist:
            sl_price = entry - min_dist
        if tp_price is not None and tp_price <= entry:
            tp_price = tp_r(entry, sl_price, side, tp_r_val)
    else:
        if sl_price <= entry or sl_price - entry < min_dist:
            sl_price = entry + min_dist
        if tp_price is not None and tp_price >= entry:
            tp_price = tp_r(entry, sl_price, side, tp_r_val)
    return sl_price, tp_price


def make_signal(
    ledger: str,
    reason: str,
    df: pd.DataFrame,
    side: Side,
    sl: Optional[float] = None,
    extra: Optional[dict] = None,
    *,
    tp_r_val: float = 2.0,
    tp_price: Optional[float] = None,
    tp_levels: Optional[list[float]] = None,
    tp_mode: TpMode = "r",
    entry_mode: EntryMode = "market",
    entry_limit: Optional[float] = None,
    trail_at_r: Optional[float] = None,
    be_at_r: Optional[float] = None,
    partial_pct: float = 0.5,
    strength: float = 1.0,
) -> Optional[Signal]:
    entry = float(df["close"].iloc[-1])
    atr = float(df["atr"].iloc[-1]) if "atr" in df.columns and pd.notna(df["atr"].iloc[-1]) else entry * 0.01
    sl_price = sl if sl is not None else sl_from_swing(df, side)
    if sl_price is None:
        return None

    levels = list(tp_levels or [])
    final_tp = tp_price
    if final_tp is None and not levels:
        final_tp = tp_r(entry, sl_price, side, tp_r_val)
    elif final_tp is None and levels:
        final_tp = levels[0]

    sl_price, final_tp = _normalize_sl_tp(entry, sl_price, final_tp, side, atr, tp_r_val)
    min_dist = _min_sl_distance(entry, atr)
    if abs(entry - sl_price) < min_dist * 0.5:
        return None

    return Signal(
        side=side,
        strategy=reason,
        ledger=ledger,
        reason=reason,
        sl_price=float(sl_price),
        tp_price=float(final_tp) if final_tp is not None else None,
        extra=extra or {},
        tp_mode=tp_mode,
        tp_levels=levels,
        entry_mode=entry_mode,
        entry_limit=entry_limit,
        trail_at_r=trail_at_r,
        be_at_r=be_at_r,
        partial_pct=partial_pct,
        tp_r=tp_r_val,
        strength=strength,
    )


def near(price: float, level: float, pct: float = NEAR_PCT) -> bool:
    if level <= 0 or price <= 0:
        return False
    return abs(price - level) / price <= pct


def valid_row(df: Optional[pd.DataFrame], cols: tuple[str, ...]) -> bool:
    if df is None or len(df) < 30:
        return False
    row = df.iloc[-1]
    return all(c in df.columns and pd.notna(row[c]) for c in cols)


def finite(*vals) -> bool:
    return all(v is not None and not (isinstance(v, float) and (np.isnan(v) or np.isinf(v))) for v in vals)
