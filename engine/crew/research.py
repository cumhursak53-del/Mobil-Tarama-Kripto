from __future__ import annotations

from engine.config import GEMINI_API_KEY, RESEARCH_ENABLED
from engine.crew.config import CREW_DAILY_GROWTH_TARGET_PCT, CREW_RESEARCH_QUERIES
from engine.gemini_client import gemini_available, gemini_usable, generate_recipes_from_text
from engine.recipe_validator import validate_recipes
from engine.research_dedup import migrate_legacy_lists


GROWTH_BRIEF = f"""
Hedef: $100 kasayi takvim gunu icinde en az %{CREW_DAILY_GROWTH_TARGET_PCT:.0f} buyutebilecek stratejiler.
Oncelik: patlama/selale momentum, 15m-1h tetik, 4H yon, SMC OB retest, yuksek R (tp_r 2.5-4),
gun icinde birden fazla islem potansiyeli, volatil altcoinler.
"""


def run_crew_research(state: dict, *, log=None) -> tuple[str, list[dict]]:
    """YouTube/haber/web tara; %20 odakli ozet + ham tarif onerileri."""
    migrate_legacy_lists(state.setdefault("research", {}))
    research_meta = state.setdefault("research", {})
    research_meta["gemini_configured"] = bool(GEMINI_API_KEY)
    snippets: list[str] = []
    raw_recipes: list[dict] = []

    if RESEARCH_ENABLED and gemini_usable():
        from engine.news_research import collect_news_recipes
        from engine.web_research import collect_web_recipes
        from engine.youtube_research import collect_youtube_recipes

        for fn in (collect_youtube_recipes, collect_news_recipes, collect_web_recipes):
            try:
                batch = fn(state, log=log)
                for r in batch:
                    raw_recipes.append(r)
                    snippets.append(f"- {r.get('name', '?')}: {r.get('source', 'research')}")
            except Exception as e:
                if log:
                    log(f"Crew arastirma hatasi ({fn.__name__}): {e}")

    query_block = "\n".join(f"- {q}" for q in CREW_RESEARCH_QUERIES)
    summary = (
        f"{GROWTH_BRIEF}\n\n"
        f"Web arastirma konulari:\n{query_block}\n\n"
        f"Kaynaklardan gelen tarif sayisi: {len(raw_recipes)}\n"
    )
    if snippets:
        summary += "Bulunan tarifler:\n" + "\n".join(snippets[:12])

    if gemini_available() and gemini_usable():
        try:
            extra = generate_recipes_from_text(
                source_label="gunluk %20 buyume hedefli arastirma",
                title=f"Kasa %{CREW_DAILY_GROWTH_TARGET_PCT:.0f} gunluk hedef",
                body=summary + "\n\nYuksek frekansli momentum ve SMC OB retest oncelikli tarifler uret.",
                max_recipes=2,
                log=log,
            )
            raw_recipes.extend(extra or [])
        except Exception as e:
            if log:
                log(f"Crew Gemini tarif hatasi: {e}")

    validated = validate_recipes(raw_recipes, source="crewai", state=state, log=log)
    return summary, validated
