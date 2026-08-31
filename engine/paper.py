from __future__ import annotations

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from engine.config import PRICE_POLL_SEC, SCAN_SYMBOLS, TIMEFRAMES
from engine.context import build_context
from engine.data import fetch_dominance, fetch_klines, fetch_symbols, last_prices
from engine.portfolio import Portfolio
from strategies.registry import all_strategies

_STRATS = all_strategies()

# How often each TF is refreshed while rotating the universe
_TF_TTL_SEC = {"15m": 90, "1h": 180, "4h": 900, "1d": 3600, "1w": 7200}


class _Handler(BaseHTTPRequestHandler):
    portfolio: Portfolio

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        body = self.portfolio.snapshot()
        self.wfile.write(json.dumps(body, default=str).encode("utf-8"))

    def log_message(self, format, *args):
        return


def start_http(portfolio: Portfolio) -> None:
    _Handler.portfolio = portfolio
    port = int(os.environ.get("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    portfolio.log(f"HTTP state API :{port}")


def _update_dominance(pf: Portfolio, raw: dict) -> dict:
    prev = pf.signal_log.get("_dominance") or {}
    out = dict(raw)
    if prev.get("btc_d") is not None and raw.get("btc_d") is not None:
        out["btc_d_chg"] = float(raw["btc_d"]) - float(prev["btc_d"])
    if prev.get("usdt_d") is not None and raw.get("usdt_d") is not None:
        out["usdt_d_chg"] = float(raw["usdt_d"]) - float(prev["usdt_d"])
    pf.signal_log["_dominance"] = {"btc_d": raw.get("btc_d"), "usdt_d": raw.get("usdt_d")}
    return out


class FrameCache:
    def __init__(self):
        self.frames: dict[str, dict] = {}
        self.fetched_at: dict[tuple[str, str], float] = {}
        self.last_close: dict[tuple[str, str], object] = {}

    def get(self, symbol: str) -> dict:
        return self.frames.get(symbol, {})

    def refresh(self, symbol: str, tfs: tuple[str, ...] = TIMEFRAMES) -> dict:
        now = time.time()
        bag = self.frames.setdefault(symbol, {})
        for tf in tfs:
            age = now - self.fetched_at.get((symbol, tf), 0)
            if age < _TF_TTL_SEC.get(tf, 300) and tf in bag:
                continue
            try:
                df = fetch_klines(symbol, tf)
            except Exception:
                continue
            if df is None or df.empty:
                continue
            bag[tf] = df
            self.fetched_at[(symbol, tf)] = now
            time.sleep(0.03)
        self.frames[symbol] = bag
        return bag

    def new_closed_bar(self, symbol: str, tf: str = "1h") -> bool:
        bag = self.frames.get(symbol) or {}
        df = bag.get(tf)
        if df is None or df.empty or "close_time" not in df.columns:
            return False
        ts = df["close_time"].iloc[-1]
        key = (symbol, tf)
        prev = self.last_close.get(key)
        self.last_close[key] = ts
        if prev is None:
            return False
        return prev != ts


def run_scan(pf: Portfolio, symbols: list[str], dominance: dict) -> None:
    cache = FrameCache()
    pf.log(f"MTF tarama basladi ({len(symbols)} sembol)")
    for i, sym in enumerate(symbols):
        _scan_one(pf, cache, sym, dominance, force_entry=True)
        if i % 10 == 9:
            pf.save(sync_github=True)
    pf.save(sync_github=True)
    eq = pf.snapshot()["equity"]
    pf.log(f"Tarama bitti. Aktif {len(pf.positions)} | Toplam ${eq:.2f}")


def _scan_one(pf: Portfolio, cache: FrameCache, sym: str, dominance: dict, force_entry: bool) -> None:
    try:
        frames = cache.refresh(sym)
        if "1h" not in frames or "1d" not in frames:
            return
        last = float(frames["1h"]["close"].iloc[-1])
        pf.mark(sym, last)
        closed = pf.check_exits(sym, last)
        if closed:
            pf.save(sync_github=True)
        if not force_entry and not cache.new_closed_bar(sym, "1h"):
            return
        ctx = build_context(sym, frames, dominance, indicated=False)
        opened = False
        for strat in _STRATS:
            try:
                sig = strat.signal(ctx)
            except Exception:
                continue
            if sig is None:
                continue
            pf.record_signal(sym, sig)
            if pf.try_open(sym, sig, last):
                opened = True
        if opened:
            pf.save(sync_github=True)
    except Exception as e:
        pf.log(f"{sym} hata: {e}")


def run_price_pass(pf: Portfolio) -> bool:
    if not pf.positions:
        return False
    symbols = list({p.symbol for p in pf.positions.values()})
    try:
        prices = last_prices(symbols)
    except Exception as e:
        pf.log(f"Fiyat hatasi: {e}")
        return False
    changed = False
    for sym, px in prices.items():
        pf.mark(sym, px)
        if pf.check_exits(sym, px):
            changed = True
    pf.save(sync_github=changed)
    return changed


def run_paper(scan_limit: int = SCAN_SYMBOLS) -> None:
    pf = Portfolio()
    start_http(pf)
    pf.log("Canli piyasa simülasyonu: tum USDT perpetual, 28 kasa, mum kapanisi giris")
    cache = FrameCache()
    cursor = 0
    last_universe_refresh = 0.0
    last_github_heartbeat = 0.0
    symbols: list[str] = []
    dominance: dict = {}

    while True:
        loop_start = time.time()
        try:
            if time.time() - last_universe_refresh > 900 or not symbols:
                symbols = fetch_symbols(scan_limit)
                dominance = _update_dominance(pf, fetch_dominance())
                last_universe_refresh = time.time()
                pf.log(f"Piyasa listesi: {len(symbols)} sembol (tum USDT perpetual)")

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

            if time.time() - last_github_heartbeat > 120:
                eq = pf.snapshot()["equity"]
                pos = f"{cursor}/{len(symbols)}" if symbols else "0/0"
                pf.log(f"Calisiyor | tarama {pos} | Aktif {len(pf.positions)} | Fon ${eq:.2f}")
                pf.save(sync_github=True)
                last_github_heartbeat = time.time()
        except Exception as e:
            pf.log(f"Dongu hatasi: {e}")
        elapsed = time.time() - loop_start
        time.sleep(max(2.0, PRICE_POLL_SEC - elapsed))
