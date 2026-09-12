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
    if not out:
        out = _research_from_queue(state, log=log)
    return out


def _research_from_queue(state: dict, *, log=None) -> list[dict]:
    """Kaynaklar bos kaldiginda kuyruk konularindan tarif uret."""
    from engine.gemini_client import generate_recipes_from_text
    from engine.recipe_validator import validate_recipes
    from engine.research_queue import dequeue_research_topics

    topics = dequeue_research_topics(state, limit=2)
    if not topics:
        return []
    existing_ids = {r.get("id") for r in (state.get("recipes") or []) if r.get("id")}
    body = "\n\n".join(f"Arastirma konusu: {t}" for t in topics)
    if log:
        log(f"Arastirma kuyrugu fallback: {len(topics)} konu -> Gemini")
    try:
        raw = generate_recipes_from_text(
            source_label="arastirma kuyrugu (backtest basarisiz/konu)",
            title=topics[0][:120],
            body=body,
            max_recipes=2,
            log=log,
        )
    except Exception as e:
        if log:
            log(f"Kuyruk arastirma hatasi: {e}")
        return []
    valid = validate_recipes(raw, source="queue", state=state, log=log)
    out = []
    for r in valid:
        if r.get("id") and r["id"] not in existing_ids:
            r["source"] = r.get("source") or "queue"
            out.append(r)
            existing_ids.add(r["id"])
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
