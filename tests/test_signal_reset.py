from datetime import datetime, timezone, timedelta

from engine.signal_reset import _reset_key, maybe_reset_signal_log

TR = timezone(timedelta(hours=3))


def test_reset_key_before_3am_uses_previous_day():
    now = datetime(2026, 9, 12, 2, 30, tzinfo=TR)
    assert _reset_key(now) == "2026-09-11_0300"


def test_reset_key_after_3am_uses_today():
    now = datetime(2026, 9, 12, 4, 0, tzinfo=TR)
    assert _reset_key(now) == "2026-09-12_0300"


def test_maybe_reset_clears_signals_keeps_dominance():
    log = {"BTCUSDT": {"count": 5}, "_dominance": {"btc_d": 50.0}}
    assert maybe_reset_signal_log(log) is True
    assert "BTCUSDT" not in log
    assert log["_dominance"]["btc_d"] == 50.0
    assert maybe_reset_signal_log(log) is False
