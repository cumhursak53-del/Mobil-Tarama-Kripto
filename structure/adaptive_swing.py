"""ATR/volatiliteye gore adaptive swing lookback (Lux benzeri)."""
from __future__ import annotations

import pandas as pd

from engine.config import SWING_N


def _atr_pct(df: pd.DataFrame) -> float:
    if df is None or df.empty:
        return 0.01
    if "atr" in df.columns and pd.notna(df["atr"].iloc[-1]):
        atr = float(df["atr"].iloc[-1])
    else:
        hl = (df["high"] - df["low"]).tail(14)
        atr = float(hl.mean()) if len(hl) else float(df["close"].iloc[-1]) * 0.01
    price = float(df["close"].iloc[-1])
    return atr / max(price, 1e-9)


def swing_ns(
    df: pd.DataFrame,
    *,
    base: int = SWING_N,
    min_internal: int = 2,
    max_external: int = 12,
) -> tuple[int, int]:
    """
    Volatilite yuksek → daha genis swing (gurultu filtre).
    Volatilite dusuk → daha dar swing (hassas yapi).
    Returns (internal_n, external_n).
    """
    atr_pct = _atr_pct(df)
    if atr_pct >= 0.025:
        external = min(max_external, base + 3)
    elif atr_pct >= 0.015:
        external = min(max_external, base + 1)
    elif atr_pct <= 0.006:
        external = max(min_internal + 2, base - 2)
    elif atr_pct <= 0.010:
        external = max(min_internal + 2, base - 1)
    else:
        external = base
    internal = max(min_internal, external - 2)
    return internal, external
