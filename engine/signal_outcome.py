"""24s sinyal izleme kuyrugu — post_exit benzeri."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

from engine.config import (
    SIGNAL_OUTCOME_LOG_MAX,
    SIGNAL_WATCH_HOURS,
    SIGNAL_WATCH_KLINE_TF,
    SIGNAL_WATCH_MAX,
    TR_TZ,
)
from engine.signal_analysis import analyze_completed_signal, make_signal_id
from engine.types import Signal


def parse_tr_ts(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=TR_TZ)
    except Exception:
        return None


def watch_until_str(signal_time: str, hours: float | None = None) -> str:
    h = float(hours if hours is not None else SIGNAL_WATCH_HOURS)
    base = parse_tr_ts(signal_time) or datetime.now(TR_TZ)
    return (base + timedelta(hours=h)).strftime("%Y-%m-%d %H:%M:%S")


def enqueue_signal_watch(
    watchlist: list[dict],
    *,
    symbol: str,
    sig: Signal,
    entry_price: float,
    signal_time: str,
    log: Callable[[str], None] | None = None,
) -> None:
    """Sembol+strateji+yon basina tek aktif 24s izleme."""
    if entry_price <= 0 or sig.sl_price <= 0:
        return
    side = sig.side.value
    signal_id = make_signal_id(symbol, sig.strategy, side, signal_time)
    if any(w.get("signal_id") == signal_id for w in watchlist):
        return
    dedup_key = f"{symbol}|{sig.strategy}|{side}"
    if any(w.get("dedup_key") == dedup_key for w in watchlist):
        return
    entry = float(entry_price)
    watch = {
        "signal_id": signal_id,
        "dedup_key": dedup_key,
        "symbol": symbol,
        "side": side,
        "ledger": sig.ledger,
        "source_ledger": (sig.extra or {}).get("source_ledger") or sig.ledger,
        "strategy": sig.strategy,
        "entry": entry,
        "sl_price": float(sig.sl_price),
        "tp_price": sig.tp_price,
        "strength": float(sig.strength or 1.0),
        "notional": 100.0,
        "signal_time": signal_time,
        "watch_until": watch_until_str(signal_time),
        "post_high": entry,
        "post_low": entry,
        "last_price": entry,
    }
    watchlist.append(watch)
    if len(watchlist) > SIGNAL_WATCH_MAX:
        watchlist[:] = watchlist[-SIGNAL_WATCH_MAX:]
    if log:
        log(f"Sinyal izleme: {symbol} | {sig.strategy} | {side} ({SIGNAL_WATCH_HOURS:.0f}s)")


def update_signal_watch_prices(watchlist: list[dict], prices: dict[str, float]) -> None:
    for w in watchlist:
        sym = w.get("symbol")
        if not sym or sym not in prices:
            continue
        px = float(prices[sym])
        w["last_price"] = px
        w["post_high"] = max(float(w.get("post_high") or px), px)
        w["post_low"] = min(float(w.get("post_low") or px), px)


def _is_expired(watch: dict, now: datetime | None = None) -> bool:
    now = now or datetime.now(TR_TZ)
    until = parse_tr_ts(str(watch.get("watch_until") or ""))
    return bool(until and now >= until)


def finalize_expired_signal_watches(
    watchlist: list[dict],
    log_store: list[dict],
    *,
    fetch_klines=None,
    log: Callable[[str], None] | None = None,
) -> bool:
    changed = False
    remain: list[dict] = []
    now = datetime.now(TR_TZ)
    for w in watchlist:
        if not _is_expired(w, now):
            remain.append(w)
            continue
        klines = None
        if fetch_klines:
            try:
                klines = fetch_klines(w["symbol"], SIGNAL_WATCH_KLINE_TF, limit=200)
            except Exception:
                klines = None
        w["analyzed_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
        analysis = analyze_completed_signal(w, klines)
        sid = str(analysis.get("signal_id") or "")
        if sid and not any(x.get("signal_id") == sid for x in log_store):
            log_store.append(analysis)
            changed = True
            if log:
                rec = "; ".join(analysis.get("recommendations") or [])[:100]
                log(
                    f"Sinyal analizi: {w.get('symbol')} | {analysis.get('verdict')} | {rec}"
                )
    watchlist[:] = remain
    if len(log_store) > SIGNAL_OUTCOME_LOG_MAX:
        log_store[:] = log_store[-SIGNAL_OUTCOME_LOG_MAX:]
    return changed


def run_signal_outcome_tick(
    watchlist: list[dict],
    log_store: list[dict],
    *,
    last_prices_fn,
    fetch_klines=None,
    log: Callable[[str], None] | None = None,
) -> bool:
    if not watchlist:
        return False
    symbols = list({str(w.get("symbol")) for w in watchlist if w.get("symbol")})
    try:
        prices = last_prices_fn(symbols)
    except Exception as e:
        if log:
            log(f"Sinyal izleme fiyat hatasi: {e}")
        return False
    update_signal_watch_prices(watchlist, prices)
    return finalize_expired_signal_watches(
        watchlist, log_store, fetch_klines=fetch_klines, log=log
    )


def merge_signal_outcome_log(*logs: list | None) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for chunk in logs:
        for item in chunk or []:
            if not isinstance(item, dict):
                continue
            sid = str(item.get("signal_id") or "")
            if not sid or sid in seen:
                continue
            seen.add(sid)
            out.append(item)
    out.sort(key=lambda x: str(x.get("signal_time") or ""))
    return out[-SIGNAL_OUTCOME_LOG_MAX:]


def merge_signal_watchlist(*lists: list | None) -> list[dict]:
    by_id: dict[str, dict] = {}
    for chunk in lists:
        for w in chunk or []:
            if not isinstance(w, dict):
                continue
            sid = str(w.get("signal_id") or "")
            if not sid:
                continue
            prev = by_id.get(sid)
            if not prev:
                by_id[sid] = w
                continue
            merged = dict(prev)
            merged["post_high"] = max(float(prev.get("post_high") or 0), float(w.get("post_high") or 0))
            merged["post_low"] = min(float(prev.get("post_low") or 0), float(w.get("post_low") or 0))
            by_id[sid] = merged
    return list(by_id.values())[-SIGNAL_WATCH_MAX:]
