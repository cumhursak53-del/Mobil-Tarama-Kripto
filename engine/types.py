from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Optional


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class Stage(str, Enum):
    ACCUMULATION = "accumulation"
    ADVANCING = "advancing"
    DISTRIBUTION = "distribution"
    DECLINING = "declining"
    UNKNOWN = "unknown"


TpMode = Literal["r", "measured_move", "liquidity", "multi"]
EntryMode = Literal["market", "limit", "retest_zone"]


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
    tp_mode: TpMode = "r"
    tp_levels: list[float] = field(default_factory=list)
    entry_mode: EntryMode = "market"
    entry_limit: Optional[float] = None
    trail_at_r: Optional[float] = None
    be_at_r: Optional[float] = None
    partial_pct: float = 0.5
    tp_r: float = 2.0
    strength: float = 1.0


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
    tp_levels: list[float] = field(default_factory=list)
    trail_at_r: Optional[float] = None
    be_at_r: Optional[float] = None
    partial_pct: float = 0.5
    initial_sl: float = 0.0
    remaining_notional: float = 0.0
    remaining_qty: float = 0.0


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
