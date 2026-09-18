"""7/24 live entrypoint: Bybit testnet/mainnet — Hacim + PiyasaEvresi."""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

from engine.env_loader import bootstrap_env

bootstrap_env(live=True)

from engine.config import LIVE_TRADING_ENABLED, SCAN_SYMBOLS, TRADING_MODE, is_live_exchange
from engine.live import run_live


def _preflight() -> None:
    if TRADING_MODE == "paper":
        print("UYARI: TRADING_MODE=paper — live.env icinde bybit_testnet ayarlayin.", flush=True)
    if not LIVE_TRADING_ENABLED:
        print(
            "UYARI: LIVE_TRADING_ENABLED=0 — motor calisir ama borsaya emir gitmez.",
            flush=True,
        )
    if is_live_exchange():
        print(f"CANLI MOD AKTIF: {TRADING_MODE}", flush=True)
    else:
        print("Simulasyon modu (Bybit emirleri kapali).", flush=True)


if __name__ == "__main__":
    _preflight()
    n = int(os.environ.get("SCAN_SYMBOLS", str(SCAN_SYMBOLS)))
    run_live(n)
