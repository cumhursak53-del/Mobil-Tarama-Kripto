from __future__ import annotations

from typing import Optional

from engine.types import Signal, Side, Stage
from strategies.base import MarketContext, Strategy
from strategies.helpers import make_signal, valid_row
from structure.core import broken_above, broken_below, candle_features, last_pivots, nearest_level, support_resistance


class PiyasaEvresi(Strategy):
    name = ledger = "Kasa_PiyasaEvresi"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("1h")
        daily = ctx.tf("1d")
        if not valid_row(df, ("close",)) or daily is None:
            return None
        close = float(df["close"].iloc[-1])
        cf = candle_features(df)
        supports, resistances = support_resistance(daily if len(daily) > 40 else df)
        ema20 = float(df["ema20"].iloc[-1]) if "ema20" in df.columns else close
        pulled_up = close <= ema20 * 1.008 and float(df["low"].iloc[-1]) <= ema20
        pulled_dn = close >= ema20 * 0.992 and float(df["high"].iloc[-1]) >= ema20
        if ctx.stage == Stage.ADVANCING and ctx.aligned(Side.BUY) and cf["bullish"] and pulled_up:
            return make_signal(self.ledger, "[STRAT: Evre_Advancing_Long]", df, Side.BUY)
        if ctx.stage == Stage.DECLINING and ctx.aligned(Side.SELL) and cf["bearish"] and pulled_dn:
            return make_signal(self.ledger, "[STRAT: Evre_Declining_Short]", df, Side.SELL)
        if ctx.stage in (Stage.ACCUMULATION, Stage.DISTRIBUTION):
            res = nearest_level(close, resistances, 0.005)
            sup = nearest_level(close, supports, 0.005)
            if sup and (cf["hammer"] or cf["bull_engulf"]):
                return make_signal(self.ledger, "[STRAT: Evre_Range_Long]", df, Side.BUY, sl=sup * 0.99)
            if res and (cf["shooting_star"] or cf["bear_engulf"]):
                return make_signal(self.ledger, "[STRAT: Evre_Range_Short]", df, Side.SELL, sl=res * 1.01)
        return None


class MumOnay(Strategy):
    name = ledger = "Kasa_MumOnay"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("1h")
        setup = ctx.tf("4h")
        if not valid_row(df, ("close",)):
            return None
        cf = candle_features(df)
        src = setup if setup is not None and len(setup) > 40 else df
        supports, resistances = support_resistance(src)
        close = float(df["close"].iloc[-1])
        if (cf["hammer"] or cf["bull_engulf"]) and nearest_level(close, supports, 0.008):
            if ctx.aligned(Side.BUY):
                return make_signal(self.ledger, "[STRAT: Mum_Destek_Long]", df, Side.BUY)
        if (cf["shooting_star"] or cf["bear_engulf"]) and nearest_level(close, resistances, 0.008):
            if ctx.aligned(Side.SELL):
                return make_signal(self.ledger, "[STRAT: Mum_Direnc_Short]", df, Side.SELL)
        return None


class YapiKirilim(Strategy):
    name = ledger = "Kasa_YapiKirilim"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("1h")
        setup = ctx.tf("4h")
        if not valid_row(df, ("close", "volume")) or setup is None:
            return None
        highs = last_pivots(setup, "high", 4)
        lows = last_pivots(setup, "low", 4)
        if len(highs) >= 2 and broken_above(setup, highs[-1][1]) and ctx.aligned(Side.BUY):
            if float(setup["volume"].iloc[-1]) > float(setup["vol_sma"].iloc[-1]):
                return make_signal(self.ledger, "[STRAT: BOS_High_Long]", df, Side.BUY, sl=lows[-1][1] if lows else None)
        if len(lows) >= 2 and broken_below(setup, lows[-1][1]) and ctx.aligned(Side.SELL):
            if float(setup["volume"].iloc[-1]) > float(setup["vol_sma"].iloc[-1]):
                return make_signal(self.ledger, "[STRAT: BOS_Low_Short]", df, Side.SELL, sl=highs[-1][1] if highs else None)
        return None
