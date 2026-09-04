"""SMC likidite: pool, inducement, turtle soup, nested sweep."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

import pandas as pd

from structure.core import broken_above, broken_below, last_pivots

PoolScope = Literal["internal", "external"]


@dataclass
class LiquidityPool:
    side: Literal["buy", "sell"]
    level: float
    touches: int
    scope: PoolScope
    swept: bool = False


def _count_touches(sl: pd.DataFrame, level: float, tol: float = 0.003) -> int:
    touches = 0
    for i in range(len(sl)):
        h = float(sl["high"].iloc[i])
        l = float(sl["low"].iloc[i])
        if abs(h - level) / max(level, 1e-9) <= tol or abs(l - level) / max(level, 1e-9) <= tol:
            touches += 1
    return touches


def build_liquidity_pools(
    df: pd.DataFrame,
    eq_highs: list[float],
    eq_lows: list[float],
    *,
    internal_n: int = 3,
    external_n: int = 5,
) -> list[LiquidityPool]:
    pools: list[LiquidityPool] = []
    sl = df.iloc[-80:].reset_index(drop=True) if len(df) > 80 else df.reset_index(drop=True)
    last_h = float(sl["high"].iloc[-1])
    last_l = float(sl["low"].iloc[-1])
    last_c = float(sl["close"].iloc[-1])

    for lv in eq_highs:
        pools.append(
            LiquidityPool(
                side="sell",
                level=lv,
                touches=_count_touches(sl, lv),
                scope="external",
                swept=last_h > lv and last_c < lv,
            )
        )
    for lv in eq_lows:
        pools.append(
            LiquidityPool(
                side="buy",
                level=lv,
                touches=_count_touches(sl, lv),
                scope="external",
                swept=last_l < lv and last_c > lv,
            )
        )

    int_highs = last_pivots(df, "high", 6, n=internal_n)
    int_lows = last_pivots(df, "low", 6, n=internal_n)
    for _, lv in int_highs[-3:]:
        pools.append(
            LiquidityPool(
                side="sell",
                level=lv,
                touches=_count_touches(sl, lv),
                scope="internal",
                swept=last_h > lv and last_c < lv,
            )
        )
    for _, lv in int_lows[-3:]:
        pools.append(
            LiquidityPool(
                side="buy",
                level=lv,
                touches=_count_touches(sl, lv),
                scope="internal",
                swept=last_l < lv and last_c > lv,
            )
        )
    return pools[-20:]


def detect_inducement(
    df: pd.DataFrame,
    external_trend: str,
    internal_event: str,
) -> tuple[bool, bool]:
    """Sahte internal kirilim → asil yon devam (Lux inducement)."""
    if df is None or len(df) < 20:
        return False, False
    highs = last_pivots(df, "high", 4, n=3)
    lows = last_pivots(df, "low", 4, n=3)
    bull_ind = False
    bear_ind = False
    if external_trend == "bull" and internal_event == "choch_bear" and len(lows) >= 2:
        if broken_below(df, lows[-2][1]) and float(df["close"].iloc[-1]) > lows[-2][1]:
            bull_ind = True
    if external_trend == "bear" and internal_event == "choch_bull" and len(highs) >= 2:
        if broken_above(df, highs[-2][1]) and float(df["close"].iloc[-1]) < highs[-2][1]:
            bear_ind = True
    return bull_ind, bear_ind


def detect_turtle_soup(df: pd.DataFrame) -> tuple[bool, bool]:
    """Son swing high/low sweep + hizli geri donus."""
    if df is None or len(df) < 10:
        return False, False
    highs = last_pivots(df, "high", 3)
    lows = last_pivots(df, "low", 3)
    row = df.iloc[-1]
    h, l, c = float(row["high"]), float(row["low"]), float(row["close"])
    bull_ts = False
    bear_ts = False
    if lows:
        lv = lows[-1][1]
        bull_ts = l < lv and c > lv
    if highs:
        lv = highs[-1][1]
        bear_ts = h > lv and c < lv
    return bull_ts, bear_ts


def detect_nested_sweep(
    pools: list[LiquidityPool],
    range_high: float,
    range_low: float,
) -> tuple[bool, bool]:
    """Dealing range icindeki internal likidite avi."""
    if range_high <= range_low:
        return False, False
    mid = (range_high + range_low) / 2.0
    nested_bull = any(
        p.scope == "internal" and p.side == "buy" and p.swept and p.level <= mid
        for p in pools
    )
    nested_bear = any(
        p.scope == "internal" and p.side == "sell" and p.swept and p.level >= mid
        for p in pools
    )
    return nested_bull, nested_bear
