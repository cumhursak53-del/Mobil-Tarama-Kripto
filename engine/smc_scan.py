"""SMC tarayici skoru — LuxAlgo benzeri MTF analiz + confluence checklist."""
from __future__ import annotations

from typing import Optional

from engine.config import (
    SMC_MIN_CONFLUENCE,
    SMC_MIN_GRADE,
    SMC_MIN_TRADE_SCORE,
    SMC_REQUIRE_CANDLE_CONFIRM,
    SMC_REQUIRE_KILLZONE,
    SMC_REQUIRE_OB_FVG,
    SMT_ENABLED,
)
from engine.types import Side
from strategies.base import MarketContext
from structure.smc import SMCAnalysis, SetupGrade, analyze_smc_mtf

_GRADE_RANK = {"A": 3, "B": 2, "C": 1, "none": 0}


def score_smc(ctx: MarketContext) -> SMCAnalysis:
    analysis = analyze_smc_mtf(ctx.frames)
    if SMT_ENABLED and ctx.ref_frames:
        from structure.smc_smt import apply_smt_to_analysis

        apply_smt_to_analysis(analysis, ctx.frames, ctx.ref_frames)
    return analysis


def _has_trigger(notes: str, *needles: str) -> bool:
    return any(n in notes for n in needles)


def _grade_ok(grade: SetupGrade) -> bool:
    return _GRADE_RANK.get(grade, 0) >= _GRADE_RANK.get(SMC_MIN_GRADE, 2)  # type: ignore[arg-type]


def _killzone_penalty(analysis: SMCAnalysis) -> int:
    if analysis.session in ("london_open", "ny_open", "london_close", "asia"):
        return 0
    return 1


def _killzone_ok(analysis: SMCAnalysis, side: Side) -> bool:
    if SMC_REQUIRE_KILLZONE and _killzone_penalty(analysis) > 0:
        notes = " ".join(analysis.long_notes if side == Side.BUY else analysis.short_notes)
        return "killzone:" in notes
    return True


def _ob_fvg_ok(analysis: SMCAnalysis, side: Side) -> bool:
    if not SMC_REQUIRE_OB_FVG:
        return True
    if side == Side.BUY:
        return analysis.ob_fvg_valid_long
    return analysis.ob_fvg_valid_short


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
    candle_long = (not SMC_REQUIRE_CANDLE_CONFIRM) or ("candle_confirm" in notes_l)
    candle_short = (not SMC_REQUIRE_CANDLE_CONFIRM) or ("candle_confirm" in notes_s)
    if (
        analysis.long_score >= SMC_MIN_TRADE_SCORE
        and analysis.long_score > analysis.short_score
        and long_trigger
        and analysis.hierarchy_long
        and analysis.confluence_long >= SMC_MIN_CONFLUENCE
        and _grade_ok(analysis.setup_grade_long)
        and _killzone_ok(analysis, Side.BUY)
        and _ob_fvg_ok(analysis, Side.BUY)
        and candle_long
        and analysis.external_event != "choch_bear"
        and not (analysis.trend == "bear" and analysis.internal_event == "choch_bear")
    ):
        return Side.BUY
    if (
        analysis.short_score >= SMC_MIN_TRADE_SCORE
        and analysis.short_score > analysis.long_score
        and short_trigger
        and analysis.hierarchy_short
        and analysis.confluence_short >= SMC_MIN_CONFLUENCE
        and _grade_ok(analysis.setup_grade_short)
        and _killzone_ok(analysis, Side.SELL)
        and _ob_fvg_ok(analysis, Side.SELL)
        and candle_short
        and analysis.external_event != "choch_bull"
        and not (analysis.trend == "bull" and analysis.internal_event == "choch_bull")
    ):
        return Side.SELL
    return None
