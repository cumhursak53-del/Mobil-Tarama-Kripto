"""YouTube + haber arastirmasini lab state'e yazar."""
from __future__ import annotations

from engine.config import GEMINI_API_KEY, RESEARCH_ENABLED
from engine.gemini_client import gemini_usable
from engine.news_research import collect_news_recipes
from engine.web_research import collect_web_recipes
from engine.youtube_research import collect_youtube_recipes


def run_research(state: dict, *, log=None) -> list[dict]:
    if not RESEARCH_ENABLED or not gemini_usable():
        return []
    from engine.research_dedup import migrate_legacy_lists

    migrate_legacy_lists(state.setdefault("research", {}))
    existing_ids = {r.get("id") for r in (state.get("recipes") or []) if r.get("id")}
    out: list[dict] = []
    try:
        for batch_fn in (collect_youtube_recipes, collect_news_recipes, collect_web_recipes):
            try:
                batch = batch_fn(state, log=log)
            except Exception as e:
                if log:
                    log(f"Arastirma hatasi ({batch_fn.__name__}): {e}")
                batch = []
            for r in batch:
                if r.get("id") and r["id"] not in existing_ids:
                    out.append(r)
                    existing_ids.add(r["id"])
    except Exception as e:
        if log:
            log(f"Research genel hata: {e}")
    return out


def research_status(state: dict) -> dict:
    meta = state.get("research") or {}
    return {
        "enabled": RESEARCH_ENABLED and bool(GEMINI_API_KEY),
        "gemini": bool(GEMINI_API_KEY),
        "last_youtube_at": meta.get("last_youtube_at", ""),
        "last_news_at": meta.get("last_news_at", ""),
        "last_web_at": meta.get("last_web_at", ""),
        "youtube_recipes_total": meta.get("youtube_recipes", 0),
        "news_recipes_total": meta.get("news_recipes", 0),
        "web_recipes_total": meta.get("web_recipes", 0),
        "processed_videos": len(meta.get("processed_videos") or []),
        "processed_web_queries": len(meta.get("processed_web_queries") or []),
    }
