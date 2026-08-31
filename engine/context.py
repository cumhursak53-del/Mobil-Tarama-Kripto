from __future__ import annotations

from typing import Optional

from indicators.core import add_indicators
from engine.types import Stage
from strategies.base import MarketContext
from structure.core import add_structure, market_stage, weekly_bias


def prepare_frame(df):
    if df is None or df.empty:
        return df
    return add_structure(add_indicators(df))


def indicate_frame(df):
    if df is None or df.empty:
        return df
    if "rsi" in df.columns:
        return df
    return add_indicators(df)


def build_context(symbol: str, frames: dict, dominance: Optional[dict] = None, indicated: bool = False) -> MarketContext:
    prepped = {}
    for tf, df in frames.items():
        if df is None or df.empty:
            continue
        base = df if indicated else add_indicators(df)
        prepped[tf] = base if "swing_high" in base.columns else add_structure(base)
    daily = prepped.get("1d")
    weekly = prepped.get("1w")
    stage = market_stage(daily) if daily is not None else Stage.UNKNOWN
    wbias = weekly_bias(weekly)
    return MarketContext(symbol, prepped, stage, wbias, dominance or {})
