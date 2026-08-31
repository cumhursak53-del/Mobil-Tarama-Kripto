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
    ):
        self.symbol = symbol
        self.frames = frames
        self.stage = stage
        self.week_bias = week_bias
        self.dominance = dominance

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

    @abstractmethod
    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        ...
