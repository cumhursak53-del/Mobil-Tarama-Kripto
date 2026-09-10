from ui_common import ledger_summary_rows


def test_ledger_summary_closed_only():
    history = [
        {"ledger": "Kasa_A", "pnl": 5.0},
        {"ledger": "Kasa_A", "pnl": -2.0},
    ]
    df = ledger_summary_rows({"Kasa_A": 103.0}, {}, history, start=100.0)
    row = df.iloc[0]
    assert row["Bakiye"] == 103.0
    assert row["PnL"] == 3.0
    assert row["Total"] == 103.0


def test_ledger_summary_with_open_position():
    active = {
        "Kasa_A|BTC": {
            "ledger_name": "Kasa_A",
            "margin": 10.0,
            "unrealized_pnl": 4.0,
        }
    }
    history = [{"ledger": "Kasa_A", "pnl": 5.0}]
    df = ledger_summary_rows({"Kasa_A": 95.0}, active, history, start=100.0)
    row = df.iloc[0]
    assert row["Bakiye"] == 105.0
    assert row["PnL"] == 9.0
    assert row["Total"] == 109.0
