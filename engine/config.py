from __future__ import annotations

import os
from datetime import timezone, timedelta

TR_TZ = timezone(timedelta(hours=3))

BINANCE_FAPI = os.environ.get("BINANCE_FAPI", "https://fapi.binance.com")
STATE_FILE = os.environ.get("STATE_FILE", "state.json")

TIMEFRAMES = ("15m", "1h", "4h", "1d", "1w")
KLINE_LIMITS = {"15m": 500, "1h": 500, "4h": 400, "1d": 400, "1w": 200}

# Signal evaluation TF / HTF bias
ENTRY_TF = "1h"
SETUP_TF = "4h"
DAILY_TF = "1d"
WEEKLY_TF = "1w"
TRIGGER_TF = "15m"

KASA_START_USD = 100.0
CASH_RESERVE_PCT = 0.20
RISK_PCT = 0.02
COMBO_LEDGER = "Kasa_RejimOsilator"
COMBO_RISK_PCT = 0.03
PATLAMA_LEDGER = "Kasa_PatlamaSelale"
PRIORITY_LEDGERS = (COMBO_LEDGER, PATLAMA_LEDGER)
MIN_SURVIVAL_USD = 20.0
LIQ_ADVERSE_PCT = 0.08  # 10x korelasyonlu dump tamponu
MIN_LEVERAGE = float(os.environ.get("MIN_LEVERAGE", "10"))
MAX_LEVERAGE = float(os.environ.get("MAX_LEVERAGE", "10"))
MAX_POSITIONS_PER_KASA = 2
TAKER_FEE = 0.0004  # 0.04% each side
PARTIAL_R = 2.0  # take 50% at 2R
SWING_N = 5
NEAR_PCT = 0.004  # 0.4% proximity to level
VOLUME_SMA = 20
ATR_PERIOD = 14
SCAN_SYMBOLS = int(os.environ.get("SCAN_SYMBOLS", "0"))  # 0 = tum USDT perpetual
PRICE_POLL_SEC = int(os.environ.get("PRICE_POLL_SEC", "20"))
GITHUB_REPO = os.environ.get("GITHUB_REPO", "cumhursak53-del/Mobil-Tarama-Kripto")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")
GITHUB_STATE_PATH = os.environ.get("GITHUB_STATE_PATH", "state.json")
LAB_STATE_FILE = os.environ.get("LAB_STATE_FILE", "lab_state.json")
LAB_LEDGER_PREFIX = "Kasa_Lab_"
LAB_MAX_CANDIDATES = int(os.environ.get("LAB_MAX_CANDIDATES", "5"))
LAB_FREEZE = os.environ.get("LAB_FREEZE", "0") == "1"
LAB_MIN_BACKTEST_TRADES = int(os.environ.get("LAB_MIN_BACKTEST_TRADES", "20"))
LAB_MIN_BACKTEST_PF = float(os.environ.get("LAB_MIN_BACKTEST_PF", "1.15"))
LAB_AUTO = os.environ.get("LAB_AUTO", "1") == "1"
LAB_AUTO_INTERVAL_SEC = int(os.environ.get("LAB_AUTO_INTERVAL_SEC", "14400"))  # 4 saat
LAB_GENERATE_LIMIT = int(os.environ.get("LAB_GENERATE_LIMIT", "24"))
LAB_BACKTEST_BATCH = int(os.environ.get("LAB_BACKTEST_BATCH", "8"))
LAB_BACKTEST_UNIVERSE = int(os.environ.get("LAB_BACKTEST_UNIVERSE", "4"))
LAB_MIN_RECIPES = int(os.environ.get("LAB_MIN_RECIPES", "12"))
ENGINE_URL = os.environ.get("ENGINE_URL", "")

EXCLUDED_SYMBOLS = {
    "USDCUSDT", "FDUSDUSDT", "USDPUSDT", "BTCDOMUSDT", "DEFIUSDT", "UBERUSDT",
    "BTCSTUSDT", "USDPUSDT",
}

LEDGER_NAMES = [
    "Kasa_RejimOsilator",
    "Kasa_PatlamaSelale",
    "Kasa_TrendCizgisi",
    "Kasa_PulbackRetest",
    "Kasa_DUK",
    "Kasa_Tuzak",
    "Kasa_Dominance",
    "Kasa_SMA9_14",
    "Kasa_EMA_Fib",
    "Kasa_DinamikMA",
    "Kasa_PiyasaEvresi",
    "Kasa_MumOnay",
    "Kasa_YapiKirilim",
    "Kasa_RSI_Uyumsuzluk",
    "Kasa_RSI_Bolge",
    "Kasa_MACD",
    "Kasa_BB_Squeeze",
    "Kasa_CCI",
    "Kasa_Stoch",
    "Kasa_StochRSI",
    "Kasa_Ichimoku",
    "Kasa_Hacim",
    "Kasa_OBO_TOBO",
    "Kasa_IkiliDipTepe",
    "Kasa_Ucgen",
    "Kasa_BayrakFlama",
    "Kasa_Dortgen",
    "Kasa_FincanCanak",
    "Kasa_Takoz",
    "Kasa_Fib618",
]
