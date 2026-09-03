from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from engine.types import Side, Stage
from strategies.base import MarketContext
from strategies.helpers import valid_row
from structure.core import broken_above, broken_below, hh_hl, last_pivots, lh_ll, volume_ok


MIN_TRADE_SCORE = 4


@dataclass
class MomentumScore:
    symbol: str
    long_score: int = 0
    short_score: int = 0
    long_notes: list[str] = field(default_factory=list)
    short_notes: list[str] = field(default_factory=list)

    @property
    def best_side(self) -> str:
        if self.long_score >= MIN_TRADE_SCORE and self.long_score > self.short_score:
            return Side.BUY.value
        if self.short_score >= MIN_TRADE_SCORE and self.short_score > self.long_score:
            return Side.SELL.value
        if self.long_score >= self.short_score and self.long_score >= 3:
            return "WATCH_LONG"
        if self.short_score > self.long_score and self.short_score >= 3:
            return "WATCH_SHORT"
        return "NONE"

    @property
    def best_score(self) -> int:
        return max(self.long_score, self.short_score)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "long_score": self.long_score,
            "short_score": self.short_score,
            "best_side": self.best_side,
            "best_score": self.best_score,
            "long_notes": " | ".join(self.long_notes),
            "short_notes": " | ".join(self.short_notes),
        }


def _squeeze(df) -> bool:
    if not valid_row(df, ("bb_width", "bb_width_med")):
        return False
    row = df.iloc[-1]
    return float(row["bb_width"]) < float(row["bb_width_med"]) * 0.85


def _momentum_up(df) -> bool:
    if not valid_row(df, ("macd_cross_up", "macd_hist")):
        return False
    return bool(df["macd_cross_up"].iloc[-1]) and float(df["macd_hist"].iloc[-1]) > 0


def _momentum_down(df) -> bool:
    if not valid_row(df, ("macd_cross_down", "macd_hist")):
        return False
    return bool(df["macd_cross_down"].iloc[-1]) and float(df["macd_hist"].iloc[-1]) < 0


def score_momentum(ctx: MarketContext) -> MomentumScore:
    """MTF patlama (long) / selale (short) skoru: 1D yon, 4H setup, 1H kirilim, hacim, 15M tetik."""
    out = MomentumScore(symbol=ctx.symbol)
    daily = ctx.tf("1d")
    h4 = ctx.tf("4h")
    h1 = ctx.tf("1h")
    m15 = ctx.tf("15m")

    if ctx.stage == Stage.ADVANCING:
        out.long_score += 1
        out.long_notes.append("1D:yukselis")
    elif ctx.stage == Stage.DECLINING:
        out.short_score += 1
        out.short_notes.append("1D:dusus")
    elif ctx.stage == Stage.ACCUMULATION:
        out.long_score += 1
        out.long_notes.append("1D:birikim")
    elif ctx.stage == Stage.DISTRIBUTION:
        out.short_score += 1
        out.short_notes.append("1D:dagitim")

    if ctx.week_bias == 1:
        out.long_score += 1
        out.long_notes.append("1W:boğa")
    elif ctx.week_bias == -1:
        out.short_score += 1
        out.short_notes.append("1W:ayı")

    if h4 is not None and len(h4) >= 40:
        is_hh, is_hl = hh_hl(h4)
        is_lh, is_ll = lh_ll(h4)
        if is_hh and is_hl:
            out.long_score += 1
            out.long_notes.append("4H:HH-HL")
        if is_lh and is_ll:
            out.short_score += 1
            out.short_notes.append("4H:LH-LL")
        if _squeeze(h4):
            out.long_score += 1
            out.short_score += 1
            out.long_notes.append("4H:sikisma")
            out.short_notes.append("4H:sikisma")
        highs = last_pivots(h4, "high", 4)
        lows = last_pivots(h4, "low", 4)
        if len(highs) >= 2 and broken_above(h4, highs[-1][1]):
            out.long_score += 1
            out.long_notes.append("4H:direnc_kirildi")
        if len(lows) >= 2 and broken_below(h4, lows[-1][1]):
            out.short_score += 1
            out.short_notes.append("4H:destek_kirildi")
        if volume_ok(h4):
            close = float(h4["close"].iloc[-1])
            if highs and close > highs[-1][1]:
                out.long_score += 1
                out.long_notes.append("4H:hacimli_yukari")
            if lows and close < lows[-1][1]:
                out.short_score += 1
                out.short_notes.append("4H:hacimli_asagi")

    if h1 is not None and len(h1) >= 30:
        highs = last_pivots(h1, "high", 3)
        lows = last_pivots(h1, "low", 3)
        if len(highs) >= 2 and broken_above(h1, highs[-1][1]) and volume_ok(h1):
            out.long_score += 1
            out.long_notes.append("1H:kirilim+hacim")
        if len(lows) >= 2 and broken_below(h1, lows[-1][1]) and volume_ok(h1):
            out.short_score += 1
            out.short_notes.append("1H:kirilim+hacim")
        if valid_row(h1, ("stoch_k", "stoch_cross_down")):
            k = float(h1["stoch_k"].iloc[-1])
            if bool(h1["stoch_cross_down"].iloc[-1]) and k > 75:
                out.short_score += 1
                out.short_notes.append("1H:stoch_OB")
        if valid_row(h1, ("stoch_k", "stoch_cross_up")):
            k = float(h1["stoch_k"].iloc[-1])
            if bool(h1["stoch_cross_up"].iloc[-1]) and k < 25:
                out.long_score += 1
                out.long_notes.append("1H:stoch_OS")

    if m15 is not None and len(m15) >= 30:
        if _momentum_up(m15):
            out.long_score += 1
            out.long_notes.append("15M:macd_up")
        if _momentum_down(m15):
            out.short_score += 1
            out.short_notes.append("15M:macd_down")

    return out


def trade_signal_from_score(score: MomentumScore) -> Optional[Side]:
    if score.long_score >= MIN_TRADE_SCORE and score.long_score > score.short_score:
        return Side.BUY
    if score.short_score >= MIN_TRADE_SCORE and score.short_score > score.long_score:
        return Side.SELL
    return None
