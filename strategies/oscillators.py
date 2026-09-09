from __future__ import annotations

from typing import Optional

from engine.types import Signal, Side, Stage
from strategies.base import MarketContext, Strategy
from strategies.helpers import make_signal, valid_row
from structure.core import hh_hl, last_pivots, lh_ll, volume_ok
from structure.divergence import rsi_divergence


class RSIUyumsuzluk(Strategy):
    name = ledger = "Kasa_RSI_Uyumsuzluk"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("1h")
        h4 = ctx.tf("4h")
        if not valid_row(df, ("rsi", "close")) or len(df) < 60:
            return None
        div = rsi_divergence(df, min_pivots=3)
        rsi_val = float(df["rsi"].iloc[-1])
        h4_bull = h4 is None or len(h4) < 30 or (hh_hl(h4)[0] and hh_hl(h4)[1])
        h4_bear = h4 is None or len(h4) < 30 or (lh_ll(h4)[0] and lh_ll(h4)[1])
        if div in ("regular_bull", "hidden_bull") and rsi_val < 50 and h4_bull and ctx.aligned(Side.BUY):
            tag = "RSI_PozitifUyumsuzluk" if div == "regular_bull" else "RSI_HiddenBull"
            return make_signal(self.ledger, f"[STRAT: {tag}]", df, Side.BUY, strength=3.0 if div == "regular_bull" else 2.5)
        if div in ("regular_bear", "hidden_bear") and rsi_val > 50 and h4_bear and ctx.aligned(Side.SELL):
            tag = "RSI_NegatifUyumsuzluk" if div == "regular_bear" else "RSI_HiddenBear"
            return make_signal(self.ledger, f"[STRAT: {tag}]", df, Side.SELL, strength=3.0 if div == "regular_bear" else 2.5)
        return None


class RSIBolge(Strategy):
    name = ledger = "Kasa_RSI_Bolge"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        if ctx.stage not in (Stage.ACCUMULATION, Stage.DISTRIBUTION, Stage.UNKNOWN):
            return None
        df = ctx.tf("1h")
        if not valid_row(df, ("rsi",)):
            return None
        r, prev = float(df["rsi"].iloc[-1]), float(df["rsi"].iloc[-2])
        if prev <= 30 < r and ctx.aligned(Side.BUY):
            return make_signal(self.ledger, "[STRAT: RSI_OversoldExit_Long]", df, Side.BUY)
        if prev >= 70 > r and ctx.aligned(Side.SELL):
            return make_signal(self.ledger, "[STRAT: RSI_OverboughtExit_Short]", df, Side.SELL)
        return None


class MACDCross(Strategy):
    name = ledger = "Kasa_MACD"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("1h")
        h4 = ctx.tf("4h")
        if not valid_row(df, ("macd_cross_up", "macd_hist", "macd")):
            return None
        row = df.iloc[-1]
        h4_ok_long = h4 is None or len(h4) < 30 or float(h4["macd"].iloc[-1]) > 0
        h4_ok_short = h4 is None or len(h4) < 30 or float(h4["macd"].iloc[-1]) < 0
        if bool(row["macd_cross_up"]) and float(row["macd_hist"]) > 0 and float(row["macd"]) > 0 and h4_ok_long and ctx.aligned(Side.BUY):
            return make_signal(self.ledger, "[STRAT: MACD_Cross_Long]", df, Side.BUY, strength=2.0)
        if bool(row["macd_cross_down"]) and float(row["macd_hist"]) < 0 and float(row["macd"]) < 0 and h4_ok_short and ctx.aligned(Side.SELL):
            return make_signal(self.ledger, "[STRAT: MACD_Cross_Short]", df, Side.SELL, strength=2.0)
        return None


class BBSqueeze(Strategy):
    name = ledger = "Kasa_BB_Squeeze"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("1h")
        if not valid_row(df, ("ttm_squeeze_on", "bb_upper", "bb_lower", "close")):
            return None
        row = df.iloc[-1]
        if not bool(row.get("ttm_squeeze_on", False)):
            return None
        close = float(row["close"])
        if close > float(row["bb_upper"]) and volume_ok(df) and ctx.aligned(Side.BUY):
            return make_signal(self.ledger, "[STRAT: BB_Squeeze_Long]", df, Side.BUY, tp_r_val=2.5, strength=2.5)
        if close < float(row["bb_lower"]) and volume_ok(df) and ctx.aligned(Side.SELL):
            return make_signal(self.ledger, "[STRAT: BB_Squeeze_Short]", df, Side.SELL, tp_r_val=2.5, strength=2.5)
        return None


class CCICross(Strategy):
    name = ledger = "Kasa_CCI"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("1h")
        if not valid_row(df, ("cci", "cci_cross_up")):
            return None
        cci = float(df["cci"].iloc[-1])
        if bool(df["cci_cross_up"].iloc[-1]) and -100 < cci < 100 and ctx.aligned(Side.BUY):
            return make_signal(self.ledger, "[STRAT: CCI_Cross_Long]", df, Side.BUY)
        if bool(df["cci_cross_down"].iloc[-1]) and -100 < cci < 100 and ctx.aligned(Side.SELL):
            return make_signal(self.ledger, "[STRAT: CCI_Cross_Short]", df, Side.SELL)
        return None


class StochCross(Strategy):
    name = ledger = "Kasa_Stoch"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("1h")
        h4 = ctx.tf("4h")
        if not valid_row(df, ("stoch_k", "stoch_cross_up")):
            return None
        k = float(df["stoch_k"].iloc[-1])
        h4_bull = h4 is None or len(h4) < 30 or (hh_hl(h4)[0] and hh_hl(h4)[1])
        h4_bear = h4 is None or len(h4) < 30 or (lh_ll(h4)[0] and lh_ll(h4)[1])
        if bool(df["stoch_cross_up"].iloc[-1]) and k < 25 and h4_bull and ctx.aligned(Side.BUY):
            return make_signal(self.ledger, "[STRAT: Stoch_OS_Long]", df, Side.BUY)
        if bool(df["stoch_cross_down"].iloc[-1]) and k > 75 and h4_bear and ctx.aligned(Side.SELL):
            return make_signal(self.ledger, "[STRAT: Stoch_OB_Short]", df, Side.SELL)
        return None


class StochRSICross(Strategy):
    name = ledger = "Kasa_StochRSI"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("1h")
        h4 = ctx.tf("4h")
        if not valid_row(df, ("stochrsi_k", "stochrsi_cross_up")):
            return None
        k = float(df["stochrsi_k"].iloc[-1])
        h4_bull = h4 is None or len(h4) < 30 or (hh_hl(h4)[0] and hh_hl(h4)[1])
        h4_bear = h4 is None or len(h4) < 30 or (lh_ll(h4)[0] and lh_ll(h4)[1])
        if bool(df["stochrsi_cross_up"].iloc[-1]) and k < 25 and h4_bull and ctx.aligned(Side.BUY):
            return make_signal(self.ledger, "[STRAT: StochRSI_OS_Long]", df, Side.BUY)
        if bool(df["stochrsi_cross_down"].iloc[-1]) and k > 75 and h4_bear and ctx.aligned(Side.SELL):
            return make_signal(self.ledger, "[STRAT: StochRSI_OB_Short]", df, Side.SELL)
        return None


class IchimokuFull(Strategy):
    name = ledger = "Kasa_Ichimoku"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        setup = ctx.tf("4h")
        trig = ctx.tf("1h")
        if not valid_row(setup, ("ichi_tenkan", "ichi_span_a", "ichi_span_b")) or trig is None:
            return None
        if not valid_row(trig, ("tenkan_cross_up", "tenkan_cross_down", "close")):
            return None
        row = setup.iloc[-1]
        trow = trig.iloc[-1]
        close = float(row["close"])
        sa, sb = float(row["ichi_span_a"]), float(row["ichi_span_b"])
        cloud_top, cloud_bot = max(sa, sb), min(sa, sb)
        if len(setup) < 53:
            return None
        chikou_ok_long = bool(row.get("chikou_bull", False))
        chikou_ok_short = bool(row.get("chikou_bear", False))
        if cloud_bot <= close <= cloud_top:
            return None
        if bool(trow["tenkan_cross_up"]) and close > cloud_top and sa > sb and chikou_ok_long and ctx.aligned(Side.BUY):
            return make_signal(self.ledger, "[STRAT: Ichimoku_Long]", trig, Side.BUY, strength=2.5)
        if bool(trow["tenkan_cross_down"]) and close < cloud_bot and sa < sb and chikou_ok_short and ctx.aligned(Side.SELL):
            return make_signal(self.ledger, "[STRAT: Ichimoku_Short]", trig, Side.SELL, strength=2.5)
        return None


class Hacim(Strategy):
    name = ledger = "Kasa_Hacim"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("1h")
        if not valid_row(df, ("volume", "vol_sma", "close", "obv")) or len(df) < 40:
            return None
        highs = last_pivots(df, "high", 3)
        lows = last_pivots(df, "low", 3)
        vol = df["volume"]
        obv = df["obv"]
        if len(highs) >= 2:
            i1, p1 = highs[-2]
            i2, p2 = highs[-1]
            if p2 > p1 and float(vol.iloc[i2]) < float(vol.iloc[i1]) * 0.85:
                if float(obv.iloc[i2]) < float(obv.iloc[i1]) and ctx.aligned(Side.SELL):
                    if float(df["close"].iloc[-1]) < float(df["open"].iloc[-1]):
                        return make_signal(self.ledger, "[STRAT: Hacim_NegatifUyumsuzluk]", df, Side.SELL, strength=2.0)
        if len(lows) >= 2:
            i1, p1 = lows[-2]
            i2, p2 = lows[-1]
            if p2 < p1 and float(vol.iloc[i2]) < float(vol.iloc[i1]) * 0.85:
                if float(obv.iloc[i2]) > float(obv.iloc[i1]) and ctx.aligned(Side.BUY):
                    if float(df["close"].iloc[-1]) > float(df["open"].iloc[-1]):
                        return make_signal(self.ledger, "[STRAT: Hacim_PozitifUyumsuzluk]", df, Side.BUY, strength=2.0)
        return None
