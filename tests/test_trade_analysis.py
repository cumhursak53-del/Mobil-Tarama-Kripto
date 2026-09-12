from engine.trade_analysis import analyze_completed_watch, ledger_analysis_summary


def test_sl_too_tight_after_recovery():
    watch = {
        "trade_id": "Kasa_Fib618|BTCUSDT|2026-09-10 10:00:00",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "ledger": "Kasa_Fib618",
        "strategy": "t",
        "entry": 100.0,
        "exit": 98.0,
        "pnl": -2.0,
        "entry_time": "2026-09-10 10:00:00",
        "exit_time": "2026-09-10 12:00:00",
        "close_reason": "SL",
        "initial_sl": 98.0,
        "sl_price": 98.0,
        "tp_price": 105.0,
        "peak_price": 101.5,
        "notional": 1000.0,
        "post_high": 101.0,
        "post_low": 97.0,
        "last_price": 100.5,
        "watch_until": "2026-09-11 12:00:00",
    }
    out = analyze_completed_watch(watch)
    assert out["sl_verdict"] == "too_tight"
    assert out["recommendations"]


def test_tp_too_early():
    watch = {
        "trade_id": "Kasa_MumOnay|ETHUSDT|2026-09-10 10:00:00",
        "symbol": "ETHUSDT",
        "side": "BUY",
        "ledger": "Kasa_MumOnay",
        "strategy": "t",
        "entry": 100.0,
        "exit": 104.0,
        "pnl": 4.0,
        "entry_time": "2026-09-10 10:00:00",
        "exit_time": "2026-09-10 14:00:00",
        "close_reason": "TP",
        "initial_sl": 98.0,
        "sl_price": 98.0,
        "tp_price": 104.0,
        "peak_price": 104.0,
        "notional": 1000.0,
        "post_high": 108.0,
        "post_low": 103.0,
        "last_price": 107.0,
        "watch_until": "2026-09-11 14:00:00",
    }
    out = analyze_completed_watch(watch)
    assert out["tp_verdict"] == "too_early"
    assert out["missed_upside_usd"] > 0


def test_ledger_summary():
    log = [
        {"ledger": "Kasa_A", "close_reason": "SL", "sl_verdict": "too_tight"},
        {"ledger": "Kasa_A", "close_reason": "SL", "sl_verdict": "too_tight"},
        {"ledger": "Kasa_B", "close_reason": "TP", "tp_verdict": "too_early"},
    ]
    df = ledger_analysis_summary(log)
    assert not df.empty
    assert int(df[df["Kasa"] == "Kasa_A"].iloc[0]["SL_siki"]) == 2
