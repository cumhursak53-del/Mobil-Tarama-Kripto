import json
import math
import os
import time
import threading
import base64
from http.server import HTTPServer, BaseHTTPRequestHandler
from curl_cffi import requests as curl_requests

STATE_FILE = "durum.json"
MAX_POSITIONS = 10
LEVERAGE = 10
DEFAULT_BALANCE = 100.0

TRAILING_ACTIVATION_ROE = 10.0
TRAILING_CALLBACK_PCT = 1.2

# --- GITHUB OTOMATİK KALICILIK AYARLARI ---
GITHUB_REPO = "cumhursak53-del/Mobil-Tarama-Krypto"
GITHUB_FILE_PATH = "durum.json"
# Buraya GitHub'dan aldığınız ghp_ ile başlayan Token'ı yazın:
GITHUB_TOKEN = "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"

EXCLUDED_SYMBOLS = [
    "USDCUSDT", "FDUSDUSDT", "USDPUSDT", "BTCDOMUSDT",
    "DEFIUSDT", "UBERUSDT", "STXXUSDT", "BIRBUSDT"
]

ENGINE_LOGS = []

def add_log(msg: str):
    timestamp = time.strftime("%H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    print(formatted, flush=True)
    ENGINE_LOGS.append(formatted)
    if len(ENGINE_LOGS) > 100:
        ENGINE_LOGS.pop(0)

def push_state_to_github(data_dict):
    """durum.json içeriğini doğrudan GitHub deponuza commit eder (Kalıcılık Sağlar)."""
    if GITHUB_TOKEN == "YOUR_GITHUB_PERSONAL_ACCESS_TOKEN":
        return

    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    try:
        # Mevcut dosya sha değerini al
        res = curl_requests.get(url, headers=headers, timeout=8)
        sha = res.json().get("sha", "") if res.status_code == 200 else ""

        content_str = json.dumps(data_dict, indent=4)
        content_b64 = base64.b64encode(content_str.encode('utf-8')).decode('utf-8')

        payload = {
            "message": "Auto update state [Bot Engine]",
            "content": content_b64,
            "branch": "ana"
        }
        if sha:
            payload["sha"] = sha

        curl_requests.put(url, headers=headers, json=payload, timeout=10)
    except Exception as e:
        add_log(f"[HATA] GitHub Kayıt Hatası: {e}")

# --- RENDER CANLI API SUNUCUSU ---
class APIHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        
        state_data = {"balance": DEFAULT_BALANCE, "active_positions": {}, "history": [], "signal_log": {}}
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    state_data = json.load(f)
            except Exception:
                pass

        state_data["engine_logs"] = ENGINE_LOGS
        self.wfile.write(json.dumps(state_data).encode('utf-8'))

    def log_message(self, format, *args):
        return

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), APIHandler)
    add_log(f"🌐 Render API Canlı Sunucusu {port} Portunda Baslatildi.")
    server.serve_forever()

threading.Thread(target=run_dummy_server, daemon=True).start()

# --- FUTURES BOT ENGINE ---
class HeadlessFuturesEngine:
    def __init__(self):
        self.state = self.load_state()
        self.live_prices = {}
        self.cooldown_tracker = {}

    def load_state(self):
        # 1. Önce GitHub'daki en güncel durum.json dosyasını çekmeyi dene
        if GITHUB_TOKEN != "YOUR_GITHUB_PERSONAL_ACCESS_TOKEN":
            url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/ana/{GITHUB_FILE_PATH}"
            try:
                res = curl_requests.get(url, timeout=8)
                if res.status_code == 200:
                    data = res.json()
                    if "signal_log" not in data: data["signal_log"] = {}
                    add_log("📥 Güncel Kasa ve Pozisyonlar GitHub Deposundan Yüklendi.")
                    return data
            except Exception:
                pass

        # 2. Yerel dosyadan yükle
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    data = json.load(f)
                    if "signal_log" not in data: data["signal_log"] = {}
                    return data
            except Exception:
                pass
        return {"balance": DEFAULT_BALANCE, "active_positions": {}, "history": [], "signal_log": {}}

    def save_state(self):
        # 1. Yerel dosyaya kaydet
        with open(STATE_FILE, "w") as f:
            json.dump(self.state, f, indent=4)

        # 2. GitHub deponuza kaydet (Bulutta kalıcılık sağlar)
        threading.Thread(target=push_state_to_github, args=(self.state,), daemon=True).start()

    def get_total_equity(self):
        allocated_margin = sum(pos["margin"] for pos in self.state["active_positions"].values())
        return self.state["balance"] + allocated_margin

    def get_binance_futures_symbols(self) -> list:
        url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
        try:
            res = curl_requests.get(url, impersonate="chrome120", timeout=8)
            if res.status_code == 200:
                data = res.json()
                return [
                    s["symbol"] for s in data["symbols"]
                    if s.get("quoteAsset") == "USDT"
                    and s.get("contractType") == "PERPETUAL"
                    and s.get("status") == "TRADING"
                    and s["symbol"] not in EXCLUDED_SYMBOLS
                ]
            return []
        except Exception:
            return []

    def fetch_tv_15m_technical_data(self, valid_symbols: list) -> dict:
        url = "https://scanner.tradingview.com/crypto/scan"
        payload = {
            "filter": [
                {"left": "exchange", "operation": "equal", "right": "BINANCE"},
                {"left": "name", "operation": "match", "right": "USDT.P$"}
            ],
            "options": {"active_symbols_only": True},
            "columns": [
                "name", "close|15", "RSI|15", "BB.upper|15", "BB.lower|15",
                "SMA20|15", "High.20|15", "Low.20|15", "funding_rate|15",
                "EMA9|15", "EMA21|15", "SMA50|15", "volume|15", "volume|15[1]"
            ],
            "sort": {"sortBy": "volume|15", "sortOrder": "desc"},
            "range": [0, 600]
        }
        try:
            res = curl_requests.post(url, json=payload, impersonate="chrome120", timeout=15)
            result_map = {}
            if res.status_code == 200:
                results = res.json().get("data", [])
                for item in results:
                    d = item.get("d", [])
                    if len(d) >= 14:
                        symbol = d[0].replace(".P", "")
                        if valid_symbols and symbol not in valid_symbols: continue
                        close = d[1] or 0.0
                        rsi = d[2] or 50.0
                        bb_upper = d[3] or close
                        bb_lower = d[4] or close
                        sma20 = d[5] or close
                        high20 = d[6] or close
                        low20 = d[7] or close
                        funding_rate = (d[8] or 0.0) * 100
                        ema9 = d[9] or close
                        ema21 = d[10] or close
                        sma50 = d[11] or close
                        vol_curr = d[12] or 1.0
                        vol_prev = d[13] or 1.0
                        vol_ratio = vol_curr / vol_prev if vol_prev > 0 else 1.0
                        result_map[symbol] = {
                            "symbol": symbol, "close": close, "rsi": rsi,
                            "bb_upper": bb_upper, "bb_lower": bb_lower, "sma20": sma20,
                            "high20": high20, "low20": low20, "funding_rate": funding_rate,
                            "ema9": ema9, "ema21": ema21, "sma50": sma50, "vol_ratio": vol_ratio
                        }
                return result_map
            return {}
        except Exception as e:
            add_log(f"[HATA] TV Veri Hatasi: {e}")
            return {}

    def run_cycle(self):
        add_log("🔍 15m Piyasa Taraması Başlatıldı...")
        binance_symbols = self.get_binance_futures_symbols()
        tv_data_map = self.fetch_tv_15m_technical_data(binance_symbols)
        if not tv_data_map: return

        for sym, coin in tv_data_map.items():
            self.live_prices[sym] = coin["close"]

        for sym in list(self.cooldown_tracker.keys()):
            self.cooldown_tracker[sym] -= 1
            if self.cooldown_tracker[sym] <= 0: del self.cooldown_tracker[sym]

        # Pozisyon Kapanış & Trailing Stop & Canlı Fiyat Güncelleme
        active_syms = list(self.state["active_positions"].keys())
        for symbol in active_syms:
            pos = self.state["active_positions"].get(symbol)
            if not pos: continue
            current_price = self.live_prices.get(symbol, pos["entry_price"])
            pos["current_price"] = current_price
            
            entry, side, margin = pos["entry_price"], pos["side"], pos["margin"]
            ratio = (current_price - entry) / entry if side == "BUY" else (entry - current_price) / entry
            current_roe = ratio * LEVERAGE * 100

            should_close, close_reason = False, ""
            peak_price = pos.get("peak_price", entry)
            is_trailing = pos.get("trailing_active", False)

            if side == "BUY":
                if current_price > peak_price:
                    pos["peak_price"] = current_price
                    peak_price = current_price
                if not is_trailing and current_roe >= TRAILING_ACTIVATION_ROE:
                    pos["trailing_active"] = True; is_trailing = True
                    add_log(f"🔥 [TRAILING STOPE GİRDİ] {symbol} | ROE: %{current_roe:.1f}")
                if is_trailing:
                    if current_price <= peak_price * (1 - (TRAILING_CALLBACK_PCT / 100)):
                        should_close, close_reason = True, f"🏹 Trailing Stop (%{current_roe:.1f})"
                else:
                    if current_price <= pos["sl_price"]: should_close, close_reason = True, "🛑 Stop Loss"

            elif side == "SELL":
                if peak_price == entry or current_price < peak_price:
                    pos["peak_price"] = current_price
                    peak_price = current_price
                if not is_trailing and current_roe >= TRAILING_ACTIVATION_ROE:
                    pos["trailing_active"] = True; is_trailing = True
                    add_log(f"🔥 [TRAILING STOPE GİRDİ] {symbol} | ROE: %{current_roe:.1f}")
                if is_trailing:
                    if current_price >= peak_price * (1 + (TRAILING_CALLBACK_PCT / 100)):
                        should_close, close_reason = True, f"🏹 Trailing Stop (%{current_roe:.1f})"
                else:
                    if current_price >= pos["sl_price"]: should_close, close_reason = True, "🛑 Stop Loss"

            if should_close:
                pnl = margin * LEVERAGE * ratio
                self.state["balance"] += max(margin + pnl, 0)
                self.state["history"].append({
                    "symbol": symbol, "side": side, "entry_score": pos.get("entry_score", 0),
                    "strategies": pos.get("strategies", "-"), "entry": entry, "exit": current_price,
                    "pnl": pnl, "close_reason": close_reason, "new_balance": self.get_total_equity(),
                    "entry_time": pos.get("entry_time", "-"), "exit_time": time.strftime("%Y-%m-%d %H:%M:%S")
                })
                del self.state["active_positions"][symbol]
                self.cooldown_tracker[symbol] = 6
                add_log(f"🎯 [KAPANDI] {symbol} | PnL: ${pnl:+.2f} | Neden: {close_reason}")

        self.save_state()

        # Skorlama & Aday Havuzu Engine
        candidate_pool = []
        for symbol, coin in tv_data_map.items():
            close, rsi, bb_upper, bb_lower = coin["close"], coin["rsi"], coin["bb_upper"], coin["bb_lower"]
            sma20, high20, low20, funding_rate = coin["sma20"], coin["high20"], coin["low20"], coin["funding_rate"]
            ema9, ema21, sma50, vol_ratio = coin["ema9"], coin["ema21"], coin["sma50"], coin["vol_ratio"]

            if close == 0 or sma20 == 0: continue
            bb_width = (bb_upper - bb_lower) / sma20
            atr_est = abs(bb_upper - bb_lower) / 2
            score, trig_strategies = 0, []

            if close >= high20 and rsi > 62 and vol_ratio > 2.2: score += 40; trig_strategies.append("Parabolik Breakout (LONG)")
            if bb_width < 0.020 and close > bb_upper and vol_ratio > 1.8: score += 35; trig_strategies.append("Bollinger Squeeze (LONG)")
            if ema9 > ema21 and close > sma50 and vol_ratio > 1.5 and rsi > 58: score += 30; trig_strategies.append("EMA Golden Cross (LONG)")

            if close <= low20 and rsi < 38 and vol_ratio > 2.2: score -= 40; trig_strategies.append("Parabolik Breakdown (SHORT)")
            if bb_width < 0.020 and close < bb_lower and vol_ratio > 1.8: score -= 35; trig_strategies.append("Bollinger Squeeze (SHORT)")
            if ema9 < ema21 and close < sma50 and vol_ratio > 1.5 and rsi < 42: score -= 30; trig_strategies.append("EMA Death Cross (SHORT)")

            if funding_rate <= -0.03: score += 20
            elif funding_rate >= 0.03: score -= 20

            if rsi >= 75:
                if vol_ratio > 1.8 and close >= high20: score += 20; trig_strategies.append("Güçlü RSI Momentum (LONG)")
                else: score -= 25; trig_strategies.append("Aşırı Alım Düzeltme (SHORT)")
            elif rsi <= 25:
                if vol_ratio > 1.8 and close <= low20: score -= 20; trig_strategies.append("Güçlü Düşüş Momentum (SHORT)")
                else: score += 25; trig_strategies.append("Aşırı Satım Tepkisi (LONG)")

            if score >= 0:
                base_tp = max(bb_upper, high20)
                est_tp_price = close + max(atr_est, close * 0.015) if base_tp <= close else base_tp
                roe_pct = min(max(((est_tp_price - close) / close) * 100 * LEVERAGE, 8.0), 35.0)
                est_tp_price = close * (1 + (roe_pct / (100 * LEVERAGE)))
                est_sl_price = min(bb_lower, close * 0.985)
            else:
                base_tp = min(bb_lower, low20)
                est_tp_price = close - max(atr_est, close * 0.015) if base_tp >= close else base_tp
                roe_pct = min(max(((close - est_tp_price) / close) * 100 * LEVERAGE, 8.0), 35.0)
                est_tp_price = close * (1 - (roe_pct / (100 * LEVERAGE)))
                est_sl_price = max(bb_upper, close * 1.015)

            strat_str = ", ".join(trig_strategies) if trig_strategies else "Teknik Sinyal"
            is_valid_long = (score >= 85 and roe_pct >= 8.0)
            is_valid_short = (score <= -85 and roe_pct >= 8.0)

            if is_valid_long or is_valid_short:
                now_str = time.strftime("%Y-%m-%d %H:%M:%S")
                if symbol not in self.state["signal_log"]:
                    self.state["signal_log"][symbol] = {"count": 0, "last_time": "", "last_side": "", "last_score": 0, "last_roe": 0.0, "strategies": ""}
                self.state["signal_log"][symbol]["count"] += 1
                self.state["signal_log"][symbol]["last_time"] = now_str
                self.state["signal_log"][symbol]["last_side"] = "LONG" if is_valid_long else "SHORT"
                self.state["signal_log"][symbol]["last_score"] = score
                self.state["signal_log"][symbol]["last_roe"] = roe_pct
                self.state["signal_log"][symbol]["strategies"] = strat_str

                if symbol not in self.state["active_positions"] and symbol not in self.cooldown_tracker:
                    candidate_pool.append({
                        "symbol": symbol, "score": score, "close": close, "roe_pct": roe_pct,
                        "tp_price": est_tp_price, "sl_price": est_sl_price, "strategies": strat_str
                    })

        # Öncelikli Pozisyon Açılışı
        available_slots = MAX_POSITIONS - len(self.state["active_positions"])
        if candidate_pool and available_slots > 0:
            candidate_pool.sort(key=lambda x: (abs(x["score"]), x["roe_pct"]), reverse=True)
            for cand in candidate_pool[:available_slots]:
                sym, close, score = cand["symbol"], cand["close"], cand["score"]
                roe_pct, est_tp_price, est_sl_price = cand["roe_pct"], cand["tp_price"], cand["sl_price"]
                strat_str, now_str = cand["strategies"], time.strftime("%Y-%m-%d %H:%M:%S")
                margin_per_trade = self.get_total_equity() / MAX_POSITIONS
                side = "BUY" if score >= 85 else "SELL"

                self.state["balance"] -= margin_per_trade
                self.state["active_positions"][sym] = {
                    "side": side, "entry_price": close, "current_price": close, "tp_price": est_tp_price, "sl_price": est_sl_price,
                    "margin": margin_per_trade, "amount": (margin_per_trade * LEVERAGE) / close,
                    "entry_score": score, "strategies": strat_str, "entry_time": now_str, "target_roe": roe_pct,
                    "peak_price": close, "trailing_active": False
                }
                self.live_prices[sym] = close
                add_log(f"🚀 [ISLEM ACILDI] {sym} | Skor: {score} | Yön: {side}")

            self.save_state()
        
        add_log(f"✅ Tarama Bitti. Aktif Pozisyon: {len(self.state['active_positions'])} | Kasa: ${self.get_total_equity():.2f}")

if __name__ == "__main__":
    engine = HeadlessFuturesEngine()
    add_log("🤖 Futures Bot Engine 7/24 Kesintisiz Modda Baslatildi...")
    while True:
        try:
            engine.run_cycle()
        except Exception as e:
            add_log(f"Döngü Hatasi: {e}")
        time.sleep(10)
