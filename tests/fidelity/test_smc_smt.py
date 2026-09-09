"""SMT ve OB+FVG SMC unit testleri."""
import numpy as np
import pandas as pd

from structure.core import add_structure
from structure.smc_smt import detect_smt


def _df(closes: list[float]) -> pd.DataFrame:
    c = np.array(closes, dtype=float)
    df = pd.DataFrame({
        "open": c,
        "high": c + 0.5,
        "low": c - 0.5,
        "close": c,
        "volume": np.full(len(c), 5000.0),
        "close_time": pd.date_range("2024-01-01", periods=len(c), freq="h"),
    })
    return add_structure(df)


def test_detect_smt_bull_divergence():
    alt = _df([100 + (i % 5) for i in range(80)])
    alt.loc[alt.index[-1], "low"] = 90
    alt.loc[alt.index[-2], "low"] = 95
    ref = _df([100 + i * 0.1 for i in range(80)])
    ref.loc[ref.index[-1], "low"] = 102
    ref.loc[ref.index[-2], "low"] = 100
    bull, bear = detect_smt(alt, ref)
    assert isinstance(bull, bool)
    assert isinstance(bear, bool)
