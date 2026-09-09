"""RSI / fiyat uyumsuzluk tespiti — regular + hidden, 3+ pivot."""
from __future__ import annotations

from typing import Literal, Optional

import pandas as pd

from structure.core import last_pivots

DivKind = Literal["regular_bull", "regular_bear", "hidden_bull", "hidden_bear"]


def rsi_divergence(
    df: pd.DataFrame,
    *,
    rsi_col: str = "rsi",
    min_pivots: int = 3,
) -> Optional[DivKind]:
    """Son pivot zincirinde regular veya hidden divergence."""
    if df is None or len(df) < 60 or rsi_col not in df.columns:
        return None
    rsi = df[rsi_col]
    lows = last_pivots(df, "low", min_pivots + 2)
    highs = last_pivots(df, "high", min_pivots + 2)
    if len(lows) >= min_pivots:
        seg = lows[-min_pivots:]
        prices = [p[1] for p in seg]
        rsis = [float(rsi.iloc[p[0]]) for p in seg]
        if all(prices[i] > prices[i + 1] for i in range(len(prices) - 1)) and all(
            rsis[i] < rsis[i + 1] for i in range(len(rsis) - 1)
        ):
            return "regular_bull"
        if all(prices[i] < prices[i + 1] for i in range(len(prices) - 1)) and all(
            rsis[i] > rsis[i + 1] for i in range(len(rsis) - 1)
        ):
            return "hidden_bull"
    if len(highs) >= min_pivots:
        seg = highs[-min_pivots:]
        prices = [p[1] for p in seg]
        rsis = [float(rsi.iloc[p[0]]) for p in seg]
        if all(prices[i] < prices[i + 1] for i in range(len(prices) - 1)) and all(
            rsis[i] > rsis[i + 1] for i in range(len(rsis) - 1)
        ):
            return "regular_bear"
        if all(prices[i] > prices[i + 1] for i in range(len(prices) - 1)) and all(
            rsis[i] < rsis[i + 1] for i in range(len(rsis) - 1)
        ):
            return "hidden_bear"
    return None
