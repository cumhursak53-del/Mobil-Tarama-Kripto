"""Strateji smoke + fidelity — her kasa en az bir kez calisir."""
import numpy as np
import pandas as pd

from engine.context import build_context
from engine.types import Stage
from indicators.core import add_indicators
from strategies.registry import all_strategies
from structure.core import add_structure


def _ctx() -> tuple:
    rng = np.random.default_rng(99)
    frames = {}
    for tf in ("15m", "1h", "4h", "1d", "1w"):
        n = 250
        close = 100 + np.cumsum(rng.normal(0, 1, n))
        df = pd.DataFrame({
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": rng.integers(1000, 9000, n).astype(float),
            "close_time": pd.date_range("2024-01-01", periods=n, freq="h"),
        })
        frames[tf] = add_indicators(add_structure(df))
    dominance = {"btc_d": 52.0, "usdt_d": 4.5, "btc_d_chg": -0.2, "usdt_d_chg": -0.1, "btc_chg": 0.5, "total2": 48.0}
    ctx = build_context("SOLUSDT", frames, dominance, indicated=True)
    return ctx, frames


def test_all_strategies_signal_callable():
    ctx, _ = _ctx()
    strats = all_strategies()
    assert len(strats) >= 31
    errors = []
    for s in strats:
        try:
            sig = s.signal(ctx)
            if sig is not None:
                assert sig.sl_price > 0
                assert hasattr(s, "signal_strength")
        except Exception as e:
            errors.append(f"{s.ledger}: {e}")
    assert not errors, errors


def test_best_signal_strength_order():
    from strategies.base import Strategy
    from engine.types import Signal, Side

    class _A(Strategy):
        name = ledger = "A"
        def signal(self, ctx):
            return Signal(Side.BUY, "t", "A", "t", 99.0, strength=1.0)
        def signal_strength(self, ctx, sig):
            return 1.0

    class _B(Strategy):
        name = ledger = "B"
        def signal(self, ctx):
            return Signal(Side.BUY, "t", "B", "t", 99.0, strength=3.0)
        def signal_strength(self, ctx, sig):
            return 3.0

    ctx, _ = _ctx()
    scores = [(s.signal_strength(ctx, s.signal(ctx)), s.ledger) for s in [_A(), _B()] if s.signal(ctx)]
    scores.sort(reverse=True)
    assert scores[0][1] == "B"
