import json
import os
import time
import threading
import base64
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from curl_cffi import requests as curl_requests

STATE_FILE = "state.json"
MAX_POSITIONS_DEFAULT = 2
MAX_POSITIONS_KASA_10 = 10
LEVERAGE = 10

GITHUB_REPO = "cumhursak53-del/Mobil-Tarama-Krypto"
GITHUB_FILE_PATH = "state.json"
GITHUB_BRANCH = "main"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

EXCLUDED_SYMBOLS = ["USDCUSDT", "FDUSDUSDT", "USDPUSDT", "BTCDOMUSDT", "DEFIUSDT", "UBERUSDT"]
ENGINE_LOGS = []
DEFAULT_LEDGERS = [
    "Kasa_1_Momentum", "Kasa_2_SMC_PA", "Kasa_3_MTF_Swing", "Kasa_4_MTF_Scalp", 
    "Kasa_5_Squeeze", "Kasa_6_VWAP", "Kasa_7_GoreceliGuc", "Kasa_8_Oturum", 
    "Kasa_9_PriceAction", "Kasa_10_BorsaEditoru"
]

# Türkiye Saati (UTC+3) Ayarı
TR_TZ = timezone(timedelta(hours=3))

def get_tr_time(fmt="%Y-%m-%d %H:%M:%S"):
    return datetime.now(TR_TZ).strftime(fmt)

def add_log(msg: str):
    timestamp = get_tr_time("%H:%M:%S")
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
        
        # Kasa 10 Başlangıç Bütçesi 1000$, diğerleri 100$
        initial_ledgers = {k: 100.0 for k in DEFAULT_LEDGERS}
        initial_ledgers["Kasa_10_BorsaEditoru"] = 1000.0
        return {"ledgers": initial_ledgers, "active_positions": {}, "history": [], "signal_log": {}, "signal_date": ""}

    def save_state(self, sync_github=True):
        with open(STATE_FILE, "w") as f: json.dump(self.state, f, indent=4)
        if sync_github: push_state_to_github(self.state)

    def fetch_tv_multi_timeframe(self) -> dict:
        url = "https://scanner.tradingview.com/crypto/scan"
        payload = {
            "filter": [{"left": "exchange", "operation": "equal", "right": "BINANCE"}, {"left": "name", "operation": "match", "right": "USDT.P$"}],
            "options": {"active_symbols_only": True},
            "columns": [
                "name", "close|15", "RSI|15", "BB.upper|15", "BB.lower|15", "SMA20|15", "funding_rate|15", 
                "volume|15", "volume|15[1]", "VWAP|15", "ADX|15", "ATR|15", "close|60", "SMA50|60", 
                "close|240", "SMA50|240", "high|15", "low|15", "open|15", "high|15[1]", "RSI|15[1]", 
                "low|15[1]", "close|15[1]", "open|15[1]", "SMA200|60", "MACD.macd|15", "MACD.signal|15",
                "Stoch.K|15", "Stoch.D|15", "Ichimoku.CLine|15", "Ichimoku.BLine|15", "Ichimoku.Lead1|15", "Ichimoku.Lead2|15",
                "EMA50|15", "EMA200|15", "low|15[2]", "high|15[2]"
            ],
            "sort": {"sortBy": "volume|15", "sortOrder": "desc"},
            "range": [0, 500]
        }
        try:
            res = curl_requests.post(url, json=payload, impersonate="chrome120", timeout=15)
            result_map = {}
            if res.status_code == 200:
                for item in res.json().get("data", []):
                    d = item.get("d", [])
                    if len(d) >= 37:
                        sym = d[0].replace(".P", "")
                        if sym in EXCLUDED_SYMBOLS: continue
                        result_map[sym] = {
                            "close": d[1] or 0.0, "rsi": d[2] or 50.0, "bb_upper": d[3] or 0.0, "bb_lower": d[4] or 0.0,
                            "sma20": d[5] or 0.0, "funding": (d[6] or 0.0) * 100, "vol_curr": d[7] or 1.0, "vol_prev": d[8] or 1.0,
                            "vwap": d[9] or 0.0, "adx": d[10] or 0.0, "atr": d[11] or 0.0, "close60": d[12] or 0.0,
                            "sma50_60": d[13] or 0.0, "close240": d[14] or 0.0, "sma50_240": d[15] or 0.0, 
                            "high15": d[16] or 0.0, "low15": d[17] or 0.0, "open15": d[18] or 0.0, 
                            "prev_high15": d[19] or 0.0, "prev_rsi15": d[20] or 50.0, "prev_low15": d[21] or 0.0,
                            "prev_close15": d[22] or 0.0, "prev_open15": d[23] or 0.0, "sma200_60": d[24] or 0.0,
                            "macd": d[25] or 0.0, "macd_signal": d[26] or 0.0, "stoch_k": d[27] or 50.0, "stoch_d": d[28] or 50.0,
                            "ichi_tenkan": d[29] or 0.0, "ichi_kijun": d[30] or 0.0, "ichi_spanA": d[31] or 0.0, "ichi_spanB": d[32] or 0.0,
                            "ema50": d[33] or 0.0, "ema200": d[34] or 0.0, "low_2": d[35] or 0.0, "high_2": d[36] or 0.0
                        }
                return result_map
            return {}
        except: return {}

    def run_cycle(self):
        add_log("🔍 MTF & Borsa Editörü Taraması Başlatıldı...")
        today_str = get_tr_time("%Y-%m-%d")
        if self.state.get("signal_date") != today_str:
            self.state["signal_log"] = {}
            self.state["signal_date"] = today_str
            add_log("📅 Yeni Gün: Sinyal Geçmişi Sıfırlandı.")

        if "ledgers" not in self.state: self.state["ledgers"] = {}
        for k in DEFAULT_LEDGERS:
            if k not in self.state["ledgers"]: 
                self.state["ledgers"][k] = 1000.0 if k == "Kasa_10_BorsaEditoru" else 100.0

        tv_data = self.fetch_tv_multi_timeframe()
        if not tv_data: return

        for sym, c in tv_data.items(): self.live_prices[sym] = c["close"]
        for sym in list(self.cooldown_tracker.keys()):
            self.cooldown_tracker[sym] -= 1
            if self.cooldown_tracker[sym] <= 0: del self.cooldown_tracker[sym]

        state_changed = False
        
        # --- POZİSYON YÖNETİMİ ---
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
                    "ledger": ledger_name, "exit_time": get_tr_time("%Y-%m-%d %H:%M:%S")
                })
                
                # Geçmişi 100 adet işlemle sınırla
                if len(self.state["history"]) > 100:
                    self.state["history"] = self.state["history"][-100:]
                    
                del self.state["active_positions"][symbol]
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

            # Dict key hatasını engellemek için get() güvenliği (Tüm kasalar kullanabilir)
            ema50 = c.get("ema50", 0.0)
            ema200 = c.get("ema200", 0.0)
            sma20 = c.get("sma20", 0.0)
            macd = c.get("macd", 0.0)
            macd_signal = c.get("macd_signal", 0.0)
            stoch_k = c.get("stoch_k", 50.0)
            stoch_d = c.get("stoch_d", 50.0)
            ichi_tenkan = c.get("ichi_tenkan", 0.0)
            ichi_kijun = c.get("ichi_kijun", 0.0)
            ichi_spanA = c.get("ichi_spanA", 0.0)
            ichi_spanB = c.get("ichi_spanB", 0.0)
            low_2 = c.get("low_2", c.get("low15", 0.0))
            high_2 = c.get("high_2", c.get("high15", 0.0))
            vwap = c.get("vwap", 0.0)
            adx = c.get("adx", 0.0)

            # --- DİĞER KASALAR İÇİN TEMEL STRATEJİLER (Kasa 1 - 9) ---
            # Kasa 1 Momentum
            if c["rsi"] > 65 and vol_ratio > 1.5 and c["close"] > sma20:
                candidate_pool.append({"sym": sym, "side": "BUY", "ledger": "Kasa_1_Momentum", "strat": "[STRAT: Momentum_Long]", "c": c})
            
            # Kasa 2 SMC PA
            if c["close"] > ema200 and is_solid_body and c["close"] > c["prev_high15"]:
                candidate_pool.append({"sym": sym, "side": "BUY", "ledger": "Kasa_2_SMC_PA", "strat": "[STRAT: SMC_Trend_Devami]", "c": c})
                
            # Kasa 3 MTF Swing
            if c["close60"] > c["sma50_60"] and c["close240"] > c["sma50_240"] and c["close"] > ema50:
                candidate_pool.append({"sym": sym, "side": "BUY", "ledger": "Kasa_3_MTF_Swing", "strat": "[STRAT: MTF_Swing_Onay]", "c": c})
                
            # Kasa 4 MTF Scalp
            if c["close"] > sma20 and c["rsi"] > 55 and vol_ratio > 1.2:
                candidate_pool.append({"sym": sym, "side": "BUY", "ledger": "Kasa_4_MTF_Scalp", "strat": "[STRAT: Scalp_Long]", "c": c})
                
            # Kasa 5 Squeeze
            if bb_width < 0.04 and c["close"] > c["bb_upper"]:
                candidate_pool.append({"sym": sym, "side": "BUY", "ledger": "Kasa_5_Squeeze", "strat": "[STRAT: BB_Patlamasi]", "c": c})
                
            # Kasa 6 VWAP
            if c["close"] > vwap and c["prev_close15"] <= vwap:
                candidate_pool.append({"sym": sym, "side": "BUY", "ledger": "Kasa_6_VWAP", "strat": "[STRAT: VWAP_Kesisim]", "c": c})
                
            # Kasa 7 Göreceli Güç
            if adx > 25 and c["rsi"] > 60 and c["close"] > sma20:
                candidate_pool.append({"sym": sym, "side": "BUY", "ledger": "Kasa_7_GoreceliGuc", "strat": "[STRAT: Trend_Gucu_ADX]", "c": c})
                
            # Kasa 8 Oturum
            if vol_ratio > 2.0 and c["close"] > c["open15"] and c["close"] > ema50:
                candidate_pool.append({"sym": sym, "side": "BUY", "ledger": "Kasa_8_Oturum", "strat": "[STRAT: Hacim_Artisi]", "c": c})
                
            # Kasa 9 Price Action
            if c["close"] > c["prev_high15"] and c["low15"] > c["prev_low15"] and c["close"] > sma20:
                candidate_pool.append({"sym": sym, "side": "BUY", "ledger": "Kasa_9_PriceAction", "strat": "[STRAT: PA_Yukselen_DipTepe]", "c": c})

            # --- KASA 10: BORSA EDİTÖRÜ AVCI MODÜLLERİ ---
            # Modül 1: Hacimli DÜK (Düşen Kırılımı + Yüksek Hacim)
            if c["close"] > c["prev_high15"] and c["close"] > ema50 and vol_ratio > 2.0 and is_solid_body:
                candidate_pool.append({"sym": sym, "side": "BUY", "ledger": "Kasa_10_BorsaEditoru", "strat": "[STRAT: BorsaEd_Hacimli_DUK]", "c": c})

            # Modül 2: İkili Dip (W Formasyonu - Fiyat dipleri yakın, boyun kırılıyor)
            if c["low15"] > 0 and low_2 > 0 and abs(c["low15"] - low_2) / low_2 < 0.005 and c["close"] > c["prev_high15"] and c["rsi"] > 40:
                candidate_pool.append({"sym": sym, "side": "BUY", "ledger": "Kasa_10_BorsaEditoru", "strat": "[STRAT: BorsaEd_IkiliDip_Long]", "c": c})

            # Modül 3: İkili Tepe (M Formasyonu - Fiyat tepeleri yakın, boyun aşağı kırılıyor)
            if c["high15"] > 0 and high_2 > 0 and abs(c["high15"] - high_2) / high_2 < 0.005 and c["close"] < c["prev_low15"] and c["rsi"] < 60:
                candidate_pool.append({"sym": sym, "side": "SELL", "ledger": "Kasa_10_BorsaEditoru", "strat": "[STRAT: BorsaEd_CiftTepe_Short]", "c": c})

            # Modül 4: RSI Pozitif Uyumsuzluk (Fiyat daha düşük dip yapıyor, RSI yükseliyor)
            if c["low15"] < c["prev_low15"] and c["rsi"] > c["prev_rsi15"] and c["rsi"] < 40 and c["close"] > c["open15"]:
                candidate_pool.append({"sym": sym, "side": "BUY", "ledger": "Kasa_10_BorsaEditoru", "strat": "[STRAT: BorsaEd_RSIPozitifUyumsuzluk]", "c": c})

            # Modül 5: RSI Negatif Uyumsuzluk (Fiyat daha yüksek tepe yapıyor, RSI düşüyor)
            if c["high15"] > c["prev_high15"] and c["rsi"] < c["prev_rsi15"] and c["rsi"] > 60 and c["close"] < c["open15"]:
                candidate_pool.append({"sym": sym, "side": "SELL", "ledger": "Kasa_10_BorsaEditoru", "strat": "[STRAT: BorsaEd_RSINegatifUyumsuzluk]", "c": c})

            # Modül 6: MACD Al Sinyali (Sıfır hattı altında momentum kesişimi)
            if macd > macd_signal and macd < 0 and vol_ratio > 1.2 and c["close"] > sma20:
                candidate_pool.append({"sym": sym, "side": "BUY", "ledger": "Kasa_10_BorsaEditoru", "strat": "[STRAT: BorsaEd_MACD_Kesisim_Long]", "c": c})

            # Modül 7: Ichimoku Bulutu Üstü Tenkan & Kijun Golden Cross
            if c["close"] > ichi_spanA and c["close"] > ichi_spanB and ichi_spanA > ichi_spanB:
                if ichi_tenkan > ichi_kijun and c["close"] > ichi_tenkan:
                    candidate_pool.append({"sym": sym, "side": "BUY", "ledger": "Kasa_10_BorsaEditoru", "strat": "[STRAT: BorsaEd_Ichimoku_GoldenCross]", "c": c})

            # Modül 8: Bollinger Bantları Daralması ve Hacimli Kırılım (Squeeze)
            if bb_width < 0.03 and c["close"] > c["bb_upper"] and vol_ratio > 2.5:
                candidate_pool.append({"sym": sym, "side": "BUY", "ledger": "Kasa_10_BorsaEditoru", "strat": "[STRAT: BorsaEd_Bollinger_Daralma_Breakout]", "c": c})

            # Modül 9: Stokastik Aşırı Satım Bölgesinden Dönüş (< 20)
            if stoch_k > stoch_d and stoch_k < 25 and c["close"] > sma20:
                candidate_pool.append({"sym": sym, "side": "BUY", "ledger": "Kasa_10_BorsaEditoru", "strat": "[STRAT: BorsaEd_Stoch_Oversold_Cross]", "c": c})

            # Modül 10: Bayrak / Fincan Kulp Onayı (Geri çekilme sonrası hareketli ortalama retesti)
            if c["low15"] <= sma20 and c["close"] > sma20 and c["close"] > c["prev_high15"] and sma20 > ema50:
                candidate_pool.append({"sym": sym, "side": "BUY", "ledger": "Kasa_10_BorsaEditoru", "strat": "[STRAT: BorsaEd_Bayrak_FincanKulp_Retest]", "c": c})

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
            
            # Kasa 10 için işlem limiti 10, diğerleri için 2
            max_limit = MAX_POSITIONS_KASA_10 if ledger == "Kasa_10_BorsaEditoru" else MAX_POSITIONS_DEFAULT
            if ledger_counts.get(ledger, 0) >= max_limit: continue
            
            ledger_balance = self.state["ledgers"].get(ledger, 0)
            if ledger_balance < 10: continue

            # Kasa 10'da marjin bütçeye göre (1000 / 10 = 100$)
            margin_per_trade = ledger_balance / (max_limit - ledger_counts.get(ledger, 0))
            atr = c["atr"] if c["atr"] > 0 else c["close"] * 0.01
            sl_price = c["close"] - (atr * 1.5) if side == "BUY" else c["close"] + (atr * 1.5)
            
            self.state["ledgers"][ledger] -= margin_per_trade
            self.state["active_positions"][sym] = {
                "side": side, "entry_price": c["close"], "current_price": c["close"], "sl_price": sl_price,
                "max_reached_price": c["close"], "min_reached_price": c["close"],
                "margin": margin_per_trade, "strategy": strat, "ledger_name": ledger, "atr": atr,
                "entry_time": get_tr_time("%Y-%m-%d %H:%M:%S"), "peak_price": c["close"], 
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
    add_log("🤖 Kurumsal MTF Engine 10 Kasalı Modda Başlatıldı...")
    while True:
        try: engine.run_cycle()
        except Exception as e: add_log(f"Döngü Hatası: {e}")
        time.sleep(10)
