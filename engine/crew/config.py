from __future__ import annotations

import os

CREW_DAILY_GROWTH_TARGET_PCT = float(os.environ.get("CREW_DAILY_GROWTH_TARGET_PCT", "20"))
CREW_DAILY_RECIPE_LIMIT = int(os.environ.get("CREW_DAILY_RECIPE_LIMIT", "4"))
CREW_BACKTEST_UNIVERSE = int(os.environ.get("CREW_BACKTEST_UNIVERSE", "6"))
CREW_QUICK_SYMBOL = os.environ.get("CREW_QUICK_SYMBOL", "BTCUSDT")
CREW_STATE_FILE = os.environ.get("CREW_STATE_FILE", "crew_state.json")
CREW_GEMINI_MODEL = os.environ.get("CREW_GEMINI_MODEL", "gemini/gemini-2.0-flash-lite")

_DEFAULT_VOLATILE = "BTCUSDT,ETHUSDT,SOLUSDT,DOGEUSDT,PEPEUSDT,WIFUSDT"
CREW_VOLATILE_SYMBOLS = tuple(
    x.strip().upper()
    for x in os.environ.get("CREW_VOLATILE_SYMBOLS", _DEFAULT_VOLATILE).split(",")
    if x.strip()
)

CREW_RESEARCH_QUERIES = (
    "crypto scalping strategy high daily return futures",
    "momentum breakout 15m cryptocurrency backtest",
    "smart money order block retest quick profit strategy",
)

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_APP_PASSWORD = os.environ.get("SMTP_APP_PASSWORD", "")
REPORT_TO_EMAIL = os.environ.get("REPORT_TO_EMAIL", "cumhursak53@gmail.com")
