from __future__ import annotations

from engine.config import LEDGER_NAMES
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
from strategies.pa import MumOnay, PiyasaEvresi, YapiKirilim
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
]


def all_strategies() -> list[Strategy]:
    return [cls() for cls in _CLASSES]


def ledger_names() -> list[str]:
    return list(LEDGER_NAMES)
