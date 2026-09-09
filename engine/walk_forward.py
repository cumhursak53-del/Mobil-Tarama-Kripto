"""Walk-forward backtest — 70/30 train/test bolme."""
from __future__ import annotations

from typing import Optional

import pandas as pd

from engine.config import WALK_FORWARD_TRAIN_RATIO
from engine.fidelity_gate import check_backtest_promotion, check_walk_forward_acceptance
from engine.lab_backtest import backtest_recipe, summarize_recipe_results
from engine.strategy_recipe import StrategyRecipe


def _split_frames(frames: dict[str, pd.DataFrame], train_ratio: float, warmup: int = 120) -> tuple[dict, dict]:
    h1 = frames.get("1h")
    if h1 is None or len(h1) < warmup + 40:
        return {}, {}
    split = int(len(h1) * train_ratio)
    split = max(split, warmup + 20)
    split = min(split, len(h1) - warmup - 10)
    train = {tf: df.iloc[:split].copy() for tf, df in frames.items()}
    test_start = max(0, split - warmup)
    test = {tf: df.iloc[test_start:].copy() for tf, df in frames.items()}
    return train, test


def walk_forward_recipe(
    recipe: StrategyRecipe | dict,
    symbol: str,
    frames: dict[str, pd.DataFrame],
    dominance: Optional[dict] = None,
    train_ratio: float = WALK_FORWARD_TRAIN_RATIO,
) -> dict:
    rec = recipe if isinstance(recipe, StrategyRecipe) else StrategyRecipe.from_dict(recipe)
    train_frames, test_frames = _split_frames(frames, train_ratio)
    if not train_frames or not test_frames:
        return {
            "symbol": symbol,
            "recipe_id": rec.id,
            "error": "not_enough_data",
            "walk_forward": {"passed": False},
        }
    train_r = backtest_recipe(rec, symbol, train_frames, dominance)
    test_r = backtest_recipe(rec, symbol, test_frames, dominance)
    train_m = summarize_recipe_results([train_r])
    test_m = summarize_recipe_results([test_r])
    wf = check_walk_forward_acceptance(train_m, test_m)
    full_m = summarize_recipe_results([test_r])
    promo = check_backtest_promotion(full_m, wf)
    return {
        "symbol": symbol,
        "recipe_id": rec.id,
        "train_metrics": train_m,
        "test_metrics": test_m,
        "metrics": {**full_m, "passed": promo["passed"]},
        "walk_forward": wf,
        "promotion": promo,
        "train_trades": train_r.get("trades") or [],
        "test_trades": test_r.get("trades") or [],
    }


def walk_forward_recipe_batch(
    recipes: list[dict],
    symbol_frames: dict[str, dict],
    dominance: Optional[dict] = None,
) -> list[dict]:
    rows = []
    for recipe in recipes:
        rec = StrategyRecipe.from_dict(recipe)
        per_symbol = []
        for sym, frames in symbol_frames.items():
            per_symbol.append(walk_forward_recipe(rec, sym, frames, dominance))
        test_results = [{"trades": r.get("test_trades") or []} for r in per_symbol]
        metrics = summarize_recipe_results(test_results)
        wf_passed = all(r.get("walk_forward", {}).get("passed") for r in per_symbol if not r.get("error"))
        promo = check_backtest_promotion(metrics, {"passed": wf_passed})
        metrics["passed"] = promo["passed"]
        rows.append({
            "recipe": recipe,
            "metrics": metrics,
            "walk_forward_passed": wf_passed,
            "results": per_symbol,
        })
    return rows
