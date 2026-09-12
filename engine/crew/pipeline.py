from __future__ import annotations

import time
from typing import Callable

from engine.crew.backtest_runner import backtest_recipes
from engine.crew.config import CREW_DAILY_GROWTH_TARGET_PCT, CREW_DAILY_RECIPE_LIMIT
from engine.crew.report import build_csv_attachment, build_html_report, build_run_summary, build_subject
from engine.crew.research import GROWTH_BRIEF, run_crew_research
from engine.crew.state import append_recipes, load_state, now_tr, save_state
from engine.gemini_client import gemini_usable, generate_recipes_from_text
from engine.recipe_validator import validate_recipes


def _log_default(msg: str) -> None:
    print(f"[Crew] {msg}", flush=True)


def _generate_architect_recipes(state: dict, brief: str, need: int, log) -> list[dict]:
    if need <= 0 or not gemini_usable():
        return []
    raw = generate_recipes_from_text(
        source_label="CrewAI Strategy Architect",
        title=f"Gunluk %{CREW_DAILY_GROWTH_TARGET_PCT:.0f} kasa buyume hedefi",
        body=(
            f"{GROWTH_BRIEF}\n\nAraştirma ozeti:\n{brief[:8000]}\n\n"
            "entry_tf 15m veya 1h, tp_r 2.5-4.0, momentum/SMC/bos kurallari oncelikli."
        ),
        max_recipes=need,
        log=log,
    )
    return validate_recipes(raw, source="crewai_architect", state=state, log=log)


def _try_crew_ai_narrative(brief: str, results: list[dict], log) -> str:
    """CrewAI varsa kisa QA yorumu; yoksa bos."""
    try:
        from crewai import Agent, Crew, LLM, Process, Task

        from engine.crew.config import CREW_GEMINI_MODEL

        import os

        llm = LLM(model=CREW_GEMINI_MODEL, api_key=os.environ.get("GEMINI_API_KEY"), temperature=0.2)
        reporter = Agent(
            role="QA Reporter",
            goal="Backtest sonuclarini Turkce 3-5 cumle ile ozetle",
            backstory="Kripto strateji analisti",
            llm=llm,
            verbose=False,
        )
        top = results[:3]
        task = Task(
            description=(
                f"Hedef kasa gunluk +{CREW_DAILY_GROWTH_TARGET_PCT}%. "
                f"Arastirma: {brief[:2000]}. Sonuclar: {top}. Kisa yorum yaz."
            ),
            expected_output="Turkce 3-5 cumlelik ozet",
            agent=reporter,
        )
        crew = Crew(agents=[reporter], tasks=[task], process=Process.sequential, verbose=False)
        out = crew.kickoff()
        return str(out).strip()
    except Exception as e:
        if log:
            log(f"CrewAI narrative atlandi: {e}")
        return ""


def run_daily_crew(
    *,
    send_email: bool = False,
    dry_run: bool = False,
    log: Callable[[str], None] | None = None,
) -> dict:
    """Gunluk Crew pipeline: arastir -> tarif -> backtest -> rapor."""
    log = log or _log_default
    t0 = time.time()
    state = load_state()
    errors: list[str] = []

    try:
        brief, recipes = run_crew_research(state, log=log)
    except Exception as e:
        brief, recipes = GROWTH_BRIEF, []
        errors.append(f"research: {e}")
        log(f"Crew research hata: {e}")

    need = max(0, CREW_DAILY_RECIPE_LIMIT - len(recipes))
    extra = _generate_architect_recipes(state, brief, need, log)
    recipes = recipes + extra
    recipes = recipes[:CREW_DAILY_RECIPE_LIMIT]

    if recipes:
        append_recipes(state, recipes)

    tested_ids = set()
    new_for_bt = [r for r in recipes if r.get("id")]
    try:
        bt_rows = backtest_recipes(new_for_bt, log=log) if new_for_bt else []
    except Exception as e:
        bt_rows = []
        errors.append(f"backtest: {e}")
        log(f"Crew backtest hata: {e}")

    for row in bt_rows:
        rid = row.get("recipe_id")
        if rid:
            tested_ids.add(rid)
            state.setdefault("backtests", []).append(row)

    narrative = _try_crew_ai_narrative(brief, bt_rows, log)

    run_record = {
        "date": now_tr("%Y-%m-%d"),
        "started_at": now_tr(),
        "research_summary": brief[:4000],
        "narrative": narrative,
        "recipes_generated": len(recipes),
        "results": bt_rows,
        "duration_sec": round(time.time() - t0, 1),
        "errors": errors,
    }
    state.setdefault("daily_runs", []).append(run_record)
    state["daily_runs"] = state["daily_runs"][-60:]

    summary = build_run_summary(run_record)
    html = build_html_report(summary)
    subject = build_subject(summary)
    csv_bytes = build_csv_attachment(summary)

    if not dry_run:
        save_state(state)

    email_sent = False
    if send_email and not dry_run:
        try:
            from engine.crew.mailer import send_report_email

            csv_name = f"crew_report_{summary['date']}.csv"
            send_report_email(subject=subject, html_body=html, csv_bytes=csv_bytes, csv_name=csv_name)
            email_sent = True
            log("Crew mail gonderildi")
        except Exception as e:
            errors.append(f"email: {e}")
            log(f"Crew mail hatasi: {e}")

    return {
        "summary": summary,
        "html": html,
        "subject": subject,
        "email_sent": email_sent,
        "errors": errors,
        "dry_run": dry_run,
    }
