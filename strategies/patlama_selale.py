from __future__ import annotations

from typing import Optional

from engine.config import PATLAMA_LEDGER
from engine.momentum_scan import score_momentum, trade_signal_from_score
from engine.types import Signal, Side
from strategies.base import MarketContext, Strategy
from strategies.helpers import make_signal, valid_row


class PatlamaSelale(Strategy):
    """MTF patlama / selale skoru >= 4 ise islem."""

    name = ledger = PATLAMA_LEDGER

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("1h")
        if not valid_row(df, ("close",)):
            return None
        scored = score_momentum(ctx)
        side = trade_signal_from_score(scored)
        if side is None or not ctx.aligned(side):
            return None
        tag = "Patlama_Long" if side == Side.BUY else "Selale_Short"
        notes = scored.long_notes if side == Side.BUY else scored.short_notes
        extra = {
            "long_score": scored.long_score,
            "short_score": scored.short_score,
            "notes": " | ".join(notes[-4:]),
        }
        return make_signal(
            self.ledger,
            f"[STRAT: {tag}]",
            df,
            side,
            extra=extra,
        )
