from __future__ import annotations

from typing import Optional

from engine.config import RETEST_HOLD_BARS
from engine.types import Signal, Side, Stage
from strategies.base import MarketContext, Strategy
from strategies.helpers import make_signal, near, valid_row
from structure.core import (
    broken_above,
    broken_below,
    candle_features,
    displacement_bar,
    last_pivots,
    nearest_level,
    retest_after_break,
    support_resistance,
    trendline_from_pivots,
    trendline_touches,
    volume_ok,
    wick_ratio,
)


class TrendCizgisi(Strategy):
    name = ledger = "Kasa_TrendCizgisi"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("1h")
        setup = ctx.tf("4h")
        if not valid_row(df, ("close", "atr")) or setup is None or len(setup) < 40:
            return None
        i = len(setup) - 1
        close = float(df["close"].iloc[-1])
        cf = candle_features(df)
        lows = last_pivots(setup, "low", 5)
        highs = last_pivots(setup, "high", 5)
        up_line = trendline_from_pivots(lows, i)
        down_line = trendline_from_pivots(highs, i)
        if up_line and trendline_touches(lows, i) >= 3 and near(close, up_line, 0.008):
            if cf["hammer"] or cf["bull_engulf"] or cf["pin_bull"] or cf["bullish"]:
                if ctx.aligned(Side.BUY):
                    return make_signal(self.ledger, "[STRAT: TrendCizgisi_Long]", df, Side.BUY, sl=up_line * 0.992, tp_mode="r", tp_r_val=2.5)
        if down_line and trendline_touches(highs, i) >= 3 and near(close, down_line, 0.008):
            if cf["shooting_star"] or cf["bear_engulf"] or cf["pin_bear"] or cf["bearish"]:
                if ctx.aligned(Side.SELL):
                    return make_signal(self.ledger, "[STRAT: TrendCizgisi_Short]", df, Side.SELL, sl=down_line * 1.008, tp_mode="r", tp_r_val=2.5)
        return None


class PulbackRetest(Strategy):
    name = ledger = "Kasa_PulbackRetest"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("1h")
        setup = ctx.tf("4h")
        if not valid_row(df, ("close",)) or setup is None or len(setup) < 50:
            return None
        supports, resistances = support_resistance(setup)
        close = float(df["close"].iloc[-1])
        cf = candle_features(df)
        for res in resistances:
            if retest_after_break(setup, res, "up", RETEST_HOLD_BARS) and cf["bullish"] and volume_ok(df):
                if ctx.aligned(Side.BUY):
                    return make_signal(self.ledger, "[STRAT: Retest_Long]", df, Side.BUY, sl=res * 0.99, tp_mode="measured_move", strength=2.5)
        for sup in supports:
            if retest_after_break(setup, sup, "down", RETEST_HOLD_BARS) and cf["bearish"] and volume_ok(df):
                if ctx.aligned(Side.SELL):
                    return make_signal(self.ledger, "[STRAT: Retest_Short]", df, Side.SELL, sl=sup * 1.01, tp_mode="measured_move", strength=2.5)
        return None


class DUK(Strategy):
    name = ledger = "Kasa_DUK"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("1h")
        setup = ctx.tf("4h")
        if not valid_row(df, ("close", "volume", "atr")) or setup is None or len(setup) < 40:
            return None
        i = len(setup) - 1
        highs = last_pivots(setup, "high", 5)
        lows = last_pivots(setup, "low", 5)
        vol_declining = len(setup) >= 10 and float(setup["volume"].iloc[-5:].mean()) < float(setup["volume"].iloc[-15:-5].mean()) * 0.85
        if len(highs) >= 3 and highs[-1][1] < highs[-2][1] < highs[-3][1]:
            line = trendline_from_pivots(highs, i)
            if line and broken_above(setup, line) and displacement_bar(setup) and vol_declining and ctx.aligned(Side.BUY):
                return make_signal(self.ledger, "[STRAT: DUK_Long]", df, Side.BUY, sl=line * 0.99, tp_mode="measured_move", strength=2.0)
        if len(lows) >= 3 and lows[-1][1] > lows[-2][1] > lows[-3][1]:
            line = trendline_from_pivots(lows, i)
            if line and broken_below(setup, line) and displacement_bar(setup) and vol_declining and ctx.aligned(Side.SELL):
                return make_signal(self.ledger, "[STRAT: YUK_Short]", df, Side.SELL, sl=line * 1.01, tp_mode="measured_move", strength=2.0)
        return None


class Tuzak(Strategy):
    name = ledger = "Kasa_Tuzak"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("1h")
        setup = ctx.tf("4h")
        if not valid_row(df, ("close",)) or setup is None or len(setup) < 40:
            return None
        supports, resistances = support_resistance(setup)
        h, l, c, o = float(df["high"].iloc[-1]), float(df["low"].iloc[-1]), float(df["close"].iloc[-1]), float(df["open"].iloc[-1])
        if ctx.stage in (Stage.ADVANCING, Stage.ACCUMULATION) and ctx.aligned(Side.BUY):
            for s in supports:
                if wick_ratio(df, "lower") >= 0.55 and l < s * 0.997 and c > s and c > o:
                    return make_signal(self.ledger, "[STRAT: AyiTuzagi_Long]", df, Side.BUY, sl=l * 0.997, strength=2.0)
        if ctx.stage in (Stage.DECLINING, Stage.DISTRIBUTION) and ctx.aligned(Side.SELL):
            for r in resistances:
                if wick_ratio(df, "upper") >= 0.55 and h > r * 1.003 and c < r and c < o:
                    return make_signal(self.ledger, "[STRAT: BogaTuzagi_Short]", df, Side.SELL, sl=h * 1.003, strength=2.0)
        return None


class DominanceAlt(Strategy):
    name = ledger = "Kasa_Dominance"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        if ctx.symbol in ("BTCUSDT", "ETHUSDT"):
            return None
        df = ctx.tf("1h")
        if not valid_row(df, ("close", "ema50")):
            return None
        d = ctx.dominance or {}
        btc_d_chg = d.get("btc_d_chg")
        usdt_d_chg = d.get("usdt_d_chg")
        btc_chg = d.get("btc_chg")
        total2 = d.get("total2")
        eth_btc = d.get("eth_btc")
        eth_btc_chg = d.get("eth_btc_chg")
        if btc_d_chg is None or usdt_d_chg is None:
            return None
        close = float(df["close"].iloc[-1])
        ema50 = float(df["ema50"].iloc[-1])
        alt_season = (eth_btc is None or float(eth_btc) > 0.03) and (eth_btc_chg is None or float(eth_btc_chg) >= -0.3)
        if btc_d_chg < 0 and (btc_chg or 0) >= -0.5 and usdt_d_chg < 0 and alt_season:
            if total2 is None or float(total2) > 35:
                if close > ema50 and ctx.aligned(Side.BUY):
                    return make_signal(self.ledger, "[STRAT: Dominance_AltLong]", df, Side.BUY, strength=2.5)
        if btc_d_chg > 0 and usdt_d_chg > 0:
            if (eth_btc_chg is None or float(eth_btc_chg) <= 0.5) and close < ema50 and ctx.aligned(Side.SELL):
                return make_signal(self.ledger, "[STRAT: Dominance_AltShort]", df, Side.SELL, strength=2.5)
        return None
