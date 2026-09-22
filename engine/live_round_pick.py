"""Tur sonu sinyal secimi — beklenen kar (TP R) ile sirala, en iyiden islem ac."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from engine.config import LIVE_COMBO_LEDGER, LIVE_LONG_ONLY
from engine.context import build_context
from engine.data import last_prices
from engine.entry_timing import refresh_tfs_for_scan
from engine.types import Side, Signal
from risk.sizer import risk_pct_for_ledger


@dataclass
class RoundCandidate:
    symbol: str
    strategy: object
    sig: Signal
    entry: float
    strength: float
    expected_profit_usd: float


def tp_r_multiple(sig: Signal, entry: float) -> float:
    sl = float(sig.sl_price or 0)
    if entry <= 0 or sl <= 0 or entry == sl:
        return 0.0
    risk_dist = abs(entry - sl)
    tp = sig.tp_price
    if tp is not None and float(tp) > 0:
        tp = float(tp)
        if sig.side == Side.BUY:
            reward = tp - entry
        else:
            reward = entry - tp
        return max(0.0, reward / risk_dist)
    return max(0.0, float(sig.tp_r or 2.0))


def expected_profit_usd(pf, entry: float, sig: Signal, *, ledger: str = LIVE_COMBO_LEDGER) -> float:
    """TP'ye ulasilirsa beklenen USD kar — siralama icin (marjin taban esigi yok)."""
    cash = float(pf.ledgers.get(ledger, 0))
    sl = float(sig.sl_price or 0)
    if cash <= 0 or entry <= 0 or sl <= 0 or entry == sl:
        return 0.0
    sl_dist = abs(entry - sl) / entry
    if sl_dist < 0.001:
        return 0.0
    risk_usd = cash * risk_pct_for_ledger(ledger)
    return risk_usd * tp_r_multiple(sig, entry)


def collect_round_candidate(
    pf,
    *,
    symbol: str,
    strategy: object,
    ctx,
    entry: float,
    sig: Signal,
    strength: float,
) -> RoundCandidate | None:
    if sig is None or entry <= 0 or sig.sl_price <= 0:
        return None
    if LIVE_LONG_ONLY and sig.side == Side.SELL:
        return None
    if not ctx.aligned(sig.side):
        return None
    exp = expected_profit_usd(pf, entry, sig)
    if exp <= 0:
        return None
    return RoundCandidate(
        symbol=symbol,
        strategy=strategy,
        sig=sig,
        entry=entry,
        strength=strength,
        expected_profit_usd=exp,
    )


def _revalidate(
    cache,
    dominance: dict,
    cand: RoundCandidate,
    *,
    entry_price_fn: Callable,
) -> tuple[float, Signal, object] | None:
    from strategies.registry import live_strategies

    strats = live_strategies()
    scan_tfs = refresh_tfs_for_scan(strats)
    frames = cache.refresh(cand.symbol, scan_tfs)
    if "1h" not in frames or "1d" not in frames:
        return None
    live_px = None
    try:
        live_px = last_prices([cand.symbol]).get(cand.symbol)
    except Exception:
        live_px = None
    ctx = build_context(cand.symbol, frames, dominance, indicated=False, ref_frames=None)
    try:
        sig = cand.strategy.signal(ctx)
    except Exception:
        return None
    if sig is None or not ctx.aligned(sig.side):
        return None
    if LIVE_LONG_ONLY and sig.side == Side.SELL:
        return None
    px = entry_price_fn(cand.strategy, cand.symbol, frames, live_px)
    if px <= 0:
        return None
    return px, sig, ctx


def flush_round_entries(
    pf,
    cache,
    dominance: dict,
    candidates: list[RoundCandidate],
    *,
    try_entry_fn: Callable,
    entry_price_fn: Callable,
    log: Callable[[str], None] | None = None,
) -> int:
    if not candidates:
        return 0
    ranked = sorted(
        candidates,
        key=lambda c: (c.expected_profit_usd, c.strength),
        reverse=True,
    )
    if log:
        best = ranked[0]
        log(
            f"Tur sinyal secimi: {len(ranked)} aday | "
            f"en iyi {best.symbol} ${best.expected_profit_usd:.2f} beklenen kar"
        )
    opened = 0
    for cand in ranked:
        try:
            refreshed = _revalidate(cache, dominance, cand, entry_price_fn=entry_price_fn)
            if refreshed is None:
                if log:
                    log(f"Tur secim atlandi {cand.symbol} | {cand.sig.strategy} (sinyal gecersiz)")
                continue
            px, sig, ctx = refreshed
            source = getattr(sig, "ledger", "") or cand.sig.ledger
            if not pf.live_strategy_has_slot(source):
                if log:
                    log(f"Tur secim atlandi {cand.symbol} | {sig.strategy} (strateji kotasi dolu)")
                continue
            if try_entry_fn(pf, cand.strategy, ctx, cand.symbol, px, sig=sig):
                opened += 1
                if log:
                    log(
                        f"Tur GIRIS {cand.symbol} | {sig.strategy} | "
                        f"beklenen kar ${cand.expected_profit_usd:.2f} | skor {cand.strength:.2f}"
                    )
            elif log:
                log(
                    f"Tur secim red {cand.symbol} | {sig.strategy} | "
                    f"beklenen kar ${cand.expected_profit_usd:.2f} (cap/kilit/marjin)"
                )
        except Exception as exc:
            if log:
                log(f"Tur secim hata {cand.symbol}: {exc}")
    candidates.clear()
    return opened
