"""Internet arastirmasi — web arama + Gemini tarif cikarimi."""
from __future__ import annotations

import hashlib

from engine.config import (
    WEB_RESEARCH_AI_QUERIES,
    WEB_RESEARCH_ENABLED,
    WEB_RESEARCH_MAX_PAGES,
    WEB_RESEARCH_MAX_RESULTS,
    WEB_RESEARCH_QUERIES,
    WEB_RESEARCH_QUERIES_PER_RUN,
    WEB_RESEARCH_TOPICS,
)
from engine.gemini_client import gemini_usable, generate_recipes_from_text, suggest_web_queries
from engine.recipe_validator import validate_recipes
from engine.research_dedup import is_recent, mark_done, migrate_legacy_lists, prune_expired
from engine.web_search import build_research_document, search_web
from engine.youtube_research import _research_meta

_DEFAULT_TOPICS = [
    "smart money concepts order block FVG crypto futures strategy rules",
    "crypto futures MACD histogram crossover entry exit rules",
    "liquidity sweep inducement trading strategy cryptocurrency",
    "ichimoku cloud kumo breakout crypto futures strategy",
    "RSI divergence hidden regular crypto futures trading setup",
    "Bollinger band squeeze breakout crypto strategy backtest rules",
    "fibonacci 618 retracement confluence crypto trading strategy",
    "multi timeframe confluence crypto futures entry strategy",
    "funding rate open interest crypto futures trading edge",
    "stochastic RSI oversold overbought crypto futures rules",
    "market structure break of structure CHoCH crypto strategy",
    "volume profile VWAP crypto futures day trading strategy",
]


def _query_key(query: str) -> str:
    return hashlib.sha256(query.strip().lower().encode()).hexdigest()[:16]


def _next_queries(state: dict, *, log=None) -> list[str]:
    from engine.research_queue import dequeue_research_topics

    meta = _research_meta(state)
    migrate_legacy_lists(meta)
    prune_expired(meta, "processed_web_queries")
    queue_topics = dequeue_research_topics(state, limit=WEB_RESEARCH_QUERIES_PER_RUN)
    if queue_topics:
        if log:
            log(f"Arastirma kuyrugu: {len(queue_topics)} konu")
        return queue_topics

    topics = list(WEB_RESEARCH_TOPICS or _DEFAULT_TOPICS)
    if WEB_RESEARCH_QUERIES:
        topics = list(WEB_RESEARCH_QUERIES) + topics

    pending = [q for q in topics if not is_recent(meta, "processed_web_queries", _query_key(q))]
    if WEB_RESEARCH_AI_QUERIES and gemini_usable() and len(pending) < WEB_RESEARCH_QUERIES_PER_RUN:
        try:
            done_keys = list((meta.get("processed_web_queries") or {}).keys())[-20:]
            ai = suggest_web_queries(
                already_done=done_keys,
                limit=max(1, WEB_RESEARCH_QUERIES_PER_RUN),
                log=log,
            )
            for q in ai:
                qkey = _query_key(q)
                if q and not is_recent(meta, "processed_web_queries", qkey) and q not in pending:
                    pending.append(q)
        except Exception as e:
            if log:
                log(f"Web AI sorgu hatasi: {e}")

    if not pending:
        if log:
            log("Web arastirma: tum sorgular yakin zamanda islendi")
        pending = topics[:WEB_RESEARCH_QUERIES_PER_RUN]

    return pending[:WEB_RESEARCH_QUERIES_PER_RUN]


def collect_web_recipes(state: dict, *, log=None) -> list[dict]:
    if not WEB_RESEARCH_ENABLED or not gemini_usable():
        return []

    meta = _research_meta(state)
    migrate_legacy_lists(meta)
    recipes: list[dict] = []

    for query in _next_queries(state, log=log):
        qkey = _query_key(query)
        if is_recent(meta, "processed_web_queries", qkey):
            continue
        hits = search_web(query, max_results=WEB_RESEARCH_MAX_RESULTS)
        if not hits:
            if log:
                log(f"Web arama sonuc yok: {query[:60]}")
            continue

        doc = build_research_document(query, hits, fetch_pages=WEB_RESEARCH_MAX_PAGES)
        if len(doc) < 300:
            if log:
                log(f"Web arastirma icerik yetersiz: {query[:60]}")
            continue

        raw = generate_recipes_from_text(
            source_label="internet arastirmasi (web arama + sayfa ozeti)",
            title=query[:120],
            body=doc,
            max_recipes=2,
            log=log,
        )
        valid = validate_recipes(raw, source=f"web:{qkey}", state=state, log=log)
        if valid:
            for r in valid:
                r["source_ref"] = {
                    "query": query[:120],
                    "urls": [h.get("url") for h in hits[:3] if h.get("url")],
                }
            recipes.extend(valid)
            mark_done(meta, "processed_web_queries", qkey)
            if log:
                log(f"Web '{query[:50]}': {len(valid)} tarif ({len(hits)} sonuc)")
        elif raw and log:
            log(f"Web '{query[:50]}': 0 gecerli tarif — tekrar denenecek")

    if recipes:
        from engine.lab_state import now_tr
        meta["last_web_at"] = now_tr()
    meta["web_recipes"] = int(meta.get("web_recipes") or 0) + len(recipes)
    return recipes
