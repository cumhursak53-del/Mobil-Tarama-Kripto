from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional

from engine.config import (
    PATLAMA_LEDGER,
    SETUP_INVALIDATION,
    SETUP_INVALIDATION_GRACE_MIN,
    SETUP_INVALIDATION_LEDGERS,
    TR_TZ,
)
from engine.momentum_scan import score_momentum, trade_signal_from_score
from engine.smc_scan import score_smc, smc_trade_side
from engine.types import ClosedTrade, Side
from strategies.base import MarketContext, Strategy

SMC_LEDGER = "Kasa_SMC"


def _ledger_enabled(ledger: str) -> bool:
    if not SETUP_INVALIDATION:
        return False
    if not SETUP_INVALIDATION_LEDGERS:
        return True
    return ledger in SETUP_INVALIDATION_LEDGERS


def _entry_age_minutes(entry_time: str) -> float:
    if not entry_time:
        return 9999.0
    try:
        ts = datetime.strptime(str(entry_time)[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=TR_TZ)
        return (datetime.now(TR_TZ) - ts).total_seconds() / 60.0
    except Exception:
        return 9999.0


def setup_still_valid(strat: Strategy, ctx: MarketContext, side: Side) -> bool:
    """Giris tezinin hala gecerli olup olmadigini strateji mantigiyla kontrol et."""
    if not ctx.aligned(side):
        return False
    if strat.ledger == PATLAMA_LEDGER:
        scored = score_momentum(ctx)
        sig_side = trade_signal_from_score(scored)
        return sig_side == side
    if strat.ledger == SMC_LEDGER:
        analysis = score_smc(ctx)
        sig_side = smc_trade_side(analysis)
        return sig_side == side
    sig = strat.signal(ctx)
    if sig is None:
        return False
    return sig.side == side


def check_setup_invalidations(
    pf,
    symbol: str,
    strats: list[Strategy],
    ctx: MarketContext,
    *,
    bar_closed: dict[str, bool],
    price: float,
    force: bool = False,
) -> list[ClosedTrade]:
    """Acik pozisyonlarda setup bozulduysa erken cikis (INVALIDATED)."""
    if not SETUP_INVALIDATION or price <= 0:
        return []
    strat_map = {s.ledger: s for s in strats}
    closed: list[ClosedTrade] = []
    for key, pos in list(pf.positions.items()):
        if pos.symbol != symbol:
            continue
        if not _ledger_enabled(pos.ledger):
            continue
        if _entry_age_minutes(pos.entry_time) < SETUP_INVALIDATION_GRACE_MIN:
            continue
        strat = strat_map.get(pos.ledger)
        if strat is None:
            continue
        tf = pos.entry_tf or strat.entry_timeframe()
        if not force and not bar_closed.get(tf, False):
            continue
        if setup_still_valid(strat, ctx, pos.side):
            continue
        trade = pf._close(key, price, "INVALIDATED")
        closed.append(trade)
    return closed
