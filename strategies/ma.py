from __future__ import annotations

from typing import Optional

from engine.types import Signal, Side, Stage
from strategies.base import MarketContext, Strategy
from strategies.helpers import make_signal, near, valid_row
from structure.core import candle_features


class SMA9_14(Strategy):
    name = ledger = "Kasa_SMA9_14"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("1h")
        if not valid_row(df, ("sma9_cross_up", "sma9_cross_down")):
            return None
        row = df.iloc[-1]
        if bool(row["sma9_cross_up"]) and ctx.aligned(Side.BUY):
            return make_signal(self.ledger, "[STRAT: SMA9_14_Long]", df, Side.BUY)
        if bool(row["sma9_cross_down"]) and ctx.aligned(Side.SELL):
            return make_signal(self.ledger, "[STRAT: SMA9_14_Short]", df, Side.SELL)
        return None


class EMAFib(Strategy):
    name = ledger = "Kasa_EMA_Fib"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("1h")
        daily = ctx.tf("1d")
        if not valid_row(df, ("ema21_cross_up", "ema21_cross_down", "ema55")):
            return None
        row = df.iloc[-1]
        dclose = float(daily["close"].iloc[-1]) if daily is not None and len(daily) else None
        dsma = float(daily["sma200"].iloc[-1]) if daily is not None and "sma200" in daily.columns and len(daily) else None
        if bool(row["ema21_cross_up"]) and ctx.aligned(Side.BUY):
            if dsma is None or dclose is None or dclose > dsma:
                return make_signal(self.ledger, "[STRAT: EMA21_55_Long]", df, Side.BUY)
        if bool(row["ema21_cross_down"]) and ctx.aligned(Side.SELL):
            if dsma is None or dclose is None or dclose < dsma:
                return make_signal(self.ledger, "[STRAT: EMA21_55_Short]", df, Side.SELL)
        return None


class DinamikMA(Strategy):
    name = ledger = "Kasa_DinamikMA"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("1h")
        setup = ctx.tf("4h")
        if not valid_row(df, ("ema20", "ema50", "close")):
            return None
        close = float(df["close"].iloc[-1])
        ema20 = float(setup["ema20"].iloc[-1]) if setup is not None and "ema20" in setup.columns else float(df["ema20"].iloc[-1])
        ema50 = float(setup["ema50"].iloc[-1]) if setup is not None and "ema50" in setup.columns else float(df["ema50"].iloc[-1])
        cf = candle_features(df)
        if ctx.stage == Stage.ADVANCING and ctx.aligned(Side.BUY):
            if (near(close, ema20, 0.006) or near(close, ema50, 0.006)) and (cf["hammer"] or cf["bull_engulf"] or cf["bullish"]):
                if close >= min(ema20, ema50):
                    return make_signal(self.ledger, "[STRAT: DinamikMA_Long]", df, Side.BUY)
        if ctx.stage == Stage.DECLINING and ctx.aligned(Side.SELL):
            if (near(close, ema20, 0.006) or near(close, ema50, 0.006)) and (cf["shooting_star"] or cf["bear_engulf"] or cf["bearish"]):
                if close <= max(ema20, ema50):
                    return make_signal(self.ledger, "[STRAT: DinamikMA_Short]", df, Side.SELL)
        return None
