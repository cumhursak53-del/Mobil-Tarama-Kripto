from __future__ import annotations

from typing import Optional

from engine.types import Signal, Side, Stage
from strategies.base import MarketContext, Strategy
from strategies.helpers import make_signal, near, valid_row
from structure.core import (
    broken_above,
    broken_below,
    candle_features,
    last_pivots,
    nearest_level,
    support_resistance,
    trendline_from_pivots,
    volume_ok,
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
        if up_line and near(close, up_line, 0.008) and (cf["hammer"] or cf["bull_engulf"] or cf["bullish"]):
            if not ctx.aligned(Side.BUY):
                return None
            return make_signal(self.ledger, "[STRAT: TrendCizgisi_Long]", df, Side.BUY, sl=up_line * 0.992)
        if down_line and near(close, down_line, 0.008) and (cf["shooting_star"] or cf["bear_engulf"] or cf["bearish"]):
            if not ctx.aligned(Side.SELL):
                return None
            return make_signal(self.ledger, "[STRAT: TrendCizgisi_Short]", df, Side.SELL, sl=down_line * 1.008)
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
        prev = float(df["close"].iloc[-2])
        cf = candle_features(df)
        res = nearest_level(close, resistances, 0.006)
        sup = nearest_level(close, supports, 0.006)
        # Role reversal: broken resistance becomes support (retest hold)
        if res and prev > res * 1.003 and close >= res and close <= res * 1.006 and cf["bullish"] and volume_ok(df):
            if ctx.aligned(Side.BUY):
                return make_signal(self.ledger, "[STRAT: Retest_Long]", df, Side.BUY, sl=res * 0.99)
        if sup and prev < sup * 0.997 and close <= sup and close >= sup * 0.994 and cf["bearish"] and volume_ok(df):
            if ctx.aligned(Side.SELL):
                return make_signal(self.ledger, "[STRAT: Retest_Short]", df, Side.SELL, sl=sup * 1.01)
        return None


class DUK(Strategy):
    name = ledger = "Kasa_DUK"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("1h")
        setup = ctx.tf("4h")
        if not valid_row(df, ("close", "volume")) or setup is None or len(setup) < 40:
            return None
        i = len(setup) - 1
        highs = last_pivots(setup, "high", 5)
        lows = last_pivots(setup, "low", 5)
        if len(highs) >= 3 and highs[-1][1] < highs[-2][1] < highs[-3][1]:
            line = trendline_from_pivots(highs, i)
            if line and broken_above(setup, line) and volume_ok(setup) and ctx.aligned(Side.BUY):
                return make_signal(self.ledger, "[STRAT: DUK_Long]", df, Side.BUY, sl=line * 0.99)
        if len(lows) >= 3 and lows[-1][1] > lows[-2][1] > lows[-3][1]:
            line = trendline_from_pivots(lows, i)
            if line and broken_below(setup, line) and volume_ok(setup) and ctx.aligned(Side.SELL):
                return make_signal(self.ledger, "[STRAT: YUK_Short]", df, Side.SELL, sl=line * 1.01)
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
        # Bear trap: wick below support, close back above (in advancing / HH)
        if ctx.stage in (Stage.ADVANCING, Stage.ACCUMULATION) and ctx.aligned(Side.BUY):
            for s in supports:
                if l < s * 0.997 and c > s and c > o:
                    return make_signal(self.ledger, "[STRAT: AyiTuzagi_Long]", df, Side.BUY, sl=l * 0.997)
        if ctx.stage in (Stage.DECLINING, Stage.DISTRIBUTION) and ctx.aligned(Side.SELL):
            for r in resistances:
                if h > r * 1.003 and c < r and c < o:
                    return make_signal(self.ledger, "[STRAT: BogaTuzagi_Short]", df, Side.SELL, sl=h * 1.003)
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
        btc_d = d.get("btc_d")
        usdt_d = d.get("usdt_d")
        btc_d_chg = d.get("btc_d_chg")
        usdt_d_chg = d.get("usdt_d_chg")
        btc_chg = d.get("btc_chg")
        if btc_d is None or usdt_d is None:
            return None
        close = float(df["close"].iloc[-1])
        ema50 = float(df["ema50"].iloc[-1])
        # PDF: BTC.D falling, BTC rising/flat, USDT.D falling → alt long
        if btc_d_chg is not None and btc_d_chg < 0 and (btc_chg or 0) >= 0 and (usdt_d_chg or 0) < 0:
            if close > ema50 and ctx.aligned(Side.BUY):
                return make_signal(self.ledger, "[STRAT: Dominance_AltLong]", df, Side.BUY)
        # BTC.D rising + USDT.D rising → risk-off alts
        if btc_d_chg is not None and btc_d_chg > 0 and (usdt_d_chg or 0) > 0:
            if close < ema50 and ctx.aligned(Side.SELL):
                return make_signal(self.ledger, "[STRAT: Dominance_AltShort]", df, Side.SELL)
        return None
