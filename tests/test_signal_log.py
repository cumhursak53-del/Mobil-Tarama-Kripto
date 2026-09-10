from engine.portfolio import Portfolio
from engine.types import Side, Signal


def _sig(strategy: str = "TestStrat") -> Signal:
    return Signal(
        side=Side.BUY,
        strategy=strategy,
        ledger="Kasa_Test",
        reason="test",
        sl_price=90.0,
        tp_price=110.0,
        strength=1.0,
    )


def test_record_signal_tracks_first_and_last_time():
    pf = Portfolio()
    sym = "TESTSIGXYZUSDT"
    pf.record_signal(sym, _sig())
    first = pf.signal_log[sym]["first_time"]
    last = pf.signal_log[sym]["last_time"]
    assert first
    assert last
    assert pf.signal_log[sym]["count"] == 1

    pf.record_signal(sym, _sig("Other"))
    assert pf.signal_log[sym]["first_time"] == first
    assert pf.signal_log[sym]["count"] == 2


def test_signal_log_rows_columns():
    from ui_common import signal_log_rows

    sig_log = {
        "ATHUSDT": {
            "count": 681,
            "last_side": "BUY",
            "last_ledger": "Kasa_A",
            "first_time": "2026-09-01 10:00:00",
            "last_time": "2026-09-10 15:00:00",
            "strategies": ["A", "B"],
        }
    }
    df = signal_log_rows(sig_log)
    row = df.iloc[0]
    assert row["Ilk sinyal"] == "2026-09-01 10:00:00"
    assert row["Son sinyal"] == "2026-09-10 15:00:00"
    assert row["Sinyal"] == 681
