"""LuxAlgo SMC benzeri yapı: BOS, CHoCH, order block, FVG, likidite sweep."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

import pandas as pd

from structure.core import (
    broken_above,
    broken_below,
    candle_features,
    hh_hl,
    last_pivots,
    lh_ll,
    swing_highs,
    swing_lows,
)

Trend = Literal["bull", "bear", "range"]
EventKind = Literal["bos_bull", "bos_bear", "choch_bull", "choch_bear", "none"]


@dataclass
class OrderBlock:
    side: Literal["bull", "bear"]
    top: float
    bottom: float
    bar_index: int
    mitigated: bool = False

    @property
    def mid(self) -> float:
        return (self.top + self.bottom) / 2.0


@dataclass
class FVG:
    side: Literal["bull", "bear"]
    top: float
    bottom: float
    bar_index: int


@dataclass
class SMCAnalysis:
    trend: Trend = "range"
    last_event: EventKind = "none"
    order_blocks: list[OrderBlock] = field(default_factory=list)
    fvgs: list[FVG] = field(default_factory=list)
    eqh_levels: list[float] = field(default_factory=list)
    eql_levels: list[float] = field(default_factory=list)
    sweep_bull: bool = False
    sweep_bear: bool = False
    in_discount: bool = False
    in_premium: bool = False
    long_score: int = 0
    short_score: int = 0
    long_notes: list[str] = field(default_factory=list)
    short_notes: list[str] = field(default_factory=list)

    @property
    def best_side(self) -> str:
        if self.long_score >= 5 and self.long_score > self.short_score:
            return "BUY"
        if self.short_score >= 5 and self.short_score > self.long_score:
            return "SELL"
        if self.long_score >= self.short_score and self.long_score >= 3:
            return "WATCH_LONG"
        if self.short_score > self.long_score and self.short_score >= 3:
            return "WATCH_SHORT"
        return "NONE"

    @property
    def best_score(self) -> int:
        return max(self.long_score, self.short_score)

    def to_dict(self) -> dict:
        active_bull = [ob for ob in self.order_blocks if ob.side == "bull" and not ob.mitigated]
        active_bear = [ob for ob in self.order_blocks if ob.side == "bear" and not ob.mitigated]
        return {
            "trend": self.trend,
            "last_event": self.last_event,
            "long_score": self.long_score,
            "short_score": self.short_score,
            "best_side": self.best_side,
            "best_score": self.best_score,
            "long_notes": " | ".join(self.long_notes),
            "short_notes": " | ".join(self.short_notes),
            "bull_ob_count": len(active_bull),
            "bear_ob_count": len(active_bear),
            "nearest_bull_ob": active_bull[-1].mid if active_bull else None,
            "nearest_bear_ob": active_bear[-1].mid if active_bear else None,
            "sweep_bull": self.sweep_bull,
            "sweep_bear": self.sweep_bear,
            "in_discount": self.in_discount,
            "in_premium": self.in_premium,
            "eqh": self.eqh_levels[-3:],
            "eql": self.eql_levels[-3:],
        }


def _trend_from_structure(df: pd.DataFrame) -> Trend:
    is_hh, is_hl = hh_hl(df)
    is_lh, is_ll = lh_ll(df)
    if is_hh and is_hl:
        return "bull"
    if is_lh and is_ll:
        return "bear"
    return "range"


def _detect_structure_event(df: pd.DataFrame, trend: Trend) -> EventKind:
    highs = last_pivots(df, "high", 5)
    lows = last_pivots(df, "low", 5)
    if len(highs) < 2 or len(lows) < 2:
        return "none"
    broke_high = broken_above(df, highs[-2][1])
    broke_low = broken_below(df, lows[-2][1])
    if trend == "bull":
        if broke_high:
            return "bos_bull"
        if broke_low:
            return "choch_bear"
    elif trend == "bear":
        if broke_low:
            return "bos_bear"
        if broke_high:
            return "choch_bull"
    else:
        if broke_high:
            return "bos_bull"
        if broke_low:
            return "bos_bear"
    return "none"


def _find_order_blocks(df: pd.DataFrame, lookback: int = 80) -> list[OrderBlock]:
    """Impuls oncesi son karsi mum = order block."""
    out: list[OrderBlock] = []
    if len(df) < lookback + 5:
        sl = df
    else:
        sl = df.iloc[-lookback:].copy()
    sl = sl.reset_index(drop=True)
    atr = float(sl["atr"].iloc[-1]) if "atr" in sl.columns and pd.notna(sl["atr"].iloc[-1]) else float(sl["close"].iloc[-1]) * 0.01
    min_move = atr * 1.2

    for i in range(2, len(sl) - 3):
        o, h, l, c = (
            float(sl["open"].iloc[i]),
            float(sl["high"].iloc[i]),
            float(sl["low"].iloc[i]),
            float(sl["close"].iloc[i]),
        )
        nxt = float(sl["close"].iloc[i + 1])
        nxt2 = float(sl["close"].iloc[i + 2])
        bearish_candle = c < o
        bullish_candle = c > o
        up_impulse = nxt2 - c >= min_move and nxt > c
        down_impulse = c - nxt2 >= min_move and nxt < c
        if bearish_candle and up_impulse:
            ob = OrderBlock(side="bull", top=max(o, c), bottom=l, bar_index=i)
            out.append(ob)
        if bullish_candle and down_impulse:
            ob = OrderBlock(side="bear", top=h, bottom=min(o, c), bar_index=i)
            out.append(ob)

    close = float(sl["close"].iloc[-1])
    for ob in out:
        if ob.side == "bull" and close < ob.bottom:
            ob.mitigated = True
        if ob.side == "bear" and close > ob.top:
            ob.mitigated = True
    return out[-12:]


def _find_fvgs(df: pd.DataFrame, lookback: int = 60) -> list[FVG]:
    out: list[FVG] = []
    sl = df.iloc[-lookback:] if len(df) > lookback else df
    sl = sl.reset_index(drop=True)
    for i in range(2, len(sl)):
        h0 = float(sl["high"].iloc[i - 2])
        l0 = float(sl["low"].iloc[i - 2])
        h2 = float(sl["high"].iloc[i])
        l2 = float(sl["low"].iloc[i])
        if l2 > h0:
            out.append(FVG(side="bull", bottom=h0, top=l2, bar_index=i))
        if h2 < l0:
            out.append(FVG(side="bear", top=l0, bottom=h2, bar_index=i))
    return out[-8:]


def _equal_levels(pivots: list[tuple[int, float]], tol: float = 0.002) -> list[float]:
    if len(pivots) < 2:
        return []
    levels: list[float] = []
    prices = [p[1] for p in pivots]
    for i, p in enumerate(prices):
        for q in prices[i + 1 :]:
            if p > 0 and abs(p - q) / p <= tol:
                levels.append((p + q) / 2.0)
    return levels[-5:]


def _detect_sweep(df: pd.DataFrame, eq_highs: list[float], eq_lows: list[float]) -> tuple[bool, bool]:
    if df.empty:
        return False, False
    row = df.iloc[-1]
    h, l, c = float(row["high"]), float(row["low"]), float(row["close"])
    sweep_bull = False
    sweep_bear = False
    for lv in eq_lows:
        if l < lv and c > lv:
            sweep_bull = True
    for lv in eq_highs:
        if h > lv and c < lv:
            sweep_bear = True
    return sweep_bull, sweep_bear


def _premium_discount(df: pd.DataFrame, price: float) -> tuple[bool, bool]:
    highs = last_pivots(df, "high", 6)
    lows = last_pivots(df, "low", 6)
    if not highs or not lows:
        return False, False
    hi = max(p[1] for p in highs)
    lo = min(p[1] for p in lows)
    if hi <= lo:
        return False, False
    mid = (hi + lo) / 2.0
    return price <= mid, price >= mid


def _price_in_zone(price: float, top: float, bottom: float, pad: float = 0.003) -> bool:
    lo = min(top, bottom) * (1 - pad)
    hi = max(top, bottom) * (1 + pad)
    return lo <= price <= hi


def analyze_smc(df: pd.DataFrame, *, internal_n: int = 3) -> SMCAnalysis:
    """Tek TF SMC analizi."""
    out = SMCAnalysis()
    if df is None or len(df) < 40:
        return out

    out.trend = _trend_from_structure(df)
    out.last_event = _detect_structure_event(df, out.trend)
    out.order_blocks = _find_order_blocks(df)
    out.fvgs = _find_fvgs(df)

    highs = last_pivots(df, "high", 8)
    lows = last_pivots(df, "low", 8)
    out.eqh_levels = _equal_levels(highs)
    out.eql_levels = _equal_levels(lows)
    out.sweep_bull, out.sweep_bear = _detect_sweep(df, out.eqh_levels, out.eql_levels)

    price = float(df["close"].iloc[-1])
    out.in_discount, out.in_premium = _premium_discount(df, price)

    active_bull = [ob for ob in out.order_blocks if ob.side == "bull" and not ob.mitigated]
    active_bear = [ob for ob in out.order_blocks if ob.side == "bear" and not ob.mitigated]
    in_bull_ob = any(_price_in_zone(price, ob.top, ob.bottom) for ob in active_bull)
    in_bear_ob = any(_price_in_zone(price, ob.top, ob.bottom) for ob in active_bear)

    if out.trend == "bull":
        out.long_score += 1
        out.long_notes.append("trend:bull")
    elif out.trend == "bear":
        out.short_score += 1
        out.short_notes.append("trend:bear")

    if out.last_event == "bos_bull":
        out.long_score += 2
        out.long_notes.append("BOS")
    elif out.last_event == "bos_bear":
        out.short_score += 2
        out.short_notes.append("BOS")
    elif out.last_event == "choch_bull":
        out.long_score += 1
        out.long_notes.append("CHoCH")
    elif out.last_event == "choch_bear":
        out.short_score += 1
        out.short_notes.append("CHoCH")

    if in_bull_ob:
        out.long_score += 2
        out.long_notes.append("OB_retest")
    if in_bear_ob:
        out.short_score += 2
        out.short_notes.append("OB_retest")

    if out.sweep_bull:
        out.long_score += 1
        out.long_notes.append("sweep_low")
    if out.sweep_bear:
        out.short_score += 1
        out.short_notes.append("sweep_high")

    if out.in_discount:
        out.long_score += 1
        out.long_notes.append("discount")
    if out.in_premium:
        out.short_score += 1
        out.short_notes.append("premium")

    bull_fvg = [f for f in out.fvgs if f.side == "bull"]
    bear_fvg = [f for f in out.fvgs if f.side == "bear"]
    if bull_fvg and _price_in_zone(price, bull_fvg[-1].top, bull_fvg[-1].bottom):
        out.long_score += 1
        out.long_notes.append("FVG")
    if bear_fvg and _price_in_zone(price, bear_fvg[-1].top, bear_fvg[-1].bottom):
        out.short_score += 1
        out.short_notes.append("FVG")

    cf = candle_features(df)
    if in_bull_ob and (cf["bull_engulf"] or cf["hammer"]):
        out.long_score += 1
        out.long_notes.append("15m_onay")
    if in_bear_ob and (cf["bear_engulf"] or cf["shooting_star"]):
        out.short_score += 1
        out.short_notes.append("15m_onay")

    return out


def analyze_smc_mtf(
    frames: dict[str, pd.DataFrame],
    *,
    setup_tf: str = "4h",
    trigger_tf: str = "15m",
    bias_tf: str = "1d",
) -> SMCAnalysis:
    """MTF SMC: HTF bias + setup TF yapı + trigger TF giris."""
    merged = SMCAnalysis()
    setup = frames.get(setup_tf)
    trigger = frames.get(trigger_tf)
    if trigger is None:
        trigger = frames.get("1h")
    bias = frames.get(bias_tf)

    if setup is not None and len(setup) >= 40:
        base = analyze_smc(setup)
        merged.trend = base.trend
        merged.last_event = base.last_event
        merged.order_blocks = base.order_blocks
        merged.fvgs = base.fvgs
        merged.eqh_levels = base.eqh_levels
        merged.eql_levels = base.eql_levels
        merged.long_score += base.long_score
        merged.short_score += base.short_score
        merged.long_notes.extend([f"4H:{n}" for n in base.long_notes])
        merged.short_notes.extend([f"4H:{n}" for n in base.short_notes])

    if bias is not None and len(bias) >= 30:
        bt = _trend_from_structure(bias)
        if bt == "bull":
            merged.long_score += 1
            merged.long_notes.append("1D:bull")
        elif bt == "bear":
            merged.short_score += 1
            merged.short_notes.append("1D:bear")

    if trigger is not None and len(trigger) >= 30:
        tr = analyze_smc(trigger)
        merged.sweep_bull = merged.sweep_bull or tr.sweep_bull
        merged.sweep_bear = merged.sweep_bear or tr.sweep_bear
        if tr.sweep_bull:
            merged.long_score += 1
            merged.long_notes.append("15m:sweep")
        if tr.sweep_bear:
            merged.short_score += 1
            merged.short_notes.append("15m:sweep")
        cf = candle_features(trigger)
        if cf["bull_engulf"]:
            merged.long_score += 1
            merged.long_notes.append("15m:bull_engulf")
        if cf["bear_engulf"]:
            merged.short_score += 1
            merged.short_notes.append("15m:bear_engulf")

    return merged
