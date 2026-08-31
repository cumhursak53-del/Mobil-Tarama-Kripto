from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from engine.config import NEAR_PCT
from engine.types import Signal, Side
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


def make_signal(ledger: str, reason: str, df: pd.DataFrame, side: Side, sl: Optional[float] = None, extra: Optional[dict] = None) -> Optional[Signal]:
    entry = float(df["close"].iloc[-1])
    sl_price = sl if sl is not None else sl_from_swing(df, side)
    if sl_price is None:
        return None
    if side == Side.BUY and sl_price >= entry:
        sl_price = entry * (1 - 0.01)
    if side == Side.SELL and sl_price <= entry:
        sl_price = entry * (1 + 0.01)
    if abs(entry - sl_price) / entry < 0.002:
        return None
    return Signal(
        side=side,
        strategy=reason,
        ledger=ledger,
        reason=reason,
        sl_price=float(sl_price),
        tp_price=tp_r(entry, sl_price, side, 2.0),
        extra=extra or {},
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
