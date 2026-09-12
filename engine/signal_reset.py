"""Gunluk sinyal gunlugu sifirlama — 03:00 TR (1d mum baslangici)."""
from __future__ import annotations

from datetime import datetime

from engine.config import SIGNAL_LOG_RESET_HOUR, TR_TZ


def _reset_key(now: datetime) -> str:
    """03:00 gecildiyse bugunun anahtari; degilse dunun oturumu devam."""
    if now.hour >= SIGNAL_LOG_RESET_HOUR:
        day = now.date()
    else:
        from datetime import timedelta
        day = (now - timedelta(days=1)).date()
    return f"{day.isoformat()}_{SIGNAL_LOG_RESET_HOUR:02d}00"


def maybe_reset_signal_log(signal_log: dict, *, log=None) -> bool:
    """03:00 TR oturumu basinda sinyal gunlugunu temizler (_dominance korunur)."""
    if not isinstance(signal_log, dict):
        return False
    now = datetime.now(TR_TZ)
    key = _reset_key(now)
    meta = signal_log.setdefault("_meta", {})
    if meta.get("signal_log_reset_key") == key:
        return False
    dominance = signal_log.get("_dominance")
    keep_meta = {"signal_log_reset_key": key, "signal_log_reset_at": now.strftime("%Y-%m-%d %H:%M:%S")}
    signal_log.clear()
    if dominance:
        signal_log["_dominance"] = dominance
    signal_log["_meta"] = keep_meta
    if log:
        log(f"Sinyal gunlugu sifirlandi ({SIGNAL_LOG_RESET_HOUR:02d}:00 TR oturumu, key={key})")
    return True
