"""Coin 24s degisimi / BTC 24s degisimi orani."""
from __future__ import annotations

import time

from engine.data import _get

BTC_SYMBOL = "BTCUSDT"
_CACHE_TTL_SEC = 45.0
_BTC_EPS_PCT = 0.05
_cache: dict = {"at": 0.0, "changes": {}}


def _parse_pct(raw) -> float | None:
    if raw is None:
        return None
    try:
        return float(raw) * 100.0
    except (TypeError, ValueError):
        return None


def fetch_all_24h_changes() -> dict[str, float]:
    """Bybit linear tum semboller — price24hPcnt yuzde olarak."""
    out: dict[str, float] = {}
    try:
        raw = _get("https://api.bybit.com/v5/market/tickers", {"category": "linear"}, timeout=12)
        for t in (raw.get("result") or {}).get("list") or []:
            sym = t.get("symbol")
            pct = _parse_pct(t.get("price24hPcnt"))
            if sym and pct is not None:
                out[str(sym)] = pct
        if out:
            return out
    except Exception:
        pass
    try:
        raw = _get("https://api.binance.com/api/v3/ticker/24hr", timeout=12)
        for t in raw if isinstance(raw, list) else []:
            sym = str(t.get("symbol") or "")
            if not sym.endswith("USDT"):
                continue
            try:
                out[sym] = float(t.get("priceChangePercent") or 0)
            except (TypeError, ValueError):
                continue
    except Exception:
        pass
    return out


def get_24h_changes(*, refresh: bool = False) -> dict[str, float]:
    global _cache
    now = time.time()
    if not refresh and _cache.get("changes") and now - float(_cache.get("at") or 0) < _CACHE_TTL_SEC:
        return dict(_cache["changes"])
    changes = fetch_all_24h_changes()
    if changes:
        _cache = {"at": now, "changes": changes}
    return dict(_cache.get("changes") or {})


def btc_relative_change(symbol: str, changes: dict[str, float] | None = None) -> dict:
    data = changes if changes is not None else get_24h_changes()
    coin = data.get(symbol)
    btc = data.get(BTC_SYMBOL)
    ratio = None
    if coin is not None and btc is not None and abs(btc) >= _BTC_EPS_PCT:
        ratio = round(coin / btc, 3)
    return {
        "coin_chg_24h": round(coin, 3) if coin is not None else None,
        "btc_chg_24h": round(btc, 3) if btc is not None else None,
        "btc_rel_ratio": ratio,
    }


def format_btc_relative_log(rel: dict | None) -> str:
    if not rel:
        return ""
    coin = rel.get("coin_chg_24h")
    btc = rel.get("btc_chg_24h")
    ratio = rel.get("btc_rel_ratio")
    if coin is None and btc is None:
        return ""
    parts = []
    if coin is not None:
        parts.append(f"coin24 {coin:+.2f}%")
    if btc is not None:
        parts.append(f"btc24 {btc:+.2f}%")
    if ratio is not None:
        parts.append(f"btc_oran {ratio:+.3f}")
    return " | ".join(parts)
