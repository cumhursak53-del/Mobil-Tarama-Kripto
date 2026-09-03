from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from engine.config import (
    CASH_RESERVE_PCT,
    COMBO_LEDGER,
    COMBO_RISK_PCT,
    KASA_START_USD,
    LIQ_ADVERSE_PCT,
    MAX_LEVERAGE,
    MAX_POSITIONS_PER_KASA,
    MIN_LEVERAGE,
    MIN_SURVIVAL_USD,
    RISK_PCT,
)


@dataclass
class RiskLimits:
    ledger_balance: float
    cash_reserve_pct: float = CASH_RESERVE_PCT
    risk_pct: float = RISK_PCT
    min_leverage: float = MIN_LEVERAGE
    max_leverage: float = MAX_LEVERAGE


@dataclass
class SizedTrade:
    margin: float
    notional: float
    leverage: float
    qty: float
    risk_usd: float


@dataclass
class PositionRisk:
    entry: float
    sl: float
    notional: float
    margin: float


def risk_pct_for_ledger(ledger: str) -> float:
    return COMBO_RISK_PCT if ledger == COMBO_LEDGER else RISK_PCT


def max_positions_for_ledger(ledger: str) -> int | None:
    if ledger == COMBO_LEDGER:
        return None
    return MAX_POSITIONS_PER_KASA


def _sl_loss(entry: float, sl: float, notional: float) -> float:
    if entry <= 0:
        return 0.0
    return abs(entry - sl) / entry * notional


def would_survive_all_sl(
    *,
    cash: float,
    open_positions: Sequence[PositionRisk],
    new: PositionRisk,
    kasa_start: float = KASA_START_USD,
    min_equity: float | None = None,
    adverse_pct: float = LIQ_ADVERSE_PCT,
) -> bool:
    """True if the kasa still stands after every SL at once, and after an 8% correlated dump at 10x."""
    if new.margin > cash + 1e-9:
        return False
    cash_after = cash - new.margin
    positions = list(open_positions) + [new]
    sl_loss = sum(_sl_loss(p.entry, p.sl, p.notional) for p in positions)
    margins = sum(p.margin for p in positions)
    after_sl = cash_after + margins - sl_loss
    floor = min_equity if min_equity is not None else max(MIN_SURVIVAL_USD, kasa_start * CASH_RESERVE_PCT)
    if after_sl < floor:
        return False
    shock = adverse_pct * sum(p.notional for p in positions)
    after_shock = cash_after + margins - shock
    return after_shock >= 0


def size_position(
    *,
    ledger_balance: float,
    entry: float,
    sl: float,
    cash_reserve_pct: float = CASH_RESERVE_PCT,
    risk_pct: float = RISK_PCT,
    min_leverage: float = MIN_LEVERAGE,
    max_leverage: float = MAX_LEVERAGE,
) -> SizedTrade | None:
    if entry <= 0 or sl <= 0 or entry == sl:
        return None
    deployable = ledger_balance * (1.0 - cash_reserve_pct)
    if deployable < 5:
        return None
    sl_dist = abs(entry - sl) / entry
    if sl_dist < 0.001:
        return None
    if min_leverage > max_leverage:
        max_leverage = min_leverage
    leverage = max(min_leverage, 1.0)
    risk_usd = ledger_balance * risk_pct
    notional = risk_usd / sl_dist
    margin = notional / leverage
    if margin > deployable:
        margin = deployable
        notional = margin * leverage
        risk_usd = notional * sl_dist
    if margin < 1:
        return None
    qty = notional / entry
    if qty <= 0:
        return None
    return SizedTrade(margin=margin, notional=notional, leverage=leverage, qty=qty, risk_usd=risk_usd)
