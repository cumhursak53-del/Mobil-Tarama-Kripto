from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Optional

from engine.config import KASA_START_USD, LEDGER_NAMES, STATE_FILE, TAKER_FEE, TR_TZ
from engine.github_sync import pull_state, push_state
from engine.types import ClosedTrade, Position, Side, Signal
from risk.sizer import (
    PositionRisk,
    max_positions_for_ledger,
    risk_pct_for_ledger,
    size_position,
    would_survive_all_sl,
)


def now_tr(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    return datetime.now(TR_TZ).strftime(fmt)


class Portfolio:
    def __init__(self, path: str = STATE_FILE):
        self.path = path
        self.ledgers: dict[str, float] = {k: KASA_START_USD for k in LEDGER_NAMES}
        self.positions: dict[str, Position] = {}  # key: ledger|symbol
        self.history: list[dict] = []
        self.signal_log: dict = {}
        self.logs: list[str] = []
        self._equity_curve: list[dict] = []
        remote = pull_state()
        if remote and not os.path.exists(self.path):
            self._apply_raw(remote)
        self.load()

    @staticmethod
    def pos_key(ledger: str, symbol: str) -> str:
        return f"{ledger}|{symbol}"

    def load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:
            return
        self._apply_raw(raw)

    def _apply_raw(self, raw: dict) -> None:
        self.ledgers.update(raw.get("ledgers") or {})
        for k in LEDGER_NAMES:
            self.ledgers.setdefault(k, KASA_START_USD)
        self.history = raw.get("history") or []
        self.signal_log = raw.get("signal_log") or {}
        self.logs = raw.get("engine_logs") or []
        self._equity_curve = raw.get("equity_curve") or []
        self.positions = {}
        for key, p in (raw.get("active_positions") or {}).items():
            try:
                self.positions[key] = Position(
                    symbol=p["symbol"],
                    side=Side(p["side"]),
                    ledger=p["ledger_name"],
                    strategy=p.get("strategy", ""),
                    entry_price=float(p["entry_price"]),
                    sl_price=float(p["sl_price"]),
                    tp_price=p.get("tp_price"),
                    margin=float(p["margin"]),
                    notional=float(p.get("notional") or p["margin"] * p.get("leverage", 1)),
                    leverage=float(p.get("leverage") or 1),
                    qty=float(p.get("qty") or 0),
                    entry_time=p.get("entry_time", ""),
                    entry_tf=p.get("entry_tf", "1h"),
                    peak_price=float(p.get("peak_price") or p["entry_price"]),
                    partial_taken=bool(p.get("partial_tp_taken")),
                    current_price=float(p.get("current_price") or p["entry_price"]),
                )
            except Exception:
                continue

    def save(self, sync_github: bool = False) -> None:
        payload = self.snapshot()
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        if sync_github:
            push_state(payload)

    def _pos_dict(self, p: Position) -> dict:
        return {
            "symbol": p.symbol,
            "side": p.side.value,
            "ledger_name": p.ledger,
            "strategy": p.strategy,
            "entry_price": p.entry_price,
            "sl_price": p.sl_price,
            "tp_price": p.tp_price,
            "margin": p.margin,
            "notional": p.notional,
            "leverage": p.leverage,
            "qty": p.qty,
            "entry_time": p.entry_time,
            "entry_tf": p.entry_tf,
            "peak_price": p.peak_price,
            "partial_tp_taken": p.partial_taken,
            "current_price": p.current_price,
        }

    def log(self, msg: str) -> None:
        line = f"[{now_tr('%H:%M:%S')}] {msg}"
        print(line, flush=True)
        self.logs.append(line)
        if len(self.logs) > 100:
            self.logs = self.logs[-100:]

    def ledger_position_count(self, ledger: str) -> int:
        return sum(1 for p in self.positions.values() if p.ledger == ledger)

    def symbol_open(self, symbol: str) -> bool:
        return any(p.symbol == symbol for p in self.positions.values())

    def _ledger_risks(self, ledger: str) -> list[PositionRisk]:
        return [
            PositionRisk(entry=p.entry_price, sl=p.sl_price, notional=p.notional, margin=p.margin)
            for p in self.positions.values()
            if p.ledger == ledger
        ]

    def try_open(self, symbol: str, sig: Signal, price: float) -> bool:
        cap = max_positions_for_ledger(sig.ledger)
        if cap is not None and self.ledger_position_count(sig.ledger) >= cap:
            return False
        if self.symbol_open(symbol):
            return False
        key = self.pos_key(sig.ledger, symbol)
        if key in self.positions:
            return False
        cash = self.ledgers.get(sig.ledger, 0)
        sized = size_position(
            ledger_balance=cash,
            entry=price,
            sl=sig.sl_price,
            risk_pct=risk_pct_for_ledger(sig.ledger),
        )
        if sized is None:
            return False
        new_risk = PositionRisk(entry=price, sl=sig.sl_price, notional=sized.notional, margin=sized.margin)
        if not would_survive_all_sl(cash=cash, open_positions=self._ledger_risks(sig.ledger), new=new_risk):
            return False
        self.ledgers[sig.ledger] -= sized.margin
        self.positions[key] = Position(
            symbol=symbol,
            side=sig.side,
            ledger=sig.ledger,
            strategy=sig.strategy,
            entry_price=price,
            sl_price=sig.sl_price,
            tp_price=sig.tp_price,
            margin=sized.margin,
            notional=sized.notional,
            leverage=sized.leverage,
            qty=sized.qty,
            entry_time=now_tr(),
            peak_price=price,
            current_price=price,
        )
        self.log(
            f"YENI {sig.side.value} {symbol} | {sig.strategy} | {sig.ledger} "
            f"| {sized.leverage:.0f}x | marjin ${sized.margin:.2f} | notional ${sized.notional:.2f}"
        )
        return True

    def mark(self, symbol: str, price: float) -> None:
        for p in self.positions.values():
            if p.symbol == symbol:
                p.current_price = price
                if p.side == Side.BUY:
                    p.peak_price = max(p.peak_price, price)
                else:
                    p.peak_price = min(p.peak_price, price) if p.peak_price else price

    def check_exits(self, symbol: str, price: float) -> list[ClosedTrade]:
        closed: list[ClosedTrade] = []
        for key in list(self.positions):
            p = self.positions[key]
            if p.symbol != symbol:
                continue
            reason = self._exit_reason(p, price)
            if not reason:
                continue
            closed.append(self._close(key, price, reason))
        return closed

    def _exit_reason(self, p: Position, price: float) -> Optional[str]:
        if p.side == Side.BUY:
            if price <= p.sl_price:
                return "SL"
            if p.tp_price and price >= p.tp_price:
                return "TP"
        else:
            if price >= p.sl_price:
                return "SL"
            if p.tp_price and price <= p.tp_price:
                return "TP"
        return None

    def _close(self, key: str, price: float, reason: str) -> ClosedTrade:
        p = self.positions.pop(key)
        ratio = (price - p.entry_price) / p.entry_price if p.side == Side.BUY else (p.entry_price - price) / p.entry_price
        gross = p.notional * ratio
        fee = p.notional * TAKER_FEE * 2
        net = gross - fee
        self.ledgers[p.ledger] = max(self.ledgers.get(p.ledger, 0) + p.margin + net, 0.0)
        risk = abs(p.entry_price - p.sl_price) / p.entry_price * p.notional
        r_mult = net / risk if risk else 0.0
        trade = ClosedTrade(
            symbol=p.symbol,
            side=p.side.value,
            ledger=p.ledger,
            strategy=p.strategy,
            entry=p.entry_price,
            exit=price,
            pnl=net,
            close_reason=reason,
            exit_time=now_tr(),
            r_multiple=r_mult,
        )
        eq = sum(self.ledgers.values()) + sum(p.margin for p in self.positions.values())
        self.history.append({
            "symbol": trade.symbol, "side": trade.side, "strategy": trade.strategy,
            "entry": trade.entry, "exit": trade.exit, "pnl": trade.pnl,
            "close_reason": trade.close_reason, "ledger": trade.ledger,
            "exit_time": trade.exit_time, "entry_time": p.entry_time,
            "r": trade.r_multiple, "new_balance": eq,
        })
        self._equity_curve.append({"time": trade.exit_time, "equity": eq})
        self._equity_curve = self._equity_curve[-300:]
        self.log(f"KAPANDI {p.symbol} {reason} | {p.ledger} | PnL ${net:+.2f}")
        return trade

    def record_signal(self, symbol: str, sig: Signal) -> None:
        rec = self.signal_log.setdefault(symbol, {"count": 0, "strategies": [], "last_side": "", "last_time": ""})
        rec["count"] += 1
        rec["last_side"] = sig.side.value
        rec["last_time"] = now_tr()
        rec["last_ledger"] = sig.ledger
        if sig.strategy not in rec["strategies"]:
            rec["strategies"].append(sig.strategy)

    def snapshot(self) -> dict:
        eq = sum(self.ledgers.values()) + sum(p.margin for p in self.positions.values())
        cash = sum(self.ledgers.values())
        pos_dicts = {k: self._pos_dict(p) for k, p in self.positions.items()}
        for d in pos_dicts.values():
            entry, cur, side = d["entry_price"], d["current_price"], d["side"]
            if entry:
                ratio = (cur - entry) / entry if side == "BUY" else (entry - cur) / entry
                d["unrealized_pnl"] = d["notional"] * ratio
                d["roe_pct"] = ratio * d["leverage"] * 100
            else:
                d["unrealized_pnl"] = 0.0
                d["roe_pct"] = 0.0
        return {
            "ledgers": self.ledgers,
            "balance": cash,
            "equity": eq,
            "active_positions": pos_dicts,
            "history": self.history[-200:],
            "signal_log": {k: v for k, v in self.signal_log.items() if not str(k).startswith("_")},
            "engine_logs": self.logs[-100:],
            "equity_curve": self._equity_curve[-300:],
            "kasa_count": len(LEDGER_NAMES),
            "updated_at": now_tr(),
        }
