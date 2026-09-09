"""Arastirma kuyrugu ve kaynak bazli lab metrikleri."""
from __future__ import annotations

from engine.lab_state import now_tr

SOURCE_BUCKETS = ("youtube", "web", "news", "combinator", "other")
MAX_QUEUE = 80


def normalize_source(source: str | None) -> str:
    raw = str(source or "other").lower()
    if raw.startswith("youtube") or raw == "youtube":
        return "youtube"
    if raw.startswith("web"):
        return "web"
    if raw.startswith("news"):
        return "news"
    if raw == "combinator":
        return "combinator"
    return "other"


def _empty_metrics() -> dict:
    return {
        "recipes_added": 0,
        "backtests": 0,
        "backtest_pass": 0,
        "quick_screen_fail": 0,
        "paper_promoted": 0,
        "paper_rejected": 0,
        "paper_pnl": 0.0,
    }


def ensure_source_metrics(state: dict) -> dict:
    metrics = state.setdefault("source_metrics", {})
    for bucket in SOURCE_BUCKETS:
        metrics.setdefault(bucket, _empty_metrics())
    return metrics


def bump_metric(state: dict, source: str | None, field: str, delta: int | float = 1) -> None:
    bucket = normalize_source(source)
    m = ensure_source_metrics(state)[bucket]
    m[field] = type(delta)(m.get(field, 0)) + delta


def enqueue_research(
    state: dict,
    topic: str,
    *,
    reason: str = "",
    source: str = "other",
    priority: int = 5,
) -> None:
    text = (topic or "").strip()
    if len(text) < 12:
        return
    queue = state.setdefault("research_queue", [])
    key = text.lower()[:120]
    for item in queue:
        if item.get("topic", "").lower()[:120] == key:
            item["priority"] = max(int(item.get("priority") or 0), priority)
            item["updated_at"] = now_tr()
            if reason:
                item["reason"] = reason
            return
    queue.append({
        "topic": text[:200],
        "reason": reason[:120],
        "source": normalize_source(source),
        "priority": priority,
        "created_at": now_tr(),
        "updated_at": now_tr(),
    })
    queue.sort(key=lambda x: (-int(x.get("priority") or 0), x.get("created_at", "")))
    state["research_queue"] = queue[:MAX_QUEUE]


def dequeue_research_topics(state: dict, limit: int = 3) -> list[str]:
    queue = state.get("research_queue") or []
    if not queue:
        return []
    out: list[str] = []
    remain = []
    for item in queue:
        topic = str(item.get("topic") or "").strip()
        if topic and len(out) < limit:
            out.append(topic)
        else:
            remain.append(item)
    state["research_queue"] = remain
    return out


def record_backtest_outcome(state: dict, recipe: dict, metrics: dict, *, quick_fail: bool = False) -> None:
    source = recipe.get("source")
    bump_metric(state, source, "backtests")
    if quick_fail:
        bump_metric(state, source, "quick_screen_fail")
        enqueue_research(
            state,
            f"crypto futures strategy alternative to {recipe.get('name', 'failed recipe')}: "
            f"need higher PF and more trades",
            reason="quick_screen_fail",
            source=source,
            priority=6,
        )
        return
    if metrics.get("passed"):
        bump_metric(state, source, "backtest_pass")
    else:
        pf = metrics.get("profit_factor")
        n = metrics.get("n")
        enqueue_research(
            state,
            f"improve {normalize_source(source)} futures strategy rules: PF={pf} trades={n}",
            reason="backtest_fail",
            source=source,
            priority=7,
        )


def record_paper_rejection(state: dict, candidate: dict, recipe: dict | None = None) -> None:
    source = (recipe or {}).get("source") if recipe else "other"
    bump_metric(state, source, "paper_rejected")
    name = (recipe or {}).get("name") or candidate.get("recipe_id") or "lab recipe"
    m = candidate.get("metrics") or {}
    enqueue_research(
        state,
        f"replace underperforming strategy {name}: paper WR={m.get('wr')} pnl={m.get('pnl')}",
        reason="paper_reject",
        source=source,
        priority=8,
    )


def record_recipes_added(state: dict, recipes: list[dict]) -> None:
    for r in recipes:
        bump_metric(state, r.get("source"), "recipes_added")


def record_paper_promotion(state: dict, recipe: dict) -> None:
    bump_metric(state, recipe.get("source"), "paper_promoted")
