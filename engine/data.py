from __future__ import annotations

import time
from typing import Optional

import pandas as pd

from engine.config import EXCLUDED_SYMBOLS, KLINE_LIMITS, SCAN_SYMBOLS, TIMEFRAMES

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

try:
    from curl_cffi import requests as cf_requests
    _HTTP = cf_requests.Session(impersonate="chrome120")
except Exception:
    import requests
    _HTTP = requests.Session()
    _HTTP.headers.update({"User-Agent": _UA})

_BYBIT_TF = {"15m": "15", "1h": "60", "4h": "240", "1d": "D", "1w": "W"}
_OKX_TF = {"15m": "15m", "1h": "1H", "4h": "4H", "1d": "1Dutc", "1w": "1Wutc"}
_CC_KIND = {
    "15m": ("histominute", 15),
    "1h": ("histohour", 1),
    "4h": ("histohour", 4),
    "1d": ("histoday", 1),
    "1w": ("histoday", 7),
}
DEFAULT_UNIVERSE = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "BNBUSDT",
    "ADAUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT", "NEARUSDT", "SUIUSDT",
    "LTCUSDT", "ATOMUSDT", "APTUSDT", "ARBUSDT", "OPUSDT", "INJUSDT",
]

_active_venue: Optional[str] = None  # bybit | okx | binance | cryptocompare


def _get(url: str, params: Optional[dict] = None, timeout: int = 12):
    r = _HTTP.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _to_df(rows: list) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["open_time", "open", "high", "low", "close", "volume", "close_time"])
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)
    df = df.dropna().sort_values("open_time").drop_duplicates("open_time")
    df = df.set_index("open_time")
    if len(df) >= 2:
        df = df.iloc[:-1]
    return df


def _binance_klines(symbol: str, interval: str, limit: int) -> pd.DataFrame:
    raw = _get(
        "https://api.binance.com/api/v3/klines",
        {"symbol": symbol, "interval": interval, "limit": limit},
        timeout=8,
    )
    rows = [[x[0], x[1], x[2], x[3], x[4], x[5], x[6]] for x in raw]
    return _to_df(rows)


def _bybit_klines(symbol: str, interval: str, limit: int) -> pd.DataFrame:
    iv = _BYBIT_TF[interval]
    raw = _get(
        "https://api.bybit.com/v5/market/kline",
        {"category": "linear", "symbol": symbol, "interval": iv, "limit": min(limit, 1000)},
        timeout=10,
    )
    lst = (raw.get("result") or {}).get("list") or []
    # Bybit: newest first: start, open, high, low, close, volume, turnover
    rows = []
    ms = {"15m": 15 * 60_000, "1h": 60 * 60_000, "4h": 4 * 60 * 60_000, "1d": 86_400_000, "1w": 7 * 86_400_000}[interval]
    for x in reversed(lst):
        start = int(x[0])
        rows.append([start, x[1], x[2], x[3], x[4], x[5], start + ms - 1])
    return _to_df(rows)


def _okx_symbol(symbol: str) -> str:
    if symbol.endswith("USDT"):
        return symbol[:-4] + "-USDT-SWAP"
    return symbol + "-SWAP"


def _okx_klines(symbol: str, interval: str, limit: int) -> pd.DataFrame:
    inst = _okx_symbol(symbol)
    raw = _get(
        "https://www.okx.com/api/v5/market/candles",
        {"instId": inst, "bar": _OKX_TF[interval], "limit": str(min(limit, 300))},
        timeout=10,
    )
    lst = raw.get("data") or []
    ms = {"15m": 15 * 60_000, "1h": 60 * 60_000, "4h": 4 * 60 * 60_000, "1d": 86_400_000, "1w": 7 * 86_400_000}[interval]
    rows = []
    for x in reversed(lst):
        start = int(x[0])
        rows.append([start, x[1], x[2], x[3], x[4], x[5], start + ms - 1])
    return _to_df(rows)


def _cc_parts(symbol: str) -> tuple[str, str]:
    if symbol.endswith("USDT"):
        return symbol[:-4], "USDT"
    return symbol, "USD"


def _cc_klines(symbol: str, interval: str, limit: int) -> pd.DataFrame:
    kind, agg = _CC_KIND[interval]
    fsym, tsym = _cc_parts(symbol)
    raw = _get(
        f"https://min-api.cryptocompare.com/data/v2/{kind}",
        {"fsym": fsym, "tsym": tsym, "limit": min(limit, 2000), "aggregate": agg},
        timeout=10,
    )
    lst = ((raw.get("Data") or {}).get("Data") or [])
    ms = {"15m": 15 * 60_000, "1h": 60 * 60_000, "4h": 4 * 60 * 60_000, "1d": 86_400_000, "1w": 7 * 86_400_000}[interval]
    rows = []
    for x in lst:
        start = int(x["time"]) * 1000
        rows.append([start, x["open"], x["high"], x["low"], x["close"], x.get("volumefrom") or 0, start + ms - 1])
    return _to_df(rows)


def fetch_klines(symbol: str, interval: str, limit: Optional[int] = None) -> pd.DataFrame:
    global _active_venue
    limit = limit or KLINE_LIMITS.get(interval, 400)
    venues = ("bybit", "okx", "cryptocompare", "binance")
    order = [_active_venue] + [v for v in venues if v != _active_venue]
    last_err = None
    for venue in order:
        if venue is None:
            continue
        try:
            if venue == "bybit":
                df = _bybit_klines(symbol, interval, limit)
            elif venue == "okx":
                df = _okx_klines(symbol, interval, limit)
            elif venue == "cryptocompare":
                df = _cc_klines(symbol, interval, limit)
            else:
                df = _binance_klines(symbol, interval, limit)
            if df is None or df.empty:
                continue
            _active_venue = venue
            return df
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(f"klines failed {symbol} {interval}: {last_err}")


def fetch_symbols(limit: int = SCAN_SYMBOLS) -> list[str]:
    """USDT perpetual evreni. limit<=0 ise hacmi olan tum sozlesmeler."""
    global _active_venue
    rows: list[tuple[str, float]] = []
    try:
        raw = _get("https://api.bybit.com/v5/market/tickers", {"category": "linear"}, timeout=10)
        lst = (raw.get("result") or {}).get("list") or []
        for t in lst:
            sym = t.get("symbol") or ""
            if not _is_tradeable_usdt(sym):
                continue
            rows.append((sym, float(t.get("turnover24h") or 0)))
        if rows:
            _active_venue = _active_venue or "bybit"
            return _rank_symbols(rows, limit)
    except Exception:
        pass
    try:
        raw = _get("https://www.okx.com/api/v5/market/tickers", {"instType": "SWAP"}, timeout=10)
        for t in raw.get("data") or []:
            inst = t.get("instId") or ""
            if not inst.endswith("-USDT-SWAP"):
                continue
            base = inst.replace("-USDT-SWAP", "") + "USDT"
            if not _is_tradeable_usdt(base):
                continue
            rows.append((base, float(t.get("volCcy24h") or 0)))
        if rows:
            _active_venue = _active_venue or "okx"
            return _rank_symbols(rows, limit)
    except Exception:
        pass
    return list(DEFAULT_UNIVERSE if (not limit or limit <= 0) else DEFAULT_UNIVERSE[:limit])


def _is_tradeable_usdt(sym: str) -> bool:
    if not sym.endswith("USDT"):
        return False
    if sym in EXCLUDED_SYMBOLS:
        return False
    if sym.endswith("USDC") or "USDC" in sym[:4]:
        return False
    return True


def _rank_symbols(rows: list[tuple[str, float]], limit: int) -> list[str]:
    rows = [(s, v) for s, v in rows if v > 0]
    rows.sort(key=lambda x: x[1], reverse=True)
    names = [s for s, _ in rows]
    if limit and limit > 0:
        return names[:limit]
    return names


def fetch_all_timeframes(symbol: str) -> dict[str, pd.DataFrame]:
    out = {}
    for tf in TIMEFRAMES:
        try:
            out[tf] = fetch_klines(symbol, tf)
        except Exception:
            continue
        time.sleep(0.03)
    return out


def fetch_dominance() -> dict:
    try:
        g = _get("https://api.coingecko.com/api/v3/global", timeout=12)
        data = g.get("data", {})
        btc_d = float(data.get("market_cap_percentage", {}).get("btc") or 0)
        usdt_d = float(data.get("market_cap_percentage", {}).get("usdt") or 0)
        return {
            "btc_d": btc_d,
            "usdt_d": usdt_d,
            "btc_chg": 0.0,
            "btc_d_chg": None,
            "usdt_d_chg": None,
        }
    except Exception:
        return {}


def last_prices(symbols: list[str]) -> dict[str, float]:
    want = set(symbols)
    out: dict[str, float] = {}
    try:
        raw = _get("https://api.bybit.com/v5/market/tickers", {"category": "linear"}, timeout=8)
        for t in (raw.get("result") or {}).get("list") or []:
            if t.get("symbol") in want:
                out[t["symbol"]] = float(t["lastPrice"])
        if out:
            return out
    except Exception:
        pass
    try:
        raw = _get("https://www.okx.com/api/v5/market/tickers", {"instType": "SWAP"}, timeout=8)
        for t in raw.get("data") or []:
            inst = t.get("instId") or ""
            if inst.endswith("-USDT-SWAP"):
                name = inst.replace("-USDT-SWAP", "") + "USDT"
                if name in want:
                    out[name] = float(t["last"])
    except Exception:
        pass
    return out
