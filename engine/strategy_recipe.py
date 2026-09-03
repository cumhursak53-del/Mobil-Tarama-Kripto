from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from engine.momentum_scan import score_momentum
from engine.types import Side
from strategies.base import MarketContext
from strategies.helpers import valid_row
from structure.core import broken_above, broken_below, hh_hl, last_pivots, lh_ll, volume_ok


@dataclass
class StrategyRecipe:
    id: str
    name: str
    min_votes: int = 2
    long_rules: list[dict] = field(default_factory=list)
    short_rules: list[dict] = field(default_factory=list)
    require_aligned: bool = True
    source: str = "combinator"

    @classmethod
    def from_dict(cls, raw: dict) -> "StrategyRecipe":
        return cls(
            id=str(raw["id"]),
            name=str(raw.get("name") or raw["id"]),
            min_votes=int(raw.get("min_votes") or 2),
            long_rules=list(raw.get("long_rules") or []),
            short_rules=list(raw.get("short_rules") or []),
            require_aligned=bool(raw.get("require_aligned", True)),
            source=str(raw.get("source") or "combinator"),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "min_votes": self.min_votes,
            "long_rules": self.long_rules,
            "short_rules": self.short_rules,
            "require_aligned": self.require_aligned,
            "source": self.source,
        }


def _squeeze(df) -> bool:
    if not valid_row(df, ("bb_width", "bb_width_med")):
        return False
    row = df.iloc[-1]
    return float(row["bb_width"]) < float(row["bb_width_med"]) * 0.85


def _eval_rule(ctx: MarketContext, rule: dict) -> bool:
    rtype = rule.get("type")
    if rtype == "stage":
        want = str(rule.get("value", "")).lower()
        return ctx.stage.value == want
    if rtype == "week_bias":
        return ctx.week_bias == int(rule.get("value", 0))
    if rtype == "momentum_score":
        scored = score_momentum(ctx)
        side = str(rule.get("side", "long")).lower()
        need = int(rule.get("min", 4))
        return scored.long_score >= need if side == "long" else scored.short_score >= need
    tf = str(rule.get("tf") or "1h")
    df = ctx.tf(tf)
    if df is None or len(df) < 30:
        return False
    if rtype == "volume":
        return volume_ok(df)
    if rtype == "structure":
        kind = str(rule.get("kind", ""))
        if kind == "squeeze":
            return _squeeze(df)
        if kind == "hh_hl":
            hh, hl = hh_hl(df)
            return hh and hl
        if kind == "lh_ll":
            lh, ll = lh_ll(df)
            return lh and ll
        highs = last_pivots(df, "high", 4)
        lows = last_pivots(df, "low", 4)
        if kind == "bos_high" and len(highs) >= 2:
            return broken_above(df, highs[-1][1])
        if kind == "bos_low" and len(lows) >= 2:
            return broken_below(df, lows[-1][1])
        return False
    if rtype == "indicator":
        field_name = str(rule.get("field", ""))
        if field_name not in df.columns:
            return False
        row = df.iloc[-1]
        if not bool(row.get(field_name)):
            return False
        extra = str(rule.get("extra") or "")
        if extra == "k_lt_25" and "stoch_k" in df.columns:
            return float(row["stoch_k"]) < 25
        if extra == "k_gt_75" and "stoch_k" in df.columns:
            return float(row["stoch_k"]) > 75
        if extra == "rsi_lt_45" and "rsi" in df.columns:
            return float(row["rsi"]) < 45
        if extra == "rsi_gt_55" and "rsi" in df.columns:
            return float(row["rsi"]) > 55
        if extra == "hist_pos" and "macd_hist" in df.columns:
            return float(row["macd_hist"]) > 0
        if extra == "hist_neg" and "macd_hist" in df.columns:
            return float(row["macd_hist"]) < 0
        if extra == "cci_lt_100" and "cci" in df.columns:
            return float(row["cci"]) < 100
        if extra == "cci_gt_-100" and "cci" in df.columns:
            return float(row["cci"]) > -100
        return True
    return False


def evaluate_recipe(ctx: MarketContext, recipe: StrategyRecipe) -> Optional[Side]:
    long_votes = sum(1 for r in recipe.long_rules if _eval_rule(ctx, r))
    short_votes = sum(1 for r in recipe.short_rules if _eval_rule(ctx, r))
    if long_votes >= recipe.min_votes and long_votes > short_votes:
        side = Side.BUY
    elif short_votes >= recipe.min_votes and short_votes > long_votes:
        side = Side.SELL
    else:
        return None
    if recipe.require_aligned and not ctx.aligned(side):
        return None
    return side
