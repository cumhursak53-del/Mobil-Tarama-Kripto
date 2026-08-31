from __future__ import annotations

from typing import Optional

from engine.types import Signal, Side
from strategies.base import MarketContext, Strategy
from strategies.helpers import make_signal, valid_row
from structure.core import last_pivots, volume_ok


def _rel(a: float, b: float, tol: float = 0.015) -> bool:
    return abs(a - b) / max(abs(b), 1e-12) <= tol


class OBOTOBO(Strategy):
    name = ledger = "Kasa_OBO_TOBO"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("4h")
        trig = ctx.tf("1h")
        if not valid_row(df, ("close",)) or trig is None:
            return None
        highs = last_pivots(df, "high", 6)
        lows = last_pivots(df, "low", 6)
        # OBO: 3 highs, middle highest; neck = avg of 2 troughs between
        if len(highs) >= 3 and len(lows) >= 2:
            l, h, r = highs[-3], highs[-2], highs[-1]
            if h[1] > l[1] and h[1] > r[1] and _rel(l[1], r[1], 0.03) and l[0] < h[0] < r[0]:
                troughs = [p for p in lows if l[0] < p[0] < r[0]]
                if len(troughs) >= 2:
                    neck = (troughs[0][1] + troughs[-1][1]) / 2.0
                    if float(df["close"].iloc[-1]) < neck and float(df["close"].iloc[-2]) >= neck and volume_ok(df):
                        if ctx.aligned(Side.SELL):
                            target = neck - (h[1] - neck)
                            sig = make_signal(self.ledger, "[STRAT: OBO_Short]", trig, Side.SELL, sl=h[1])
                            if sig:
                                sig.tp_price = target
                            return sig
        # TOBO: 3 lows, middle lowest
        if len(lows) >= 3 and len(highs) >= 2:
            l, h, r = lows[-3], lows[-2], lows[-1]
            if h[1] < l[1] and h[1] < r[1] and _rel(l[1], r[1], 0.03) and l[0] < h[0] < r[0]:
                peaks = [p for p in highs if l[0] < p[0] < r[0]]
                if len(peaks) >= 2:
                    neck = (peaks[0][1] + peaks[-1][1]) / 2.0
                    if float(df["close"].iloc[-1]) > neck and float(df["close"].iloc[-2]) <= neck and volume_ok(df):
                        if ctx.aligned(Side.BUY):
                            target = neck + (neck - h[1])
                            sig = make_signal(self.ledger, "[STRAT: TOBO_Long]", trig, Side.BUY, sl=h[1])
                            if sig:
                                sig.tp_price = target
                            return sig
        return None


class IkiliDipTepe(Strategy):
    name = ledger = "Kasa_IkiliDipTepe"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("4h")
        trig = ctx.tf("1h")
        if not valid_row(df, ("close",)) or trig is None:
            return None
        lows = last_pivots(df, "low", 5)
        highs = last_pivots(df, "high", 5)
        if len(lows) >= 2 and len(highs) >= 1:
            a, b = lows[-2], lows[-1]
            if _rel(a[1], b[1], 0.012) and b[0] - a[0] >= 8:
                neck_cands = [p for p in highs if a[0] < p[0] < b[0]]
                if neck_cands:
                    neck = max(neck_cands, key=lambda x: x[1])[1]
                    if float(df["close"].iloc[-1]) > neck and float(df["close"].iloc[-2]) <= neck and volume_ok(df):
                        if ctx.aligned(Side.BUY):
                            target = neck + (neck - min(a[1], b[1]))
                            sig = make_signal(self.ledger, "[STRAT: IkiliDip_Long]", trig, Side.BUY, sl=min(a[1], b[1]) * 0.995)
                            if sig:
                                sig.tp_price = target
                            return sig
        if len(highs) >= 2 and len(lows) >= 1:
            a, b = highs[-2], highs[-1]
            if _rel(a[1], b[1], 0.012) and b[0] - a[0] >= 8:
                neck_cands = [p for p in lows if a[0] < p[0] < b[0]]
                if neck_cands:
                    neck = min(neck_cands, key=lambda x: x[1])[1]
                    if float(df["close"].iloc[-1]) < neck and float(df["close"].iloc[-2]) >= neck and volume_ok(df):
                        if ctx.aligned(Side.SELL):
                            target = neck - (max(a[1], b[1]) - neck)
                            sig = make_signal(self.ledger, "[STRAT: IkiliTepe_Short]", trig, Side.SELL, sl=max(a[1], b[1]) * 1.005)
                            if sig:
                                sig.tp_price = target
                            return sig
        return None


class Ucgen(Strategy):
    name = ledger = "Kasa_Ucgen"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("4h")
        trig = ctx.tf("1h")
        if not valid_row(df, ("close",)) or trig is None:
            return None
        highs = last_pivots(df, "high", 5)
        lows = last_pivots(df, "low", 5)
        if len(highs) < 3 or len(lows) < 3:
            return None
        h_slope = highs[-1][1] < highs[-3][1]
        l_slope = lows[-1][1] > lows[-3][1]
        width = highs[-3][1] - lows[-3][1]
        if width <= 0:
            return None
        close = float(df["close"].iloc[-1])
        upper = highs[-1][1]
        lower = lows[-1][1]
        if h_slope and l_slope:  # symmetric / coil
            if close > upper and volume_ok(df) and ctx.aligned(Side.BUY):
                sig = make_signal(self.ledger, "[STRAT: Ucgen_Long]", trig, Side.BUY, sl=lower)
                if sig:
                    sig.tp_price = close + width
                return sig
            if close < lower and volume_ok(df) and ctx.aligned(Side.SELL):
                sig = make_signal(self.ledger, "[STRAT: Ucgen_Short]", trig, Side.SELL, sl=upper)
                if sig:
                    sig.tp_price = close - width
                return sig
        return None


class BayrakFlama(Strategy):
    name = ledger = "Kasa_BayrakFlama"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("1h")
        if not valid_row(df, ("close", "atr", "body")) or len(df) < 30:
            return None
        # pole: strong directional move over 3-8 bars, then 4-12 bar consolidation
        closes = df["close"]
        for pole_len in (5, 6, 7, 8):
            if len(df) < pole_len + 8:
                continue
            pole = closes.iloc[-8 - pole_len:-8]
            cons = df.iloc[-8:]
            pole_ret = float(pole.iloc[-1] / pole.iloc[0] - 1)
            cons_high, cons_low = float(cons["high"].max()), float(cons["low"].min())
            cons_w = (cons_high - cons_low) / float(cons["close"].iloc[-1])
            if cons_w > 0.04:
                continue
            close = float(df["close"].iloc[-1])
            if pole_ret > 0.04 and close > cons_high and volume_ok(df) and ctx.aligned(Side.BUY):
                sig = make_signal(self.ledger, "[STRAT: Bayrak_Long]", df, Side.BUY, sl=cons_low)
                if sig:
                    sig.tp_price = close + abs(float(pole.iloc[-1]) - float(pole.iloc[0]))
                return sig
            if pole_ret < -0.04 and close < cons_low and volume_ok(df) and ctx.aligned(Side.SELL):
                sig = make_signal(self.ledger, "[STRAT: Bayrak_Short]", df, Side.SELL, sl=cons_high)
                if sig:
                    sig.tp_price = close - abs(float(pole.iloc[-1]) - float(pole.iloc[0]))
                return sig
        return None


class Dortgen(Strategy):
    name = ledger = "Kasa_Dortgen"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("4h")
        trig = ctx.tf("1h")
        if not valid_row(df, ("close",)) or trig is None:
            return None
        highs = last_pivots(df, "high", 6)
        lows = last_pivots(df, "low", 6)
        if len(highs) < 2 or len(lows) < 2:
            return None
        top = sum(p[1] for p in highs[-2:]) / 2.0
        bot = sum(p[1] for p in lows[-2:]) / 2.0
        if not _rel(highs[-1][1], highs[-2][1], 0.012) or not _rel(lows[-1][1], lows[-2][1], 0.012):
            return None
        height = top - bot
        if height / bot < 0.015:
            return None
        close, prev = float(df["close"].iloc[-1]), float(df["close"].iloc[-2])
        if prev <= top < close and volume_ok(df) and ctx.aligned(Side.BUY):
            sig = make_signal(self.ledger, "[STRAT: Dortgen_Long]", trig, Side.BUY, sl=bot)
            if sig:
                sig.tp_price = close + height
            return sig
        if prev >= bot > close and volume_ok(df) and ctx.aligned(Side.SELL):
            sig = make_signal(self.ledger, "[STRAT: Dortgen_Short]", trig, Side.SELL, sl=top)
            if sig:
                sig.tp_price = close - height
            return sig
        return None


class FincanCanak(Strategy):
    name = ledger = "Kasa_FincanCanak"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("4h")
        trig = ctx.tf("1h")
        if not valid_row(df, ("close",)) or trig is None or len(df) < 40:
            return None
        window = df.iloc[-36:]
        lows = window["low"]
        mid = lows.idxmin()
        mid_pos = list(window.index).index(mid)
        if mid_pos < 8 or mid_pos > 28:
            return None
        left = float(window["high"].iloc[:mid_pos].max())
        right = float(window["high"].iloc[mid_pos:].max())
        bottom = float(lows.min())
        if not _rel(left, right, 0.04):
            return None
        # U not V: bottom region should be rounded (several bars near low)
        near_bot = (window["low"] < bottom * 1.02).sum()
        if near_bot < 3:
            return None
        rim = (left + right) / 2.0
        close, prev = float(df["close"].iloc[-1]), float(df["close"].iloc[-2])
        if prev <= rim < close and volume_ok(df) and ctx.aligned(Side.BUY):
            sig = make_signal(self.ledger, "[STRAT: FincanCanak_Long]", trig, Side.BUY, sl=bottom)
            if sig:
                sig.tp_price = close + (rim - bottom)
            return sig
        return None


class Takoz(Strategy):
    name = ledger = "Kasa_Takoz"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("4h")
        trig = ctx.tf("1h")
        if not valid_row(df, ("close",)) or trig is None:
            return None
        highs = last_pivots(df, "high", 4)
        lows = last_pivots(df, "low", 4)
        if len(highs) < 3 or len(lows) < 3:
            return None
        falling_h = highs[-1][1] < highs[-3][1]
        falling_l = lows[-1][1] < lows[-3][1]
        rising_h = highs[-1][1] > highs[-3][1]
        rising_l = lows[-1][1] > lows[-3][1]
        narrowing = (highs[-1][1] - lows[-1][1]) < (highs[-3][1] - lows[-3][1])
        close = float(df["close"].iloc[-1])
        if falling_h and falling_l and narrowing and close > highs[-1][1] and volume_ok(df) and ctx.aligned(Side.BUY):
            return make_signal(self.ledger, "[STRAT: AlcalanTakoz_Long]", trig, Side.BUY, sl=lows[-1][1])
        if rising_h and rising_l and narrowing and close < lows[-1][1] and volume_ok(df) and ctx.aligned(Side.SELL):
            return make_signal(self.ledger, "[STRAT: YukselenTakoz_Short]", trig, Side.SELL, sl=highs[-1][1])
        return None
