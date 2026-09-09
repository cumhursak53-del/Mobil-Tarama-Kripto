"""Kapali mum (close_time) dogrulama testleri."""
import pandas as pd

from engine.paper import FrameCache


def _frame_with_times(times: list) -> dict:
    df = pd.DataFrame({
        "open": [1.0] * len(times),
        "high": [1.1] * len(times),
        "low": [0.9] * len(times),
        "close": [1.0] * len(times),
        "volume": [100.0] * len(times),
        "close_time": times,
    })
    return {"1h": df}


def test_new_closed_bar_detects_change():
    cache = FrameCache()
    t1 = pd.Timestamp("2024-01-01 10:00:00")
    t2 = pd.Timestamp("2024-01-01 11:00:00")
    cache.frames["BTCUSDT"] = _frame_with_times([t1])
    assert cache.new_closed_bar("BTCUSDT", "1h") is False
    cache.frames["BTCUSDT"] = _frame_with_times([t1, t2])
    assert cache.new_closed_bar("BTCUSDT", "1h") is True
    assert cache.new_closed_bar("BTCUSDT", "1h") is False


def test_close_time_monotonic():
    idx = pd.date_range("2024-01-01", periods=50, freq="h")
    df = pd.DataFrame({"close_time": idx + pd.Timedelta(hours=1)})
    assert df["close_time"].is_monotonic_increasing
