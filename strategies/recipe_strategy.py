from __future__ import annotations

from typing import Optional

from engine.strategy_recipe import StrategyRecipe, evaluate_recipe
from engine.types import Signal, Side
from strategies.base import MarketContext, Strategy
from strategies.helpers import make_signal, valid_row


class RecipeStrategy(Strategy):
    def __init__(self, recipe: StrategyRecipe, ledger: str):
        self.recipe = recipe
        self.name = recipe.name
        self.ledger = ledger

    def signal(self, ctx: MarketContext) -> Optional[Signal]:
        df = ctx.tf("1h")
        if not valid_row(df, ("close",)):
            return None
        side = evaluate_recipe(ctx, self.recipe)
        if side is None:
            return None
        tag = f"Lab_{self.recipe.id}_{'Long' if side == Side.BUY else 'Short'}"
        return make_signal(self.ledger, f"[STRAT: {tag}]", df, side, extra={"recipe_id": self.recipe.id})
