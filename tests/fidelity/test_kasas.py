"""Kasa basina golden smoke testleri — 31 strateji."""
import numpy as np
import pandas as pd
import pytest

from engine.context import build_context
from indicators.core import add_indicators
from strategies.registry import _CLASSES
from structure.core import add_structure


def _make_frames(seed: int = 42) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    frames = {}
    for tf in ("15m", "1h", "4h", "1d", "1w"):
        n = 260
        close = 100 + np.cumsum(rng.normal(0, 0.9, n))
        df = pd.DataFrame({
            "open": close,
            "high": close + rng.random(n) * 1.5,
            "low": close - rng.random(n) * 1.5,
            "close": close,
            "volume": rng.integers(1000, 9000, n).astype(float),
            "close_time": pd.date_range("2024-01-01", periods=n, freq="h"),
        })
        frames[tf] = add_indicators(add_structure(df))
    return frames


@pytest.mark.parametrize("strategy_cls", _CLASSES, ids=lambda c: c().ledger)
def test_kasa_signal_smoke(strategy_cls):
    frames = _make_frames(hash(strategy_cls.__name__) % 1000)
    dominance = {
        "btc_d": 52.0,
        "usdt_d": 4.5,
        "btc_d_chg": -0.2,
        "usdt_d_chg": -0.1,
        "btc_chg": 0.5,
        "total2": 48.0,
    }
    ctx = build_context("ETHUSDT", frames, dominance, indicated=True)
    strat = strategy_cls()
    sig = strat.signal(ctx)
    if sig is not None:
        assert sig.sl_price > 0
        assert sig.side is not None
        assert strat.signal_strength(ctx, sig) >= 0
