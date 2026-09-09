from __future__ import annotations

from typing import Optional

from engine.config import COMBO_LEDGER
from engine.types import Signal, Side, Stage
from strategies.base import MarketContext, Strategy
from strategies.helpers import make_signal, valid_row
from structure.core import hh_hl, lh_ll, volume_ok


class RejimOsilator(Strategy):
    """PDF: evre + osilator konfluans; indikatör tek başına yetmez — hacim/yapı 3. oy."""

    name = ledger = COMBO_LEDGER

    def signal_strength(self, ctx: MarketContext, sig: Signal) -> float:
        return float(sig.extra.get("votes_long") or sig.extra.get("votes_short") or 2)

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("1h")
        h4 = ctx.tf("4h")
        cols = (
            "close", "cci", "cci_cross_up", "cci_cross_down", "macd_hist",
            "macd_cross_up", "macd_cross_down", "stoch_k", "stoch_cross_up",
            "stoch_cross_down", "stochrsi_k", "stochrsi_cross_up", "stochrsi_cross_down",
        )
        if not valid_row(df, cols):
            return None

        votes_long = 0.0
        votes_short = 0.0
        if ctx.stage == Stage.ADVANCING:
            votes_long += 1.0
        elif ctx.stage == Stage.DECLINING:
            votes_short += 1.0

        if h4 is not None and len(h4) >= 40:
            hh, hl = hh_hl(h4)
            lh, ll = lh_ll(h4)
            if hh and hl:
                votes_long += 1.0
            if lh and ll:
                votes_short += 1.0

        cci = float(df["cci"].iloc[-1])
        hist = float(df["macd_hist"].iloc[-1])
        if (bool(df["cci_cross_up"].iloc[-1]) and cci < 100) or (bool(df["macd_cross_up"].iloc[-1]) and hist > 0):
            votes_long += 1.0
        if (bool(df["cci_cross_down"].iloc[-1]) and cci > -100) or (bool(df["macd_cross_down"].iloc[-1]) and hist < 0):
            votes_short += 1.0

        k = float(df["stoch_k"].iloc[-1])
        rk = float(df["stochrsi_k"].iloc[-1])
        if (bool(df["stoch_cross_up"].iloc[-1]) and k < 25) or (bool(df["stochrsi_cross_up"].iloc[-1]) and rk < 25):
            votes_long += 1.0
        if (bool(df["stoch_cross_down"].iloc[-1]) and k > 75) or (bool(df["stochrsi_cross_down"].iloc[-1]) and rk > 75):
            votes_short += 1.0

        if volume_ok(df):
            if votes_long >= votes_short:
                votes_long += 0.5
            else:
                votes_short += 0.5

        if votes_long >= 2.5 and votes_long > votes_short and ctx.aligned(Side.BUY):
            return make_signal(
                self.ledger, "[STRAT: RejimOsilator_Long]", df, Side.BUY,
                extra={"votes_long": votes_long, "votes_short": votes_short}, strength=votes_long,
            )
        if votes_short >= 2.5 and votes_short > votes_long and ctx.aligned(Side.SELL):
            return make_signal(
                self.ledger, "[STRAT: RejimOsilator_Short]", df, Side.SELL,
                extra={"votes_long": votes_long, "votes_short": votes_short}, strength=votes_short,
            )
        return None
