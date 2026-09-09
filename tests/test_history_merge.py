from engine.state_merge import merge_history, merge_trading_state


def test_merge_history_keeps_all_unique_closes():
    a = [
        {"ledger": "Kasa_A", "symbol": "BTCUSDT", "exit_time": "2026-09-09 10:00:00",
         "entry_time": "2026-09-09 09:00:00", "entry": 100.0, "exit": 101.0, "close_reason": "TP", "pnl": 1.0},
    ]
    b = [
        {"ledger": "Kasa_B", "symbol": "ETHUSDT", "exit_time": "2026-09-09 11:00:00",
         "entry_time": "2026-09-09 10:30:00", "entry": 200.0, "exit": 198.0, "close_reason": "SL", "pnl": -1.0},
        {"ledger": "Kasa_A", "symbol": "BTCUSDT", "exit_time": "2026-09-09 10:00:00",
         "entry_time": "2026-09-09 09:00:00", "entry": 100.0, "exit": 101.0, "close_reason": "TP", "pnl": 1.0},
    ]
    merged = merge_history(a, b)
    assert len(merged) == 2


def test_merge_trading_state_prefers_more_history():
    local = {
        "updated_at": "2026-09-09 12:00:00",
        "equity": 3600,
        "active_positions": {},
        "history": [{"ledger": "A", "symbol": "X", "exit_time": "2026-09-09 11:00:00",
                     "entry_time": "2026-09-09 10:00:00", "entry": 1, "exit": 2, "close_reason": "TP", "pnl": 1}],
    }
    remote = {
        "updated_at": "2026-09-09 12:05:00",
        "equity": 3590,
        "active_positions": {},
        "history": [
            {"ledger": "B", "symbol": "Y", "exit_time": "2026-09-09 10:30:00",
             "entry_time": "2026-09-09 10:00:00", "entry": 1, "exit": 2, "close_reason": "SL", "pnl": -1},
            {"ledger": "C", "symbol": "Z", "exit_time": "2026-09-09 10:45:00",
             "entry_time": "2026-09-09 10:15:00", "entry": 1, "exit": 2, "close_reason": "TP", "pnl": 2},
        ],
    }
    merged, _src = merge_trading_state(local, remote)
    assert len(merged["history"]) == 3
    assert merged["closed_pnl_total"] == 2.0
