from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from engine.momentum_scan import score_momentum
from engine.types import Side
from strategies.base import MarketContext
from strategies.helpers import valid_row
from structure.core import broken_above, broken_below, hh_hl, last_pivots, lh_ll, volume_ok
from structure.smc import analyze_smc, analyze_smc_mtf


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
    if rtype == "smc":
        kind = str(rule.get("kind", ""))
        if tf in ("15m", "1h") and len(ctx.frames) > 1:
            smc = analyze_smc_mtf(ctx.frames)
        else:
            smc = analyze_smc(df)
        price = float(df["close"].iloc[-1])
        active_bull = smc.active_blocks("bull")
        active_bear = smc.active_blocks("bear")
        in_bull_ob = any(
            min(ob.top, ob.bottom) * 0.997 <= price <= max(ob.top, ob.bottom) * 1.003
            for ob in smc.order_blocks
            if ob.side == "bull" and not ob.mitigated and ob.block_type == "order"
        )
        in_bear_ob = any(
            min(ob.top, ob.bottom) * 0.997 <= price <= max(ob.top, ob.bottom) * 1.003
            for ob in smc.order_blocks
            if ob.side == "bear" and not ob.mitigated and ob.block_type == "order"
        )
        in_bull_breaker = any(
            min(ob.top, ob.bottom) * 0.997 <= price <= max(ob.top, ob.bottom) * 1.003
            for ob in smc.breaker_blocks
            if ob.side == "bull" and not ob.mitigated
        )
        in_bear_breaker = any(
            min(ob.top, ob.bottom) * 0.997 <= price <= max(ob.top, ob.bottom) * 1.003
            for ob in smc.breaker_blocks
            if ob.side == "bear" and not ob.mitigated
        )
        in_bull_mit = any(
            min(ob.top, ob.bottom) * 0.997 <= price <= max(ob.top, ob.bottom) * 1.003
            for ob in smc.mitigation_blocks
            if ob.side == "bull" and not ob.mitigated
        )
        in_bear_mit = any(
            min(ob.top, ob.bottom) * 0.997 <= price <= max(ob.top, ob.bottom) * 1.003
            for ob in smc.mitigation_blocks
            if ob.side == "bear" and not ob.mitigated
        )
        active_fvg_bull = any(
            not f.mitigated for f in smc.fvgs if f.side == "bull"
        )
        active_fvg_bear = any(
            not f.mitigated for f in smc.fvgs if f.side == "bear"
        )
        notes_l = " ".join(smc.long_notes)
        notes_s = " ".join(smc.short_notes)
        mapping = {
            "bos_bull": smc.last_event == "bos_bull",
            "bos_bear": smc.last_event == "bos_bear",
            "choch_bull": smc.last_event == "choch_bull",
            "choch_bear": smc.last_event == "choch_bear",
            "internal_bos_bull": smc.internal_event == "bos_bull",
            "internal_bos_bear": smc.internal_event == "bos_bear",
            "external_bos_bull": smc.external_event == "bos_bull",
            "external_bos_bear": smc.external_event == "bos_bear",
            "ob_bull_retest": in_bull_ob,
            "ob_bear_retest": in_bear_ob,
            "breaker_bull_retest": in_bull_breaker,
            "breaker_bear_retest": in_bear_breaker,
            "mitigation_bull": in_bull_mit,
            "mitigation_bear": in_bear_mit,
            "sweep_bull": smc.sweep_bull,
            "sweep_bear": smc.sweep_bear,
            "inducement_bull": smc.inducement_bull,
            "inducement_bear": smc.inducement_bear,
            "turtle_soup_bull": smc.turtle_soup_bull,
            "turtle_soup_bear": smc.turtle_soup_bear,
            "nested_sweep_bull": smc.nested_sweep_bull,
            "nested_sweep_bear": smc.nested_sweep_bear,
            "discount": smc.in_discount,
            "premium": smc.in_premium,
            "ote_long": smc.in_ote_long,
            "ote_short": smc.in_ote_short,
            "equilibrium": smc.in_equilibrium,
            "killzone": smc.killzone,
            "hierarchy_long": smc.hierarchy_long,
            "hierarchy_short": smc.hierarchy_short,
            "trend_bull": smc.trend == "bull",
            "trend_bear": smc.trend == "bear",
            "fvg_bull": "FVG" in notes_l,
            "fvg_bear": "FVG" in notes_s,
            "fvg_bull_active": active_fvg_bull and "FVG_active" in notes_l,
            "fvg_bear_active": active_fvg_bear and "FVG_active" in notes_s,
            "ifvg_bull": "IFVG" in notes_l,
            "ifvg_bear": "IFVG" in notes_s,
            "fvg_ce_bull": "FVG_CE" in notes_l,
            "fvg_ce_bear": "FVG_CE" in notes_s,
            "weak_high_swept": smc.swing_high_strength == "weak" and smc.sweep_bear,
            "weak_low_swept": smc.swing_low_strength == "weak" and smc.sweep_bull,
            "strong_high_break": smc.swing_high_strength == "strong" and smc.external_event == "bos_bear",
            "strong_low_break": smc.swing_low_strength == "strong" and smc.external_event == "bos_bull",
            "setup_grade_a_long": smc.setup_grade_long == "A",
            "setup_grade_b_long": smc.setup_grade_long in ("A", "B"),
            "setup_grade_a_short": smc.setup_grade_short == "A",
            "setup_grade_b_short": smc.setup_grade_short in ("A", "B"),
            "smc_score_long": smc.long_score >= int(rule.get("min", 5)),
            "smc_score_short": smc.short_score >= int(rule.get("min", 5)),
        }
        return mapping.get(kind, False)
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
