"""Golden test OHLCV fixture ureticileri."""
from __future__ import annotations

import numpy as np
import pandas as pd

from engine.context import build_context
from engine.types import Stage
from indicators.core import add_indicators
from structure.core import add_structure


def _ohlcv(n: int, close: np.ndarray, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "open": close,
        "high": close + rng.random(n) * 0.8 + 0.2,
        "low": close - rng.random(n) * 0.8 - 0.2,
        "close": close,
        "volume": rng.integers(2000, 8000, n).astype(float),
        "close_time": pd.date_range("2024-01-01", periods=n, freq="h"),
    })
    return add_indicators(add_structure(df))


def build_mtf_frames(n: int = 260, seed: int = 42, close: np.ndarray | None = None) -> dict[str, pd.DataFrame]:
    if close is None:
        rng = np.random.default_rng(seed)
        close = 100 + np.cumsum(rng.normal(0, 0.7, n))
    return {
        "15m": _ohlcv(n, close, seed),
        "1h": _ohlcv(n, close, seed + 1),
        "4h": _ohlcv(n, close, seed + 2),
        "1d": _ohlcv(n, close, seed + 3),
        "1w": _ohlcv(max(n // 4, 80), close[-max(n // 4, 80):], seed + 4),
    }


def make_context(
    symbol: str = "SOLUSDT",
    seed: int = 42,
    dominance: dict | None = None,
    close: np.ndarray | None = None,
):
    frames = build_mtf_frames(seed=seed, close=close)
    dom = dominance or {
        "btc_d": 51.0, "usdt_d": 4.2, "btc_d_chg": -0.3, "usdt_d_chg": -0.2,
        "btc_chg": 0.2, "total2": 48.0, "eth_btc": 0.05, "eth_btc_chg": 0.1,
    }
    ctx = build_context(symbol, frames, dom, indicated=True)
    return ctx, frames


def fixture_rsi_regular_bull() -> tuple:
    """Fiyat lower low, RSI higher low — pozitif uyumsuzluk."""
    n = 200
    close = np.full(n, 100.0)
    for i in range(n):
        close[i] = 100 - (i // 40) * 2 + np.sin(i / 5) * 0.5
    frames = build_mtf_frames(n=n, close=close, seed=11)
    df = frames["1h"]
    lows_idx = [40, 80, 120]
    rsi_vals = [28.0, 34.0, 40.0]
    for idx, rv in zip(lows_idx, rsi_vals):
        df.loc[df.index[idx], "low"] = float(close[idx]) - 2.0
        df.loc[df.index[idx], "close"] = float(close[idx]) - 1.0
        df.loc[df.index[idx], "rsi"] = rv
    df.loc[df.index[-1], "rsi"] = 38.0
    frames["1h"] = df
    ctx, _ = make_context(dominance={"btc_d_chg": 0, "usdt_d_chg": 0, "btc_chg": 0})
    ctx.frames = frames
    return ctx


def fixture_wyckoff_spring() -> tuple:
    n = 120
    close = np.linspace(100, 99, n)
    close[-5:] = [98.5, 98.2, 97.8, 99.5, 100.2]
    frames = build_mtf_frames(n=n, close=close, seed=22)
    df = frames["1d"]
    df.loc[df.index[-2], "low"] = 97.0
    df.loc[df.index[-2], "close"] = 99.0
    df.loc[df.index[-2], "volume"] = float(df["vol_sma"].iloc[-2]) * 1.5
    df.loc[df.index[-1], "close"] = 100.0
    frames["1d"] = df
    ctx, _ = make_context()
    ctx.frames = frames
    ctx.stage = Stage.ACCUMULATION
    return ctx


def fixture_dominance_alt_long() -> tuple:
    ctx, _ = make_context(
        dominance={
            "btc_d": 50.0, "usdt_d": 4.0, "btc_d_chg": -0.4, "usdt_d_chg": -0.3,
            "btc_chg": 0.1, "total2": 40.0, "eth_btc": 0.04, "eth_btc_chg": 0.05,
        },
    )
    df = ctx.tf("1h")
    df.loc[df.index[-1], "close"] = float(df["ema50"].iloc[-1]) * 1.02
    return ctx


def fixture_fib_ote_long() -> tuple:
    n = 200
    close = np.concatenate([np.linspace(90, 110, 120), np.linspace(110, 102, 80)])
    frames = build_mtf_frames(n=n, close=close, seed=33)
    ctx, _ = make_context()
    ctx.frames = frames
    return ctx
