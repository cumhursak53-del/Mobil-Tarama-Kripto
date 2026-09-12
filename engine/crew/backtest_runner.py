from __future__ import annotations

import time
from typing import Callable

from engine.crew.config import CREW_BACKTEST_UNIVERSE, CREW_QUICK_SYMBOL, CREW_VOLATILE_SYMBOLS
from engine.crew.daily_growth import compute_daily_growth_metrics, growth_gate
from engine.crew.state import now_tr
from engine.data import fetch_all_timeframes, fetch_dominance, fetch_symbols
from engine.lab_backtest import quick_screen_recipe
from engine.walk_forward import walk_forward_recipe


def _load_symbol_frames(symbols: list[str], log: Callable[[str], None] | None = None) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for sym in symbols:
        try:
            out[sym] = fetch_all_timeframes(sym)
            time.sleep(0.08)
        except Exception as e:
            if log:
                log(f"Crew veri hatasi {sym}: {e}")
    return out


def resolve_universe() -> list[str]:
    preferred = list(CREW_VOLATILE_SYMBOLS)
    if len(preferred) >= CREW_BACKTEST_UNIVERSE:
        return preferred[:CREW_BACKTEST_UNIVERSE]
    try:
        extra = fetch_symbols(CREW_BACKTEST_UNIVERSE * 2)
    except Exception:
        extra = []
    for sym in extra:
        if sym not in preferred:
            preferred.append(sym)
        if len(preferred) >= CREW_BACKTEST_UNIVERSE:
            break
    return preferred[:CREW_BACKTEST_UNIVERSE]


def backtest_recipes(
    recipes: list[dict],
    *,
    log: Callable[[str], None] | None = None,
) -> list[dict]:
    """Quick screen + walk-forward + gunluk %20 metrik."""
    if not recipes:
        return []

    symbols = resolve_universe()
    if CREW_QUICK_SYMBOL not in symbols:
        symbols = [CREW_QUICK_SYMBOL] + symbols
    dominance = fetch_dominance()
    frames = _load_symbol_frames(symbols, log=log)
    if not frames:
        return []

    screen_sym = CREW_QUICK_SYMBOL if CREW_QUICK_SYMBOL in frames else next(iter(frames))
    screen_frames = frames[screen_sym]
    rows: list[dict] = []

    for recipe in recipes:
        rid = recipe.get("id", "?")
        qs = quick_screen_recipe(recipe, screen_sym, screen_frames, dominance)
        if not qs.get("passed"):
            rows.append({
                "recipe_id": rid,
                "recipe_name": recipe.get("name", rid),
                "stage": "quick_screen",
                "passed": False,
                "reason": "quick_fail",
                "quick_metrics": qs.get("metrics") or {},
                "run_at": now_tr(),
            })
            if log:
                pf = (qs.get("metrics") or {}).get("profit_factor")
                log(f"Crew quick FAIL {rid} PF={pf}")
            continue

        best_growth = {"test_best_day_pct": 0.0, "days_ge_target": 0}
        best_sym = screen_sym
        wf_passed_any = False
        wf_rows = []

        for sym, sym_frames in frames.items():
            wf = walk_forward_recipe(recipe, sym, sym_frames, dominance)
            test_trades = wf.get("test_trades") or []
            growth = compute_daily_growth_metrics(test_trades)
            growth["symbol"] = sym
            wf_ok = bool((wf.get("walk_forward") or {}).get("passed"))
            promo_ok = bool((wf.get("promotion") or {}).get("passed"))
            wf_passed = wf_ok and promo_ok
            if wf_passed:
                wf_passed_any = True
            wf_rows.append({
                "symbol": sym,
                "walk_forward": wf.get("walk_forward"),
                "test_metrics": wf.get("test_metrics"),
                "growth": growth,
                "wf_passed": wf_passed,
            })
            if growth.get("best_day_pct", 0) >= best_growth.get("test_best_day_pct", 0):
                best_growth = {**growth, "test_best_day_pct": growth.get("best_day_pct", 0)}
                best_sym = sym

        gate = growth_gate(best_growth, wf_passed=wf_passed_any)
        row = {
            "recipe_id": rid,
            "recipe_name": recipe.get("name", rid),
            "stage": "walk_forward",
            "passed": gate["passed"],
            "reason": gate["reason"],
            "best_symbol": best_sym,
            "test_best_day_pct": gate["test_best_day_pct"],
            "days_ge_target": best_growth.get("days_ge_target", 0),
            "wf_passed": wf_passed_any,
            "per_symbol": wf_rows,
            "run_at": now_tr(),
        }
        if wf_rows:
            test_m = wf_rows[0].get("test_metrics") or {}
            for w in wf_rows:
                if w.get("symbol") == best_sym:
                    test_m = w.get("test_metrics") or test_m
                    break
            row["test_pf"] = test_m.get("profit_factor")
            row["test_trades"] = test_m.get("n")
            row["max_dd"] = test_m.get("max_drawdown")
        rows.append(row)
        if log:
            log(
                f"Crew BT {rid} | best_day={gate['test_best_day_pct']:.1f}% | "
                f"wf={wf_passed_any} | {gate['reason']}"
            )
    return rows
