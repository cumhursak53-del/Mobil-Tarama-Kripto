from ui_common import ledger_daily_performance_rows, ledger_live_candidate_rows


def test_daily_performance_and_candidates():
    history = [
        {
            "ledger": "Kasa_Fib618",
            "side": "SELL",
            "pnl": 17.0,
            "exit_time": "2026-09-10 12:00:00",
        },
        {
            "ledger": "Kasa_Fib618",
            "side": "BUY",
            "pnl": -2.0,
            "exit_time": "2026-09-11 12:00:00",
        },
    ]
    active = {
        "Kasa_MumOnay|X": {
            "ledger_name": "Kasa_MumOnay",
            "side": "BUY",
            "unrealized_pnl": 20.0,
            "entry_time": "2026-09-10 01:00:00",
        }
    }
    daily = ledger_daily_performance_rows(history, active, start=100.0)
    fib_short = daily[(daily["Kasa"] == "Kasa_Fib618") & (daily["Yon"] == "SHORT")]
    assert float(fib_short.iloc[0]["Gunluk_pct"]) == 17.0
    mum = daily[(daily["Kasa"] == "Kasa_MumOnay") & (daily["Yon"] == "LONG")]
    assert float(mum.iloc[0]["Gunluk_pct"]) == 20.0

    cands = ledger_live_candidate_rows(daily, min_pct=15.0)
    assert len(cands) == 2
    assert set(cands["Yon"]) == {"LONG", "SHORT"}
