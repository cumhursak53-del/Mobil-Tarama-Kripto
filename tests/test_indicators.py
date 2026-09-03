"""Indicator correctness checks (no network). Run: python -m engine.main validate"""
from __future__ import annotations

import numpy as np
import pandas as pd

from indicators.core import bollinger, ema, macd, rsi, sma, wma


def _assert_close(a, b, tol, msg):
    if abs(float(a) - float(b)) > tol:
        raise AssertionError(f"{msg}: {a} != {b} (tol={tol})")


def test_sma():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    out = sma(s, 3)
    _assert_close(out.iloc[2], 2.0, 1e-9, "sma3[2]")
    _assert_close(out.iloc[4], 4.0, 1e-9, "sma3[4]")
    assert pd.isna(out.iloc[1])


def test_ema_reacts_faster_than_sma():
    s = pd.Series([10.0] * 20 + [20.0])
    e = ema(s, 5)
    m = sma(s, 5)
    assert e.iloc[-1] > m.iloc[-1]


def test_wma_weights_recent():
    s = pd.Series([1.0, 1.0, 1.0, 10.0])
    w = wma(s, 4)
    simple = s.mean()
    assert w.iloc[-1] > simple


def test_rsi_bounds_and_wilder():
    up = pd.Series(np.linspace(100, 200, 40))
    r = rsi(up, 14)
    assert r.iloc[-1] > 80
    down = pd.Series(np.linspace(200, 100, 40))
    r2 = rsi(down, 14)
    assert r2.iloc[-1] < 20
    # Wilder RSI of a known short series: after 14 up-days of +1, RSI → 100
    s = pd.Series([50.0 + i for i in range(20)])
    r3 = rsi(s, 14)
    assert r3.iloc[-1] > 95


def test_macd_cross_identity():
    s = pd.Series(np.sin(np.linspace(0, 20, 80)) + np.linspace(0, 3, 80))
    line, sig, hist = macd(s)
    assert np.allclose(hist.dropna(), (line - sig).dropna())
    assert line.notna().sum() > 40


def test_bollinger_contains_price_mostly():
    rng = np.random.default_rng(0)
    s = pd.Series(100 + np.cumsum(rng.normal(0, 1, 200)))
    mid, up, lo, width = bollinger(s, 20, 2)
    inside = ((s > lo) & (s < up)).iloc[20:].mean()
    assert inside > 0.85
    assert (width.iloc[20:] > 0).all()


def test_no_lookahead_sma():
    s = pd.Series(range(30), dtype=float)
    a = sma(s, 5)
    s2 = s.copy()
    s2.iloc[-1] = 10_000
    b = sma(s2, 5)
    assert a.iloc[-2] == b.iloc[-2]
    assert a.iloc[-1] != b.iloc[-1]


def test_risk_sizer():
    from risk.sizer import PositionRisk, size_position, would_survive_all_sl
    sized = size_position(ledger_balance=100.0, entry=100.0, sl=98.0)
    assert sized is not None
    assert abs(sized.notional - 100.0) < 1e-6  # 2% of 100 / 2% SL
    assert sized.leverage == 10
    assert abs(sized.margin - 10.0) < 1e-6  # 100 notional / 10x
    too_tight = size_position(ledger_balance=100.0, entry=100.0, sl=100.0)
    assert too_tight is None
    ok = PositionRisk(entry=100.0, sl=98.0, notional=100.0, margin=10.0)
    assert would_survive_all_sl(cash=100.0, open_positions=[], new=ok)
    nuke = PositionRisk(entry=100.0, sl=99.0, notional=2000.0, margin=80.0)
    assert not would_survive_all_sl(cash=100.0, open_positions=[], new=nuke)
    existing = [PositionRisk(entry=100.0, sl=90.0, notional=200.0, margin=50.0)]
    extra = PositionRisk(entry=100.0, sl=90.0, notional=200.0, margin=50.0)
    assert not would_survive_all_sl(cash=25.0, open_positions=existing, new=extra)


def test_rejim_osilator_priority_and_count():
    from engine.config import COMBO_LEDGER, LEDGER_NAMES
    from strategies.registry import all_strategies

    strats = all_strategies()
    assert strats[0].ledger == COMBO_LEDGER
    assert COMBO_LEDGER in LEDGER_NAMES
    assert len(strats) == len(LEDGER_NAMES)
    assert len(strats) == 29


def test_symbol_lock_caps_and_combo_risk():
    import os
    import tempfile

    from engine.config import COMBO_LEDGER
    from engine.portfolio import Portfolio
    from engine.types import Signal, Side

    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    os.remove(path)
    pf = Portfolio(path=path)

    def sig(ledger: str) -> Signal:
        return Signal(
            side=Side.SELL,
            strategy="t",
            ledger=ledger,
            reason="t",
            sl_price=101.5,
            tp_price=97.0,
        )

    assert pf.try_open("AAAUSDT", sig("Kasa_CCI"), 100.0)
    assert not pf.try_open("AAAUSDT", sig("Kasa_Stoch"), 100.0)
    assert pf.try_open("BBBUSDT", sig("Kasa_CCI"), 100.0)
    assert not pf.try_open("CCCUSDT", sig("Kasa_CCI"), 100.0)
    assert pf.try_open("DDDUSDT", sig(COMBO_LEDGER), 100.0)
    assert pf.try_open("EEEUSDT", sig(COMBO_LEDGER), 100.0)
    assert pf.try_open("FFFUSDT", sig(COMBO_LEDGER), 100.0)
    combo_n = pf.ledger_position_count(COMBO_LEDGER)
    assert combo_n >= 3


def test_strategy_count_and_smoke():
    from engine.context import build_context
    from engine.config import LEDGER_NAMES, TIMEFRAMES
    from strategies.registry import all_strategies

    rng = np.random.default_rng(1)
    n = 250
    strats = all_strategies()
    assert len(strats) == len(LEDGER_NAMES)
    assert {s.ledger for s in strats} == set(LEDGER_NAMES)
    frames = {}
    for tf in TIMEFRAMES:
        close = 100 + np.cumsum(rng.normal(0, 1, n))
        high = close + rng.random(n)
        low = close - rng.random(n)
        open_ = close + rng.normal(0, 0.2, n)
        vol = rng.random(n) * 1000 + 10
        idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
        df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": vol}, index=idx)
        df["close_time"] = idx + pd.Timedelta(hours=1)
        frames[tf] = df
    ctx = build_context("BTCUSDT", frames, {"btc_d": 55, "usdt_d": 5, "btc_chg": 1, "btc_d_chg": -0.2, "usdt_d_chg": -0.1})
    for s in strats:
        sig = s.signal(ctx)
        assert sig is None or sig.ledger == s.ledger


def run_all():
    tests = [
        test_sma, test_ema_reacts_faster_than_sma, test_wma_weights_recent,
        test_rsi_bounds_and_wilder, test_macd_cross_identity,
        test_bollinger_contains_price_mostly, test_no_lookahead_sma,
        test_risk_sizer, test_rejim_osilator_priority_and_count,
        test_symbol_lock_caps_and_combo_risk, test_strategy_count_and_smoke,
    ]
    for t in tests:
        t()
        print(f"OK  {t.__name__}")
    print(f"{len(tests)} gosterge testi gecti.")


if __name__ == "__main__":
    run_all()
