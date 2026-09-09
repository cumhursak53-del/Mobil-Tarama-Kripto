from __future__ import annotations

from typing import Optional

from engine.strategy_recipe import StrategyRecipe, evaluate_recipe
from engine.types import Signal, Side, TpMode
from strategies.base import MarketContext, Strategy
from strategies.helpers import make_signal, valid_row


class RecipeStrategy(Strategy):
    entry_mode = "live"

    def __init__(self, recipe: StrategyRecipe, ledger: str):
        self.recipe = recipe
        self.name = recipe.name
        self.ledger = ledger
        self.entry_tf = recipe.entry_tf

    def signal_strength(self, ctx: MarketContext, sig: Signal) -> float:
        return float(sig.extra.get("votes") or self.recipe.min_votes)

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        tf = self.recipe.entry_tf or "1h"
        df = ctx.tf(tf)
        if not valid_row(df, ("close",)):
            return None
        side = evaluate_recipe(ctx, self.recipe)
        if side is None:
            return None
        tag = f"Lab_{self.recipe.id}_{'Long' if side == Side.BUY else 'Short'}"
        tp_mode: TpMode = "r"
        if self.recipe.tp_mode in ("r", "measured_move", "liquidity", "multi"):
            tp_mode = self.recipe.tp_mode  # type: ignore[assignment]
        return make_signal(
            self.ledger,
            f"[STRAT: {tag}]",
            df,
            side,
            tp_mode=tp_mode,
            tp_r_val=self.recipe.tp_r,
            trail_at_r=1.5 if self.recipe.tp_mode == "r" else None,
            extra={"recipe_id": self.recipe.id, "votes": self.recipe.min_votes},
            strength=float(self.recipe.min_votes),
        )
