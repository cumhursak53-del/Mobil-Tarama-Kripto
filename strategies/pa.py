from __future__ import annotations

from typing import Optional

from engine.types import Signal, Side, Stage
from strategies.base import MarketContext, Strategy
from strategies.helpers import make_signal, valid_row
from structure.core import (
    candle_features,
    displacement_bar,
    last_pivots,
    nearest_level,
    structure_event,
    support_resistance,
    volume_ok,
)
from structure.wyckoff import wyckoff_spring, wyckoff_upthrust


class PiyasaEvresi(Strategy):
    name = ledger = "Kasa_PiyasaEvresi"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("1h")
        daily = ctx.tf("1d")
        if not valid_row(df, ("close", "volume", "vol_sma")) or daily is None:
            return None
        close = float(df["close"].iloc[-1])
        cf = candle_features(df)
        vol_rising = float(df["volume"].iloc[-1]) > float(df["vol_sma"].iloc[-1])
        supports, resistances = support_resistance(daily if len(daily) > 40 else df)
        ema20 = float(df["ema20"].iloc[-1]) if "ema20" in df.columns else close
        pulled_up = close <= ema20 * 1.008 and float(df["low"].iloc[-1]) <= ema20
        pulled_dn = close >= ema20 * 0.992 and float(df["high"].iloc[-1]) >= ema20
        if ctx.stage == Stage.ADVANCING and ctx.aligned(Side.BUY) and cf["bullish"] and pulled_up and vol_rising:
            return make_signal(self.ledger, "[STRAT: Evre_Advancing_Long]", df, Side.BUY)
        if ctx.stage == Stage.DECLINING and ctx.aligned(Side.SELL) and cf["bearish"] and pulled_dn and vol_rising:
            return make_signal(self.ledger, "[STRAT: Evre_Declining_Short]", df, Side.SELL)
        if ctx.stage in (Stage.ACCUMULATION, Stage.DISTRIBUTION):
            res = nearest_level(close, resistances, 0.005)
            sup = nearest_level(close, supports, 0.005)
            if ctx.stage == Stage.ACCUMULATION and wyckoff_spring(daily if len(daily) > 40 else df) and ctx.aligned(Side.BUY):
                sl = float(df["low"].iloc[-1]) * 0.995
                return make_signal(self.ledger, "[STRAT: Evre_Wyckoff_Spring]", df, Side.BUY, sl=sl, strength=3.0)
            if ctx.stage == Stage.DISTRIBUTION and wyckoff_upthrust(daily if len(daily) > 40 else df) and ctx.aligned(Side.SELL):
                sl = float(df["high"].iloc[-1]) * 1.005
                return make_signal(self.ledger, "[STRAT: Evre_Wyckoff_Upthrust]", df, Side.SELL, sl=sl, strength=3.0)
            if sup and (cf["hammer"] or cf["pin_bull"] or cf["bull_engulf"]):
                return make_signal(self.ledger, "[STRAT: Evre_Range_Long]", df, Side.BUY, sl=sup * 0.99)
            if res and (cf["shooting_star"] or cf["pin_bear"] or cf["bear_engulf"]):
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
        bull_pat = cf["hammer"] or cf["bull_engulf"] or cf["pin_bull"] or cf["inside_bar"]
        bear_pat = cf["shooting_star"] or cf["bear_engulf"] or cf["pin_bear"] or cf["inside_bar"]
        if bull_pat and nearest_level(close, supports, 0.008):
            if ctx.aligned(Side.BUY):
                return make_signal(self.ledger, "[STRAT: Mum_Destek_Long]", df, Side.BUY, strength=2.0)
        if bear_pat and nearest_level(close, resistances, 0.008):
            if ctx.aligned(Side.SELL):
                return make_signal(self.ledger, "[STRAT: Mum_Direnc_Short]", df, Side.SELL, strength=2.0)
        return None


class YapiKirilim(Strategy):
    name = ledger = "Kasa_YapiKirilim"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("1h")
        setup = ctx.tf("4h")
        if not valid_row(df, ("close", "volume")) or setup is None:
            return None
        evt = structure_event(setup, "external")
        lows = last_pivots(setup, "low", 4)
        highs = last_pivots(setup, "high", 4)
        if evt in ("bos_bull", "choch_bull") and displacement_bar(setup) and volume_ok(setup) and ctx.aligned(Side.BUY):
            sl = lows[-1][1] if lows else None
            return make_signal(self.ledger, "[STRAT: BOS_High_Long]", df, Side.BUY, sl=sl, tp_r_val=2.5, strength=2.5)
        if evt in ("bos_bear", "choch_bear") and displacement_bar(setup) and volume_ok(setup) and ctx.aligned(Side.SELL):
            sl = highs[-1][1] if highs else None
            return make_signal(self.ledger, "[STRAT: BOS_Low_Short]", df, Side.SELL, sl=sl, tp_r_val=2.5, strength=2.5)
        return None
