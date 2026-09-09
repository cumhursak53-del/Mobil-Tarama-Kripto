from __future__ import annotations

from typing import Optional

from engine.config import TRIGGER_TF
from engine.smc_scan import score_smc, smc_trade_side
from engine.types import Signal, Side
from strategies.base import MarketContext, Strategy
from strategies.helpers import make_signal, sl_from_swing, tp_r, valid_row

SMC_LEDGER = "Kasa_SMC"


class SmartMoneyConcepts(Strategy):
    """LuxAlgo SMC: 4H yapı + OB retest + 15m sweep/onay."""

    name = ledger = SMC_LEDGER
    entry_mode = "live"
    entry_tf = "15m"

    def signal_strength(self, ctx: MarketContext, sig: Signal) -> float:
        grade = sig.extra.get("smc_grade", "C")
        conf = float(sig.extra.get("smc_confluence") or 0)
        rank = {"A": 3.0, "B": 2.0, "C": 1.0}.get(str(grade), 1.0)
        return rank * 2 + conf * 0.3 + float(sig.extra.get("smc_score") or 0) * 0.2

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

        sl = sl_from_swing(df, side)
        active_bull = analysis.active_blocks("bull")
        active_bear = analysis.active_blocks("bear")
        price = float(df["close"].iloc[-1])
        entry_limit = None
        entry_mode = "market"

        ce_level = None
        for fvg in analysis.fvgs:
            if fvg.mitigated:
                continue
            if side == Side.BUY and fvg.side == "bull" and fvg.ce_level:
                ce_level = fvg.ce_level
            if side == Side.SELL and fvg.side == "bear" and fvg.ce_level:
                ce_level = fvg.ce_level

        if side == Side.BUY and active_bull:
            ob = active_bull[-1]
            sl = min(sl or price * 0.99, ob.bottom * 0.998)
            entry_limit = ce_level if ce_level and abs(price - ce_level) / price < 0.012 else ob.mid
            entry_mode = "limit"
        if side == Side.SELL and active_bear:
            ob = active_bear[-1]
            sl = max(sl or price * 1.01, ob.top * 1.002)
            entry_limit = ce_level if ce_level and abs(price - ce_level) / price < 0.012 else ob.mid
            entry_mode = "limit"

        dr = analysis.dealing_range
        if dr and entry_limit is None:
            if side == Side.BUY and analysis.in_ote_long:
                entry_limit = (dr.ote_low + dr.ote_high) / 2.0
                entry_mode = "limit"
            if side == Side.SELL and analysis.in_ote_short:
                entry_limit = (dr.ote_low + dr.ote_high) / 2.0
                entry_mode = "limit"

        tag = "SMC_Long" if side == Side.BUY else "SMC_Short"
        tp_price = None
        pools = analysis.liquidity_pools or []
        if pools:
            if side == Side.BUY:
                targets = [p.level for p in pools if p.level > price and p.side == "sell" and not p.swept]
                if targets:
                    tp_price = min(targets)
            else:
                targets = [p.level for p in pools if p.level < price and p.side == "buy" and not p.swept]
                if targets:
                    tp_price = max(targets)
        if tp_price is None:
            if side == Side.BUY and analysis.eqh_levels:
                above = [lv for lv in analysis.eqh_levels if lv > price]
                if above:
                    tp_price = min(above)
            if side == Side.SELL and analysis.eql_levels:
                below = [lv for lv in analysis.eql_levels if lv < price]
                if below:
                    tp_price = max(below)

        sig = make_signal(
            self.ledger,
            f"[STRAT: {tag}]",
            df,
            side,
            sl=sl,
            tp_price=tp_price,
            tp_mode="liquidity" if tp_price else "r",
            tp_r_val=2.5,
            entry_mode=entry_mode,
            entry_limit=entry_limit,
            trail_at_r=1.5,
            be_at_r=1.0,
            extra={
                "smc_score": analysis.long_score if side == Side.BUY else analysis.short_score,
                "smc_grade": analysis.setup_grade_long if side == Side.BUY else analysis.setup_grade_short,
                "smc_confluence": analysis.confluence_long if side == Side.BUY else analysis.confluence_short,
                "trend": analysis.trend,
                "last_event": analysis.last_event,
                "session": analysis.session,
            },
            strength=float(analysis.long_score if side == Side.BUY else analysis.short_score) + float(analysis.confluence_long if side == Side.BUY else analysis.confluence_short),
        )
        if sig:
            sig.entry_tf = self.entry_tf
            if tp_price is None:
                if side == Side.BUY and active_bear:
                    sig.tp_price = tp_r(price, sl or price * 0.99, side, 2.5)
                elif side == Side.SELL and active_bull:
                    sig.tp_price = tp_r(price, sl or price * 1.01, side, 2.5)
        return sig
