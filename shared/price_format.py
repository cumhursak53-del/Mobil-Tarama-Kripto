"""Bybit uyumlu fiyat gosterimi (tickSize)."""
from __future__ import annotations

import math
import time

_TICK_CACHE: dict[str, tuple[float, float]] = {}
_CACHE_TTL = 3600.0


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


def _fetch_tick_size(symbol: str) -> float:
    sym = symbol.upper()
    now = time.time()
    cached = _TICK_CACHE.get(sym)
    if cached and now - cached[1] < _CACHE_TTL:
        return cached[0]
    tick = 0.0
    try:
        from engine.data import _get

        raw = _get(
            "https://api.bybit.com/v5/market/instruments-info",
            {"category": "linear", "symbol": sym},
            timeout=8,
        )
        rows = (raw.get("result") or {}).get("list") or []
        if rows:
            pf = rows[0].get("priceFilter") or {}
            tick = float(pf.get("tickSize") or 0)
    except Exception:
        tick = 0.0
    _TICK_CACHE[sym] = (tick, now)
    return tick


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
    """Bybit tickSize ile yuvarla — borsadaki gosterimle ayni ondalik."""
    if price is None:
        return "-"
    try:
        val = float(price)
    except (TypeError, ValueError):
        return str(price)
    if val == 0:
        return "0"
    tick = _fetch_tick_size(symbol) if symbol else 0.0
    if tick > 0:
        val = _round_to_tick(val, tick)
        dec = _decimals_from_tick(tick)
        text = f"{val:.{dec}f}"
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return text or "0"
    return format_price(val)
