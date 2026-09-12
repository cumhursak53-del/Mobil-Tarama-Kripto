from engine.crew.daily_growth import compute_daily_growth_metrics, growth_gate


def test_best_day_pct():
    trades = [
        {"time": "2026-09-10 12:00:00", "pnl": 10.0},
        {"time": "2026-09-10 15:00:00", "pnl": 12.0},
        {"time": "2026-09-11 10:00:00", "pnl": 5.0},
    ]
    m = compute_daily_growth_metrics(trades, start_usd=100, target_pct=20)
    assert m["best_day_pct"] == 22.0
    assert m["days_ge_target"] == 1
    assert m["meets_target"] is True


def test_growth_gate():
    g = growth_gate({"test_best_day_pct": 21.0}, wf_passed=True, target_pct=20)
    assert g["passed"] is True
    g2 = growth_gate({"test_best_day_pct": 15.0}, wf_passed=True, target_pct=20)
    assert g2["passed"] is False
    assert g2["reason"] == "growth_fail"
