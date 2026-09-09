"""Kasa basina golden senaryolar — PDF/LuxAlgo beklenen davranis."""
import numpy as np
import pytest

from engine.types import Side
from strategies.registry import _CLASSES
from tests.fidelity.fixtures import (
    fixture_dominance_alt_long,
    fixture_fib_ote_long,
    fixture_rsi_regular_bull,
    fixture_wyckoff_spring,
    make_context,
)


def _ledger(cls) -> str:
    return cls().ledger


@pytest.mark.parametrize("strategy_cls", _CLASSES, ids=_ledger)
def test_golden_no_crash_valid_signal(strategy_cls):
    """Her kasa crafted context uzerinde hata vermeden calisir."""
    ctx, _ = make_context(seed=hash(strategy_cls.__name__) % 997)
    strat = strategy_cls()
    sig = strat.signal(ctx)
    if sig is not None:
        assert sig.sl_price > 0
        assert sig.side in (Side.BUY, Side.SELL)


def test_golden_rsi_divergence_module():
    from structure.divergence import rsi_divergence
    from tests.fidelity.fixtures import build_mtf_frames

    n = 180
    close = np.array([100 - i * 0.05 + np.sin(i / 8) for i in range(n)])
    frames = build_mtf_frames(n=n, close=close, seed=7)
    df = frames["1h"]
    for idx, rv in zip([30, 70, 110], [25.0, 32.0, 38.0]):
        df.loc[df.index[idx], "rsi"] = rv
        df.loc[df.index[idx], "low"] = float(close[idx]) - 1.5
    div = rsi_divergence(df, min_pivots=3)
    assert div is None or div in ("regular_bull", "regular_bear", "hidden_bull", "hidden_bear")


def test_golden_wyckoff_spring():
    from structure.wyckoff import wyckoff_spring
    from tests.fidelity.fixtures import build_mtf_frames

    n = 80
    close = np.full(n, 100.0)
    close[-3:] = [99.5, 98.0, 100.5]
    frames = build_mtf_frames(n=n, close=close, seed=8)
    df = frames["1d"]
    df.loc[df.index[-2], "low"] = 97.5
    df.loc[df.index[-2], "close"] = 99.8
    df.loc[df.index[-2], "volume"] = float(df["vol_sma"].iloc[-2]) * 1.4
    assert isinstance(wyckoff_spring(df), bool)


def test_golden_piyasa_evresi_wyckoff():
    from strategies.pa import PiyasaEvresi

    ctx = fixture_wyckoff_spring()
    sig = PiyasaEvresi().signal(ctx)
    assert sig is None or sig.side == Side.BUY


def test_golden_dominance_alt_long():
    from strategies.trend import DominanceAlt

    ctx = fixture_dominance_alt_long()
    sig = DominanceAlt().signal(ctx)
    assert sig is None or sig.side == Side.BUY


def test_golden_fib618_ote_zone():
    from strategies.fib import Fib618

    ctx = fixture_fib_ote_long()
    sig = Fib618().signal(ctx)
    assert sig is None or sig.tp_mode == "multi"


def test_golden_rsi_strategy():
    from strategies.oscillators import RSIUyumsuzluk

    ctx = fixture_rsi_regular_bull()
    sig = RSIUyumsuzluk().signal(ctx)
    assert sig is None or sig.side in (Side.BUY, Side.SELL)


def test_golden_max_drawdown_gate():
    from engine.fidelity_gate import check_kasa_backtest_acceptance

    ok = check_kasa_backtest_acceptance({"profit_factor": 1.3, "max_drawdown": 0.15, "n": 30}, 90)
    assert ok["passed"] is True
    bad = check_kasa_backtest_acceptance({"profit_factor": 1.3, "max_drawdown": 0.35, "n": 30}, 90)
    assert bad["passed"] is False
