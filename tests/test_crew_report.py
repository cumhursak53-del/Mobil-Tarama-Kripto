from engine.crew.report import build_html_report, build_run_summary, build_subject


def test_report_highlights_passed():
    run = {
        "date": "2026-09-12",
        "recipes_generated": 3,
        "results": [
            {
                "recipe_name": "Alpha",
                "test_best_day_pct": 24.0,
                "days_ge_target": 2,
                "test_pf": 1.4,
                "test_trades": 18,
                "max_dd": 0.12,
                "best_symbol": "SOLUSDT",
                "passed": True,
                "reason": "passed",
            },
            {
                "recipe_name": "Beta",
                "test_best_day_pct": 11.0,
                "passed": False,
                "reason": "growth_fail",
            },
        ],
    }
    summary = build_run_summary(run)
    assert summary["recipes_passed"] == 1
    html = build_html_report(summary)
    assert "Alpha" in html
    assert "24.0%" in html
    assert build_subject(summary).startswith("Krpito Crew")
