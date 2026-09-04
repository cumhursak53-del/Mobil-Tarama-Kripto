"""SMC tarayici skoru — LuxAlgo benzeri MTF analiz + confluence checklist."""
from __future__ import annotations

from typing import Optional

from engine.config import SMC_MIN_CONFLUENCE, SMC_MIN_GRADE
from engine.types import Side
from strategies.base import MarketContext
from structure.smc import SMCAnalysis, SetupGrade, analyze_smc_mtf

MIN_SMC_TRADE_SCORE = 5
_GRADE_RANK = {"A": 3, "B": 2, "C": 1, "none": 0}


def score_smc(ctx: MarketContext) -> SMCAnalysis:
    return analyze_smc_mtf(ctx.frames)


def _has_trigger(notes: str, *needles: str) -> bool:
    return any(n in notes for n in needles)


def _grade_ok(grade: SetupGrade) -> bool:
    return _GRADE_RANK.get(grade, 0) >= _GRADE_RANK.get(SMC_MIN_GRADE, 2)  # type: ignore[arg-type]


def smc_trade_side(analysis: SMCAnalysis) -> Optional[Side]:
    notes_l = " ".join(analysis.long_notes)
    notes_s = " ".join(analysis.short_notes)
    long_trigger = _has_trigger(
        notes_l,
        "OB_retest", "BOS", "breaker_retest", "ext_BOS", "int_BOS", "IFVG", "inducement",
    )
    short_trigger = _has_trigger(
        notes_s,
        "OB_retest", "BOS", "breaker_retest", "ext_BOS", "int_BOS", "IFVG", "inducement",
    )
    if (
        analysis.long_score >= MIN_SMC_TRADE_SCORE
        and analysis.long_score > analysis.short_score
        and long_trigger
        and analysis.hierarchy_long
        and analysis.confluence_long >= SMC_MIN_CONFLUENCE
        and _grade_ok(analysis.setup_grade_long)
        and analysis.external_event != "choch_bear"
        and not (analysis.trend == "bear" and analysis.internal_event == "choch_bear")
    ):
        return Side.BUY
    if (
        analysis.short_score >= MIN_SMC_TRADE_SCORE
        and analysis.short_score > analysis.long_score
        and short_trigger
        and analysis.hierarchy_short
        and analysis.confluence_short >= SMC_MIN_CONFLUENCE
        and _grade_ok(analysis.setup_grade_short)
        and analysis.external_event != "choch_bull"
        and not (analysis.trend == "bull" and analysis.internal_event == "choch_bull")
    ):
        return Side.SELL
    return None
