"""Lab backtest listesi — UI icin ozet ve tarif basina son sonuc."""
from __future__ import annotations


def latest_backtest_per_recipe(backtests: list[dict]) -> list[dict]:
    by_id: dict[str, dict] = {}
    for b in backtests or []:
        if not isinstance(b, dict):
            continue
        rid = b.get("recipe_id")
        if rid:
            by_id[str(rid)] = b
    return sorted(by_id.values(), key=lambda x: str(x.get("run_at") or ""), reverse=True)


def backtest_summary(recipes: list[dict] | None, backtests: list[dict] | None) -> dict:
    recipes = recipes or []
    backtests = backtests or []
    latest = latest_backtest_per_recipe(backtests)
    tested_ids = {str(b.get("recipe_id")) for b in latest if b.get("recipe_id")}
    recipe_ids = {str(r.get("id")) for r in recipes if r.get("id")}
    passed = sum(1 for b in latest if (b.get("metrics") or {}).get("passed"))
    quick_fails = sum(
        1 for b in backtests
        if isinstance(b, dict) and (b.get("metrics") or {}).get("stage") == "quick_screen"
        and not (b.get("metrics") or {}).get("passed")
    )
    return {
        "total_runs": len(backtests),
        "unique_tested": len(tested_ids),
        "recipe_total": len(recipe_ids),
        "pending_test": max(0, len(recipe_ids - tested_ids)),
        "passed_count": passed,
        "quick_screen_fails": quick_fails,
        "latest_results": latest,
    }
