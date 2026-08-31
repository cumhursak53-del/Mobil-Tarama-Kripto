"""Local technical indicators. All series are aligned to the input index; no lookahead."""
from __future__ import annotations

import numpy as np
import pandas as pd


def sma(series: pd.Series, n: int) -> pd.Series:
    return series.rolling(n, min_periods=n).mean()


def ema(series: pd.Series, n: int) -> pd.Series:
    return series.ewm(span=n, adjust=False, min_periods=n).mean()


def wma(series: pd.Series, n: int) -> pd.Series:
    weights = np.arange(1, n + 1, dtype=float)

    def _wma(x: np.ndarray) -> float:
        return float(np.dot(x, weights) / weights.sum())

    return series.rolling(n, min_periods=n).apply(_wma, raw=True)


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev = close.shift(1)
    return pd.concat([(high - low), (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)


def atr(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.Series:
    tr = true_range(high, low, close)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    avg_loss = loss.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100.0 - (100.0 / (1.0 + rs))
    out = out.mask(avg_loss.eq(0) & avg_gain.gt(0), 100.0)
    out = out.mask(avg_loss.eq(0) & avg_gain.eq(0), 50.0)
    return out


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    line = ema(close, fast) - ema(close, slow)
    sig = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    hist = line - sig
    return line, sig, hist


def bollinger(close: pd.Series, n: int = 20, k: float = 2.0):
    mid = sma(close, n)
    std = close.rolling(n, min_periods=n).std(ddof=0)
    upper = mid + k * std
    lower = mid - k * std
    width = (upper - lower) / mid.replace(0, np.nan)
    return mid, upper, lower, width


def cci(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 20) -> pd.Series:
    tp = (high + low + close) / 3.0
    ma = sma(tp, n)
    mad = tp.rolling(n, min_periods=n).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
    return (tp - ma) / (0.015 * mad.replace(0, np.nan))


def stochastic(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14, d: int = 3):
    lowest = low.rolling(n, min_periods=n).min()
    highest = high.rolling(n, min_periods=n).max()
    k = 100.0 * (close - lowest) / (highest - lowest).replace(0, np.nan)
    d_line = sma(k, d)
    return k, d_line


def stoch_rsi(close: pd.Series, n: int = 14, d: int = 3):
    r = rsi(close, n)
    lowest = r.rolling(n, min_periods=n).min()
    highest = r.rolling(n, min_periods=n).max()
    k = 100.0 * (r - lowest) / (highest - lowest).replace(0, np.nan)
    d_line = sma(k, d)
    return k, d_line


def donchian_mid(high: pd.Series, low: pd.Series, n: int) -> pd.Series:
    return (high.rolling(n, min_periods=n).max() + low.rolling(n, min_periods=n).min()) / 2.0


def ichimoku(high: pd.Series, low: pd.Series, close: pd.Series, tenkan_n=9, kijun_n=26, senkou_b_n=52, shift=26):
    tenkan = donchian_mid(high, low, tenkan_n)
    kijun = donchian_mid(high, low, kijun_n)
    span_a = ((tenkan + kijun) / 2.0).shift(shift)
    span_b = donchian_mid(high, low, senkou_b_n).shift(shift)
    chikou = close.shift(-shift)
    return tenkan, kijun, span_a, span_b, chikou


def crossed_up(a: pd.Series, b: pd.Series) -> pd.Series:
    prev_a, prev_b = a.shift(1), b.shift(1)
    return (a > b) & (prev_a <= prev_b)


def crossed_down(a: pd.Series, b: pd.Series) -> pd.Series:
    prev_a, prev_b = a.shift(1), b.shift(1)
    return (a < b) & (prev_a >= prev_b)


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Mutates a copy: expects columns open, high, low, close, volume."""
    out = df.copy()
    c, h, l, v = out["close"], out["high"], out["low"], out["volume"]

    out["sma9"] = sma(c, 9)
    out["sma14"] = sma(c, 14)
    out["sma20"] = sma(c, 20)
    out["sma50"] = sma(c, 50)
    out["sma200"] = sma(c, 200)
    out["ema8"] = ema(c, 8)
    out["ema13"] = ema(c, 13)
    out["ema20"] = ema(c, 20)
    out["ema21"] = ema(c, 21)
    out["ema34"] = ema(c, 34)
    out["ema50"] = ema(c, 50)
    out["ema55"] = ema(c, 55)
    out["wma9"] = wma(c, 9)
    out["vol_sma"] = sma(v, 20)
    out["atr"] = atr(h, l, c, 14)
    out["rsi"] = rsi(c, 14)
    macd_line, macd_sig, macd_hist = macd(c)
    out["macd"] = macd_line
    out["macd_signal"] = macd_sig
    out["macd_hist"] = macd_hist
    bb_mid, bb_up, bb_lo, bb_w = bollinger(c)
    out["bb_mid"] = bb_mid
    out["bb_upper"] = bb_up
    out["bb_lower"] = bb_lo
    out["bb_width"] = bb_w
    out["bb_width_med"] = bb_w.rolling(50, min_periods=20).median()
    out["cci"] = cci(h, l, c, 20)
    out["cci_sma5"] = sma(out["cci"], 5)
    k, d = stochastic(h, l, c, 14, 3)
    out["stoch_k"] = k
    out["stoch_d"] = d
    sr_k, sr_d = stoch_rsi(c, 14, 3)
    out["stochrsi_k"] = sr_k
    out["stochrsi_d"] = sr_d
    tenkan, kijun, sa, sb, chikou = ichimoku(h, l, c)
    out["ichi_tenkan"] = tenkan
    out["ichi_kijun"] = kijun
    out["ichi_span_a"] = sa
    out["ichi_span_b"] = sb
    out["ichi_chikou"] = chikou
    out["macd_cross_up"] = crossed_up(out["macd"], out["macd_signal"])
    out["macd_cross_down"] = crossed_down(out["macd"], out["macd_signal"])
    out["sma9_cross_up"] = crossed_up(out["sma9"], out["sma14"])
    out["sma9_cross_down"] = crossed_down(out["sma9"], out["sma14"])
    out["ema21_cross_up"] = crossed_up(out["ema21"], out["ema55"])
    out["ema21_cross_down"] = crossed_down(out["ema21"], out["ema55"])
    out["stoch_cross_up"] = crossed_up(out["stoch_k"], out["stoch_d"])
    out["stoch_cross_down"] = crossed_down(out["stoch_k"], out["stoch_d"])
    out["stochrsi_cross_up"] = crossed_up(out["stochrsi_k"], out["stochrsi_d"])
    out["stochrsi_cross_down"] = crossed_down(out["stochrsi_k"], out["stochrsi_d"])
    out["cci_cross_up"] = crossed_up(out["cci"], out["cci_sma5"])
    out["cci_cross_down"] = crossed_down(out["cci"], out["cci_sma5"])
    out["tenkan_cross_up"] = crossed_up(out["ichi_tenkan"], out["ichi_kijun"])
    out["tenkan_cross_down"] = crossed_down(out["ichi_tenkan"], out["ichi_kijun"])
    body = (c - out["open"]).abs()
    rng = (h - l).replace(0, np.nan)
    out["body"] = body
    out["range"] = h - l
    out["body_ratio"] = body / rng
    out["close_loc"] = (c - l) / rng
    out["vol_ok"] = v > out["vol_sma"]
    return out
