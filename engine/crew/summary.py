from __future__ import annotations

from engine.crew.config import CREW_DAILY_GROWTH_TARGET_PCT


def crew_summary_from_state(state: dict | None) -> dict:
    state = state or {}
    daily_runs = state.get("daily_runs") or []
    last_run = daily_runs[-1] if daily_runs else {}
    results = last_run.get("results") or []
    passed = [r for r in results if r.get("passed")]
    pipe = state.get("pipeline") or {}
    return {
        "updated_at": state.get("updated_at", ""),
        "target_pct": CREW_DAILY_GROWTH_TARGET_PCT,
        "pipeline": pipe,
        "last_run_date": last_run.get("date", ""),
        "last_run_at": last_run.get("started_at", pipe.get("last_run_at", "")),
        "recipes_generated": int(last_run.get("recipes_generated") or 0),
        "recipes_tested": len(results),
        "recipes_passed": len(passed),
        "duration_sec": last_run.get("duration_sec"),
        "narrative": last_run.get("narrative", ""),
        "research_summary": (last_run.get("research_summary") or "")[:500],
        "last_results": results,
        "all_runs_count": len(daily_runs),
        "recipes_total": len(state.get("recipes") or []),
        "errors": last_run.get("errors") or [],
    }
