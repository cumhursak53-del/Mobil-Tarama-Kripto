"""Bybit uyumlu fiyat gosterimi (tickSize) — tek seferlik toplu cache."""
from __future__ import annotations

import math
import threading
import time

_TICK_CACHE: dict[str, float] = {}
_BULK_LOADED = False
_BULK_LOCK = threading.Lock()
_CACHE_TTL = 3600.0
_BULK_TS = 0.0


def _decimals_from_tick(tick: float) -> int:
    if tick <= 0:
        return 8
    s = f"{tick:.14f}".rstrip("0")
    if "." not in s:
        return 0
    return len(s.split(".")[1])


def _round_to_tick(price: float, tick: float) -> float:
    if tick <= 0:
        return price
    steps = round(price / tick)
    return round(steps * tick, 14)


def _load_all_ticks() -> None:
    """Tum linear tickSize — tek seferlik (UI donmasin diye sembol basi HTTP yok)."""
    global _BULK_LOADED, _BULK_TS
    now = time.time()
    if _BULK_LOADED and now - _BULK_TS < _CACHE_TTL:
        return
    found: dict[str, float] = {}
    try:
        from engine.data import _get

        cursor = ""
        pages = 0
        while pages < 8:
            params: dict = {"category": "linear", "limit": "1000"}
            if cursor:
                params["cursor"] = cursor
            raw = _get(
                "https://api.bybit.com/v5/market/instruments-info",
                params,
                timeout=8,
            )
            result = raw.get("result") or {}
            for item in result.get("list") or []:
                sym = str(item.get("symbol") or "")
                pf = item.get("priceFilter") or {}
                tick = float(pf.get("tickSize") or 0)
                if sym and tick > 0:
                    found[sym] = tick
            cursor = str(result.get("nextPageCursor") or "")
            pages += 1
            if not cursor:
                break
        if found:
            _TICK_CACHE.update(found)
    except Exception:
        pass
    finally:
        # Basarisiz olsa bile tekrar tekrar ag cagrisi yapma (monitor donmasin).
        _BULK_LOADED = True
        _BULK_TS = now


def warm_tick_cache(_symbols: list[str] | None = None) -> None:
    """UI oncesi tick cache doldur (bloklamadan once bir kez cagir)."""
    del _symbols
    if _BULK_LOADED:
        return
    with _BULK_LOCK:
        if not _BULK_LOADED:
            _load_all_ticks()


def _tick_size(symbol: str | None) -> float:
    if not symbol:
        return 0.0
    sym = str(symbol).upper()
    if sym in _TICK_CACHE:
        return _TICK_CACHE[sym]
    return 0.0


def format_price(v: float | None) -> str:
    """Sembol bilinmiyorsa Bybit benzeri ondalik (sifir kaybi yok)."""
    if v is None:
        return "-"
    try:
        val = float(v)
    except (TypeError, ValueError):
        return str(v)
    if val == 0:
        return "0"
    av = abs(val)
    if av >= 1000:
        text = f"{val:,.4f}"
    elif av >= 1:
        text = f"{val:.6f}"
    elif av >= 0.0001:
        text = f"{val:.8f}"
    else:
        decimals = min(12, max(8, int(-math.floor(math.log10(av))) + 4))
        text = f"{val:.{decimals}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text.replace(",", "")


def format_price_symbol(symbol: str | None, price: float | None) -> str:
    """Bybit tickSize ile yuvarla — hot path'te ag cagrisi yok."""
    if price is None:
        return "-"
    try:
        val = float(price)
    except (TypeError, ValueError):
        return str(price)
    if val == 0:
        return "0"
    tick = _tick_size(symbol)
    if tick > 0:
        val = _round_to_tick(val, tick)
        dec = _decimals_from_tick(tick)
        text = f"{val:.{dec}f}"
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return text or "0"
    return format_price(val)
