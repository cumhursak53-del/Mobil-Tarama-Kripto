"""LuxAlgo SMC: internal/external, breaker, OTE, session, likidite, IFVG, setup grade."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

import pandas as pd

from engine.config import SWING_N
from structure.adaptive_swing import swing_ns
from structure.core import (
    broken_above,
    broken_below,
    candle_features,
    last_pivots,
    volume_ok,
)
from structure.smc_liquidity import (
    LiquidityPool,
    build_liquidity_pools,
    detect_inducement,
    detect_nested_sweep,
    detect_turtle_soup,
)
from structure.smc_sessions import in_killzone, session_label

Trend = Literal["bull", "bear", "range"]
EventKind = Literal["bos_bull", "bos_bear", "choch_bull", "choch_bear", "none"]
StructureScope = Literal["internal", "external"]
BlockType = Literal["order", "breaker", "mitigation"]
Strength = Literal["strong", "weak", "none"]
SetupGrade = Literal["A", "B", "C", "none"]

INTERNAL_N = 3
EXTERNAL_N = SWING_N
OTE_LOW = 0.62
OTE_HIGH = 0.79


@dataclass
class OrderBlock:
    side: Literal["bull", "bear"]
    top: float
    bottom: float
    bar_index: int
    mitigated: bool = False
    fill_pct: float = 0.0
    block_type: BlockType = "order"
    structure: StructureScope = "external"
    quality: float = 0.0
    displacement: bool = False
    volume_spike: bool = False

    @property
    def mid(self) -> float:
        return (self.top + self.bottom) / 2.0


@dataclass
class FVG:
    side: Literal["bull", "bear"]
    top: float
    bottom: float
    bar_index: int
    mitigated: bool = False
    fill_pct: float = 0.0
    is_inversion: bool = False
    ce_level: float = 0.0
    priority: float = 0.0


@dataclass
class DealingRange:
    high: float
    low: float
    equilibrium: float
    ote_low: float
    ote_high: float

    @classmethod
    def from_swings(cls, swing_high: float, swing_low: float, direction: Trend) -> Optional["DealingRange"]:
        if swing_high <= swing_low:
            return None
        diff = swing_high - swing_low
        eq = swing_low + diff * 0.5
        if direction == "bull":
            ote_lo = swing_high - diff * OTE_HIGH
            ote_hi = swing_high - diff * OTE_LOW
        elif direction == "bear":
            ote_lo = swing_low + diff * OTE_LOW
            ote_hi = swing_low + diff * OTE_HIGH
        else:
            ote_lo = swing_low + diff * OTE_LOW
            ote_hi = swing_low + diff * OTE_HIGH
        return cls(
            high=swing_high,
            low=swing_low,
            equilibrium=eq,
            ote_low=min(ote_lo, ote_hi),
            ote_high=max(ote_lo, ote_hi),
        )


@dataclass
class SMCAnalysis:
    trend: Trend = "range"
    last_event: EventKind = "none"
    internal_event: EventKind = "none"
    external_event: EventKind = "none"
    order_blocks: list[OrderBlock] = field(default_factory=list)
    breaker_blocks: list[OrderBlock] = field(default_factory=list)
    mitigation_blocks: list[OrderBlock] = field(default_factory=list)
    fvgs: list[FVG] = field(default_factory=list)
    liquidity_pools: list[LiquidityPool] = field(default_factory=list)
    eqh_levels: list[float] = field(default_factory=list)
    eql_levels: list[float] = field(default_factory=list)
    dealing_range: Optional[DealingRange] = None
    sweep_bull: bool = False
    sweep_bear: bool = False
    inducement_bull: bool = False
    inducement_bear: bool = False
    turtle_soup_bull: bool = False
    turtle_soup_bear: bool = False
    nested_sweep_bull: bool = False
    nested_sweep_bear: bool = False
    in_discount: bool = False
    in_premium: bool = False
    in_ote_long: bool = False
    in_ote_short: bool = False
    in_equilibrium: bool = False
    swing_high_strength: Strength = "none"
    swing_low_strength: Strength = "none"
    hierarchy_long: bool = False
    hierarchy_short: bool = False
    session: str = "off_hours"
    killzone: bool = False
    confluence_long: int = 0
    confluence_short: int = 0
    setup_grade_long: SetupGrade = "none"
    setup_grade_short: SetupGrade = "none"
    internal_swing_n: int = 3
    external_swing_n: int = SWING_N
    long_score: int = 0
    short_score: int = 0
    long_notes: list[str] = field(default_factory=list)
    short_notes: list[str] = field(default_factory=list)

    @property
    def best_side(self) -> str:
        if self.long_score >= 5 and self.long_score > self.short_score and self.setup_grade_long in ("A", "B"):
            return "BUY"
        if self.short_score >= 5 and self.short_score > self.long_score and self.setup_grade_short in ("A", "B"):
            return "SELL"
        if self.long_score >= self.short_score and self.long_score >= 3:
            return "WATCH_LONG"
        if self.short_score > self.long_score and self.short_score >= 3:
            return "WATCH_SHORT"
        return "NONE"

    @property
    def best_score(self) -> int:
        return max(self.long_score, self.short_score)

    def active_blocks(self, side: Literal["bull", "bear"]) -> list[OrderBlock]:
        blocks: list[OrderBlock] = []
        for ob in self.order_blocks:
            if ob.side == side and not ob.mitigated and ob.block_type == "order":
                blocks.append(ob)
        for ob in self.breaker_blocks:
            if ob.side == side and not ob.mitigated:
                blocks.append(ob)
        for ob in self.mitigation_blocks:
            if ob.side == side and not ob.mitigated:
                blocks.append(ob)
        return blocks

    def to_dict(self) -> dict:
        active_bull = self.active_blocks("bull")
        active_bear = self.active_blocks("bear")
        active_fvg_bull = [f for f in self.fvgs if f.side == "bull" and not f.mitigated]
        active_fvg_bear = [f for f in self.fvgs if f.side == "bear" and not f.mitigated]
        ifvg_bull = sum(1 for f in self.fvgs if f.is_inversion and f.side == "bull" and not f.mitigated)
        ifvg_bear = sum(1 for f in self.fvgs if f.is_inversion and f.side == "bear" and not f.mitigated)
        dr = self.dealing_range
        return {
            "trend": self.trend,
            "last_event": self.last_event,
            "internal_event": self.internal_event,
            "external_event": self.external_event,
            "long_score": self.long_score,
            "short_score": self.short_score,
            "best_side": self.best_side,
            "best_score": self.best_score,
            "long_notes": " | ".join(self.long_notes),
            "short_notes": " | ".join(self.short_notes),
            "bull_ob_count": len(active_bull),
            "bear_ob_count": len(active_bear),
            "breaker_bull": len([b for b in self.breaker_blocks if b.side == "bull" and not b.mitigated]),
            "breaker_bear": len([b for b in self.breaker_blocks if b.side == "bear" and not b.mitigated]),
            "nearest_bull_ob": active_bull[-1].mid if active_bull else None,
            "nearest_bear_ob": active_bear[-1].mid if active_bear else None,
            "sweep_bull": self.sweep_bull,
            "sweep_bear": self.sweep_bear,
            "inducement_bull": self.inducement_bull,
            "inducement_bear": self.inducement_bear,
            "turtle_soup_bull": self.turtle_soup_bull,
            "turtle_soup_bear": self.turtle_soup_bear,
            "nested_sweep_bull": self.nested_sweep_bull,
            "nested_sweep_bear": self.nested_sweep_bear,
            "in_discount": self.in_discount,
            "in_premium": self.in_premium,
            "in_ote_long": self.in_ote_long,
            "in_ote_short": self.in_ote_short,
            "in_equilibrium": self.in_equilibrium,
            "swing_high_strength": self.swing_high_strength,
            "swing_low_strength": self.swing_low_strength,
            "hierarchy_long": self.hierarchy_long,
            "hierarchy_short": self.hierarchy_short,
            "session": self.session,
            "killzone": self.killzone,
            "confluence_long": self.confluence_long,
            "confluence_short": self.confluence_short,
            "setup_grade_long": self.setup_grade_long,
            "setup_grade_short": self.setup_grade_short,
            "internal_swing_n": self.internal_swing_n,
            "external_swing_n": self.external_swing_n,
            "ifvg_bull": ifvg_bull,
            "ifvg_bear": ifvg_bear,
            "active_fvg_bull": len(active_fvg_bull),
            "active_fvg_bear": len(active_fvg_bear),
            "dealing_high": dr.high if dr else None,
            "dealing_low": dr.low if dr else None,
            "eqh": self.eqh_levels[-3:],
            "eql": self.eql_levels[-3:],
            "liquidity_pools": len(self.liquidity_pools),
        }


def _trend_from_structure(df: pd.DataFrame, n: int = EXTERNAL_N) -> Trend:
    highs = last_pivots(df, "high", 3, n=n)
    lows = last_pivots(df, "low", 3, n=n)
    is_hh = len(highs) >= 2 and highs[-1][1] > highs[-2][1]
    is_hl = len(lows) >= 2 and lows[-1][1] > lows[-2][1]
    is_lh = len(highs) >= 2 and highs[-1][1] < highs[-2][1]
    is_ll = len(lows) >= 2 and lows[-1][1] < lows[-2][1]
    if is_hh and is_hl:
        return "bull"
    if is_lh and is_ll:
        return "bear"
    return "range"


def _detect_structure_event(df: pd.DataFrame, trend: Trend, n: int = EXTERNAL_N) -> EventKind:
    highs = last_pivots(df, "high", 5, n=n)
    lows = last_pivots(df, "low", 5, n=n)
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


def _hierarchy_aligned(ext_trend: Trend, int_event: EventKind, side: Literal["long", "short"]) -> bool:
    if side == "long":
        if ext_trend == "bull":
            return int_event in ("none", "bos_bull", "choch_bull", "choch_bear")
        return ext_trend == "range" and int_event == "bos_bull"
    if ext_trend == "bear":
        return int_event in ("none", "bos_bear", "choch_bear", "choch_bull")
    return ext_trend == "range" and int_event == "bos_bear"


def _swing_strength(df: pd.DataFrame, pivot: tuple[int, float], kind: str) -> Strength:
    idx, level = pivot
    if idx >= len(df) - 2:
        return "none"
    segment = df.iloc[idx + 1 :]
    if segment.empty:
        return "none"
    if kind == "high":
        swept = (segment["high"] > level).any()
    else:
        swept = (segment["low"] < level).any()
    return "weak" if swept else "strong"


def _atr(sl: pd.DataFrame) -> float:
    if "atr" in sl.columns and pd.notna(sl["atr"].iloc[-1]):
        return float(sl["atr"].iloc[-1])
    return float(sl["close"].iloc[-1]) * 0.01


def _mark_ob_partial_fill(sl: pd.DataFrame, obs: list[OrderBlock]) -> None:
    for ob in obs:
        lo = min(ob.top, ob.bottom)
        hi = max(ob.top, ob.bottom)
        size = max(hi - lo, 1e-12)
        max_fill = 0.0
        for j in range(ob.bar_index + 1, len(sl)):
            bar_lo = float(sl["low"].iloc[j])
            bar_hi = float(sl["high"].iloc[j])
            if ob.side == "bull":
                if bar_lo <= hi:
                    depth = min(hi, bar_hi) - lo
                    max_fill = max(max_fill, depth / size)
            else:
                if bar_hi >= lo:
                    depth = hi - max(lo, bar_lo)
                    max_fill = max(max_fill, depth / size)
        ob.fill_pct = min(1.0, max_fill)
        if ob.fill_pct >= 1.0:
            ob.mitigated = True
        elif ob.fill_pct >= 0.5:
            ob.mitigated = True


def _dedupe_obs(obs: list[OrderBlock], tol: float = 0.004) -> list[OrderBlock]:
    if not obs:
        return []
    ranked = sorted(obs, key=lambda o: (o.quality, o.bar_index), reverse=True)
    kept: list[OrderBlock] = []
    for ob in ranked:
        mid = ob.mid
        if any(abs(mid - k.mid) / max(mid, 1e-9) <= tol for k in kept):
            continue
        kept.append(ob)
    return sorted(kept, key=lambda o: o.bar_index)[-12:]


def _find_order_blocks(
    df: pd.DataFrame,
    lookback: int = 80,
    structure: StructureScope = "external",
) -> list[OrderBlock]:
    out: list[OrderBlock] = []
    sl = df.iloc[-lookback:].copy().reset_index(drop=True) if len(df) > lookback else df.reset_index(drop=True)
    atr = _atr(sl)
    min_move = atr * 1.2
    disp_move = atr * 1.5

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
        up_disp = nxt2 - c >= disp_move
        down_disp = c - nxt2 >= disp_move
        vol_spike = volume_ok(sl, i + 1) or volume_ok(sl, i + 2)
        quality = 0.35 + (0.35 if (up_disp or down_disp) else 0) + (0.30 if vol_spike else 0)

        if bearish_candle and up_impulse:
            out.append(
                OrderBlock(
                    side="bull", top=max(o, c), bottom=l, bar_index=i,
                    structure=structure, displacement=up_disp, volume_spike=vol_spike,
                    quality=min(1.0, quality),
                )
            )
        if bullish_candle and down_impulse:
            out.append(
                OrderBlock(
                    side="bear", top=h, bottom=min(o, c), bar_index=i,
                    structure=structure, displacement=down_disp, volume_spike=vol_spike,
                    quality=min(1.0, quality),
                )
            )

    _mark_ob_partial_fill(sl, out)
    close = float(sl["close"].iloc[-1])
    for ob in out:
        if not ob.mitigated:
            if ob.side == "bull" and close < ob.bottom:
                ob.mitigated = True
            if ob.side == "bear" and close > ob.top:
                ob.mitigated = True
    return _dedupe_obs(out)


def _find_breaker_blocks(sl: pd.DataFrame, order_blocks: list[OrderBlock]) -> list[OrderBlock]:
    out: list[OrderBlock] = []
    for ob in order_blocks:
        if ob.block_type != "order":
            continue
        for j in range(ob.bar_index + 1, len(sl)):
            c = float(sl["close"].iloc[j])
            if ob.side == "bear" and c > ob.top:
                out.append(
                    OrderBlock(
                        side="bull", top=ob.top, bottom=ob.bottom, bar_index=ob.bar_index,
                        block_type="breaker", structure=ob.structure, quality=ob.quality,
                        displacement=ob.displacement, volume_spike=ob.volume_spike,
                    )
                )
                break
            if ob.side == "bull" and c < ob.bottom:
                out.append(
                    OrderBlock(
                        side="bear", top=ob.top, bottom=ob.bottom, bar_index=ob.bar_index,
                        block_type="breaker", structure=ob.structure, quality=ob.quality,
                        displacement=ob.displacement, volume_spike=ob.volume_spike,
                    )
                )
                break
    close = float(sl["close"].iloc[-1])
    for bb in out:
        if bb.side == "bull" and close < bb.bottom:
            bb.mitigated = True
        if bb.side == "bear" and close > bb.top:
            bb.mitigated = True
    return out[-8:]


def _find_mitigation_blocks(sl: pd.DataFrame, order_blocks: list[OrderBlock]) -> list[OrderBlock]:
    out: list[OrderBlock] = []
    price = float(sl["close"].iloc[-1])
    h, l = float(sl["high"].iloc[-1]), float(sl["low"].iloc[-1])
    for ob in order_blocks:
        if ob.block_type != "order" or not ob.mitigated:
            continue
        lo, hi = min(ob.top, ob.bottom), max(ob.top, ob.bottom)
        if not (l <= hi and h >= lo):
            continue
        out.append(
            OrderBlock(
                side=ob.side, top=ob.top, bottom=ob.bottom, bar_index=ob.bar_index,
                block_type="mitigation", structure=ob.structure, quality=ob.quality * 0.8,
                displacement=ob.displacement, volume_spike=ob.volume_spike,
                fill_pct=ob.fill_pct,
            )
        )
    for mb in out:
        if mb.side == "bull" and price < mb.bottom:
            mb.mitigated = True
        if mb.side == "bear" and price > mb.top:
            mb.mitigated = True
    return out[-6:]


def _find_fvgs(df: pd.DataFrame, lookback: int = 60) -> list[FVG]:
    out: list[FVG] = []
    sl = df.iloc[-lookback:].reset_index(drop=True) if len(df) > lookback else df.reset_index(drop=True)
    for i in range(2, len(sl)):
        h0, l0 = float(sl["high"].iloc[i - 2]), float(sl["low"].iloc[i - 2])
        h2, l2 = float(sl["high"].iloc[i]), float(sl["low"].iloc[i])
        if l2 > h0:
            f = FVG(side="bull", bottom=h0, top=l2, bar_index=i)
            f.ce_level = (h0 + l2) / 2.0
            out.append(f)
        if h2 < l0:
            f = FVG(side="bear", top=l0, bottom=h2, bar_index=i)
            f.ce_level = (l0 + h2) / 2.0
            out.append(f)
    return out[-12:]


def _mark_fvg_mitigation(sl: pd.DataFrame, fvgs: list[FVG]) -> None:
    for fvg in fvgs:
        gap_lo, gap_hi = min(fvg.top, fvg.bottom), max(fvg.top, fvg.bottom)
        gap_size = max(gap_hi - gap_lo, 1e-12)
        max_fill = 0.0
        inverted = False
        for j in range(fvg.bar_index + 1, len(sl)):
            lo, hi = float(sl["low"].iloc[j]), float(sl["high"].iloc[j])
            c = float(sl["close"].iloc[j])
            if fvg.side == "bull":
                if lo <= gap_hi:
                    max_fill = max(max_fill, (min(gap_hi, hi) - gap_lo) / gap_size)
                if c < gap_lo:
                    inverted = True
            else:
                if hi >= gap_lo:
                    max_fill = max(max_fill, (gap_hi - max(gap_lo, lo)) / gap_size)
                if c > gap_hi:
                    inverted = True
        fvg.fill_pct = min(1.0, max_fill)
        fvg.mitigated = fvg.fill_pct >= 0.5
        if inverted and not fvg.mitigated:
            fvg.is_inversion = True
            fvg.side = "bear" if fvg.side == "bull" else "bull"


def _rank_fvgs(fvgs: list[FVG], price: float) -> list[FVG]:
    active = [f for f in fvgs if not f.mitigated]
    for f in active:
        mid = (f.top + f.bottom) / 2.0
        dist = abs(price - mid) / max(price, 1e-9)
        f.priority = (1.0 - min(dist, 1.0)) + (0.3 if f.is_inversion else 0) + (0.2 if f.fill_pct < 0.3 else 0)
    return sorted(active, key=lambda f: f.priority, reverse=True)


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
    sweep_bull = any(l < lv and c > lv for lv in eq_lows)
    sweep_bear = any(h > lv and c < lv for lv in eq_highs)
    return sweep_bull, sweep_bear


def _price_in_zone(price: float, top: float, bottom: float, pad: float = 0.003) -> bool:
    lo = min(top, bottom) * (1 - pad)
    hi = max(top, bottom) * (1 + pad)
    return lo <= price <= hi


def _bar_timestamp(df: pd.DataFrame):
    if df.empty:
        return None
    idx = df.index[-1]
    if hasattr(idx, "to_pydatetime"):
        return idx.to_pydatetime()
    ct = df.get("close_time")
    if ct is not None and len(ct):
        return ct.iloc[-1]
    return None


def _score_event(out: SMCAnalysis, event: EventKind, scope: StructureScope) -> None:
    prefix = "int" if scope == "internal" else "ext"
    if event == "bos_bull":
        pts = 1 if scope == "internal" else 2
        out.long_score += pts
        out.long_notes.append(f"{prefix}_BOS")
    elif event == "bos_bear":
        pts = 1 if scope == "internal" else 2
        out.short_score += pts
        out.short_notes.append(f"{prefix}_BOS")
    elif event == "choch_bull":
        out.long_score += 1
        out.long_notes.append(f"{prefix}_CHoCH")
    elif event == "choch_bear":
        out.short_score += 1
        out.short_notes.append(f"{prefix}_CHoCH")


def _compute_confluence(out: SMCAnalysis, price: float, side: Literal["long", "short"]) -> int:
    notes = out.long_notes if side == "long" else out.short_notes
    joined = " ".join(notes)
    checks = 0
    if side == "long":
        if out.hierarchy_long:
            checks += 1
        if out.trend == "bull" or "ext_BOS" in joined:
            checks += 1
        if out.in_discount or out.in_ote_long:
            checks += 1
        if any(x in joined for x in ("OB_retest", "breaker_retest", "mitigation_retest")):
            checks += 1
        if out.sweep_bull or out.turtle_soup_bull or out.inducement_bull or out.nested_sweep_bull:
            checks += 1
        if "FVG_active" in joined or "IFVG" in joined:
            checks += 1
        if out.killzone:
            checks += 1
        if "candle_confirm" in joined or "bull_engulf" in joined:
            checks += 1
    else:
        if out.hierarchy_short:
            checks += 1
        if out.trend == "bear" or "ext_BOS" in joined:
            checks += 1
        if out.in_premium or out.in_ote_short:
            checks += 1
        if any(x in joined for x in ("OB_retest", "breaker_retest", "mitigation_retest")):
            checks += 1
        if out.sweep_bear or out.turtle_soup_bear or out.inducement_bear or out.nested_sweep_bear:
            checks += 1
        if "FVG_active" in joined or "IFVG" in joined:
            checks += 1
        if out.killzone:
            checks += 1
        if "candle_confirm" in joined or "bear_engulf" in joined:
            checks += 1
    return checks


def _setup_grade(confluence: int, score: int) -> SetupGrade:
    if confluence >= 6 and score >= 7:
        return "A"
    if confluence >= 4 and score >= 5:
        return "B"
    if confluence >= 3 and score >= 4:
        return "C"
    return "none"


def analyze_smc(df: pd.DataFrame) -> SMCAnalysis:
    out = SMCAnalysis()
    if df is None or len(df) < 40:
        return out

    int_n, ext_n = swing_ns(df)

    ext_trend = _trend_from_structure(df, ext_n)
    int_trend = _trend_from_structure(df, int_n)
    out.trend = ext_trend
    out.internal_swing_n = int_n
    out.external_swing_n = ext_n
    out.external_event = _detect_structure_event(df, ext_trend, ext_n)
    out.internal_event = _detect_structure_event(df, int_trend, int_n)
    out.last_event = out.external_event if out.external_event != "none" else out.internal_event
    out.hierarchy_long = _hierarchy_aligned(ext_trend, out.internal_event, "long")
    out.hierarchy_short = _hierarchy_aligned(ext_trend, out.internal_event, "short")

    ts = _bar_timestamp(df)
    out.session = session_label(ts)
    out.killzone = in_killzone(ts)

    ext_obs = _find_order_blocks(df, structure="external")
    int_obs = _find_order_blocks(df, lookback=50, structure="internal")
    out.order_blocks = (ext_obs + int_obs)[-20:]

    sl = df.iloc[-80:].copy().reset_index(drop=True) if len(df) > 80 else df.reset_index(drop=True)
    out.breaker_blocks = _find_breaker_blocks(sl, out.order_blocks)
    out.mitigation_blocks = _find_mitigation_blocks(sl, out.order_blocks)

    out.fvgs = _find_fvgs(df)
    fvg_sl = df.iloc[-60:].reset_index(drop=True) if len(df) > 60 else df.reset_index(drop=True)
    _mark_fvg_mitigation(fvg_sl, out.fvgs)

    highs = last_pivots(df, "high", 8)
    lows = last_pivots(df, "low", 8)
    out.eqh_levels = _equal_levels(highs)
    out.eql_levels = _equal_levels(lows)
    out.sweep_bull, out.sweep_bear = _detect_sweep(df, out.eqh_levels, out.eql_levels)

    if highs:
        out.swing_high_strength = _swing_strength(df, highs[-1], "high")
    if lows:
        out.swing_low_strength = _swing_strength(df, lows[-1], "low")

    if highs and lows:
        out.dealing_range = DealingRange.from_swings(highs[-1][1], lows[-1][1], ext_trend)

    price = float(df["close"].iloc[-1])
    dr = out.dealing_range
    if dr:
        out.in_discount = price <= dr.equilibrium
        out.in_premium = price >= dr.equilibrium
        out.in_equilibrium = abs(price - dr.equilibrium) / max(dr.equilibrium, 1e-9) <= 0.005
        out.in_ote_long = dr.ote_low <= price <= dr.ote_high and ext_trend in ("bull", "range")
        out.in_ote_short = dr.ote_low <= price <= dr.ote_high and ext_trend in ("bear", "range")

    out.liquidity_pools = build_liquidity_pools(
        df, out.eqh_levels, out.eql_levels, internal_n=int_n, external_n=ext_n
    )
    out.inducement_bull, out.inducement_bear = detect_inducement(df, ext_trend, out.internal_event)
    out.turtle_soup_bull, out.turtle_soup_bear = detect_turtle_soup(df)
    if dr:
        out.nested_sweep_bull, out.nested_sweep_bear = detect_nested_sweep(
            out.liquidity_pools, dr.high, dr.low
        )

    active_bull = out.active_blocks("bull")
    active_bear = out.active_blocks("bear")
    in_bull_zone = any(_price_in_zone(price, ob.top, ob.bottom) for ob in active_bull)
    in_bear_zone = any(_price_in_zone(price, ob.top, ob.bottom) for ob in active_bear)
    in_bull_ob = any(
        _price_in_zone(price, ob.top, ob.bottom)
        for ob in out.order_blocks if ob.side == "bull" and not ob.mitigated and ob.block_type == "order"
    )
    in_bear_ob = any(
        _price_in_zone(price, ob.top, ob.bottom)
        for ob in out.order_blocks if ob.side == "bear" and not ob.mitigated and ob.block_type == "order"
    )
    in_bull_breaker = any(
        _price_in_zone(price, ob.top, ob.bottom)
        for ob in out.breaker_blocks if ob.side == "bull" and not ob.mitigated
    )
    in_bear_breaker = any(
        _price_in_zone(price, ob.top, ob.bottom)
        for ob in out.breaker_blocks if ob.side == "bear" and not ob.mitigated
    )
    in_bull_mit = any(
        _price_in_zone(price, ob.top, ob.bottom)
        for ob in out.mitigation_blocks if ob.side == "bull" and not ob.mitigated
    )
    in_bear_mit = any(
        _price_in_zone(price, ob.top, ob.bottom)
        for ob in out.mitigation_blocks if ob.side == "bear" and not ob.mitigated
    )

    if out.trend == "bull":
        out.long_score += 1
        out.long_notes.append("trend:bull")
    elif out.trend == "bear":
        out.short_score += 1
        out.short_notes.append("trend:bear")

    if out.hierarchy_long:
        out.long_notes.append("hierarchy_ok")
    if out.hierarchy_short:
        out.short_notes.append("hierarchy_ok")

    if out.internal_event != "none":
        _score_event(out, out.internal_event, "internal")
    if out.external_event != "none":
        _score_event(out, out.external_event, "external")

    if in_bull_ob:
        out.long_score += 2
        out.long_notes.append("OB_retest")
        best = max((ob for ob in out.order_blocks if ob.side == "bull" and not ob.mitigated), key=lambda x: x.quality, default=None)
        if best and best.quality >= 0.65:
            out.long_score += 1
            out.long_notes.append("OB_quality")
        if best and 0 < best.fill_pct < 1:
            out.long_notes.append("OB_partial")
    if in_bear_ob:
        out.short_score += 2
        out.short_notes.append("OB_retest")
        best = max((ob for ob in out.order_blocks if ob.side == "bear" and not ob.mitigated), key=lambda x: x.quality, default=None)
        if best and best.quality >= 0.65:
            out.short_score += 1
            out.short_notes.append("OB_quality")
        if best and 0 < best.fill_pct < 1:
            out.short_notes.append("OB_partial")

    if in_bull_breaker:
        out.long_score += 2
        out.long_notes.append("breaker_retest")
    if in_bear_breaker:
        out.short_score += 2
        out.short_notes.append("breaker_retest")
    if in_bull_mit:
        out.long_score += 1
        out.long_notes.append("mitigation_retest")
    if in_bear_mit:
        out.short_score += 1
        out.short_notes.append("mitigation_retest")

    if out.sweep_bull:
        out.long_score += 1
        out.long_notes.append("sweep_low")
    if out.sweep_bear:
        out.short_score += 1
        out.short_notes.append("sweep_high")
    if out.inducement_bull:
        out.long_score += 2
        out.long_notes.append("inducement")
    if out.inducement_bear:
        out.short_score += 2
        out.short_notes.append("inducement")
    if out.turtle_soup_bull:
        out.long_score += 1
        out.long_notes.append("turtle_soup")
    if out.turtle_soup_bear:
        out.short_score += 1
        out.short_notes.append("turtle_soup")
    if out.nested_sweep_bull:
        out.long_score += 1
        out.long_notes.append("nested_sweep")
    if out.nested_sweep_bear:
        out.short_score += 1
        out.short_notes.append("nested_sweep")

    if out.swing_low_strength == "weak" and out.sweep_bull:
        out.long_score += 1
        out.long_notes.append("weak_low_swept")
    if out.swing_high_strength == "weak" and out.sweep_bear:
        out.short_score += 1
        out.short_notes.append("weak_high_swept")
    if out.swing_high_strength == "strong" and out.external_event == "bos_bear":
        out.short_score += 1
        out.short_notes.append("strong_high_break")
    if out.swing_low_strength == "strong" and out.external_event == "bos_bull":
        out.long_score += 1
        out.long_notes.append("strong_low_break")

    if out.in_discount:
        out.long_score += 1
        out.long_notes.append("discount")
    if out.in_premium:
        out.short_score += 1
        out.short_notes.append("premium")
    if out.in_ote_long:
        out.long_score += 2
        out.long_notes.append("OTE")
    if out.in_ote_short:
        out.short_score += 2
        out.short_notes.append("OTE")
    if out.in_equilibrium:
        out.long_notes.append("equilibrium")
        out.short_notes.append("equilibrium")

    ranked_fvg = _rank_fvgs(out.fvgs, price)
    for fvg in ranked_fvg[:2]:
        if _price_in_zone(price, fvg.top, fvg.bottom):
            if fvg.is_inversion:
                if fvg.side == "bull":
                    out.long_score += 2
                    out.long_notes.append("IFVG")
                else:
                    out.short_score += 2
                    out.short_notes.append("IFVG")
            else:
                if fvg.side == "bull":
                    out.long_score += 1
                    out.long_notes.append("FVG_active")
                else:
                    out.short_score += 1
                    out.short_notes.append("FVG_active")
            if abs(price - fvg.ce_level) / max(price, 1e-9) <= 0.004:
                if fvg.side == "bull":
                    out.long_score += 1
                    out.long_notes.append("FVG_CE")
                else:
                    out.short_score += 1
                    out.short_notes.append("FVG_CE")

    if out.killzone:
        out.long_score += 1
        out.short_score += 1
        out.long_notes.append(f"killzone:{out.session}")
        out.short_notes.append(f"killzone:{out.session}")

    cf = candle_features(df)
    if in_bull_zone and (cf["bull_engulf"] or cf["hammer"]):
        out.long_score += 1
        out.long_notes.append("candle_confirm")
    if in_bear_zone and (cf["bear_engulf"] or cf["shooting_star"]):
        out.short_score += 1
        out.short_notes.append("candle_confirm")

    out.confluence_long = _compute_confluence(out, price, "long")
    out.confluence_short = _compute_confluence(out, price, "short")
    out.setup_grade_long = _setup_grade(out.confluence_long, out.long_score)
    out.setup_grade_short = _setup_grade(out.confluence_short, out.short_score)

    return out


def _merge_mtf_base(merged: SMCAnalysis, base: SMCAnalysis, prefix: str) -> None:
    merged.trend = base.trend
    merged.last_event = base.last_event
    merged.internal_event = base.internal_event
    merged.external_event = base.external_event
    merged.order_blocks = base.order_blocks
    merged.breaker_blocks = base.breaker_blocks
    merged.mitigation_blocks = base.mitigation_blocks
    merged.fvgs = base.fvgs
    merged.liquidity_pools = base.liquidity_pools
    merged.eqh_levels = base.eqh_levels
    merged.eql_levels = base.eql_levels
    merged.dealing_range = base.dealing_range
    merged.swing_high_strength = base.swing_high_strength
    merged.swing_low_strength = base.swing_low_strength
    merged.hierarchy_long = base.hierarchy_long
    merged.hierarchy_short = base.hierarchy_short
    merged.in_discount = base.in_discount
    merged.in_premium = base.in_premium
    merged.in_ote_long = base.in_ote_long
    merged.in_ote_short = base.in_ote_short
    merged.in_equilibrium = base.in_equilibrium
    merged.inducement_bull = base.inducement_bull
    merged.inducement_bear = base.inducement_bear
    merged.long_score += base.long_score
    merged.short_score += base.short_score
    merged.long_notes.extend([f"{prefix}:{n}" for n in base.long_notes])
    merged.short_notes.extend([f"{prefix}:{n}" for n in base.short_notes])


def analyze_smc_mtf(
    frames: dict[str, pd.DataFrame],
    *,
    setup_tf: str = "4h",
    mid_tf: str = "1h",
    trigger_tf: str = "15m",
    bias_tf: str = "1d",
    weekly_tf: str = "1w",
) -> SMCAnalysis:
    """MTF checklist: 1W+1D bias, 4H setup, 1H ara, 15m trigger."""
    merged = SMCAnalysis()
    setup = frames.get(setup_tf)
    mid = frames.get(mid_tf)
    trigger = frames.get(trigger_tf)
    if trigger is None:
        trigger = frames.get("1h")
    bias = frames.get(bias_tf)
    weekly = frames.get(weekly_tf)

    if setup is not None and len(setup) >= 40:
        _merge_mtf_base(merged, analyze_smc(setup), "4H")

    if mid is not None and len(mid) >= 40:
        mid_a = analyze_smc(mid)
        merged.sweep_bull = merged.sweep_bull or mid_a.sweep_bull
        merged.sweep_bear = merged.sweep_bear or mid_a.sweep_bear
        if mid_a.external_event != "none":
            before_l, before_s = len(merged.long_notes), len(merged.short_notes)
            _score_event(merged, mid_a.external_event, "external")
            for i in range(before_l, len(merged.long_notes)):
                merged.long_notes[i] = f"1H:{merged.long_notes[i]}"
            for i in range(before_s, len(merged.short_notes)):
                merged.short_notes[i] = f"1H:{merged.short_notes[i]}"

    if weekly is not None and len(weekly) >= 20:
        wt = _trend_from_structure(weekly, EXTERNAL_N)
        if wt == "bull":
            merged.long_score += 1
            merged.long_notes.append("1W:bull")
        elif wt == "bear":
            merged.short_score += 1
            merged.short_notes.append("1W:bear")

    if bias is not None and len(bias) >= 30:
        bt = _trend_from_structure(bias, EXTERNAL_N)
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
        merged.turtle_soup_bull = merged.turtle_soup_bull or tr.turtle_soup_bull
        merged.turtle_soup_bear = merged.turtle_soup_bear or tr.turtle_soup_bear
        merged.killzone = merged.killzone or tr.killzone
        merged.session = tr.session if tr.killzone else merged.session
        if tr.sweep_bull:
            merged.long_score += 1
            merged.long_notes.append("15m:sweep")
        if tr.sweep_bear:
            merged.short_score += 1
            merged.short_notes.append("15m:sweep")
        if tr.internal_event != "none":
            before_l, before_s = len(merged.long_notes), len(merged.short_notes)
            _score_event(merged, tr.internal_event, "internal")
            for i in range(before_l, len(merged.long_notes)):
                merged.long_notes[i] = f"15m:{merged.long_notes[i]}"
            for i in range(before_s, len(merged.short_notes)):
                merged.short_notes[i] = f"15m:{merged.short_notes[i]}"
        if tr.turtle_soup_bull:
            merged.long_score += 1
            merged.long_notes.append("15m:turtle_soup")
        if tr.turtle_soup_bear:
            merged.short_score += 1
            merged.short_notes.append("15m:turtle_soup")
        for ob in tr.breaker_blocks:
            if ob.side == "bull" and not ob.mitigated:
                merged.long_score += 1
                merged.long_notes.append("15m:breaker_bull")
            if ob.side == "bear" and not ob.mitigated:
                merged.short_score += 1
                merged.short_notes.append("15m:breaker_bear")
        cf = candle_features(trigger)
        if cf["bull_engulf"]:
            merged.long_score += 1
            merged.long_notes.append("15m:bull_engulf")
        if cf["bear_engulf"]:
            merged.short_score += 1
            merged.short_notes.append("15m:bear_engulf")

    price = float(trigger["close"].iloc[-1]) if trigger is not None and len(trigger) else 0.0
    merged.confluence_long = _compute_confluence(merged, price, "long")
    merged.confluence_short = _compute_confluence(merged, price, "short")
    merged.setup_grade_long = _setup_grade(merged.confluence_long, merged.long_score)
    merged.setup_grade_short = _setup_grade(merged.confluence_short, merged.short_score)
    return merged
