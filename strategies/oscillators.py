from __future__ import annotations

from typing import Optional

from engine.types import Signal, Side
from strategies.base import MarketContext, Strategy
from strategies.helpers import make_signal, valid_row
from structure.core import last_pivots, volume_ok


class RSIUyumsuzluk(Strategy):
    name = ledger = "Kasa_RSI_Uyumsuzluk"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("1h")
        if not valid_row(df, ("rsi", "close")) or len(df) < 60:
            return None
        lows = last_pivots(df, "low", 4)
        highs = last_pivots(df, "high", 4)
        rsi = df["rsi"]
        if len(lows) >= 2:
            i1, p1 = lows[-2]
            i2, p2 = lows[-1]
            r1, r2 = float(rsi.iloc[i1]), float(rsi.iloc[i2])
            if p2 < p1 and r2 > r1 and r2 < 45 and ctx.aligned(Side.BUY):
                return make_signal(self.ledger, "[STRAT: RSI_PozitifUyumsuzluk]", df, Side.BUY)
        if len(highs) >= 2:
            i1, p1 = highs[-2]
            i2, p2 = highs[-1]
            r1, r2 = float(rsi.iloc[i1]), float(rsi.iloc[i2])
            if p2 > p1 and r2 < r1 and r2 > 55 and ctx.aligned(Side.SELL):
                return make_signal(self.ledger, "[STRAT: RSI_NegatifUyumsuzluk]", df, Side.SELL)
        return None


class RSIBolge(Strategy):
    name = ledger = "Kasa_RSI_Bolge"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
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
        if not valid_row(df, ("macd_cross_up", "macd_hist")):
            return None
        row = df.iloc[-1]
        if bool(row["macd_cross_up"]) and float(row["macd_hist"]) > 0 and ctx.aligned(Side.BUY):
            return make_signal(self.ledger, "[STRAT: MACD_Cross_Long]", df, Side.BUY)
        if bool(row["macd_cross_down"]) and float(row["macd_hist"]) < 0 and ctx.aligned(Side.SELL):
            return make_signal(self.ledger, "[STRAT: MACD_Cross_Short]", df, Side.SELL)
        return None


class BBSqueeze(Strategy):
    name = ledger = "Kasa_BB_Squeeze"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("1h")
        if not valid_row(df, ("bb_width", "bb_upper", "bb_lower", "bb_width_med")):
            return None
        row = df.iloc[-1]
        squeezed = float(row["bb_width"]) < float(row["bb_width_med"]) * 0.85
        prev_w = float(df["bb_width"].iloc[-2])
        expanding = squeezed or prev_w < float(df["bb_width_med"].iloc[-2]) * 0.85
        close = float(row["close"])
        if expanding and close > float(row["bb_upper"]) and volume_ok(df) and ctx.aligned(Side.BUY):
            return make_signal(self.ledger, "[STRAT: BB_Squeeze_Long]", df, Side.BUY)
        if expanding and close < float(row["bb_lower"]) and volume_ok(df) and ctx.aligned(Side.SELL):
            return make_signal(self.ledger, "[STRAT: BB_Squeeze_Short]", df, Side.SELL)
        return None


class CCICross(Strategy):
    name = ledger = "Kasa_CCI"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("1h")
        if not valid_row(df, ("cci", "cci_cross_up")):
            return None
        cci = float(df["cci"].iloc[-1])
        if bool(df["cci_cross_up"].iloc[-1]) and cci < 100 and ctx.aligned(Side.BUY):
            return make_signal(self.ledger, "[STRAT: CCI_Cross_Long]", df, Side.BUY)
        if bool(df["cci_cross_down"].iloc[-1]) and cci > -100 and ctx.aligned(Side.SELL):
            return make_signal(self.ledger, "[STRAT: CCI_Cross_Short]", df, Side.SELL)
        return None


class StochCross(Strategy):
    name = ledger = "Kasa_Stoch"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("1h")
        if not valid_row(df, ("stoch_k", "stoch_cross_up")):
            return None
        k = float(df["stoch_k"].iloc[-1])
        if bool(df["stoch_cross_up"].iloc[-1]) and k < 25 and ctx.aligned(Side.BUY):
            return make_signal(self.ledger, "[STRAT: Stoch_OS_Long]", df, Side.BUY)
        if bool(df["stoch_cross_down"].iloc[-1]) and k > 75 and ctx.aligned(Side.SELL):
            return make_signal(self.ledger, "[STRAT: Stoch_OB_Short]", df, Side.SELL)
        return None


class StochRSICross(Strategy):
    name = ledger = "Kasa_StochRSI"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("1h")
        if not valid_row(df, ("stochrsi_k", "stochrsi_cross_up")):
            return None
        k = float(df["stochrsi_k"].iloc[-1])
        if bool(df["stochrsi_cross_up"].iloc[-1]) and k < 25 and ctx.aligned(Side.BUY):
            return make_signal(self.ledger, "[STRAT: StochRSI_OS_Long]", df, Side.BUY)
        if bool(df["stochrsi_cross_down"].iloc[-1]) and k > 75 and ctx.aligned(Side.SELL):
            return make_signal(self.ledger, "[STRAT: StochRSI_OB_Short]", df, Side.SELL)
        return None


class IchimokuFull(Strategy):
    name = ledger = "Kasa_Ichimoku"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("4h")
        trig = ctx.tf("1h")
        if not valid_row(df, ("ichi_tenkan", "ichi_span_a", "ichi_span_b")) or trig is None:
            return None
        row = df.iloc[-1]
        close = float(row["close"])
        sa, sb = float(row["ichi_span_a"]), float(row["ichi_span_b"])
        cloud_top, cloud_bot = max(sa, sb), min(sa, sb)
        # Chikou: close of 26 bars ago compared to price then; series is close.shift(-26)
        # At bar -1, chikou is future-shifted so last 26 are NaN. Use close vs close.shift(26).
        if len(df) < 53:
            return None
        chikou_ok_long = float(df["close"].iloc[-1]) > float(df["close"].iloc[-27])
        chikou_ok_short = float(df["close"].iloc[-1]) < float(df["close"].iloc[-27])
        in_cloud = cloud_bot <= close <= cloud_top
        if in_cloud:
            return None
        if bool(row["tenkan_cross_up"]) and close > cloud_top and sa > sb and chikou_ok_long and ctx.aligned(Side.BUY):
            return make_signal(self.ledger, "[STRAT: Ichimoku_Long]", trig, Side.BUY)
        if bool(row["tenkan_cross_down"]) and close < cloud_bot and sa < sb and chikou_ok_short and ctx.aligned(Side.SELL):
            return make_signal(self.ledger, "[STRAT: Ichimoku_Short]", trig, Side.SELL)
        return None


class Hacim(Strategy):
    name = ledger = "Kasa_Hacim"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("1h")
        if not valid_row(df, ("volume", "vol_sma", "close")) or len(df) < 40:
            return None
        highs = last_pivots(df, "high", 3)
        lows = last_pivots(df, "low", 3)
        vol = df["volume"]
        if len(highs) >= 2:
            i1, p1 = highs[-2]
            i2, p2 = highs[-1]
            if p2 > p1 and float(vol.iloc[i2]) < float(vol.iloc[i1]) * 0.85 and ctx.aligned(Side.SELL):
                if float(df["close"].iloc[-1]) < float(df["open"].iloc[-1]):
                    return make_signal(self.ledger, "[STRAT: Hacim_NegatifUyumsuzluk]", df, Side.SELL)
        if len(lows) >= 2:
            i1, p1 = lows[-2]
            i2, p2 = lows[-1]
            if p2 < p1 and float(vol.iloc[i2]) < float(vol.iloc[i1]) * 0.85 and ctx.aligned(Side.BUY):
                if float(df["close"].iloc[-1]) > float(df["open"].iloc[-1]):
                    return make_signal(self.ledger, "[STRAT: Hacim_PozitifUyumsuzluk]", df, Side.BUY)
        return None
