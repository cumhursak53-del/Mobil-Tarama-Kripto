from __future__ import annotations

from engine.config import LEDGER_NAMES
from engine.strategy_recipe import StrategyRecipe
from strategies.base import Strategy
from strategies.fib import Fib618
from strategies.ma import DinamikMA, EMAFib, SMA9_14
from strategies.oscillators import (
    BBSqueeze,
    CCICross,
    Hacim,
    IchimokuFull,
    MACDCross,
    RSIBolge,
    RSIUyumsuzluk,
    StochCross,
    StochRSICross,
)
from strategies.patlama_selale import PatlamaSelale
from strategies.pa import MumOnay, PiyasaEvresi, YapiKirilim
from strategies.rejim_osilator import RejimOsilator
from strategies.recipe_strategy import RecipeStrategy
from strategies.smc import SmartMoneyConcepts
from strategies.patterns import (
    BayrakFlama,
    Dortgen,
    FincanCanak,
    IkiliDipTepe,
    OBOTOBO,
    Takoz,
    Ucgen,
)
from strategies.trend import DUK, DominanceAlt, PulbackRetest, TrendCizgisi, Tuzak

_CLASSES: list[type[Strategy]] = [
    RejimOsilator,
    PatlamaSelale,
    TrendCizgisi,
    PulbackRetest,
    DUK,
    Tuzak,
    DominanceAlt,
    SMA9_14,
    EMAFib,
    DinamikMA,
    PiyasaEvresi,
    MumOnay,
    YapiKirilim,
    RSIUyumsuzluk,
    RSIBolge,
    MACDCross,
    BBSqueeze,
    CCICross,
    StochCross,
    StochRSICross,
    IchimokuFull,
    Hacim,
    OBOTOBO,
    IkiliDipTepe,
    Ucgen,
    BayrakFlama,
    Dortgen,
    FincanCanak,
    Takoz,
    Fib618,
    SmartMoneyConcepts,
]


def all_strategies(lab_state: dict | None = None) -> list[Strategy]:
    base = [cls() for cls in _CLASSES]
    if not lab_state:
        return base
    return base + lab_strategies(lab_state)


def lab_strategies(lab_state: dict) -> list[Strategy]:
    out: list[Strategy] = []
    for c in lab_state.get("candidates") or []:
        if c.get("status") != "paper":
            continue
        ledger = c.get("ledger")
        rid = c.get("recipe_id")
        if not ledger or not rid:
            continue
        recipe_raw = None
        for r in lab_state.get("recipes") or []:
            if r.get("id") == rid:
                recipe_raw = r
                break
        if not recipe_raw:
            continue
        recipe = StrategyRecipe.from_dict(recipe_raw)
        out.append(RecipeStrategy(recipe, ledger))
    return out


def ledger_names(lab_state: dict | None = None) -> list[str]:
    names = list(LEDGER_NAMES)
    if lab_state:
        for c in lab_state.get("candidates") or []:
            if c.get("status") == "paper" and c.get("ledger"):
                names.append(c["ledger"])
    return names
