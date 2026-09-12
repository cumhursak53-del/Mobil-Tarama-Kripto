from engine.crew.summary import crew_summary_from_state


def test_crew_summary_from_state():
    state = {
        "updated_at": "2026-09-12 10:00:00",
        "recipes": [{"id": "a"}],
        "pipeline": {"status": "ok", "last_run_at": "2026-09-12 09:00:00"},
        "daily_runs": [{
            "date": "2026-09-12",
            "recipes_generated": 2,
            "results": [{"passed": True, "test_best_day_pct": 22.0}],
        }],
    }
    s = crew_summary_from_state(state)
    assert s["recipes_passed"] == 1
    assert s["recipes_total"] == 1
