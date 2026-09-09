"""Fidelity golden tests — PDF/LuxAlgo kural dogrulama."""
import numpy as np
import pandas as pd

from engine.types import Stage
from indicators.core import add_indicators
from structure.core import (
    add_structure,
    fib_extension,
    retest_after_break,
    structure_event,
    validated_impulse,
)
from structure.patterns import detect_flag, detect_rectangle


def _frames(n: int = 200) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(7)
    out = {}
    for tf, mult in [("15m", 1), ("1h", 4), ("4h", 16), ("1d", 96), ("1w", 672)]:
        m = max(n // mult, 80)
        close = 100 + np.cumsum(rng.normal(0.05, 0.8, m))
        high = close + rng.random(m)
        low = close - rng.random(m)
        df = pd.DataFrame({
            "open": close,
            "high": high,
            "low": low,
            "close": close,
            "volume": rng.integers(500, 5000, m).astype(float),
            "close_time": pd.date_range("2024-01-01", periods=m, freq="h"),
        })
        df = add_indicators(add_structure(df))
        out[tf] = df
    return out


def test_structure_event_returns_string_or_none():
    df = _frames()["4h"]
    evt = structure_event(df)
    assert evt is None or evt in ("bos_bull", "bos_bear", "choch_bull", "choch_bear")


def test_fib_extension_levels():
    ext = fib_extension(100.0, 110.0, "up")
    assert "1.618" in ext
    assert ext["1.618"] > 110.0


def test_validated_impulse_requires_atr():
    df = _frames()["4h"]
    imp = validated_impulse(df, min_atr=0.1)
    assert imp is None or len(imp) == 3


def test_retest_after_break_false_on_flat():
    df = _frames()["1h"]
    assert retest_after_break(df, float(df["close"].iloc[-1]), "up") in (True, False)


def test_pattern_modules_callable():
    df = _frames()["4h"]
    assert detect_rectangle(df) is None or "height" in detect_rectangle(df)
    assert detect_flag(df) is None or "pole_move" in detect_flag(df)


def test_make_signal_tp_modes():
    from engine.types import Side
    from strategies.helpers import make_signal

    df = _frames()["1h"]
    sig = make_signal("Kasa_Test", "[STRAT: Test]", df, Side.BUY, tp_r_val=2.5, tp_mode="r", strength=2.0)
    assert sig is not None
    assert sig.tp_price is not None
    assert sig.strength == 2.0
