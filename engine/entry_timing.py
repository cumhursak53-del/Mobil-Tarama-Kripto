"""Giris zamanlamasi — strateji bazli bar kapanisi vs canli fiyat."""
from __future__ import annotations

from engine.config import ENTRY_TF, TRIGGER_TF
from strategies.base import Strategy


def entry_bar_tf(strat: Strategy) -> str:
    if strat.uses_live_entry():
        return strat.entry_timeframe()
    return strat.entry_timeframe() or ENTRY_TF


def should_evaluate_entry(strat: Strategy, *, force: bool, bar_closed: dict[str, bool]) -> bool:
    """Live stratejiler her turda; digerleri ilgili TF mum kapanisinda."""
    if force:
        return True
    if strat.uses_live_entry():
        return True
    return bar_closed.get(entry_bar_tf(strat), False)


def collect_bar_closes(cache, symbol: str, strats: list[Strategy], *, force: bool) -> dict[str, bool]:
    tfs: set[str] = set()
    for s in strats:
        if not s.uses_live_entry():
            tfs.add(entry_bar_tf(s))
    out: dict[str, bool] = {}
    for tf in tfs:
        out[tf] = force or cache.new_closed_bar(symbol, tf)
    return out


def live_entry_timeframes(strats: list[Strategy]) -> set[str]:
    return {s.entry_timeframe() for s in strats if s.uses_live_entry()}


def refresh_tfs_for_scan(strats: list[Strategy]) -> tuple[str, ...]:
    from engine.config import TIMEFRAMES

    needed = set(TIMEFRAMES)
    for s in strats:
        if s.uses_live_entry():
            needed.add(s.entry_timeframe())
            needed.add(TRIGGER_TF)
    order = list(TIMEFRAMES)
    return tuple(tf for tf in order if tf in needed)
