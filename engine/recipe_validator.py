"""Gemini ciktisini guvenli StrategyRecipe dict'e cevir."""
from __future__ import annotations

from engine.lab_state import new_recipe_id
from engine.strategy_recipe import StrategyRecipe

ALLOWED_STAGE = {"advancing", "declining", "accumulation", "distribution", "unknown"}
ALLOWED_TF = {"15m", "1h", "4h", "1d", "1w"}
ALLOWED_STRUCTURE = {"bos_high", "bos_low", "squeeze", "hh_hl", "lh_ll"}
ALLOWED_FIELDS = {
    "macd_cross_up", "macd_cross_down", "stoch_cross_up", "stoch_cross_down",
    "stochrsi_cross_up", "stochrsi_cross_down", "cci_cross_up", "cci_cross_down",
    "tenkan_cross_up", "tenkan_cross_down", "sma9_cross_up", "sma9_cross_down",
    "ema21_cross_up", "ema21_cross_down",
}
ALLOWED_EXTRA = {
    "", "k_lt_25", "k_gt_75", "rsi_lt_45", "rsi_gt_55",
    "hist_pos", "hist_neg", "cci_lt_100", "cci_gt_-100",
}


def _clean_rule(rule: dict) -> dict | None:
    if not isinstance(rule, dict):
        return None
    rtype = str(rule.get("type") or "")
    if rtype == "stage":
        val = str(rule.get("value", "")).lower()
        if val not in ALLOWED_STAGE or val == "unknown":
            return None
        return {"type": "stage", "value": val}
    if rtype == "week_bias":
        try:
            v = int(rule.get("value", 0))
        except (TypeError, ValueError):
            return None
        if v not in (-1, 0, 1):
            return None
        return {"type": "week_bias", "value": v}
    if rtype == "volume":
        tf = str(rule.get("tf") or "1h")
        if tf not in ALLOWED_TF:
            tf = "1h"
        return {"type": "volume", "tf": tf}
    if rtype == "structure":
        tf = str(rule.get("tf") or "4h")
        kind = str(rule.get("kind") or "")
        if tf not in ALLOWED_TF or kind not in ALLOWED_STRUCTURE:
            return None
        return {"type": "structure", "tf": tf, "kind": kind}
    if rtype == "indicator":
        tf = str(rule.get("tf") or "1h")
        field = str(rule.get("field") or "")
        extra = str(rule.get("extra") or "")
        if tf not in ALLOWED_TF or field not in ALLOWED_FIELDS:
            return None
        if extra not in ALLOWED_EXTRA:
            extra = ""
        return {"type": "indicator", "tf": tf, "field": field, "extra": extra}
    if rtype == "momentum_score":
        side = str(rule.get("side", "long")).lower()
        if side not in ("long", "short"):
            side = "long"
        try:
            mn = int(rule.get("min", 4))
        except (TypeError, ValueError):
            mn = 4
        mn = max(3, min(7, mn))
        return {"type": "momentum_score", "side": side, "min": mn}
    return None


def validate_recipe(raw: dict, source: str) -> dict | None:
    if not isinstance(raw, dict):
        return None
    long_rules = [_clean_rule(r) for r in (raw.get("long_rules") or [])]
    short_rules = [_clean_rule(r) for r in (raw.get("short_rules") or [])]
    long_rules = [r for r in long_rules if r]
    short_rules = [r for r in short_rules if r]
    if not long_rules and not short_rules:
        return None
    try:
        min_votes = int(raw.get("min_votes") or 2)
    except (TypeError, ValueError):
        min_votes = 2
    min_votes = max(2, min(4, min_votes))
    side_rules = long_rules if len(long_rules) >= len(short_rules) else short_rules
    if len(side_rules) < min_votes:
        min_votes = max(2, len(side_rules))
    if min_votes < 2:
        return None
    rid = new_recipe_id()
    name = str(raw.get("name") or f"Research_{rid}")[:48]
    rec = StrategyRecipe(
        id=rid,
        name=name,
        min_votes=min_votes,
        long_rules=long_rules,
        short_rules=short_rules,
        require_aligned=bool(raw.get("require_aligned", True)),
        source=source,
    )
    return rec.to_dict()


def validate_recipes(raw_list: list[dict], source: str) -> list[dict]:
    out = []
    for raw in raw_list:
        v = validate_recipe(raw, source)
        if v:
            out.append(v)
    return out
