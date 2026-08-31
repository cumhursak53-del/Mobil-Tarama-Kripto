from __future__ import annotations

from dataclasses import dataclass

from engine.config import CASH_RESERVE_PCT, MAX_LEVERAGE, RISK_PCT


@dataclass
class RiskLimits:
    ledger_balance: float
    cash_reserve_pct: float = CASH_RESERVE_PCT
    risk_pct: float = RISK_PCT
    max_leverage: float = MAX_LEVERAGE


@dataclass
class SizedTrade:
    margin: float
    notional: float
    leverage: float
    qty: float
    risk_usd: float


def size_position(
    *,
    ledger_balance: float,
    entry: float,
    sl: float,
    cash_reserve_pct: float = CASH_RESERVE_PCT,
    risk_pct: float = RISK_PCT,
    max_leverage: float = MAX_LEVERAGE,
) -> SizedTrade | None:
    if entry <= 0 or sl <= 0 or entry == sl:
        return None
    deployable = ledger_balance * (1.0 - cash_reserve_pct)
    if deployable < 5:
        return None
    risk_usd = ledger_balance * risk_pct
    sl_dist = abs(entry - sl) / entry
    if sl_dist < 0.001:
        return None
    notional = risk_usd / sl_dist
    min_leverage = notional / deployable
    if min_leverage > max_leverage:
        notional = deployable * max_leverage
        risk_usd = notional * sl_dist
    leverage = min(max_leverage, max(notional / deployable, 1.0))
    margin = notional / leverage
    if margin > deployable:
        margin = deployable
        notional = margin * leverage
    qty = notional / entry
    if qty <= 0 or margin < 1:
        return None
    return SizedTrade(margin=margin, notional=notional, leverage=leverage, qty=qty, risk_usd=risk_usd)
