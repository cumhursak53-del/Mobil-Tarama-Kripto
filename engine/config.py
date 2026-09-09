from __future__ import annotations

import os
from datetime import timezone, timedelta

TR_TZ = timezone(timedelta(hours=3))

BINANCE_FAPI = os.environ.get("BINANCE_FAPI", "https://fapi.binance.com")
STATE_FILE = os.environ.get("STATE_FILE", "state.json")

TIMEFRAMES = ("15m", "1h", "4h", "1d", "1w")
KLINE_LIMITS = {"15m": 1000, "1h": 1000, "4h": 400, "1d": 400, "1w": 200}

# Signal evaluation TF / HTF bias
ENTRY_TF = os.environ.get("ENTRY_TF", "1h")
SETUP_TF = os.environ.get("SETUP_TF", "4h")
DAILY_TF = os.environ.get("DAILY_TF", "1d")
WEEKLY_TF = os.environ.get("WEEKLY_TF", "1w")
TRIGGER_TF = os.environ.get("TRIGGER_TF", "15m")
# bar_close = sadece mum kapanisinda; live = tarama dongusunde anlik fiyat
ENTRY_MODE_DEFAULT = os.environ.get("ENTRY_MODE_DEFAULT", "live")

KASA_START_USD = 100.0
CASH_RESERVE_PCT = 0.20
RISK_PCT = 0.02
COMBO_LEDGER = "Kasa_RejimOsilator"
COMBO_RISK_PCT = 0.03
PATLAMA_LEDGER = "Kasa_PatlamaSelale"

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
    "Kasa_SMC",
]

LIVE_ENTRY_LEDGERS = tuple(
    x.strip()
    for x in os.environ.get(
        "LIVE_ENTRY_LEDGERS",
        ",".join(LEDGER_NAMES),
    ).split(",")
    if x.strip()
)
SMC_MIN_GRADE = os.environ.get("SMC_MIN_GRADE", "A")
SMC_MIN_CONFLUENCE = int(os.environ.get("SMC_MIN_CONFLUENCE", "5"))
SMC_REQUIRE_KILLZONE = os.environ.get("SMC_REQUIRE_KILLZONE", "1") == "1"
SMC_REQUIRE_OB_FVG = os.environ.get("SMC_REQUIRE_OB_FVG", "1") == "1"
SMC_BODY_CLOSE = os.environ.get("SMC_BODY_CLOSE", "1") == "1"
SMT_ENABLED = os.environ.get("SMT_ENABLED", "1") == "1"
SMT_REF_SYMBOL = os.environ.get("SMT_REF_SYMBOL", "BTCUSDT")
FIDELITY_MIN_PF = float(os.environ.get("FIDELITY_MIN_PF", "1.2"))
FIDELITY_MAX_DD = float(os.environ.get("FIDELITY_MAX_DD", "0.25"))
FIDELITY_MIN_BACKTEST_DAYS = int(os.environ.get("FIDELITY_MIN_BACKTEST_DAYS", "90"))
FIDELITY_PAPER_WR_DELTA = float(os.environ.get("FIDELITY_PAPER_WR_DELTA", "0.10"))
WALK_FORWARD_TRAIN_RATIO = float(os.environ.get("WALK_FORWARD_TRAIN_RATIO", "0.7"))
PRIORITY_LEDGERS = (COMBO_LEDGER, PATLAMA_LEDGER)
MIN_SURVIVAL_USD = 20.0
LIQ_ADVERSE_PCT = 0.08  # 10x korelasyonlu dump tamponu
MIN_LEVERAGE = float(os.environ.get("MIN_LEVERAGE", "10"))
MAX_LEVERAGE = float(os.environ.get("MAX_LEVERAGE", "10"))
MAX_POSITIONS_PER_KASA = int(os.environ.get("MAX_POSITIONS_PER_KASA", "2"))
MAX_COMBO_POSITIONS = int(os.environ.get("MAX_COMBO_POSITIONS", "6"))
MAX_TOTAL_POSITIONS = int(os.environ.get("MAX_TOTAL_POSITIONS", "30"))
MAX_SHORT_OPEN_RATIO = float(os.environ.get("MAX_SHORT_OPEN_RATIO", "0.65"))
SHORT_RATIO_MIN_POSITIONS = int(os.environ.get("SHORT_RATIO_MIN_POSITIONS", "4"))
SYMBOL_COOLDOWN_AFTER_SL_SEC = int(os.environ.get("SYMBOL_COOLDOWN_AFTER_SL_SEC", "7200"))
PATLAMA_MIN_SCORE = int(os.environ.get("PATLAMA_MIN_SCORE", "5"))
PATLAMA_MIN_EDGE = int(os.environ.get("PATLAMA_MIN_EDGE", "2"))
TAKER_FEE = 0.0004  # 0.04% each side
PARTIAL_R = float(os.environ.get("PARTIAL_R", "2.0"))
PARTIAL_PCT = float(os.environ.get("PARTIAL_PCT", "0.5"))
TRAIL_ATR_MULT = float(os.environ.get("TRAIL_ATR_MULT", "1.5"))
BE_AT_R = float(os.environ.get("BE_AT_R", "1.0"))
SCAN_MODE = os.environ.get("SCAN_MODE", "best_signal")  # priority | best_signal
SYMBOL_LOCK_MODE = os.environ.get("SYMBOL_LOCK_MODE", "global")  # global | per_ledger | none
RETEST_HOLD_BARS = int(os.environ.get("RETEST_HOLD_BARS", "3"))
MIN_IMPULSE_ATR = float(os.environ.get("MIN_IMPULSE_ATR", "1.5"))
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
LAB_MIN_BACKTEST_TRADES = int(os.environ.get("LAB_MIN_BACKTEST_TRADES", "25"))
LAB_MIN_BACKTEST_PF = float(os.environ.get("LAB_MIN_BACKTEST_PF", "1.25"))
LAB_PAPER_MIN_TRADES_REJECT = int(os.environ.get("LAB_PAPER_MIN_TRADES_REJECT", "8"))
LAB_PAPER_MIN_WR = float(os.environ.get("LAB_PAPER_MIN_WR", "0.38"))
LAB_AUTO = os.environ.get("LAB_AUTO", "1") == "1"
LAB_AUTO_INTERVAL_SEC = int(os.environ.get("LAB_AUTO_INTERVAL_SEC", "1800"))  # 30 dk
LAB_GENERATE_LIMIT = int(os.environ.get("LAB_GENERATE_LIMIT", "24"))
LAB_BACKTEST_BATCH = int(os.environ.get("LAB_BACKTEST_BATCH", "8"))
LAB_BACKTEST_UNIVERSE = int(os.environ.get("LAB_BACKTEST_UNIVERSE", "4"))
LAB_MIN_RECIPES = int(os.environ.get("LAB_MIN_RECIPES", "12"))
ENGINE_URL = os.environ.get("ENGINE_URL", "")

# Gemini + arastirma
def _normalize_secret(raw: str) -> str:
    k = (raw or "").strip()
    if len(k) >= 2 and k[0] == k[-1] and k[0] in "\"'":
        k = k[1:-1].strip()
    return k


GEMINI_API_KEY = _normalize_secret(os.environ.get("GEMINI_API_KEY", ""))
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
GEMINI_MODEL_FALLBACKS = [
    x.strip() for x in os.environ.get(
        "GEMINI_MODEL_FALLBACKS",
        "gemini-2.5-flash-lite,gemini-2.0-flash-lite",
    ).split(",") if x.strip()
]
GEMINI_RETRY_MAX = int(os.environ.get("GEMINI_RETRY_MAX", "3"))
GEMINI_RETRY_DELAY_SEC = float(os.environ.get("GEMINI_RETRY_DELAY_SEC", "4"))
GEMINI_SKIP_PIPELINE_TEST = os.environ.get("GEMINI_SKIP_PIPELINE_TEST", "1") == "1"
GEMINI_RESEARCH_FALLBACK_FIRST = os.environ.get("GEMINI_RESEARCH_FALLBACK_FIRST", "1") == "1"
RESEARCH_ENABLED = os.environ.get("RESEARCH_ENABLED", "1") == "1"
YOUTUBE_CHANNEL_IDS = [
    x.strip() for x in os.environ.get(
        "YOUTUBE_CHANNEL_IDS",
        "@teknikanalizdersleri",
    ).split(",") if x.strip()
]
YOUTUBE_VIDEO_IDS = [x.strip() for x in os.environ.get("YOUTUBE_VIDEO_IDS", "").split(",") if x.strip()]
YOUTUBE_MAX_VIDEOS_PER_RUN = int(os.environ.get("YOUTUBE_MAX_VIDEOS_PER_RUN", "3"))
NEWS_RSS_URLS = [
    x.strip() for x in os.environ.get(
        "NEWS_RSS_URLS",
        "https://cryptopanic.com/news/rss/,https://www.coindesk.com/arc/outboundfeeds/rss/",
    ).split(",") if x.strip()
]
NEWS_MAX_HEADLINES = int(os.environ.get("NEWS_MAX_HEADLINES", "15"))

# Internet arastirmasi (web arama + sayfa okuma)
WEB_RESEARCH_ENABLED = os.environ.get("WEB_RESEARCH_ENABLED", "1") == "1"
WEB_RESEARCH_QUERIES_PER_RUN = int(os.environ.get("WEB_RESEARCH_QUERIES_PER_RUN", "2"))
WEB_RESEARCH_MAX_RESULTS = int(os.environ.get("WEB_RESEARCH_MAX_RESULTS", "5"))
WEB_RESEARCH_MAX_PAGES = int(os.environ.get("WEB_RESEARCH_MAX_PAGES", "2"))
WEB_RESEARCH_AI_QUERIES = os.environ.get("WEB_RESEARCH_AI_QUERIES", "1") == "1"
WEB_RESEARCH_QUERIES = [
    x.strip() for x in os.environ.get("WEB_RESEARCH_QUERIES", "").split("|") if x.strip()
]
WEB_RESEARCH_TOPICS = [
    x.strip() for x in os.environ.get("WEB_RESEARCH_TOPICS", "").split("|") if x.strip()
]

EXCLUDED_SYMBOLS = {
    "USDCUSDT", "FDUSDUSDT", "USDPUSDT", "BTCDOMUSDT", "DEFIUSDT", "UBERUSDT",
    "BTCSTUSDT", "USDPUSDT",
}
