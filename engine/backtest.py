from __future__ import annotations

from collections import defaultdict
from typing import Optional

import pandas as pd

from engine.config import LEDGER_NAMES, TAKER_FEE
from engine.context import build_context, indicate_frame
from engine.types import Side, Signal
from risk.sizer import (
    PositionRisk,
    max_positions_for_ledger,
    risk_pct_for_ledger,
    size_position,
    would_survive_all_sl,
)
from strategies.registry import all_strategies
from structure.core import add_structure


def _slice_closed(frames: dict[str, pd.DataFrame], ts) -> dict[str, pd.DataFrame]:
    out = {}
    for tf, df in frames.items():
        if df is None or df.empty or "close_time" not in df.columns:
            continue
        sl = df[df["close_time"] <= ts]
        if len(sl) >= 30:
            out[tf] = sl
    return out


def _intrabar_exit(side: Side, sl: float, tp: Optional[float], high: float, low: float) -> Optional[tuple[str, float]]:
    hit_sl = low <= sl if side == Side.BUY else high >= sl
    hit_tp = False
    if tp is not None:
        hit_tp = high >= tp if side == Side.BUY else low <= tp
    if hit_sl and hit_tp:
        return "SL", sl
    if hit_sl:
        return "SL", sl
    if hit_tp:
        return "TP", tp
    return None


def backtest_symbol(symbol: str, frames: dict[str, pd.DataFrame], dominance: Optional[dict] = None, warmup: int = 120) -> dict:
    strats = all_strategies()
    indicated = {tf: add_structure(indicate_frame(df)) for tf, df in frames.items()}
    h1 = indicated.get("1h")
    if h1 is None or len(h1) < warmup + 20:
        return {"symbol": symbol, "trades": [], "error": "not_enough_1h"}

    ledgers = {k: 100.0 for k in LEDGER_NAMES}
    open_pos: dict[str, dict] = {}
    trades: list[dict] = []

    for i in range(warmup, len(h1)):
        row = h1.iloc[i]
        ts = row["close_time"]
        price = float(row["close"])
        high, low = float(row["high"]), float(row["low"])

        for key in list(open_pos):
            p = open_pos[key]
            hit = _intrabar_exit(p["side"], p["sl"], p.get("tp"), high, low)
            if not hit:
                continue
            reason, fill = hit
            ratio = (fill - p["entry"]) / p["entry"] if p["side"] == Side.BUY else (p["entry"] - fill) / p["entry"]
            net = p["notional"] * ratio - p["notional"] * TAKER_FEE * 2
            ledgers[p["ledger"]] = max(ledgers[p["ledger"]] + p["margin"] + net, 0.0)
            trades.append({
                "symbol": symbol, "ledger": p["ledger"], "strategy": p["strategy"],
                "side": p["side"].value, "entry": p["entry"], "exit": fill,
                "pnl": net, "reason": reason, "time": str(ts),
            })
            del open_pos[key]

        sliced = _slice_closed(indicated, ts)
        if "1h" not in sliced or "1d" not in sliced:
            continue
        ctx = build_context(symbol, sliced, dominance, indicated=True)
        counts = defaultdict(int)
        for p in open_pos.values():
            counts[p["ledger"]] += 1

        for strat in strats:
            cap = max_positions_for_ledger(strat.ledger)
            if cap is not None and counts[strat.ledger] >= cap:
                continue
            if any(p["symbol"] == symbol for p in open_pos.values()):
                break
            if f"{strat.ledger}|{symbol}" in open_pos:
                continue
            try:
                sig: Optional[Signal] = strat.signal(ctx)
            except Exception:
                continue
            if sig is None:
                continue
            if not ctx.aligned(sig.side):
                continue
            cash = ledgers[sig.ledger]
            sized = size_position(
                ledger_balance=cash,
                entry=price,
                sl=sig.sl_price,
                risk_pct=risk_pct_for_ledger(sig.ledger),
            )
            if sized is None:
                continue
            existing = [
                PositionRisk(entry=p["entry"], sl=p["sl"], notional=p["notional"], margin=p["margin"])
                for p in open_pos.values()
                if p["ledger"] == sig.ledger
            ]
            new_risk = PositionRisk(entry=price, sl=sig.sl_price, notional=sized.notional, margin=sized.margin)
            if not would_survive_all_sl(cash=cash, open_positions=existing, new=new_risk):
                continue
            ledgers[sig.ledger] -= sized.margin
            open_pos[f"{sig.ledger}|{symbol}"] = {
                "side": sig.side, "entry": price, "sl": sig.sl_price, "tp": sig.tp_price,
                "margin": sized.margin, "notional": sized.notional, "ledger": sig.ledger,
                "strategy": sig.strategy, "symbol": symbol,
            }
            counts[sig.ledger] += 1
            break

    # flatten remaining at last close
    last = float(h1["close"].iloc[-1])
    for p in open_pos.values():
        ratio = (last - p["entry"]) / p["entry"] if p["side"] == Side.BUY else (p["entry"] - last) / p["entry"]
        net = p["notional"] * ratio - p["notional"] * TAKER_FEE * 2
        ledgers[p["ledger"]] = max(ledgers[p["ledger"]] + p["margin"] + net, 0.0)
        trades.append({
            "symbol": symbol, "ledger": p["ledger"], "strategy": p["strategy"],
            "side": p["side"].value, "entry": p["entry"], "exit": last,
            "pnl": net, "reason": "EOD", "time": str(h1["close_time"].iloc[-1]),
        })

    return {"symbol": symbol, "trades": trades, "ledgers": ledgers}


def summarize(results: list[dict]) -> pd.DataFrame:
    rows = []
    by_ledger: dict[str, list] = defaultdict(list)
    for r in results:
        for t in r.get("trades") or []:
            by_ledger[t["ledger"]].append(t)
    for ledger in LEDGER_NAMES:
        ts = by_ledger.get(ledger, [])
        if not ts:
            rows.append({"ledger": ledger, "n": 0, "win_rate": None, "pnl": 0.0, "profit_factor": None, "equity": 100.0})
            continue
        pnls = [t["pnl"] for t in ts]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        gp, gl = sum(wins), abs(sum(losses))
        rows.append({
            "ledger": ledger,
            "n": len(ts),
            "win_rate": len(wins) / len(ts),
            "pnl": sum(pnls),
            "profit_factor": (gp / gl) if gl else None,
            "equity": 100.0 + sum(pnls),
        })
    return pd.DataFrame(rows)
