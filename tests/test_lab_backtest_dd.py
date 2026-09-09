"""Max drawdown hesaplama testi."""
from engine.lab_backtest import compute_max_drawdown, summarize_recipe_results


def test_compute_max_drawdown():
    trades = [{"pnl": 100}, {"pnl": -200}, {"pnl": 50}]
    dd = compute_max_drawdown(trades, start_cash=1000)
    assert 0 < dd < 1


def test_summarize_includes_max_dd():
    results = [{"trades": [{"pnl": 10}, {"pnl": -5}, {"pnl": 8}]}]
    m = summarize_recipe_results(results)
    assert "max_drawdown" in m
    assert m["max_drawdown"] >= 0
