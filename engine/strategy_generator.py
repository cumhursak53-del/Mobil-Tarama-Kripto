from __future__ import annotations

from engine.lab_state import new_recipe_id
from engine.strategy_recipe import StrategyRecipe


def _base_long_filters() -> list[dict]:
    return [
        {"type": "stage", "value": "advancing"},
        {"type": "week_bias", "value": 1},
    ]


def _base_short_filters() -> list[dict]:
    return [
        {"type": "stage", "value": "declining"},
        {"type": "week_bias", "value": -1},
    ]


def _triggers() -> list[dict]:
    return [
        {"type": "indicator", "tf": "1h", "field": "cci_cross_up", "extra": "cci_lt_100"},
        {"type": "indicator", "tf": "1h", "field": "cci_cross_down", "extra": "cci_gt_-100"},
        {"type": "indicator", "tf": "1h", "field": "macd_cross_up", "extra": "hist_pos"},
        {"type": "indicator", "tf": "1h", "field": "macd_cross_down", "extra": "hist_neg"},
        {"type": "indicator", "tf": "1h", "field": "stoch_cross_up", "extra": "k_lt_25"},
        {"type": "indicator", "tf": "1h", "field": "stoch_cross_down", "extra": "k_gt_75"},
    ]


def _confirmations() -> list[dict]:
    return [
        {"type": "structure", "tf": "4h", "kind": "bos_high"},
        {"type": "structure", "tf": "4h", "kind": "bos_low"},
        {"type": "structure", "tf": "4h", "kind": "squeeze"},
        {"type": "volume", "tf": "1h"},
        {"type": "momentum_score", "side": "long", "min": 4},
        {"type": "momentum_score", "side": "short", "min": 4},
    ]


def generate_recipes(limit: int = 40) -> list[dict]:
    out: list[dict] = []
    long_filters = _base_long_filters()
    short_filters = _base_short_filters()
    triggers = _triggers()
    confirms = _confirmations()

    long_triggers = [t for t in triggers if "cross_up" in t["field"]]
    short_triggers = [t for t in triggers if "cross_down" in t["field"]]
    long_confirms = [c for c in confirms if c.get("kind") != "bos_low" and c.get("side") != "short"]
    short_confirms = [c for c in confirms if c.get("kind") != "bos_high" and c.get("side") != "long"]

    for lf in long_filters:
        for tr in long_triggers:
            for cf in long_confirms:
                rid = new_recipe_id()
                recipe = StrategyRecipe(
                    id=rid,
                    name=f"LabLong_{rid}",
                    min_votes=2,
                    long_rules=[lf, tr, cf],
                    short_rules=[],
                    source="combinator",
                )
                out.append(recipe.to_dict())
                if len(out) >= limit // 2:
                    break
            if len(out) >= limit // 2:
                break
        if len(out) >= limit // 2:
            break

    for sf in short_filters:
        for tr in short_triggers:
            for cf in short_confirms:
                rid = new_recipe_id()
                recipe = StrategyRecipe(
                    id=rid,
                    name=f"LabShort_{rid}",
                    min_votes=2,
                    long_rules=[],
                    short_rules=[sf, tr, cf],
                    source="combinator",
                )
                out.append(recipe.to_dict())
                if len(out) >= limit:
                    break
            if len(out) >= limit:
                break
        if len(out) >= limit:
            break

    return out[:limit]
