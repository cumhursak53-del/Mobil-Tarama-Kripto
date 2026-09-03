from __future__ import annotations

from collections import defaultdict
from typing import Optional

import pandas as pd

from engine.backtest import _intrabar_exit, _slice_closed
from engine.config import KASA_START_USD, LAB_MIN_BACKTEST_PF, LAB_MIN_BACKTEST_TRADES, TAKER_FEE
from engine.context import build_context, indicate_frame
from engine.strategy_recipe import StrategyRecipe, evaluate_recipe
from engine.types import Side
from risk.sizer import PositionRisk, size_position, would_survive_all_sl
from strategies.recipe_strategy import RecipeStrategy
from structure.core import add_structure


def backtest_recipe(
    recipe: StrategyRecipe | dict,
    symbol: str,
    frames: dict[str, pd.DataFrame],
    dominance: Optional[dict] = None,
    warmup: int = 120,
) -> dict:
    rec = recipe if isinstance(recipe, StrategyRecipe) else StrategyRecipe.from_dict(recipe)
    indicated = {tf: add_structure(indicate_frame(df)) for tf, df in frames.items()}
    h1 = indicated.get("1h")
    if h1 is None or len(h1) < warmup + 20:
        return {"symbol": symbol, "recipe_id": rec.id, "trades": [], "error": "not_enough_1h"}

    ledger = f"LabBT_{rec.id}"
    strat = RecipeStrategy(rec, ledger)
    cash = KASA_START_USD
    open_pos: dict | None = None
    trades: list[dict] = []

    for i in range(warmup, len(h1)):
        row = h1.iloc[i]
        ts = row["close_time"]
        price = float(row["close"])
        high, low = float(row["high"]), float(row["low"])

        if open_pos:
            hit = _intrabar_exit(open_pos["side"], open_pos["sl"], open_pos.get("tp"), high, low)
            if hit:
                reason, fill = hit
                ratio = (fill - open_pos["entry"]) / open_pos["entry"] if open_pos["side"] == Side.BUY else (open_pos["entry"] - fill) / open_pos["entry"]
                net = open_pos["notional"] * ratio - open_pos["notional"] * TAKER_FEE * 2
                cash = max(cash + open_pos["margin"] + net, 0.0)
                trades.append({"pnl": net, "reason": reason, "time": str(ts)})
                open_pos = None

        if open_pos:
            continue
        sliced = _slice_closed(indicated, ts)
        if "1h" not in sliced or "1d" not in sliced:
            continue
        ctx = build_context(symbol, sliced, dominance, indicated=True)
        sig = strat.signal(ctx)
        if sig is None:
            continue
        sized = size_position(ledger_balance=cash, entry=price, sl=sig.sl_price)
        if sized is None:
            continue
        new_risk = PositionRisk(entry=price, sl=sig.sl_price, notional=sized.notional, margin=sized.margin)
        if not would_survive_all_sl(cash=cash, open_positions=[], new=new_risk):
            continue
        cash -= sized.margin
        open_pos = {
            "side": sig.side,
            "entry": price,
            "sl": sig.sl_price,
            "tp": sig.tp_price,
            "margin": sized.margin,
            "notional": sized.notional,
        }

    if open_pos:
        last = float(h1["close"].iloc[-1])
        ratio = (last - open_pos["entry"]) / open_pos["entry"] if open_pos["side"] == Side.BUY else (open_pos["entry"] - last) / open_pos["entry"]
        net = open_pos["notional"] * ratio - open_pos["notional"] * TAKER_FEE * 2
        cash = max(cash + open_pos["margin"] + net, 0.0)
        trades.append({"pnl": net, "reason": "EOD", "time": str(h1["close_time"].iloc[-1])})

    return {"symbol": symbol, "recipe_id": rec.id, "trades": trades, "final_cash": cash}


def summarize_recipe_results(results: list[dict]) -> dict:
    pnls = [float(t["pnl"]) for r in results for t in r.get("trades") or []]
    n = len(pnls)
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    gp, gl = sum(wins), abs(sum(losses))
    pf = (gp / gl) if gl else None
    wr = len(wins) / n if n else 0.0
    passed = n >= LAB_MIN_BACKTEST_TRADES and pf is not None and pf >= LAB_MIN_BACKTEST_PF
    return {
        "n": n,
        "win_rate": wr,
        "pnl": sum(pnls),
        "profit_factor": pf,
        "passed": passed,
        "symbols": len(results),
    }


def run_lab_backtests(recipes: list[dict], symbol_frames: dict[str, dict], dominance: Optional[dict] = None) -> list[dict]:
    rows = []
    for recipe in recipes:
        rec = StrategyRecipe.from_dict(recipe)
        results = []
        for sym, frames in symbol_frames.items():
            results.append(backtest_recipe(rec, sym, frames, dominance))
        metrics = summarize_recipe_results(results)
        rows.append({"recipe": recipe, "metrics": metrics, "results": results})
    return rows
