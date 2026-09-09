"""Golden deger testleri — TradingView uyumluluk."""
import numpy as np
import pandas as pd

from indicators.core import add_indicators, obv, rsi, sma


def _sample_ohlcv(n: int = 100) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    close = 100 + np.cumsum(rng.normal(0, 0.5, n))
    high = close + rng.random(n) * 0.5
    low = close - rng.random(n) * 0.5
    open_ = close + rng.normal(0, 0.1, n)
    vol = rng.integers(1000, 5000, n).astype(float)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": vol})


def test_rsi_bounds():
    df = add_indicators(_sample_ohlcv(80))
    r = df["rsi"].dropna()
    assert len(r) > 0
    assert r.min() >= 0
    assert r.max() <= 100


def test_sma_known_values():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    out = sma(s, 3)
    assert abs(float(out.iloc[-1]) - 4.0) < 1e-9


def test_obv_monotonic_up():
    close = pd.Series([1.0, 2.0, 3.0, 4.0])
    vol = pd.Series([100.0, 100.0, 100.0, 100.0])
    o = obv(close, vol)
    assert float(o.iloc[-1]) > float(o.iloc[0])


def test_ttm_squeeze_column():
    df = add_indicators(_sample_ohlcv(120))
    assert "ttm_squeeze" in df.columns
    assert "ttm_squeeze_on" in df.columns
    assert "obv" in df.columns


def test_chikou_signal_no_lookahead():
    df = add_indicators(_sample_ohlcv(80))
    assert "chikou_bull" in df.columns
    assert "chikou_bear" in df.columns
    last = df.iloc[-1]
    assert bool(last["chikou_bull"]) == (float(last["close"]) > float(df["close"].iloc[-27]))
