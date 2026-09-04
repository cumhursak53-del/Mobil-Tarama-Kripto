from __future__ import annotations

from typing import Optional

from engine.config import TRIGGER_TF
from engine.smc_scan import score_smc, smc_trade_side
from engine.types import Signal, Side
from strategies.base import MarketContext, Strategy
from strategies.helpers import make_signal, sl_from_swing, tp_r, valid_row

SMC_LEDGER = "Kasa_SMC"


class SmartMoneyConcepts(Strategy):
    """
    LuxAlgo SMC benzeri:
    4H BOS/CHoCH + order block retest + 15m sweep/onay → anlik giris.
    """

    name = ledger = SMC_LEDGER
    entry_mode = "live"
    entry_tf = "15m"

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf(TRIGGER_TF)
        if df is None:
            df = ctx.tf("15m")
        if not valid_row(df, ("close", "atr")):
            return None

        analysis = score_smc(ctx)
        side = smc_trade_side(analysis)
        if side is None or not ctx.aligned(side):
            return None

        # OB / breaker tabanli SL
        sl = sl_from_swing(df, side)
        active_bull = analysis.active_blocks("bull")
        active_bear = analysis.active_blocks("bear")
        price = float(df["close"].iloc[-1])
        if side == Side.BUY and active_bull:
            sl = min(sl or price * 0.99, active_bull[-1].bottom * 0.998)
        if side == Side.SELL and active_bear:
            sl = max(sl or price * 1.01, active_bear[-1].top * 1.002)

        tag = "SMC_Long" if side == Side.BUY else "SMC_Short"
        sig = make_signal(
            self.ledger,
            f"[STRAT: {tag}]",
            df,
            side,
            sl=sl,
            extra={
                "smc_score": analysis.long_score if side == Side.BUY else analysis.short_score,
                "smc_grade": analysis.setup_grade_long if side == Side.BUY else analysis.setup_grade_short,
                "smc_confluence": analysis.confluence_long if side == Side.BUY else analysis.confluence_short,
                "trend": analysis.trend,
                "last_event": analysis.last_event,
                "session": analysis.session,
                "notes": analysis.to_dict().get("long_notes" if side == Side.BUY else "short_notes", ""),
            },
        )
        if sig:
            sig.entry_tf = self.entry_tf
            if side == Side.BUY and active_bear:
                sig.tp_price = tp_r(price, sl or price * 0.99, side, 2.5)
            elif side == Side.SELL and active_bull:
                sig.tp_price = tp_r(price, sl or price * 1.01, side, 2.5)
        return sig
