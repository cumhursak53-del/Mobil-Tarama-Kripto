from __future__ import annotations

import csv
import io
from datetime import datetime

from engine.config import TR_TZ
from engine.crew.config import CREW_DAILY_GROWTH_TARGET_PCT


def _today() -> str:
    return datetime.now(TR_TZ).strftime("%Y-%m-%d")


def build_run_summary(run: dict) -> dict:
    results = run.get("results") or []
    passed = [r for r in results if r.get("passed")]
    growth_fail = sum(1 for r in results if r.get("reason") == "growth_fail")
    wf_fail = sum(1 for r in results if r.get("reason") == "wf_fail")
    quick_fail = sum(1 for r in results if r.get("reason") == "quick_fail")
    ranked = sorted(
        results,
        key=lambda r: (float(r.get("test_best_day_pct") or 0), float(r.get("test_pf") or 0)),
        reverse=True,
    )
    return {
        "date": run.get("date") or _today(),
        "recipes_generated": int(run.get("recipes_generated") or 0),
        "recipes_tested": len(results),
        "recipes_passed": len(passed),
        "growth_fail": growth_fail,
        "wf_fail": wf_fail,
        "quick_fail": quick_fail,
        "top_results": ranked[:5],
        "near_miss": [r for r in ranked if not r.get("passed")][:3],
        "research_summary": run.get("research_summary") or "",
        "duration_sec": run.get("duration_sec"),
        "errors": run.get("errors") or [],
    }


def build_html_report(summary: dict) -> str:
    target = CREW_DAILY_GROWTH_TARGET_PCT
    passed_n = summary.get("recipes_passed", 0)
    date = summary.get("date", _today())
    rows_html = ""
    for r in summary.get("top_results") or []:
        ok = "EVET" if r.get("passed") else "HAYIR"
        rows_html += (
            f"<tr><td>{r.get('recipe_name', '-')}</td>"
            f"<td>{float(r.get('test_best_day_pct') or 0):.1f}%</td>"
            f"<td>{r.get('days_ge_target', 0)}</td>"
            f"<td>{r.get('test_pf') if r.get('test_pf') is not None else '-'}</td>"
            f"<td>{r.get('test_trades', '-')}</td>"
            f"<td>{float(r.get('max_dd') or 0)*100:.1f}%</td>"
            f"<td>{r.get('best_symbol', '-')}</td>"
            f"<td>{ok}</td></tr>"
        )
    near = summary.get("near_miss") or []
    near_html = ""
    if passed_n == 0 and near:
        near_html = "<h3>Yakin adaylar (%20 altinda)</h3><ul>"
        for r in near:
            near_html += (
                f"<li>{r.get('recipe_name')}: "
                f"{float(r.get('test_best_day_pct') or 0):.1f}% — {r.get('reason')}</li>"
            )
        near_html += "</ul>"

    err_html = ""
    if summary.get("errors"):
        err_html = "<p style='color:#b00'>Hatalar: " + "; ".join(summary["errors"][:5]) + "</p>"

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Krpito Crew {date}</title></head>
<body style="font-family:Segoe UI,Arial,sans-serif;max-width:820px;margin:24px auto">
<h1>Krpito Crew — Gunluk Strateji Raporu</h1>
<p><b>Tarih:</b> {date} | <b>Hedef:</b> kasa +{target:.0f}% / gun</p>
<div style="background:#e8f5e9;padding:16px;border-radius:8px;margin:16px 0">
  <h2 style="margin:0">%20+ aday: {passed_n}</h2>
  <p>Uretilen: {summary.get('recipes_generated', 0)} |
     Test: {summary.get('recipes_tested', 0)} |
     Gecti: {passed_n} |
     growth_fail: {summary.get('growth_fail', 0)} |
     wf_fail: {summary.get('wf_fail', 0)} |
     quick_fail: {summary.get('quick_fail', 0)}</p>
</div>
{err_html}
<table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;width:100%">
<thead><tr>
<th>Strateji</th><th>En iyi gun %</th><th>gun&gt;=20</th><th>Test PF</th>
<th>Trades</th><th>Max DD</th><th>Sembol</th><th>Gecti</th>
</tr></thead>
<tbody>{rows_html or '<tr><td colspan="8">Sonuc yok</td></tr>'}</tbody>
</table>
{near_html}
<p style="color:#666;font-size:12px">Canli paper motoruna bagli degil. crew_state.json</p>
</body></html>"""


def build_subject(summary: dict) -> str:
    date = summary.get("date", _today())
    n = summary.get("recipes_passed", 0)
    return f"Krpito Crew — {n} strateji %{CREW_DAILY_GROWTH_TARGET_PCT:.0f}+ gun | {date}"


def build_csv_attachment(summary: dict) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "recipe_id", "recipe_name", "test_best_day_pct", "days_ge_target",
        "test_pf", "test_trades", "max_dd", "best_symbol", "passed", "reason",
    ])
    for r in summary.get("top_results") or []:
        w.writerow([
            r.get("recipe_id"), r.get("recipe_name"),
            r.get("test_best_day_pct"), r.get("days_ge_target"),
            r.get("test_pf"), r.get("test_trades"), r.get("max_dd"),
            r.get("best_symbol"), r.get("passed"), r.get("reason"),
        ])
    return buf.getvalue().encode("utf-8-sig")
