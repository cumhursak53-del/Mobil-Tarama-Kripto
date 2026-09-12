from __future__ import annotations

from typing import Callable, Optional

from engine.config import PATLAMA_LEDGER, PATLAMA_MIN_EDGE, PATLAMA_MIN_SCORE, PATLAMA_TOP_N
from engine.context import build_context
from engine.momentum_scan import score_momentum, trade_signal_from_score
from engine.types import Side


def rank_patlama_candidates(scan: dict, universe: list[str] | None = None) -> tuple[list[tuple], list[tuple]]:
    """Trade sartini saglayan long/short adaylarini skora gore sirala."""
    longs: list[tuple[str, int, int]] = []
    shorts: list[tuple[str, int, int]] = []
    allowed = set(universe) if universe else None
    for sym, row in (scan or {}).items():
        if not isinstance(row, dict) or (allowed is not None and sym not in allowed):
            continue
        ls = int(row.get("long_score") or 0)
        ss = int(row.get("short_score") or 0)
        edge = PATLAMA_MIN_EDGE
        ms = PATLAMA_MIN_SCORE
        if ls >= ms and ls >= ss + edge:
            longs.append((sym, ls, ls - ss))
        if ss >= ms and ss >= ls + edge:
            shorts.append((sym, ss, ss - ls))
    longs.sort(key=lambda x: (x[1], x[2]), reverse=True)
    shorts.sort(key=lambda x: (x[1], x[2]), reverse=True)
    return longs, shorts


def select_top_n(
    scan: dict,
    *,
    top_n: int | None = None,
    universe: list[str] | None = None,
) -> list[tuple[str, Side, int]]:
    n = int(top_n if top_n is not None else PATLAMA_TOP_N)
    if n <= 0:
        return []
    longs, shorts = rank_patlama_candidates(scan, universe)
    out: list[tuple[str, Side, int]] = []
    for sym, score, _ in longs[:n]:
        out.append((sym, Side.BUY, score))
    for sym, score, _ in shorts[:n]:
        out.append((sym, Side.SELL, score))
    return out


def run_patlama_top_n_entries(
    pf,
    cache,
    dominance: dict,
    universe: list[str],
    *,
    refresh_strats: Callable,
    entry_price_fn: Callable,
    try_open_fn: Callable,
    log: Callable[[str], None] | None = None,
) -> int:
    """Tam tur sonunda en iyi N long + N short icin Patlama girisi dene."""
    if PATLAMA_TOP_N <= 0:
        return 0
    picks = select_top_n(pf.patlama_scan, universe=universe)
    if not picks:
        if log:
            log("Patlama top-N: trade adayi yok")
        return 0

    strats = refresh_strats(pf)
    patlama = next((s for s in strats if s.ledger == PATLAMA_LEDGER), None)
    if patlama is None:
        return 0

    from engine.entry_timing import refresh_tfs_for_scan

    scan_tfs = refresh_tfs_for_scan(strats)
    opened = 0
    if log:
        log(f"Patlama top-N: {len(picks)} aday (N={PATLAMA_TOP_N}/yon)")

    for sym, want_side, score in picks:
        try:
            frames = cache.refresh(sym, scan_tfs)
            if "1h" not in frames or "1d" not in frames:
                continue
            live_px = None
            try:
                from engine.data import last_prices

                live_px = last_prices([sym]).get(sym)
            except Exception:
                pass
            ctx = build_context(sym, frames, dominance, indicated=False)
            scored = score_momentum(ctx)
            side = trade_signal_from_score(scored)
            if side is None or side != want_side or not ctx.aligned(side):
                if log:
                    log(f"Patlama top-N atlandi {sym} | skor tablo={score} | canli={side}")
                continue
            sig = patlama.signal(ctx)
            if sig is None or sig.side != want_side:
                continue
            px = entry_price_fn(patlama, sym, frames, live_px)
            if px <= 0:
                continue
            pf.record_signal(sym, sig)
            if try_open_fn(pf, patlama, ctx, sym, px):
                opened += 1
                if log:
                    tag = "Long" if side == Side.BUY else "Short"
                    log(f"Patlama top-N GIRIS {sym} {tag} | skor {score}")
            elif log:
                log(f"Patlama top-N red {sym} | skor {score} (cap/marjin/kilit)")
        except Exception as e:
            if log:
                log(f"Patlama top-N hata {sym}: {e}")
    return opened
