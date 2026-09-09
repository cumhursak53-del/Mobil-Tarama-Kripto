"""SMT — Smart Money Technique: alt vs BTC/ETH yapı uyumsuzluğu."""
from __future__ import annotations

from typing import Optional

import pandas as pd

from structure.core import last_pivots


def detect_smt(
    alt_df: pd.DataFrame,
    ref_df: pd.DataFrame,
    *,
    pivot_count: int = 3,
) -> tuple[bool, bool]:
    """
    Bullish SMT: alt lower low + ref higher low.
    Bearish SMT: alt higher high + ref lower high.
    """
    if alt_df is None or ref_df is None or len(alt_df) < 40 or len(ref_df) < 40:
        return False, False
    alt_lows = last_pivots(alt_df, "low", pivot_count)
    alt_highs = last_pivots(alt_df, "high", pivot_count)
    ref_lows = last_pivots(ref_df, "low", pivot_count)
    ref_highs = last_pivots(ref_df, "high", pivot_count)
    smt_bull = (
        len(alt_lows) >= 2 and len(ref_lows) >= 2
        and alt_lows[-1][1] < alt_lows[-2][1]
        and ref_lows[-1][1] > ref_lows[-2][1]
    )
    smt_bear = (
        len(alt_highs) >= 2 and len(ref_highs) >= 2
        and alt_highs[-1][1] > alt_highs[-2][1]
        and ref_highs[-1][1] < ref_highs[-2][1]
    )
    return smt_bull, smt_bear


def apply_smt_to_analysis(analysis, alt_frames: dict, ref_frames: dict) -> None:
    """SMCAnalysis'a smt_bull/smt_bear ekler ve skorları günceller."""
    h1_alt = alt_frames.get("1h")
    h1_ref = ref_frames.get("1h")
    bull, bear = detect_smt(h1_alt, h1_ref)
    analysis.smt_bull = bull  # type: ignore[attr-defined]
    analysis.smt_bear = bear  # type: ignore[attr-defined]
    if bull:
        analysis.long_score += 1
        analysis.long_notes.append("SMT:bull")
    if bear:
        analysis.short_score += 1
        analysis.short_notes.append("SMT:bear")
