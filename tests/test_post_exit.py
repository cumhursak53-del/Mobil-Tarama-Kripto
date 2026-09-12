from datetime import datetime, timedelta

from engine.config import TR_TZ
from engine.post_exit import enqueue_watch, merge_post_exit_log, run_post_exit_tick, update_watch_prices


def test_enqueue_and_expire():
    watchlist: list[dict] = []
    log: list[dict] = []
    exit_time = (datetime.now(TR_TZ) - timedelta(hours=25)).strftime("%Y-%m-%d %H:%M:%S")
    trade = {
        "symbol": "BTCUSDT",
        "side": "BUY",
        "ledger": "Kasa_Test",
        "strategy": "t",
        "entry": 100.0,
        "exit": 98.0,
        "pnl": -2.0,
        "entry_time": "2026-09-10 10:00:00",
        "exit_time": exit_time,
        "close_reason": "SL",
        "initial_sl": 98.0,
        "sl_price": 98.0,
        "tp_price": 105.0,
        "peak_price": 99.0,
        "notional": 500.0,
        "partial": False,
        "trade_id": "Kasa_Test|BTCUSDT|2026-09-10 10:00:00",
    }
    enqueue_watch(watchlist, trade=trade)
    assert len(watchlist) == 1
    watchlist[0]["watch_until"] = exit_time
    watchlist[0]["post_high"] = 101.0
    watchlist[0]["post_low"] = 97.0

    changed = run_post_exit_tick(
        watchlist,
        log,
        last_prices_fn=lambda syms: {"BTCUSDT": 100.0},
        fetch_klines=None,
    )
    assert changed is True
    assert len(watchlist) == 0
    assert len(log) == 1
    assert log[0]["trade_id"] == trade["trade_id"]


def test_update_watch_prices():
    watchlist = [{"symbol": "ETHUSDT", "post_high": 100.0, "post_low": 100.0, "last_price": 100.0}]
    update_watch_prices(watchlist, {"ETHUSDT": 102.0})
    assert watchlist[0]["post_high"] == 102.0
    assert watchlist[0]["last_price"] == 102.0


def test_merge_post_exit_log():
    a = [{"trade_id": "1", "exit_time": "2026-09-10"}]
    b = [{"trade_id": "2", "exit_time": "2026-09-11"}, {"trade_id": "1", "exit_time": "2026-09-10"}]
    merged = merge_post_exit_log(a, b)
    assert len(merged) == 2
