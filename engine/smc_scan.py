"""SMC tarayici skoru — LuxAlgo benzeri MTF analiz."""
from __future__ import annotations

from typing import Optional

from engine.types import Side
from strategies.base import MarketContext
from structure.smc import SMCAnalysis, analyze_smc_mtf

MIN_SMC_TRADE_SCORE = 5


def score_smc(ctx: MarketContext) -> SMCAnalysis:
    return analyze_smc_mtf(ctx.frames)


def smc_trade_side(analysis: SMCAnalysis) -> Optional[Side]:
    notes_l = " ".join(analysis.long_notes)
    notes_s = " ".join(analysis.short_notes)
    if (
        analysis.long_score >= MIN_SMC_TRADE_SCORE
        and analysis.long_score > analysis.short_score
        and ("OB_retest" in notes_l or "BOS" in notes_l)
        and analysis.last_event != "choch_bear"
    ):
        return Side.BUY
    if (
        analysis.short_score >= MIN_SMC_TRADE_SCORE
        and analysis.short_score > analysis.long_score
        and ("OB_retest" in notes_s or "BOS" in notes_s)
        and analysis.last_event != "choch_bull"
    ):
        return Side.SELL
    return None
