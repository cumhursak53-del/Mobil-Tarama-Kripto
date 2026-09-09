from __future__ import annotations

from typing import Optional

from engine.types import Signal, Side
from strategies.base import MarketContext, Strategy
from strategies.helpers import make_signal, valid_row
from structure.core import candle_features, fib_extension, fib_retracement, validated_impulse


class Fib618(Strategy):
    name = ledger = "Kasa_Fib618"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("1h")
        setup = ctx.tf("4h")
        src = setup if setup is not None and len(setup) > 40 else df
        if not valid_row(df, ("close",)) or src is None:
            return None
        impulse = validated_impulse(src)
        if not impulse:
            return None
        lo, hi, direction = impulse
        levels = fib_retracement(lo, hi, direction)
        extensions = fib_extension(lo, hi, direction)
        if not levels:
            return None
        close = float(df["close"].iloc[-1])
        cf = candle_features(df)
        ote_lo = levels.get("0.618")
        ote_hi = levels.get("0.786") or levels.get("0.79") or ote_lo
        if direction == "up" and ote_lo and ote_hi:
            lo_z, hi_z = min(float(ote_lo), float(ote_hi)), max(float(ote_lo), float(ote_hi))
            if lo_z <= close <= hi_z * 1.004 and (cf["hammer"] or cf["pin_bull"] or cf["bullish"]):
                if ctx.aligned(Side.BUY):
                    sl = levels.get("0.786", lo)
                    tp1272 = extensions.get("1.272")
                    tp1618 = extensions.get("1.618")
                    tps = [x for x in (tp1272, tp1618) if x is not None]
                    return make_signal(
                        self.ledger, "[STRAT: Fib618_Long]", df, Side.BUY, sl=sl,
                        tp_price=tp1618 or tp1272,
                        tp_levels=tps,
                        tp_mode="multi",
                        strength=2.5,
                    )
        if direction == "down" and ote_lo and ote_hi:
            lo_z, hi_z = min(float(ote_lo), float(ote_hi)), max(float(ote_lo), float(ote_hi))
            if lo_z * 0.996 <= close <= hi_z and (cf["shooting_star"] or cf["pin_bear"] or cf["bearish"]):
                if ctx.aligned(Side.SELL):
                    sl = levels.get("0.786", hi)
                    tp1272 = extensions.get("1.272")
                    tp1618 = extensions.get("1.618")
                    tps = [x for x in (tp1272, tp1618) if x is not None]
                    return make_signal(
                        self.ledger, "[STRAT: Fib618_Short]", df, Side.SELL, sl=sl,
                        tp_price=tp1618 or tp1272,
                        tp_levels=tps,
                        tp_mode="multi",
                        strength=2.5,
                    )
        return None
