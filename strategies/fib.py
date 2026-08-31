from __future__ import annotations

from typing import Optional

from engine.types import Signal, Side
from strategies.base import MarketContext, Strategy
from strategies.helpers import make_signal, valid_row
from structure.core import candle_features, fib_retracement, last_impulse


class Fib618(Strategy):
    name = ledger = "Kasa_Fib618"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("1h")
        setup = ctx.tf("4h")
        src = setup if setup is not None and len(setup) > 40 else df
        if not valid_row(df, ("close",)) or src is None:
            return None
        impulse = last_impulse(src)
        if not impulse:
            return None
        lo, hi, direction = impulse
        levels = fib_retracement(lo, hi, direction)
        if not levels:
            return None
        close = float(df["close"].iloc[-1])
        zone_lo, zone_hi = levels.get("0.5"), levels.get("0.618")
        cf = candle_features(df)
        if direction == "up" and zone_lo and zone_hi:
            lo_z, hi_z = min(zone_lo, zone_hi), max(zone_lo, zone_hi)
            if lo_z <= close <= hi_z * 1.004 and (cf["hammer"] or cf["bull_engulf"] or cf["bullish"]):
                if ctx.aligned(Side.BUY):
                    sl = levels.get("0.786", lo)
                    return make_signal(self.ledger, "[STRAT: Fib618_Long]", df, Side.BUY, sl=sl)
        if direction == "down" and zone_lo and zone_hi:
            lo_z, hi_z = min(zone_lo, zone_hi), max(zone_lo, zone_hi)
            if lo_z * 0.996 <= close <= hi_z and (cf["shooting_star"] or cf["bear_engulf"] or cf["bearish"]):
                if ctx.aligned(Side.SELL):
                    sl = levels.get("0.786", hi)
                    return make_signal(self.ledger, "[STRAT: Fib618_Short]", df, Side.SELL, sl=sl)
        return None
