from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class Stage(str, Enum):
    ACCUMULATION = "accumulation"
    ADVANCING = "advancing"
    DISTRIBUTION = "distribution"
    DECLINING = "declining"
    UNKNOWN = "unknown"


@dataclass
class Signal:
    side: Side
    strategy: str
    ledger: str
    reason: str
    sl_price: float
    tp_price: Optional[float] = None
    entry_tf: str = "1h"
    extra: dict = field(default_factory=dict)


@dataclass
class Position:
    symbol: str
    side: Side
    ledger: str
    strategy: str
    entry_price: float
    sl_price: float
    tp_price: Optional[float]
    margin: float
    notional: float
    leverage: float
    qty: float
    entry_time: str
    entry_tf: str = "1h"
    peak_price: float = 0.0
    partial_taken: bool = False
    current_price: float = 0.0


@dataclass
class ClosedTrade:
    symbol: str
    side: str
    ledger: str
    strategy: str
    entry: float
    exit: float
    pnl: float
    close_reason: str
    exit_time: str
    r_multiple: float = 0.0
