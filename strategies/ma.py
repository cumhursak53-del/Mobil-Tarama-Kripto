from __future__ import annotations

from typing import Optional

from engine.types import Signal, Side, Stage
from strategies.base import MarketContext, Strategy
from strategies.helpers import make_signal, near, valid_row
from structure.core import candle_features, fib_retracement, validated_impulse


class SMA9_14(Strategy):
    name = ledger = "Kasa_SMA9_14"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("1h")
        h4 = ctx.tf("4h")
        if not valid_row(df, ("sma9_cross_up", "sma9_cross_down", "close", "sma50")):
            return None
        row = df.iloc[-1]
        h4_bull = h4 is not None and len(h4) >= 50 and float(h4["close"].iloc[-1]) > float(h4["sma50"].iloc[-1])
        h4_bear = h4 is not None and len(h4) >= 50 and float(h4["close"].iloc[-1]) < float(h4["sma50"].iloc[-1])
        if bool(row["sma9_cross_up"]) and h4_bull and ctx.aligned(Side.BUY):
            return make_signal(self.ledger, "[STRAT: SMA9_14_Long]", df, Side.BUY, trail_at_r=1.5)
        if bool(row["sma9_cross_down"]) and h4_bear and ctx.aligned(Side.SELL):
            return make_signal(self.ledger, "[STRAT: SMA9_14_Short]", df, Side.SELL, trail_at_r=1.5)
        return None


class EMAFib(Strategy):
    name = ledger = "Kasa_EMA_Fib"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("1h")
        daily = ctx.tf("1d")
        setup = ctx.tf("4h")
        if not valid_row(df, ("ema21_cross_up", "ema21_cross_down", "ema55", "close")):
            return None
        if daily is None or len(daily) < 200 or "sma200" not in daily.columns:
            return None
        row = df.iloc[-1]
        dclose = float(daily["close"].iloc[-1])
        dsma = float(daily["sma200"].iloc[-1])
        close = float(row["close"])
        fib_ok_long = fib_ok_short = True
        if setup is not None and len(setup) >= 40:
            impulse = validated_impulse(setup)
            if impulse:
                lo, hi, direction = impulse
                levels = fib_retracement(lo, hi, direction)
                zlo, zhi = levels.get("0.5"), levels.get("0.618")
                if direction == "up" and zlo and zhi:
                    fib_ok_long = min(zlo, zhi) <= close <= max(zlo, zhi) * 1.004
                if direction == "down" and zlo and zhi:
                    fib_ok_short = min(zlo, zhi) * 0.996 <= close <= max(zlo, zhi)
        if bool(row["ema21_cross_up"]) and dclose > dsma and fib_ok_long and ctx.aligned(Side.BUY):
            return make_signal(self.ledger, "[STRAT: EMA21_55_FibLong]", df, Side.BUY, strength=2.5)
        if bool(row["ema21_cross_down"]) and dclose < dsma and fib_ok_short and ctx.aligned(Side.SELL):
            return make_signal(self.ledger, "[STRAT: EMA21_55_FibShort]", df, Side.SELL, strength=2.5)
        return None


class DinamikMA(Strategy):
    name = ledger = "Kasa_DinamikMA"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("1h")
        setup = ctx.tf("4h")
        if not valid_row(df, ("ema20", "ema50", "close", "atr")):
            return None
        close = float(df["close"].iloc[-1])
        ema20 = float(setup["ema20"].iloc[-1]) if setup is not None and "ema20" in setup.columns else float(df["ema20"].iloc[-1])
        ema50 = float(setup["ema50"].iloc[-1]) if setup is not None and "ema50" in setup.columns else float(df["ema50"].iloc[-1])
        cf = candle_features(df)
        src = setup if setup is not None and len(setup) >= 40 else df
        impulse = validated_impulse(src)
        in_pullback = True
        if impulse:
            lo, hi, direction = impulse
            diff = hi - lo
            if direction == "up" and diff > 0:
                pct = (hi - close) / diff
                in_pullback = 0.38 <= pct <= 0.618
            elif direction == "down" and diff > 0:
                pct = (close - lo) / diff
                in_pullback = 0.38 <= pct <= 0.618
        if ctx.stage == Stage.ADVANCING and ctx.aligned(Side.BUY) and in_pullback:
            if (near(close, ema20, 0.006) or near(close, ema50, 0.006)) and (cf["hammer"] or cf["pin_bull"] or cf["bullish"]):
                if close >= min(ema20, ema50):
                    return make_signal(self.ledger, "[STRAT: DinamikMA_Long]", df, Side.BUY, sl=ema50 * 0.992)
        if ctx.stage == Stage.DECLINING and ctx.aligned(Side.SELL) and in_pullback:
            if (near(close, ema20, 0.006) or near(close, ema50, 0.006)) and (cf["shooting_star"] or cf["pin_bear"] or cf["bearish"]):
                if close <= max(ema20, ema50):
                    return make_signal(self.ledger, "[STRAT: DinamikMA_Short]", df, Side.SELL, sl=ema50 * 1.008)
        return None
