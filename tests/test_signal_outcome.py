from datetime import datetime, timedelta, timezone

from engine.signal_analysis import analyze_completed_signal, signal_move_pct, strategy_signal_summary
from engine.signal_outcome import enqueue_signal_watch, finalize_expired_signal_watches
from engine.types import Side, Signal

TR = timezone(timedelta(hours=3))


def _sig(side: Side = Side.BUY) -> Signal:
    return Signal(
        side=side,
        strategy="[STRAT: Test_Long]",
        ledger="Kasa_Test",
        reason="test",
        sl_price=95.0,
        tp_price=110.0,
        strength=2.0,
    )


def test_signal_move_pct_buy_and_sell():
    assert signal_move_pct(100.0, 101.5, "BUY") == 1.5
    assert signal_move_pct(100.0, 98.0, "SELL") == 2.0
    assert signal_move_pct(100.0, 99.0, "BUY") == -1.0


def test_enqueue_dedupes_same_symbol_strategy_side():
    watchlist: list[dict] = []
    sig = _sig()
    enqueue_signal_watch(
        watchlist, symbol="BTCUSDT", sig=sig, entry_price=100.0, signal_time="2026-09-21 10:00:00"
    )
    enqueue_signal_watch(
        watchlist, symbol="BTCUSDT", sig=sig, entry_price=100.0, signal_time="2026-09-21 10:05:00"
    )
    assert len(watchlist) == 1


def test_analyze_completed_signal_direction_ok():
    watch = {
        "signal_id": "BTCUSDT|test|BUY|t",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "entry": 100.0,
        "sl_price": 95.0,
        "tp_price": 112.5,
        "notional": 100.0,
        "signal_time": "2026-09-21 10:00:00",
        "watch_until": "2026-09-22 10:00:00",
        "post_high": 101.5,
        "post_low": 99.0,
        "last_price": 101.0,
        "strategy": "[STRAT: Test]",
        "ledger": "Kasa_Test",
        "strength": 2.0,
        "analyzed_at": "2026-09-22 10:00:00",
    }
    out = analyze_completed_signal(watch, None)
    assert out["verdict"] == "correct"
    assert out["move_pct"] >= 0.5


def test_finalize_expired_writes_log():
    watchlist = [
        {
            "signal_id": "X|s|BUY|t",
            "dedup_key": "X|s|BUY",
            "symbol": "XRPUSDT",
            "side": "BUY",
            "entry": 1.0,
            "sl_price": 0.95,
            "tp_price": 1.15,
            "notional": 100.0,
            "signal_time": "2026-09-20 10:00:00",
            "watch_until": "2026-09-20 11:00:00",
            "post_high": 1.02,
            "post_low": 0.99,
            "last_price": 1.01,
            "strategy": "[STRAT: T]",
            "ledger": "Kasa_T",
            "strength": 1.0,
        }
    ]
    log_store: list[dict] = []
    assert finalize_expired_signal_watches(watchlist, log_store) is True
    assert not watchlist
    assert len(log_store) == 1


def test_strategy_signal_summary():
    analyses = [
        {"strategy": "A", "verdict": "correct", "outcome": "tp_hit", "mfe_r": 2.0},
        {"strategy": "A", "verdict": "wrong", "outcome": "sl_hit", "mfe_r": 0.5},
    ]
    df = strategy_signal_summary(analyses)
    assert len(df) == 1
    assert int(df.iloc[0]["Analiz"]) == 2
