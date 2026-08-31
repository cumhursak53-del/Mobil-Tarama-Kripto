import json
import os
import time
import threading
import base64
from http.server import HTTPServer, BaseHTTPRequestHandler
from curl_cffi import requests as curl_requests

STATE_FILE = "state.json"
MAX_POSITIONS_PER_LEDGER = 2
LEVERAGE = 10

GITHUB_REPO = "cumhursak53-del/Mobil-Tarama-Krypto"
GITHUB_FILE_PATH = "state.json"
GITHUB_BRANCH = "main"
GITHUB_TOKEN = "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"

EXCLUDED_SYMBOLS = ["USDCUSDT", "FDUSDUSDT", "USDPUSDT", "BTCDOMUSDT", "DEFIUSDT", "UBERUSDT"]
ENGINE_LOGS = []
DEFAULT_LEDGERS = ["Kasa_1_Momentum", "Kasa_2_SMC_PA", "Kasa_3_MTF_Swing", "Kasa_4_MTF_Scalp", "Kasa_5_Squeeze", "Kasa_6_VWAP", "Kasa_7_GoreceliGuc", "Kasa_8_Oturum"]

def add_log(msg: str):
    timestamp = time.strftime("%H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    print(formatted, flush=True)
    ENGINE_LOGS.append(formatted)
    if len(ENGINE_LOGS) > 100: ENGINE_LOGS.pop(0)

def push_state_to_github(data_dict):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json", "User-Agent": "FuturesBot-Engine"}
    try:
        res = curl_requests.get(url + f"?ref={GITHUB_BRANCH}", headers=headers, timeout=8)
        sha = res.json().get("sha", "") if res.status_code == 200 else ""
        content_b64 = base64.b64encode(json.dumps(data_dict, indent=4).encode('utf-8')).decode('utf-8')
        payload = {"message": "Auto update state [Bot Engine]", "content": content_b64, "branch": GITHUB_BRANCH}
        if sha: payload["sha"] = sha
        curl_requests.put(url, headers=headers, json=payload, timeout=10)
    except Exception as e:
        add_log(f"GitHub Sync Hatası: {e}")

class APIHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        state_data = {}
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f: state_data = json.load(f)
            except: pass
        state_data["engine_logs"] = ENGINE_LOGS
        self.wfile.write(json.dumps(state_data).encode('utf-8'))
    def log_message(self, format, *args): return

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), APIHandler)
    server.serve_forever()

threading.Thread(target=run_dummy_server, daemon=True).start()

class HeadlessFuturesEngine:
    def __init__(self):
        self.state = self.load_state()
        self.live_prices = {}
        self.cooldown_tracker = {}

    def load_state(self):
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}?ref={GITHUB_BRANCH}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json", "User-Agent": "FuturesBot"}
        try:
            res = curl_requests.get(url, headers=headers, timeout=8)
            if res.status_code == 200:
                content_b64 = res.json().get("content", "")
                if content_b64: return json.loads(base64.b64decode(content_b64).decode('utf-8'))
        except: pass
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f: return json.load(f)
            except: pass
        return {"ledgers": {k: 100.0 for k in DEFAULT_LEDGERS}, "active_positions": {}, "history": [], "signal_log": {}, "signal_date": ""}

    def save_state(self, sync_github=True):
        with open(STATE_FILE, "w") as f: json.dump(self.state, f, indent=4)
        if sync_github: push_state_to_github(self.state)

    def fetch_tv_multi_timeframe(self) -> dict:
        url = "https://scanner.tradingview.com/crypto/scan"
        payload = {
            "filter": [{"left": "exchange", "operation": "equal", "right": "BINANCE"}, {"left": "name", "operation": "match", "right": "USDT.P$"}],
            "options": {"active_symbols_only": True},
            "columns": ["name", "close|15", "RSI|15", "BB.upper|15", "BB.lower|15", "SMA20|15", "funding_rate|15", "volume|15", "volume|15[1]", "VWAP|15", "ADX|15", "ATR|15", "close|60", "SMA50|60", "close|240", "SMA50|240", "high|15", "low|15", "open|15", "high|15[1]", "RSI|15[1]"],
            "sort": {"sortBy": "volume|15", "sortOrder": "desc"},
            "range": [0, 500]
        }
        try:
            res = curl_requests.post(url, json=payload, impersonate="chrome120", timeout=15)
            result_map = {}
            if res.status_code == 200:
                for item in res.json().get("data", []):
                    d = item.get("d", [])
                    if len(d) >= 21:
                        sym = d[0].replace(".P", "")
                        if sym in EXCLUDED_SYMBOLS: continue
                        result_map[sym] = {
                            "close": d[1] or 0.0, "rsi": d[2] or 50.0, "bb_upper": d[3] or 0.0, "bb_lower": d[4] or 0.0,
                            "sma20": d[5] or 0.0, "funding": (d[6] or 0.0) * 100, "vol_curr": d[7] or 1.0, "vol_prev": d[8] or 1.0,
                            "vwap": d[9] or 0.0, "adx": d[10] or 0.0, "atr": d[11] or 0.0, "close60": d[12] or 0.0,
                            "sma50_60": d[13] or 0.0, "close240": d[14] or 0.0, "sma50_240": d[15] or 0.0, 
                            "high15": d[16] or 0.0, "low15": d[17] or 0.0, "open15": d[18] or 0.0, "prev_high15": d[19] or 0.0,
                            "prev_rsi15": d[20] or 50.0
                        }
                return result_map
            return {}
        except: return {}

    def run_cycle(self):
        add_log("🔍 MTF Piyasa Taraması Başlatıldı...")
        today_str = time.strftime("%Y-%m-%d")
        if self.state.get("signal_date") != today_str:
            self.state["signal_log"] = {}
            self.state["signal_date"] = today_str
            add_log("📅 Yeni Gün: Sinyal Geçmişi Sıfırlandı.")

        if "ledgers" not in self.state: self.state["ledgers"] = {}
        for k in DEFAULT_LEDGERS:
            if k not in self.state["ledgers"]: self.state["ledgers"][k] = 100.0

        tv_data = self.fetch_tv_multi_timeframe()
        if not tv_data: return

        for sym, c in tv_data.items(): self.live_prices[sym] = c["close"]
        for sym in list(self.cooldown_tracker.keys()):
            self.cooldown_tracker[sym] -= 1
            if self.cooldown_tracker[sym] <= 0: del self.cooldown_tracker[sym]

        state_changed = False
        
        for symbol in list(self.state.get("active_positions", {}).keys()):
            pos = self.state["active_positions"][symbol]
            curr_price = self.live_prices.get(symbol, pos["entry_price"])
            pos["current_price"] = curr_price
            
            pos["max_reached_price"] = max(pos.get("max_reached_price", curr_price), curr_price)
            pos["min_reached_price"] = min(pos.get("min_reached_price", curr_price), curr_price)

            entry, side, margin = pos["entry_price"], pos["side"], pos["margin"]
            ratio = (curr_price - entry) / entry if side == "BUY" else (entry - curr_price) / entry
            curr_roe = ratio * LEVERAGE * 100

            should_close, close_reason = False, ""
            peak = pos.get("peak_price", entry)
            is_trailing = pos.get("trailing_active", False)
            partial_tp_taken = pos.get("partial_tp_taken", False)
            ledger_name = pos.get("ledger_name", "Kasa_1_Momentum")

            if not partial_tp_taken and curr_roe >= 50.0:
                tp_margin = margin * 0.5
                tp_pnl = tp_margin * LEVERAGE * ratio
                net_tp_pnl = tp_pnl - (tp_margin * LEVERAGE * 0.001)
                
                pos["margin"] = margin - tp_margin
                self.state["ledgers"][ledger_name] += (tp_margin + max(net_tp_pnl, 0))
                pos["partial_tp_taken"] = True
                margin = pos["margin"] 
                state_changed = True
                add_log(f"💸 [KISMİ KÂR] {symbol} | %50 Kilitlendi | Net PnL: ${net_tp_pnl:+.2f}")

            pos_atr = pos.get("atr", curr_price * 0.01)
            dynamic_callback_pct = (pos_atr / curr_price) * 100 * 1.5
            dynamic_callback_pct = max(0.8, min(dynamic_callback_pct, 4.0))

            if side == "BUY":
                if curr_price > peak: pos["peak_price"] = curr_price; peak = curr_price
                
                if not is_trailing and curr_roe >= 20.0:
                    pos["trailing_active"] = True; is_trailing = True
                    locked_price = entry * (1 + (10.0 / (100 * LEVERAGE)))
                    pos["sl_price"] = max(pos["sl_price"], locked_price)
                    add_log(f"🛡️ [KÂR KİLİDİ] {symbol} | Stop seviyesi +%10 ROE'ye çekildi.")
                    
                if is_trailing and curr_price <= peak * (1 - (dynamic_callback_pct / 100)):
                    should_close, close_reason = True, f"🏹 Dinamik Trailing (%{curr_roe:.1f})"
                elif curr_price <= pos["sl_price"]: 
                    should_close, close_reason = True, "🛑 Stop Loss / Kâr Kilidi"
            else:
                if peak == entry or curr_price < peak: pos["peak_price"] = curr_price; peak = curr_price
                
                if not is_trailing and curr_roe >= 20.0:
                    pos["trailing_active"] = True; is_trailing = True
                    locked_price = entry * (1 - (10.0 / (100 * LEVERAGE)))
                    pos["sl_price"] = min(pos["sl_price"], locked_price)
                    add_log(f"🛡️ [KÂR KİLİDİ] {symbol} | Stop seviyesi +%10 ROE'ye çekildi.")
                    
                if is_trailing and curr_price >= peak * (1 + (dynamic_callback_pct / 100)):
                    should_close, close_reason = True, f"🏹 Dinamik Trailing (%{curr_roe:.1f})"
                elif curr_price >= pos["sl_price"]: 
                    should_close, close_reason = True, "🛑 Stop Loss / Kâr Kilidi"

            if should_close:
                pnl = margin * LEVERAGE * ratio
                net_pnl = pnl - (margin * LEVERAGE * 0.001)
                self.state["ledgers"][ledger_name] += max(margin + net_pnl, 0)
                
                self.state["history"].append({
                    "symbol": symbol, "side": side, "strategy": pos.get("strategy", "-"),
                    "entry": entry, "exit": curr_price, "pnl": net_pnl, "close_reason": close_reason,
                    "mfe_price": pos["max_reached_price"], "mae_price": pos["min_reached_price"],
                    "ledger": ledger_name, "exit_time": time.strftime("%Y-%m-%d %H:%M:%S")
                })
                del self.state["active_positions"][symbol]
                
                # Cooldown Uzatımı (Düşen bıçak korunması için 90 döngü / 15 dk)
                self.cooldown_tracker[symbol] = 90
                
                state_changed = True
                add_log(f"🎯 [KAPANDI] {symbol} | Kasa: {ledger_name} | Net PnL: ${net_pnl:+.2f}")

        candidate_pool = []
        ledger_counts = {k: 0 for k in DEFAULT_LEDGERS}
        for pos in self.state.get("active_positions", {}).values():
            ln = pos.get("ledger_name")
            if ln in ledger_counts: ledger_counts[ln] += 1

        for sym, c in tv_data.items():
            if c["close"] == 0 or c["sma20"] == 0: continue
            
            vol_ratio = c["vol_curr"] / c["vol_prev"] if c["vol_prev"] > 0 else 1.0
            bb_width = (c["bb_upper"] - c["bb_lower"]) / c["sma20"]
            
            total_len = c["high15"] - c["low15"]
            body_len = abs(c["close"] - c["open15"])
            is_solid_body = (body_len >= (total_len * 0.60)) if total_len > 0 else False
            
            if bb_width < 0.02 and c["close"] > c["bb_upper"] and vol_ratio > 2.0:
                candidate_pool.append({"sym": sym, "side": "BUY", "ledger": "Kasa_1_Momentum", "strat": "[STRAT: Squeeze_Breakout]", "c": c})
                
            if c["low15"] < (c["close"] * 0.99) and c["close"] > c["vwap"] and c["rsi"] < 40 and c["close"] > c["prev_high15"]:
                candidate_pool.append({"sym": sym, "side": "BUY", "ledger": "Kasa_2_SMC_PA", "strat": "[STRAT: Liquidity_Sweep_Long]", "c": c})
                
            if c["close240"] > c["sma50_240"] and c["close60"] > c["sma50_60"] and c["close"] > c["sma20"] and c["adx"] > 25:
                candidate_pool.append({"sym": sym, "side": "BUY", "ledger": "Kasa_3_MTF_Swing", "strat": "[STRAT: MTF_Macro_Trend]", "c": c})
                
            if c["close240"] > c["sma50_240"] and c["close"] < c["sma20"] and c["rsi"] > 70:
                candidate_pool.append({"sym": sym, "side": "SELL", "ledger": "Kasa_4_MTF_Scalp", "strat": "[STRAT: Pullback_Scalp_Short]", "c": c})
                
            if c["funding"] <= -0.05 and vol_ratio > 1.5 and c["close"] > c["vwap"]:
                candidate_pool.append({"sym": sym, "side": "BUY", "ledger": "Kasa_5_Squeeze", "strat": "[STRAT: Short_Squeeze_Hunter]", "c": c})
                
            # KASA 6 VWAP - "ÖLÜ KEDİ SIÇRAMASI" VE DÜŞEN BIÇAK KORUMASI 
            if (c["close"] < c["vwap"] * 0.97 and 
                c["prev_rsi15"] < 30 and c["rsi"] >= 30 and 
                c["close"] > c["prev_high15"] and 
                c["close"] > c["open15"] and 
                c["close60"] > c["sma50_60"] and 
                is_solid_body):
                candidate_pool.append({"sym": sym, "side": "BUY", "ledger": "Kasa_6_VWAP", "strat": "[STRAT: VWAP_Mean_Reversion]", "c": c})
                
            if c["adx"] > 35 and vol_ratio > 2.5 and c["rsi"] > 60:
                candidate_pool.append({"sym": sym, "side": "BUY", "ledger": "Kasa_7_GoreceliGuc", "strat": "[STRAT: Strong_Divergence]", "c": c})
                
            if c["atr"] < (c["close"] * 0.005) and vol_ratio > 3.0 and is_solid_body:
                side = "BUY" if c["close"] > c["sma20"] else "SELL"
                candidate_pool.append({"sym": sym, "side": side, "ledger": "Kasa_8_Oturum", "strat": "[STRAT: Session_Volatility_Breakout]", "c": c})

        for cand in candidate_pool:
            sym = cand["sym"]
            if sym not in self.state["signal_log"]:
                self.state["signal_log"][sym] = {"count": 0, "strategies": []}
            self.state["signal_log"][sym]["count"] += 1
            if cand["strat"] not in self.state["signal_log"][sym]["strategies"]:
                self.state["signal_log"][sym]["strategies"].append(cand["strat"])
            state_changed = True

        for cand in candidate_pool:
            sym, ledger, side, strat, c = cand["sym"], cand["ledger"], cand["side"], cand["strat"], cand["c"]
            if sym in self.state.get("active_positions", {}) or sym in self.cooldown_tracker: continue
            if ledger_counts.get(ledger, 0) >= MAX_POSITIONS_PER_LEDGER: continue
            
            ledger_balance = self.state["ledgers"].get(ledger, 0)
            if ledger_balance < 10: continue

            margin_per_trade = ledger_balance / MAX_POSITIONS_PER_LEDGER
            atr = c["atr"] if c["atr"] > 0 else c["close"] * 0.01
            sl_price = c["close"] - (atr * 1.5) if side == "BUY" else c["close"] + (atr * 1.5)
            
            self.state["ledgers"][ledger] -= margin_per_trade
            self.state["active_positions"][sym] = {
                "side": side, "entry_price": c["close"], "current_price": c["close"], "sl_price": sl_price,
                "max_reached_price": c["close"], "min_reached_price": c["close"],
                "margin": margin_per_trade, "strategy": strat, "ledger_name": ledger, "atr": atr,
                "entry_time": time.strftime("%Y-%m-%d %H:%M:%S"), "peak_price": c["close"], 
                "trailing_active": False, "partial_tp_taken": False
            }
            ledger_counts[ledger] += 1
            self.live_prices[sym] = c["close"]
            state_changed = True
            add_log(f"🚀 [YENİ İŞLEM] {sym} | {strat} | Kasa: {ledger}")

        self.save_state(sync_github=state_changed)
        total_funds = sum(self.state["ledgers"].values()) + sum(p["margin"] for p in self.state.get("active_positions", {}).values())
        add_log(f"✅ Tarama Bitti. Aktif: {len(self.state.get('active_positions', {}))} | Toplam Fon: ${total_funds:.2f}")

if __name__ == "__main__":
    engine = HeadlessFuturesEngine()
    add_log("🤖 Kurumsal MTF Engine 8 Kasalı Modda Başlatıldı...")
    while True:
        try: engine.run_cycle()
        except Exception as e: add_log(f"Döngü Hatası: {e}")
        time.sleep(10)
