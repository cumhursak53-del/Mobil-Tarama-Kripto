"""Gemini API — transkript/haber metninden StrategyRecipe JSON."""
from __future__ import annotations

import json
import re
from typing import Any, Callable, Optional

try:
    from curl_cffi import requests as http
except Exception:
    import requests as http

from engine.config import GEMINI_API_KEY, GEMINI_MODEL

LogFn = Callable[[str], None]

RECIPE_SCHEMA_HINT = """
Cikti: JSON array (en fazla 3 tarif). Her tarif:
{
  "name": "kisa_isim",
  "min_votes": 2,
  "require_aligned": true,
  "long_rules": [...],
  "short_rules": [...]
}

Kural tipleri (SADECE bunlar):
- {"type":"stage","value":"advancing"|"declining"|"accumulation"|"distribution"}
- {"type":"week_bias","value":1|-1|0}
- {"type":"volume","tf":"1h"|"4h"}
- {"type":"structure","tf":"4h"|"1h","kind":"bos_high"|"bos_low"|"squeeze"|"hh_hl"|"lh_ll"}
- {"type":"indicator","tf":"1h"|"4h","field":"macd_cross_up"|"macd_cross_down"|"stoch_cross_up"|"stoch_cross_down"|"stochrsi_cross_up"|"stochrsi_cross_down"|"cci_cross_up"|"cci_cross_down"|"tenkan_cross_up"|"tenkan_cross_down","extra":""|"k_lt_25"|"k_gt_75"|"rsi_lt_45"|"rsi_gt_55"|"hist_pos"|"hist_neg"|"cci_lt_100"|"cci_gt_-100"}
- {"type":"momentum_score","side":"long"|"short","min":4}

Long strateji: long_rules dolu, short_rules bos veya zayif.
Short strateji: short_rules dolu.
Her tarifte en az 2 long veya 2 short kural. Belirsiz metin varsa bos array don.
"""


def gemini_available() -> bool:
    key = (GEMINI_API_KEY or "").strip()
    return len(key) > 10


def key_format_hint() -> str:
    key = (GEMINI_API_KEY or "").strip()
    if key.startswith("AQ."):
        return "auth (AQ.)"
    if key.startswith("AIza"):
        return "legacy (AIza)"
    return "custom"


def _gemini_headers() -> dict:
    """AQ. auth key ve AIza legacy key — native endpoint icin x-goog-api-key."""
    return {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY.strip(),
    }


def _extract_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\[[\s\S]*\]", text)
        if m:
            return json.loads(m.group(0))
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            return json.loads(m.group(0))
        raise


def test_gemini_connection(log: LogFn | None = None) -> bool:
    if not gemini_available():
        return False
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    try:
        res = http.post(
            url,
            headers=_gemini_headers(),
            json={"contents": [{"parts": [{"text": "OK"}]}]},
            timeout=20,
        )
        ok = res.status_code == 200
        if not ok:
            msg = f"Gemini test HTTP {res.status_code} ({key_format_hint()}): {res.text[:180]}"
            print(msg, flush=True)
            if log:
                log(msg)
        elif log:
            log(f"Gemini baglantisi OK ({key_format_hint()}, model {GEMINI_MODEL})")
        return ok
    except Exception as e:
        msg = f"Gemini test hatasi: {e}"
        print(msg, flush=True)
        if log:
            log(msg)
        return False


def generate_recipes_from_text(
    *,
    source_label: str,
    title: str,
    body: str,
    max_recipes: int = 3,
    log: LogFn | None = None,
) -> list[dict]:
    if not gemini_available():
        return []
    prompt = f"""Sen kripto vadeli islem strateji muhendisisin. Asagidaki {source_label} metninden
backtest edilebilir kurallar cikar. Sadece desteklenen kural tiplerini kullan.
Tahmin veya garanti ifade etme. Net teknik kural yoksa bos array [] don.

Baslik: {title}

Metin:
{body[:12000]}

{RECIPE_SCHEMA_HINT}

En fazla {max_recipes} tarif. JSON array only.
"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    try:
        res = http.post(
            url,
            headers=_gemini_headers(),
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.2,
                    "responseMimeType": "application/json",
                },
            },
            timeout=60,
        )
        if res.status_code != 200:
            msg = f"Gemini HTTP {res.status_code} ({key_format_hint()}): {res.text[:200]}"
            print(msg, flush=True)
            if log:
                log(msg)
            return []
        data = res.json()
        parts = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])
        )
        raw_text = parts[0].get("text", "") if parts else ""
        if not raw_text:
            return []
        parsed = _extract_json(raw_text)
        if isinstance(parsed, dict):
            parsed = [parsed]
        if not isinstance(parsed, list):
            return []
        return [r for r in parsed if isinstance(r, dict)][:max_recipes]
    except Exception as e:
        if log:
            log(f"Gemini parse hatasi: {e}")
        return []
