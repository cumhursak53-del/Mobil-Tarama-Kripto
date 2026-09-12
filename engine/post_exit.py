from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable, Optional

from engine.config import (
    POST_EXIT_KLINE_TF,
    POST_EXIT_LOG_MAX,
    POST_EXIT_MAX_WATCH,
    POST_EXIT_WATCH_HOURS,
    TR_TZ,
)
from engine.trade_analysis import analyze_completed_watch, make_trade_id


def parse_tr_ts(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=TR_TZ)
    except Exception:
        return None


def watch_until_str(exit_time: str, hours: float | None = None) -> str:
    h = float(hours if hours is not None else POST_EXIT_WATCH_HOURS)
    base = parse_tr_ts(exit_time) or datetime.now(TR_TZ)
    return (base + timedelta(hours=h)).strftime("%Y-%m-%d %H:%M:%S")


def enqueue_watch(
    watchlist: list[dict],
    *,
    trade: dict,
    log: Callable[[str], None] | None = None,
) -> None:
    """Tam kapanan islem icin 24s izleme kuyruguna ekle."""
    if trade.get("partial"):
        return
    if not trade.get("initial_sl") and not trade.get("sl_price"):
        return
    trade_id = trade.get("trade_id") or make_trade_id(
        str(trade.get("ledger") or ""),
        str(trade.get("symbol") or ""),
        str(trade.get("entry_time") or ""),
    )
    if any(w.get("trade_id") == trade_id for w in watchlist):
        return
    exit_px = float(trade.get("exit") or 0)
    watch = {
        "trade_id": trade_id,
        "symbol": trade.get("symbol"),
        "side": trade.get("side"),
        "ledger": trade.get("ledger"),
        "strategy": trade.get("strategy"),
        "entry": trade.get("entry"),
        "exit": exit_px,
        "pnl": trade.get("pnl"),
        "entry_time": trade.get("entry_time"),
        "exit_time": trade.get("exit_time"),
        "close_reason": trade.get("close_reason"),
        "initial_sl": trade.get("initial_sl"),
        "sl_price": trade.get("sl_price"),
        "tp_price": trade.get("tp_price"),
        "peak_price": trade.get("peak_price"),
        "notional": trade.get("notional"),
        "watch_until": watch_until_str(str(trade.get("exit_time") or "")),
        "post_high": exit_px,
        "post_low": exit_px,
        "last_price": exit_px,
    }
    watchlist.append(watch)
    if len(watchlist) > POST_EXIT_MAX_WATCH:
        watchlist[:] = watchlist[-POST_EXIT_MAX_WATCH:]
    if log:
        log(f"Post-exit izleme: {trade_id} ({POST_EXIT_WATCH_HOURS:.0f}s)")


def update_watch_prices(watchlist: list[dict], prices: dict[str, float]) -> None:
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


def finalize_expired_watches(
    watchlist: list[dict],
    log_store: list[dict],
    *,
    fetch_klines=None,
    log: Callable[[str], None] | None = None,
) -> bool:
    """Suresi dolan izlemeleri analiz et ve log'a yaz."""
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
                klines = fetch_klines(w["symbol"], POST_EXIT_KLINE_TF, limit=200)
            except Exception:
                klines = None
        w["analyzed_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
        analysis = analyze_completed_watch(w, klines)
        if not any(x.get("trade_id") == analysis.get("trade_id") for x in log_store):
            log_store.append(analysis)
            changed = True
            if log:
                rec = "; ".join(analysis.get("recommendations") or [])[:120]
                log(f"Islem analizi: {analysis.get('trade_id')} | {rec}")
    watchlist[:] = remain
    if len(log_store) > POST_EXIT_LOG_MAX:
        log_store[:] = log_store[-POST_EXIT_LOG_MAX:]
    return changed


def run_post_exit_tick(
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
            log(f"Post-exit fiyat hatasi: {e}")
        return False
    update_watch_prices(watchlist, prices)
    return finalize_expired_watches(watchlist, log_store, fetch_klines=fetch_klines, log=log)


def merge_post_exit_log(*logs: list | None) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for chunk in logs:
        for item in chunk or []:
            if not isinstance(item, dict):
                continue
            tid = str(item.get("trade_id") or "")
            if not tid or tid in seen:
                continue
            seen.add(tid)
            out.append(item)
    out.sort(key=lambda x: str(x.get("exit_time") or ""))
    return out[-POST_EXIT_LOG_MAX:]


def merge_watchlist(*lists: list | None) -> list[dict]:
    by_id: dict[str, dict] = {}
    for chunk in lists:
        for w in chunk or []:
            if not isinstance(w, dict):
                continue
            tid = str(w.get("trade_id") or "")
            if not tid:
                continue
            prev = by_id.get(tid)
            if not prev:
                by_id[tid] = w
                continue
            until_prev = parse_tr_ts(str(prev.get("watch_until") or ""))
            until_new = parse_tr_ts(str(w.get("watch_until") or ""))
            if until_new and (not until_prev or until_new > until_prev):
                by_id[tid] = w
            else:
                merged = dict(prev)
                merged["post_high"] = max(float(prev.get("post_high") or 0), float(w.get("post_high") or 0))
                merged["post_low"] = min(float(prev.get("post_low") or 0), float(w.get("post_low") or 0))
                by_id[tid] = merged
    out = list(by_id.values())
    return out[-POST_EXIT_MAX_WATCH:]
