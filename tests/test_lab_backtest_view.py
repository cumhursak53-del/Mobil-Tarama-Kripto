from engine.lab_backtest_view import backtest_summary, latest_backtest_per_recipe


def test_latest_backtest_per_recipe_dedupes():
    backtests = [
        {"recipe_id": "a", "run_at": "2026-09-01 10:00:00", "metrics": {"passed": False}},
        {"recipe_id": "a", "run_at": "2026-09-02 10:00:00", "metrics": {"passed": True}},
        {"recipe_id": "b", "run_at": "2026-09-01 11:00:00", "metrics": {"passed": False}},
    ]
    latest = latest_backtest_per_recipe(backtests)
    assert len(latest) == 2
    by_id = {x["recipe_id"]: x for x in latest}
    assert by_id["a"]["metrics"]["passed"] is True


def test_backtest_summary_counts():
    recipes = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    backtests = [
        {"recipe_id": "a", "run_at": "2026-09-01 10:00:00", "metrics": {"passed": False, "stage": "quick_screen"}},
        {"recipe_id": "a", "run_at": "2026-09-02 10:00:00", "metrics": {"passed": True, "stage": "walk_forward"}},
        {"recipe_id": "b", "run_at": "2026-09-01 11:00:00", "metrics": {"passed": False, "stage": "quick_screen"}},
    ]
    s = backtest_summary(recipes, backtests)
    assert s["total_runs"] == 3
    assert s["unique_tested"] == 2
    assert s["pending_test"] == 1
    assert s["passed_count"] == 1
