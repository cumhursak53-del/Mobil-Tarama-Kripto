from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import pandas as pd

from engine.types import Signal, Side, Stage


class MarketContext:
    def __init__(
        self,
        symbol: str,
        frames: dict[str, pd.DataFrame],
        stage: Stage,
        week_bias: Optional[int],
        dominance: dict,
        ref_frames: Optional[dict[str, pd.DataFrame]] = None,
    ):
        self.symbol = symbol
        self.frames = frames
        self.stage = stage
        self.week_bias = week_bias
        self.dominance = dominance
        self.ref_frames = ref_frames or {}

    def tf(self, name: str) -> Optional[pd.DataFrame]:
        return self.frames.get(name)

    def last(self, name: str):
        df = self.tf(name)
        if df is None or df.empty:
            return None
        return df.iloc[-1]

    def aligned(self, side: Side) -> bool:
        """Block longs in declining weekly/daily; shorts in advancing."""
        if self.week_bias == 1 and side == Side.SELL:
            return False
        if self.week_bias == -1 and side == Side.BUY:
            return False
        if self.stage == Stage.DECLINING and side == Side.BUY:
            return False
        if self.stage == Stage.ADVANCING and side == Side.SELL:
            return False
        return True


class Strategy(ABC):
    name: str
    ledger: str
    entry_mode: str = "live"  # bar_close | live
    entry_tf: str = "1h"

    def uses_live_entry(self) -> bool:
        from engine.config import LIVE_ENTRY_LEDGERS

        if self.entry_mode == "live":
            return True
        return self.ledger in LIVE_ENTRY_LEDGERS

    def entry_timeframe(self) -> str:
        from engine.config import ENTRY_TF

        return self.entry_tf or ENTRY_TF

    def signal_strength(self, ctx: MarketContext, sig: Signal) -> float:
        """Override for best_signal scan ranking. Default uses sig.strength."""
        return float(sig.strength or 1.0)

    @abstractmethod
    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        ...
