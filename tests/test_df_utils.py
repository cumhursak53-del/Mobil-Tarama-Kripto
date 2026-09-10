import numpy as np
import pandas as pd
import pytest

from engine.df_utils import pick_frame
from engine.lab_backtest import backtest_recipe
from engine.strategy_generator import generate_recipes


def test_pick_frame_skips_empty_dataframe():
    empty = pd.DataFrame()
    full = pd.DataFrame({"close": [1.0, 2.0]})
    frames = {"1h": empty, "4h": full}
    assert pick_frame(frames, "1h", "4h") is full


def test_pick_frame_or_on_empty_raises_without_helper():
    empty = pd.DataFrame()
    with pytest.raises(ValueError, match="ambiguous"):
        empty or pd.DataFrame({"close": [1.0]})


def test_backtest_recipe_falls_back_when_entry_tf_empty():
    """Bos entry_tf DataFrame'i 'or 1h' ile patlatmamali."""
    rng = np.random.default_rng(7)
    n = 200
    close = 100 + np.cumsum(rng.normal(0, 0.5, n))
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    h1 = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": rng.random(n) * 1000 + 50,
        },
        index=idx,
    )
    h1["close_time"] = h1.index
    d1 = h1.iloc[::24].copy()
    d1["close_time"] = d1.index
    frames = {"15m": pd.DataFrame(), "1h": h1, "1d": d1}
    recipe = generate_recipes(limit=1)[0]
    recipe["entry_tf"] = "15m"
    result = backtest_recipe(recipe, "TESTUSDT", frames)
    assert "error" not in result or result.get("trades") is not None
