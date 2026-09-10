"""Arastirma dedup kayitlari — TTL ile yeniden deneme."""
from __future__ import annotations

import time

from engine.config import RESEARCH_DEDUP_TTL_SEC
from engine.lab_state import now_tr


def _parse_ts(raw: str) -> float:
    if not raw:
        return 0.0
    try:
        from datetime import datetime
        from engine.config import TR_TZ

        return datetime.strptime(str(raw)[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=TR_TZ).timestamp()
    except Exception:
        return 0.0


def _ts_map(meta: dict, field: str) -> dict[str, str]:
    raw = meta.get(field)
    if isinstance(raw, dict):
        return raw
    out: dict[str, str] = {}
    if isinstance(raw, list):
        stamp = meta.get(f"{field}_migrated_at") or now_tr()
        for key in raw:
            if key:
                out[str(key)] = stamp
    meta[field] = out
    return out


def migrate_legacy_lists(meta: dict) -> None:
    if isinstance(meta.get("processed_news_batches"), list):
        _ts_map(meta, "processed_news_batches")
    if isinstance(meta.get("processed_web_queries"), list):
        _ts_map(meta, "processed_web_queries")
    if isinstance(meta.get("processed_videos"), list):
        _ts_map(meta, "processed_videos")


def is_recent(meta: dict, field: str, key: str, ttl_sec: int = RESEARCH_DEDUP_TTL_SEC) -> bool:
    if not key:
        return False
    ts_map = _ts_map(meta, field)
    at = ts_map.get(key)
    if not at:
        return False
    age = time.time() - _parse_ts(at)
    return age < ttl_sec


def mark_done(meta: dict, field: str, key: str) -> None:
    if not key:
        return
    ts_map = _ts_map(meta, field)
    ts_map[key] = now_tr()
    meta[field] = ts_map


def prune_expired(meta: dict, field: str, ttl_sec: int = RESEARCH_DEDUP_TTL_SEC) -> int:
    ts_map = _ts_map(meta, field)
    now = time.time()
    kept = {
        k: v for k, v in ts_map.items()
        if k and (now - _parse_ts(v)) < ttl_sec
    }
    removed = len(ts_map) - len(kept)
    meta[field] = kept
    return removed
