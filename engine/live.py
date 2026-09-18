"""Slim 7/24 live runner — Hacim + PiyasaEvresi tek kasada (Kasa_Canli)."""
from __future__ import annotations

import atexit
import json
import os
import signal
import threading
import time
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, HTTPServer

from engine.config import (
    BYBIT_API_KEY,
    BYBIT_API_SECRET,
    BYBIT_BASE_URL,
    LIVE_COMBO_LEDGER,
    LIVE_HTTP_PORT,
    LIVE_KASA_BALANCES,
    LIVE_KASA_USD,
    LIVE_LEDGERS,
    LIVE_LONG_ONLY,
    PRICE_POLL_SEC,
    SCAN_SYMBOLS,
    TRADING_MODE,
    is_live_exchange,
)
from engine.context import build_context
from engine.data import fetch_dominance, fetch_klines, fetch_symbols, last_prices
from engine.df_utils import pick_frame
from engine.entry_timing import collect_bar_closes, refresh_tfs_for_scan, should_evaluate_entry
from engine.exchange.bybit_client import BybitClient
from engine.exchange.executor import get_executor
from engine.paper import FrameCache, _entry_price, _mark_price, _update_dominance, run_price_pass
from engine.portfolio import Portfolio
from strategies.registry import live_strategies

_STRATS = live_strategies()
_TF_TTL_SEC = {"15m": 45, "1h": 180, "4h": 900, "1d": 3600, "1w": 7200}


class _LiveHandler(BaseHTTPRequestHandler):
    portfolio: Portfolio

    def do_GET(self):
        try:
            body = self.portfolio.snapshot()
            body["trading_mode"] = TRADING_MODE
            body["live_ledgers"] = list(LIVE_LEDGERS)
            body["live_combo_ledger"] = LIVE_COMBO_LEDGER
            body["live_strategies"] = ["Kasa_Hacim", "Kasa_PiyasaEvresi"]
            body["live_exchange"] = is_live_exchange()
            if not body["live_exchange"]:
                body["active_positions"] = {}
                body["pending_orders"] = []
                cash = float(body.get("balance") or LIVE_KASA_USD)
                body["balance"] = cash
                body["equity"] = cash
            payload = json.dumps(body, default=str).encode("utf-8")
            code = 200
        except Exception as exc:
            payload = json.dumps({"error": str(exc), "engine_logs": self.portfolio.logs[-20:]}).encode(
                "utf-8"
            )
            code = 500
        self.send_response(code)
        self.send_header("Content-type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        return


def start_http(portfolio: Portfolio) -> None:
    _LiveHandler.portfolio = portfolio
    port = int(os.environ.get("PORT", str(LIVE_HTTP_PORT)))
    server = HTTPServer(("0.0.0.0", port), _LiveHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    portfolio.log(f"Canli HTTP API :{port}")


def _sync_exchange_on_start(pf: Portfolio) -> None:
    if not is_live_exchange():
        pf.log("Canli mod kapali — paper/simulasyon")
        return
    if not BYBIT_API_KEY or not BYBIT_API_SECRET:
        pf.log("UYARI: BYBIT API key eksik — emir gonderilmeyecek")
        return
    client = BybitClient()
    try:
        if not client.ping():
            pf.log("UYARI: Bybit API erisilemiyor")
            return
        bal = client.get_wallet_balance()
        pf.log(f"Bybit baglantisi OK ({BYBIT_BASE_URL}) | USDT ${bal:.2f}")
        remote = get_executor().sync_positions()
        if remote:
            syms = ", ".join(f"{r['symbol']}({r['side']})" for r in remote[:8])
            pf.log(f"Borsada acik pozisyon: {len(remote)} | {syms}")
        else:
            pf.log("Borsada acik pozisyon yok")
    except Exception as e:
        pf.log(f"Bybit startup sync hatasi: {e}")


def _to_combo_signal(sig):
    """Hacim / PiyasaEvresi sinyallerini tek kasaya yonlendir."""
    extra = dict(sig.extra or {})
    extra["source_ledger"] = sig.ledger
    return replace(sig, ledger=LIVE_COMBO_LEDGER, extra=extra)


def _try_entry(pf: Portfolio, strat, ctx, sym: str, last: float, sig=None) -> bool:
    if sig is None:
        try:
            sig = strat.signal(ctx)
        except Exception:
            return False
    if sig is None:
        return False
    if LIVE_LONG_ONLY and sig.side.value == "SELL":
        return False
    pf.record_signal(sym, sig)
    if not ctx.aligned(sig.side):
        return False
    combo = _to_combo_signal(sig)
    if not is_live_exchange():
        return False
    opened = pf.try_open(sym, combo, last)
    if opened and combo.entry_tf:
        key = pf.pos_key(LIVE_COMBO_LEDGER, sym)
        if key in pf.positions:
            pf.positions[key].entry_tf = combo.entry_tf
    return opened


def _scan_one(pf: Portfolio, cache: FrameCache, sym: str, dominance: dict, force_entry: bool) -> None:
    try:
        strats = _STRATS
        scan_tfs = refresh_tfs_for_scan(strats)
        frames = cache.refresh(sym, scan_tfs)
        if "1h" not in frames or "1d" not in frames:
            return

        live_px: float | None = None
        if any(s.uses_live_entry() for s in strats):
            try:
                live_px = last_prices([sym]).get(sym)
            except Exception:
                live_px = None

        mark = _mark_price(pf, sym, frames, live_px)
        if mark <= 0:
            return

        if is_live_exchange():
            closed = pf.check_exits(sym, mark)
            if closed:
                pf.save(sync_github=False)

        bar_closed = collect_bar_closes(cache, sym, strats, force=force_entry)
        if not force_entry and not any(bar_closed.values()) and not any(
            s.uses_live_entry() for s in strats
        ):
            return

        ctx = build_context(sym, frames, dominance, indicated=False, ref_frames=None)
        candidates: list[tuple[float, object, float, object]] = []
        for strat in strats:
            if not should_evaluate_entry(strat, force=force_entry, bar_closed=bar_closed):
                continue
            px = _entry_price(strat, sym, frames, live_px)
            if px <= 0:
                continue
            try:
                sig = strat.signal(ctx)
            except Exception:
                continue
            if sig is None or not ctx.aligned(sig.side):
                continue
            if LIVE_LONG_ONLY and sig.side.value == "SELL":
                continue
            strength = strat.signal_strength(ctx, sig)
            candidates.append((strength, strat, px, sig))
        if not candidates:
            return
        candidates.sort(key=lambda x: x[0], reverse=True)
        picked = None
        for strength, strat, px, sig in candidates:
            if not pf.live_strategy_has_slot(sig.ledger):
                continue
            picked = (strength, strat, px, sig)
            break
        if picked is None:
            return
        best_strength, best_strat, best_px, best_sig = picked
        if is_live_exchange():
            if _try_entry(pf, best_strat, ctx, sym, best_px, sig=best_sig):
                pf.log(
                    f"canli_giris {sym} | {best_sig.strategy} -> {LIVE_COMBO_LEDGER} | skor {best_strength:.2f}"
                )
                pf.save(sync_github=False)
        else:
            pf.record_signal(sym, _to_combo_signal(best_sig))
            pf.log(
                f"sinyal {sym} | {best_sig.strategy} | {best_sig.side.value} | skor {best_strength:.2f} | emir kapali"
            )
            pf.save(sync_github=False)
    except Exception as e:
        pf.log(f"{sym} hata: {e}")


def _shutdown_save(pf: Portfolio) -> None:
    try:
        pf.log("Canli motor kapaniyor — state kaydediliyor...")
        pf.save(sync_github=False)
    except Exception as e:
        print(f"Kapanis kayit hatasi: {e}", flush=True)


def _clear_simulated_positions(pf: Portfolio) -> None:
    """Tarama modunda (emir kapali) eski paper pozisyonlari temizle."""
    if is_live_exchange():
        return
    n = len(pf.positions)
    if not n and not pf.pending_orders:
        return
    pf.positions.clear()
    pf.pending_orders.clear()
    pf.ledgers = {k: float(LIVE_KASA_BALANCES.get(k, LIVE_KASA_USD)) for k in LIVE_LEDGERS}
    pf.log(
        f"Tarama modu — {n} simule pozisyon silindi (Bybit'te acik degil, yalnizca sinyal kaydi)"
    )
    pf.save(sync_github=False)


def run_live(scan_limit: int = SCAN_SYMBOLS) -> None:
    pf = Portfolio(live_mode=True)
    _clear_simulated_positions(pf)
    atexit.register(_shutdown_save, pf)
    try:
        signal.signal(signal.SIGTERM, lambda *_: _shutdown_save(pf))
    except Exception:
        pass
    start_http(pf)
    _sync_exchange_on_start(pf)
    pf.log(
        f"Canli motor basladi | {TRADING_MODE} | kasa={LIVE_COMBO_LEDGER} ${LIVE_KASA_USD:.0f} | "
        f"stratejiler=Hacim+PiyasaEvresi | long_only={LIVE_LONG_ONLY} | tarama ~{PRICE_POLL_SEC}sn"
    )
    cache = FrameCache()
    cursor = 0
    last_universe_refresh = 0.0
    last_heartbeat = 0.0
    symbols: list[str] = []
    dominance: dict = {}

    while True:
        loop_start = time.time()
        try:
            if time.time() - last_universe_refresh > 900 or not symbols:
                symbols = fetch_symbols(scan_limit)
                dominance = _update_dominance(pf, fetch_dominance())
                last_universe_refresh = time.time()
                pf.log(f"Piyasa listesi: {len(symbols)} sembol")

            run_price_pass(pf)

            if symbols:
                batch = max(6, min(15, len(symbols) // 30 or 6))
                end = min(cursor + batch, len(symbols))
                chunk = symbols[cursor:end]
                wrapped = end >= len(symbols)
                cursor = 0 if wrapped else end
                for sym in chunk:
                    _scan_one(pf, cache, sym, dominance, force_entry=False)
                if wrapped:
                    eq = pf.snapshot()["equity"]
                    pf.log(f"Tur tamam: {len(symbols)} coin | Aktif {len(pf.positions)} | Fon ${eq:.2f}")

            if time.time() - last_heartbeat > 60:
                eq = pf.snapshot()["equity"]
                pos = f"{cursor}/{len(symbols)}" if symbols else "0/0"
                pf.log(f"Calisiyor | tarama {pos} | Aktif {len(pf.positions)} | Fon ${eq:.2f}")
                pf.save(sync_github=False)
                last_heartbeat = time.time()
        except Exception as e:
            pf.log(f"Dongu hatasi: {e}")
        elapsed = time.time() - loop_start
        time.sleep(max(2.0, PRICE_POLL_SEC - elapsed))
