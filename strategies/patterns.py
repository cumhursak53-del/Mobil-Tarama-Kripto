from __future__ import annotations

from typing import Optional

from engine.types import Signal, Side
from strategies.base import MarketContext, Strategy
from strategies.helpers import make_signal, valid_row
from structure.core import last_pivots, volume_ok
from structure.patterns import (
    detect_double_bottom,
    detect_double_top,
    detect_flag,
    detect_head_shoulders,
    detect_inverse_hs,
    detect_rectangle,
)


class OBOTOBO(Strategy):
    name = ledger = "Kasa_OBO_TOBO"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("4h")
        trig = ctx.tf("1h")
        if not valid_row(df, ("close",)) or trig is None:
            return None
        obo = detect_head_shoulders(df)
        if obo and float(df["close"].iloc[-1]) < obo["neck"] and float(df["close"].iloc[-2]) >= obo["neck"] and volume_ok(df):
            if ctx.aligned(Side.SELL):
                sig = make_signal(self.ledger, "[STRAT: OBO_Short]", trig, Side.SELL, sl=obo["invalidation"], tp_price=obo["target"], tp_mode="measured_move", strength=3.0)
                return sig
        tobo = detect_inverse_hs(df)
        if tobo and float(df["close"].iloc[-1]) > tobo["neck"] and float(df["close"].iloc[-2]) <= tobo["neck"] and volume_ok(df):
            if ctx.aligned(Side.BUY):
                sig = make_signal(self.ledger, "[STRAT: TOBO_Long]", trig, Side.BUY, sl=tobo["invalidation"], tp_price=tobo["target"], tp_mode="measured_move", strength=3.0)
                return sig
        return None


class IkiliDipTepe(Strategy):
    name = ledger = "Kasa_IkiliDipTepe"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("4h")
        trig = ctx.tf("1h")
        if not valid_row(df, ("close",)) or trig is None:
            return None
        db = detect_double_bottom(df)
        if db and float(df["close"].iloc[-1]) > db["neck"] and volume_ok(df) and ctx.aligned(Side.BUY):
            return make_signal(self.ledger, "[STRAT: IkiliDip_Long]", trig, Side.BUY, sl=db["invalidation"], tp_price=db["target"], tp_mode="measured_move", strength=2.5)
        dt = detect_double_top(df)
        if dt and float(df["close"].iloc[-1]) < dt["neck"] and volume_ok(df) and ctx.aligned(Side.SELL):
            return make_signal(self.ledger, "[STRAT: IkiliTepe_Short]", trig, Side.SELL, sl=dt["invalidation"], tp_price=dt["target"], tp_mode="measured_move", strength=2.5)
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
        asc = highs[-1][1] < highs[-2][1] and abs(lows[-1][1] - lows[-2][1]) / lows[-2][1] < 0.01
        desc = lows[-1][1] > lows[-2][1] and abs(highs[-1][1] - highs[-2][1]) / highs[-2][1] < 0.01
        width = highs[-3][1] - lows[-3][1]
        close = float(df["close"].iloc[-1])
        upper, lower = highs[-1][1], lows[-1][1]
        if width <= 0:
            return None
        if (h_slope and l_slope) or asc or desc:
            if close > upper and volume_ok(df) and ctx.aligned(Side.BUY):
                return make_signal(self.ledger, "[STRAT: Ucgen_Long]", trig, Side.BUY, sl=lower, tp_price=close + width, tp_mode="measured_move", strength=2.0)
            if close < lower and volume_ok(df) and ctx.aligned(Side.SELL):
                return make_signal(self.ledger, "[STRAT: Ucgen_Short]", trig, Side.SELL, sl=upper, tp_price=close - width, tp_mode="measured_move", strength=2.0)
        return None


class BayrakFlama(Strategy):
    name = ledger = "Kasa_BayrakFlama"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("1h")
        if not valid_row(df, ("close", "atr")):
            return None
        flag = detect_flag(df)
        if not flag:
            return None
        close = float(df["close"].iloc[-1])
        if flag["direction"] == "up" and close > flag["cons_high"] and volume_ok(df) and ctx.aligned(Side.BUY):
            return make_signal(self.ledger, "[STRAT: Bayrak_Long]", df, Side.BUY, sl=flag["cons_low"], tp_price=close + flag["pole_move"], tp_mode="measured_move", strength=2.5)
        if flag["direction"] == "down" and close < flag["cons_low"] and volume_ok(df) and ctx.aligned(Side.SELL):
            return make_signal(self.ledger, "[STRAT: Bayrak_Short]", df, Side.SELL, sl=flag["cons_high"], tp_price=close - flag["pole_move"], tp_mode="measured_move", strength=2.5)
        return None


class Dortgen(Strategy):
    name = ledger = "Kasa_Dortgen"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("4h")
        trig = ctx.tf("1h")
        if not valid_row(df, ("close",)) or trig is None:
            return None
        rect = detect_rectangle(df)
        if not rect:
            return None
        close, prev = float(df["close"].iloc[-1]), float(df["close"].iloc[-2])
        if prev <= rect["top"] < close and volume_ok(df) and ctx.aligned(Side.BUY):
            return make_signal(self.ledger, "[STRAT: Dortgen_Long]", trig, Side.BUY, sl=rect["bot"], tp_price=close + rect["height"], tp_mode="measured_move", strength=2.0)
        if prev >= rect["bot"] > close and volume_ok(df) and ctx.aligned(Side.SELL):
            return make_signal(self.ledger, "[STRAT: Dortgen_Short]", trig, Side.SELL, sl=rect["top"], tp_price=close - rect["height"], tp_mode="measured_move", strength=2.0)
        return None


class FincanCanak(Strategy):
    name = ledger = "Kasa_FincanCanak"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("4h")
        trig = ctx.tf("1h")
        if not valid_row(df, ("close", "volume", "vol_sma")) or trig is None or len(df) < 40:
            return None
        window = df.iloc[-36:]
        lows = window["low"]
        mid_pos = list(window.index).index(lows.idxmin())
        if mid_pos < 8 or mid_pos > 28:
            return None
        left = float(window["high"].iloc[:mid_pos].max())
        right = float(window["high"].iloc[mid_pos:].max())
        bottom = float(lows.min())
        if abs(left - right) / max(left, 1e-9) > 0.04:
            return None
        near_bot = (window["low"] < bottom * 1.02).sum()
        if near_bot < 3:
            return None
        vol_dry = float(window["volume"].iloc[mid_pos - 3:mid_pos + 3].mean()) < float(window["volume"].mean()) * 0.7
        handle = df.iloc[-6:]
        handle_range = (float(handle["high"].max()) - float(handle["low"].min())) / float(handle["close"].iloc[-1])
        rim = (left + right) / 2.0
        close, prev = float(df["close"].iloc[-1]), float(df["close"].iloc[-2])
        if vol_dry and handle_range < 0.03 and prev <= rim < close and volume_ok(df) and ctx.aligned(Side.BUY):
            return make_signal(self.ledger, "[STRAT: FincanCanak_Long]", trig, Side.BUY, sl=bottom, tp_price=close + (rim - bottom), tp_mode="measured_move", strength=2.5)
        return None


class Takoz(Strategy):
    name = ledger = "Kasa_Takoz"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("4h")
        trig = ctx.tf("1h")
        if not valid_row(df, ("close", "volume", "vol_sma")) or trig is None:
            return None
        highs = last_pivots(df, "high", 4)
        lows = last_pivots(df, "low", 4)
        if len(highs) < 3 or len(lows) < 3:
            return None
        narrowing = (highs[-1][1] - lows[-1][1]) < (highs[-3][1] - lows[-3][1])
        close = float(df["close"].iloc[-1])
        vol_spike = float(df["volume"].iloc[-1]) > float(df["vol_sma"].iloc[-1]) * 1.3
        if highs[-1][1] < highs[-3][1] and lows[-1][1] < lows[-3][1] and narrowing and close > highs[-1][1] and vol_spike and ctx.aligned(Side.BUY):
            height = highs[-3][1] - lows[-3][1]
            return make_signal(self.ledger, "[STRAT: AlcalanTakoz_Long]", trig, Side.BUY, sl=lows[-1][1], tp_price=close + height * 0.5, tp_mode="measured_move", strength=2.0)
        if highs[-1][1] > highs[-3][1] and lows[-1][1] > lows[-3][1] and narrowing and close < lows[-1][1] and vol_spike and ctx.aligned(Side.SELL):
            height = highs[-3][1] - lows[-3][1]
            return make_signal(self.ledger, "[STRAT: YukselenTakoz_Short]", trig, Side.SELL, sl=highs[-1][1], tp_price=close - height * 0.5, tp_mode="measured_move", strength=2.0)
        return None
