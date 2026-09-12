from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Optional

from engine.config import (
    BE_AT_R,
    CREW_AUTO,
    GEMINI_API_KEY,
    GITHUB_TOKEN,
    KASA_START_USD,
    LAB_AUTO,
    LAB_LEDGER_PREFIX,
    LEDGER_NAMES,
    MAX_SHORT_OPEN_RATIO,
    MAX_TOTAL_POSITIONS,
    PARTIAL_PCT,
    PARTIAL_R,
    RESEARCH_ENABLED,
    SHORT_RATIO_MIN_POSITIONS,
    HISTORY_MAX,
    SMC_PENDING_MAX_HOURS,
    STATE_FILE,
    SYMBOL_COOLDOWN_AFTER_SL_SEC,
    SYMBOL_LOCK_MODE,
    TAKER_FEE,
    TR_TZ,
)
from engine.github_sync import pull_state, push_state
from engine.lab_state import (
    evaluate_lab_candidates,
    load_lab_state,
    record_lab_trade,
    sync_lab_state,
)
from engine.state_merge import merge_trading_state
from engine.post_exit import enqueue_watch
from engine.trade_analysis import make_trade_id
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
        self.patlama_scan: dict[str, dict] = {}
        self.smc_scan: dict[str, dict] = {}
        self.lab_state: dict = {}
        self.crew_state: dict = {}
        self.logs: list[str] = []
        self._equity_curve: list[dict] = []
        self._symbol_sl_until: dict[str, float] = {}
        self.pending_orders: list[dict] = []
        self.post_exit_watchlist: list[dict] = []
        self.post_exit_log: list[dict] = []
        self.state_source: str = "fresh"
        remote = pull_state()
        local_raw = None
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    local_raw = json.load(f)
            except Exception:
                local_raw = None
        merged, self.state_source = merge_trading_state(local_raw, remote)
        pre_hist = len((local_raw or {}).get("history") or [])
        pre_remote_hist = len((remote or {}).get("history") or [])
        if merged:
            self._apply_raw(merged)
        else:
            self.load()
        self.lab_state = load_lab_state()
        from engine.crew.sync import load_crew_state

        self.crew_state = load_crew_state()
        self._ensure_lab_ledgers()
        if os.environ.get("RESET_TRADING_ON_START", "0") == "1":
            self.reset_trading(keep_scans=True, keep_signals=True)
            self.save(sync_github=bool(GITHUB_TOKEN))
        n_pos = len(self.positions)
        n_hist = len(self.history)
        if merged and n_hist > max(pre_hist, pre_remote_hist):
            self.log(f"Islem gecmisi birlestirildi: {n_hist} kayit (local {pre_hist}, github {pre_remote_hist})")
        sync_mode = "token" if GITHUB_TOKEN else "actions"
        self.log(
            f"State yuklendi [{self.state_source}] | acik {n_pos} | kapanan {n_hist} | "
            f"github={'ok' if remote else 'yok'} | sync={sync_mode}"
        )
        if n_pos or n_hist:
            self.save(sync_github=bool(GITHUB_TOKEN))

    @staticmethod
    def pos_key(ledger: str, symbol: str) -> str:
        return f"{ledger}|{symbol}"

    def _ensure_lab_ledgers(self) -> None:
        for c in self.lab_state.get("candidates") or []:
            if c.get("status") != "paper":
                continue
            ledger = c.get("ledger")
            if ledger:
                self.ledgers.setdefault(ledger, KASA_START_USD)

    def active_lab_ledgers(self) -> list[str]:
        return [
            c.get("ledger")
            for c in self.lab_state.get("candidates") or []
            if c.get("status") == "paper" and c.get("ledger")
        ]

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
        self.patlama_scan = raw.get("patlama_selale_scan") or {}
        self.smc_scan = raw.get("smc_scan") or {}
        self.logs = raw.get("engine_logs") or []
        self._equity_curve = raw.get("equity_curve") or []
        self.pending_orders = raw.get("pending_orders") or []
        self.post_exit_watchlist = raw.get("post_exit_watchlist") or []
        self.post_exit_log = raw.get("post_exit_log") or []
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
                    tp_levels=list(p.get("tp_levels") or []),
                    trail_at_r=p.get("trail_at_r"),
                    be_at_r=p.get("be_at_r"),
                    partial_pct=float(p.get("partial_pct") or PARTIAL_PCT),
                    initial_sl=float(p.get("initial_sl") or p["sl_price"]),
                    remaining_notional=float(p.get("remaining_notional") or p.get("notional") or 0),
                    remaining_qty=float(p.get("remaining_qty") or p.get("qty") or 0),
                )
            except Exception:
                continue

    def reset_trading(self, *, keep_scans: bool = True, keep_signals: bool = True) -> None:
        """Acik pozisyonlari ve islem gecmisini sifirla; kasa bakiyelerini baslangica cek."""
        self.positions.clear()
        self.history.clear()
        self.pending_orders.clear()
        self.post_exit_watchlist.clear()
        self.post_exit_log.clear()
        self._equity_curve.clear()
        self._symbol_sl_until.clear()
        self.ledgers = {k: KASA_START_USD for k in LEDGER_NAMES}
        self._ensure_lab_ledgers()
        for ledger in self.active_lab_ledgers():
            self.ledgers[ledger] = KASA_START_USD
        if not keep_signals:
            self.signal_log = {}
        if not keep_scans:
            self.patlama_scan.clear()
            self.smc_scan.clear()
        self.log("Islem gecmisi ve acik pozisyonlar sifirlandi")

    def save(self, sync_github: bool = False) -> None:
        payload = self.snapshot()
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        if sync_github:
            ok = push_state(payload)
            sync_lab_state(self.lab_state)
            if not ok:
                if GITHUB_TOKEN:
                    self.log("UYARI: GitHub state push basarisiz — deploy'da veri kaybi riski")
                elif not getattr(self, "_sync_info_logged", False):
                    self._sync_info_logged = True
                    self.log(
                        "GitHub yedek: Actions otomatik senkron (token gerekmez) — "
                        "public pull acik"
                    )

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
            "tp_levels": p.tp_levels,
            "trail_at_r": p.trail_at_r,
            "be_at_r": p.be_at_r,
            "partial_pct": p.partial_pct,
            "initial_sl": p.initial_sl,
            "remaining_notional": p.remaining_notional or p.notional,
            "remaining_qty": p.remaining_qty or p.qty,
        }

    def log(self, msg: str) -> None:
        line = f"[{now_tr('%H:%M:%S')}] {msg}"
        print(line, flush=True)
        self.logs.append(line)
        if len(self.logs) > 100:
            self.logs = self.logs[-100:]

    def ledger_position_count(self, ledger: str) -> int:
        return sum(1 for p in self.positions.values() if p.ledger == ledger)

    def symbol_open(self, symbol: str, ledger: str | None = None) -> bool:
        if SYMBOL_LOCK_MODE == "none":
            return False
        if SYMBOL_LOCK_MODE == "per_ledger" and ledger:
            return any(p.symbol == symbol and p.ledger == ledger for p in self.positions.values())
        return any(p.symbol == symbol for p in self.positions.values())

    def symbol_in_cooldown(self, symbol: str) -> bool:
        import time

        until = self._symbol_sl_until.get(symbol, 0)
        return until > time.time()

    def _short_open_ratio(self) -> float:
        if not self.positions:
            return 0.0
        shorts = sum(1 for p in self.positions.values() if p.side == Side.SELL)
        return shorts / len(self.positions)

    def _ledger_risks(self, ledger: str) -> list[PositionRisk]:
        return [
            PositionRisk(entry=p.entry_price, sl=p.sl_price, notional=p.notional, margin=p.margin)
            for p in self.positions.values()
            if p.ledger == ledger
        ]

    def try_open(self, symbol: str, sig: Signal, price: float) -> bool:
        if MAX_TOTAL_POSITIONS > 0 and len(self.positions) >= MAX_TOTAL_POSITIONS:
            return False
        if self.symbol_in_cooldown(symbol):
            return False
        if (
            sig.side == Side.SELL
            and MAX_SHORT_OPEN_RATIO > 0
            and len(self.positions) >= SHORT_RATIO_MIN_POSITIONS
            and self._short_open_ratio() >= MAX_SHORT_OPEN_RATIO
        ):
            return False
        cap = max_positions_for_ledger(sig.ledger)
        if cap is not None and self.ledger_position_count(sig.ledger) >= cap:
            return False
        if self.symbol_open(symbol, sig.ledger):
            return False
        key = self.pos_key(sig.ledger, symbol)
        if key in self.positions:
            return False

        if sig.entry_mode == "limit" and sig.entry_limit is not None:
            self.pending_orders.append({
                "symbol": symbol,
                "ledger": sig.ledger,
                "signal": {
                    "side": sig.side.value,
                    "strategy": sig.strategy,
                    "reason": sig.reason,
                    "sl_price": sig.sl_price,
                    "tp_price": sig.tp_price,
                    "entry_tf": sig.entry_tf,
                    "entry_limit": sig.entry_limit,
                    "tp_levels": sig.tp_levels,
                    "trail_at_r": sig.trail_at_r,
                    "be_at_r": sig.be_at_r,
                    "partial_pct": sig.partial_pct,
                },
                "created_at": now_tr(),
            })
            self.pending_orders = self.pending_orders[-50:]
            return True

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
            tp_levels=list(sig.tp_levels or []),
            trail_at_r=sig.trail_at_r,
            be_at_r=sig.be_at_r or BE_AT_R,
            partial_pct=sig.partial_pct,
            initial_sl=sig.sl_price,
            remaining_notional=sized.notional,
            remaining_qty=sized.qty,
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

    def _risk_dist(self, p: Position) -> float:
        return abs(p.entry_price - p.initial_sl) if p.initial_sl else abs(p.entry_price - p.sl_price)

    def _current_r(self, p: Position, price: float) -> float:
        dist = self._risk_dist(p)
        if dist <= 0:
            return 0.0
        if p.side == Side.BUY:
            return (price - p.entry_price) / dist
        return (p.entry_price - price) / dist

    def _maybe_partial(self, key: str, p: Position, price: float) -> bool:
        if p.partial_taken or PARTIAL_R <= 0:
            return False
        r = self._current_r(p, price)
        if r < PARTIAL_R:
            return False
        close_notional = p.remaining_notional * p.partial_pct
        if close_notional <= 0:
            return False
        ratio = (price - p.entry_price) / p.entry_price if p.side == Side.BUY else (p.entry_price - price) / p.entry_price
        gross = close_notional * ratio
        fee = close_notional * TAKER_FEE * 2
        net = gross - fee
        self.ledgers[p.ledger] = max(self.ledgers.get(p.ledger, 0) + net, 0.0)
        p.remaining_notional -= close_notional
        p.remaining_qty *= 1.0 - p.partial_pct
        p.partial_taken = True
        if p.be_at_r and r >= p.be_at_r:
            p.sl_price = p.entry_price
        eq = sum(self.ledgers.values()) + sum(x.margin for x in self.positions.values())
        trade_id = make_trade_id(p.ledger, p.symbol, p.entry_time)
        self.history.append({
            "symbol": p.symbol,
            "side": p.side.value,
            "strategy": p.strategy,
            "entry": p.entry_price,
            "exit": price,
            "pnl": net,
            "close_reason": "PARTIAL_TP",
            "ledger": p.ledger,
            "exit_time": now_tr(),
            "entry_time": p.entry_time,
            "trade_id": trade_id,
            "partial": True,
            "new_balance": eq,
        })
        self.log(f"KISMI TP {p.symbol} | {p.ledger} | {PARTIAL_PCT*100:.0f}% | PnL ${net:+.2f}")
        return True

    def _maybe_trail(self, p: Position, price: float) -> None:
        if not p.trail_at_r:
            return
        r = self._current_r(p, price)
        if r < p.trail_at_r:
            return
        dist = self._risk_dist(p)
        if dist <= 0:
            return
        if p.side == Side.BUY:
            new_sl = p.peak_price - dist * 0.5
            if new_sl > p.sl_price:
                p.sl_price = new_sl
        else:
            new_sl = p.peak_price + dist * 0.5
            if new_sl < p.sl_price:
                p.sl_price = new_sl

    def _exit_reason(self, p: Position, price: float) -> Optional[str]:
        self._maybe_trail(p, price)
        if p.side == Side.BUY:
            if price <= p.sl_price:
                return "SL"
            if p.tp_price and p.tp_price > p.entry_price and price >= p.tp_price:
                return "TP"
        else:
            if price >= p.sl_price:
                return "SL"
            if p.tp_price and p.tp_price < p.entry_price and price <= p.tp_price:
                return "TP"
        return None

    def check_exits(self, symbol: str, price: float) -> list[ClosedTrade]:
        closed: list[ClosedTrade] = []
        for key in list(self.positions):
            p = self.positions[key]
            if p.symbol != symbol:
                continue
            self._maybe_partial(key, p, price)
            reason = self._exit_reason(p, price)
            if not reason:
                continue
            closed.append(self._close(key, price, reason))
        return closed

    def _pending_expired(self, po: dict) -> bool:
        if SMC_PENDING_MAX_HOURS <= 0:
            return False
        created = po.get("created_at")
        if not created:
            return False
        try:
            ts = datetime.strptime(str(created), "%Y-%m-%d %H:%M:%S")
            age_h = (datetime.now(TR_TZ) - ts.replace(tzinfo=TR_TZ)).total_seconds() / 3600.0
            return age_h >= SMC_PENDING_MAX_HOURS
        except Exception:
            return False

    def try_pending_orders(self, symbol: str, price: float) -> bool:
        opened = False
        remain = []
        for po in self.pending_orders:
            if self._pending_expired(po):
                continue
            if po.get("symbol") != symbol:
                remain.append(po)
                continue
            limit = float(po["signal"].get("entry_limit") or 0)
            side = po["signal"].get("side")
            hit = (side == "BUY" and price <= limit) or (side == "SELL" and price >= limit)
            if not hit:
                remain.append(po)
                continue
            sig = Signal(
                side=Side(side),
                strategy=po["signal"]["strategy"],
                ledger=po["ledger"],
                reason=po["signal"]["reason"],
                sl_price=float(po["signal"]["sl_price"]),
                tp_price=po["signal"].get("tp_price"),
                entry_tf=po["signal"].get("entry_tf", "1h"),
                entry_mode="market",
                tp_levels=list(po["signal"].get("tp_levels") or []),
                trail_at_r=po["signal"].get("trail_at_r"),
                be_at_r=po["signal"].get("be_at_r"),
                partial_pct=float(po["signal"].get("partial_pct") or PARTIAL_PCT),
            )
            if self.try_open(symbol, sig, limit):
                opened = True
        self.pending_orders = remain
        return opened

    def _close(self, key: str, price: float, reason: str) -> ClosedTrade:
        p = self.positions.pop(key)
        notional = p.remaining_notional or p.notional
        ratio = (price - p.entry_price) / p.entry_price if p.side == Side.BUY else (p.entry_price - price) / p.entry_price
        gross = notional * ratio
        fee = notional * TAKER_FEE * 2
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
        eq = sum(self.ledgers.values()) + sum(x.margin for x in self.positions.values())
        trade_id = make_trade_id(p.ledger, p.symbol, p.entry_time)
        hist_row = {
            "symbol": trade.symbol,
            "side": trade.side,
            "strategy": trade.strategy,
            "entry": trade.entry,
            "exit": trade.exit,
            "pnl": trade.pnl,
            "close_reason": trade.close_reason,
            "ledger": trade.ledger,
            "exit_time": trade.exit_time,
            "entry_time": p.entry_time,
            "trade_id": trade_id,
            "initial_sl": p.initial_sl or p.sl_price,
            "sl_price": p.sl_price,
            "tp_price": p.tp_price,
            "peak_price": p.peak_price,
            "entry_tf": p.entry_tf,
            "notional": p.notional,
            "margin": p.margin,
            "partial": False,
            "r": trade.r_multiple,
            "new_balance": eq,
        }
        self.history.append(hist_row)
        enqueue_watch(self.post_exit_watchlist, trade=hist_row, log=self.log)
        self._equity_curve.append({"time": trade.exit_time, "equity": eq})
        self._equity_curve = self._equity_curve[-300:]
        self.log(f"KAPANDI {p.symbol} {reason} | {p.ledger} | PnL ${net:+.2f}")
        if reason == "SL" and SYMBOL_COOLDOWN_AFTER_SL_SEC > 0:
            import time

            self._symbol_sl_until[p.symbol] = time.time() + SYMBOL_COOLDOWN_AFTER_SL_SEC
        if p.ledger.startswith(LAB_LEDGER_PREFIX):
            record_lab_trade(self.lab_state, p.ledger, net)
            evaluate_lab_candidates(self.lab_state)
        return trade

    def record_patlama_scan(self, symbol: str, payload: dict) -> None:
        payload = dict(payload)
        payload["updated_at"] = now_tr()
        self.patlama_scan[symbol] = payload
        if len(self.patlama_scan) > 600:
            ranked = sorted(
                self.patlama_scan.items(),
                key=lambda kv: float(kv[1].get("best_score") or 0),
                reverse=True,
            )
            self.patlama_scan = dict(ranked[:500])

    def record_smc_scan(self, symbol: str, payload: dict) -> None:
        payload = dict(payload)
        payload["updated_at"] = now_tr()
        self.smc_scan[symbol] = payload
        if len(self.smc_scan) > 600:
            ranked = sorted(
                self.smc_scan.items(),
                key=lambda kv: float(kv[1].get("best_score") or 0),
                reverse=True,
            )
            self.smc_scan = dict(ranked[:500])

    def record_signal(self, symbol: str, sig: Signal) -> None:
        rec = self.signal_log.setdefault(
            symbol,
            {"count": 0, "strategies": [], "last_side": "", "last_time": "", "first_time": ""},
        )
        ts = now_tr()
        if rec["count"] == 0:
            rec["first_time"] = ts
        rec["count"] += 1
        rec["last_side"] = sig.side.value
        rec["last_time"] = ts
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
        candidates = self.lab_state.get("candidates") or []
        recipes = self.lab_state.get("recipes") or []
        backtests = self.lab_state.get("backtests") or []
        paper = [c for c in candidates if c.get("status") == "paper"]
        rejected = [c for c in candidates if c.get("status") == "rejected"]
        closed_pnl = sum(float(h.get("pnl") or 0) for h in self.history)
        from engine.lab_backtest_view import backtest_summary

        bt_summary = backtest_summary(recipes, backtests)
        return {
            "ledgers": self.ledgers,
            "balance": cash,
            "equity": eq,
            "closed_pnl_total": closed_pnl,
            "active_positions": pos_dicts,
            "pending_orders": self.pending_orders[-20:],
            "post_exit_watchlist": self.post_exit_watchlist[-200:],
            "post_exit_log": self.post_exit_log[-500:],
            "history": self.history[-HISTORY_MAX:],
            "history_count": len(self.history),
            "signal_log": {k: v for k, v in self.signal_log.items() if not str(k).startswith("_")},
            "patlama_selale_scan": self.patlama_scan,
            "smc_scan": self.smc_scan,
            "engine_logs": self.logs[-100:],
            "equity_curve": self._equity_curve[-300:],
            "kasa_count": len(LEDGER_NAMES) + len(self.active_lab_ledgers()),
            "lab_candidates": paper,
            "lab_summary": {
                "updated_at": self.lab_state.get("updated_at"),
                "recipe_count": len(recipes),
                "backtest_count": bt_summary["total_runs"],
                "backtest_unique": bt_summary["unique_tested"],
                "backtest_pending": bt_summary["pending_test"],
                "backtest_passed": bt_summary["passed_count"],
                "paper_count": len(paper),
                "rejected_count": len(rejected),
                "recent_backtests": bt_summary["latest_results"],
                "all_backtests_latest": bt_summary["latest_results"],
                "all_candidates": candidates,
                "pipeline": self.lab_state.get("pipeline") or {},
                "research": {
                    **(self.lab_state.get("research") or {}),
                    "gemini_configured": bool(GEMINI_API_KEY),
                    "research_enabled": RESEARCH_ENABLED,
                },
                "source_metrics": self.lab_state.get("source_metrics") or {},
                "research_queue_len": len(self.lab_state.get("research_queue") or []),
            },
            "engine_flags": {
                "research_enabled": RESEARCH_ENABLED,
                "gemini_configured": bool(GEMINI_API_KEY),
                "lab_auto": LAB_AUTO,
                "crew_auto": CREW_AUTO,
                "github_token": bool(GITHUB_TOKEN),
            },
            "crew_summary": self._crew_summary(),
            "updated_at": now_tr(),
        }

    def _crew_summary(self) -> dict:
        from engine.crew.summary import crew_summary_from_state

        return crew_summary_from_state(self.crew_state)
