"""Gemini API — transkript/haber metninden StrategyRecipe JSON."""
from __future__ import annotations

import json
import re
from typing import Any, Callable

try:
    from google import genai
    from google.genai import types as genai_types
except Exception:
    genai = None  # type: ignore[assignment]
    genai_types = None  # type: ignore[assignment]

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

_genai_client: Any = None


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


def _api_key() -> str:
    return GEMINI_API_KEY.strip()


def _sdk_client() -> Any:
    global _genai_client
    if genai is None:
        raise RuntimeError("google-genai paketi yuklu degil")
    if _genai_client is None:
        _genai_client = genai.Client(api_key=_api_key())
    return _genai_client


def _gemini_headers() -> dict:
    return {
        "Content-Type": "application/json",
        "x-goog-api-key": _api_key(),
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


def _format_error(exc: Exception) -> str:
    msg = str(exc).strip()
    return msg[:220] if msg else exc.__class__.__name__


def _generate_text_sdk(*, prompt: str, json_mode: bool = False) -> str:
    client = _sdk_client()
    config = None
    if json_mode and genai_types is not None:
        config = genai_types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json",
        )
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=config,
    )
    text = (getattr(response, "text", None) or "").strip()
    if text:
        return text
    raise RuntimeError("Gemini bos yanit dondurdu")


def _generate_text_rest(*, prompt: str, json_mode: bool = False) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    payload: dict[str, Any] = {"contents": [{"parts": [{"text": prompt}]}]}
    if json_mode:
        payload["generationConfig"] = {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        }
    res = http.post(url, headers=_gemini_headers(), json=payload, timeout=60)
    if res.status_code != 200:
        raise RuntimeError(f"HTTP {res.status_code}: {res.text[:180]}")
    data = res.json()
    parts = (
        data.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])
    )
    text = parts[0].get("text", "") if parts else ""
    if not text:
        raise RuntimeError("Gemini bos yanit dondurdu")
    return text


def _generate_text(*, prompt: str, json_mode: bool = False) -> str:
    """AQ. key icin once resmi SDK; basarisizsa REST fallback."""
    errors: list[str] = []
    if genai is not None:
        try:
            return _generate_text_sdk(prompt=prompt, json_mode=json_mode)
        except Exception as e:
            errors.append(f"SDK: {_format_error(e)}")
    try:
        return _generate_text_rest(prompt=prompt, json_mode=json_mode)
    except Exception as e:
        errors.append(f"REST: {_format_error(e)}")
    raise RuntimeError(" | ".join(errors))


def test_gemini_connection(log: LogFn | None = None) -> bool:
    if not gemini_available():
        return False
    try:
        _generate_text(prompt="OK", json_mode=False)
        if log:
            log(f"Gemini baglantisi OK ({key_format_hint()}, model {GEMINI_MODEL})")
        return True
    except Exception as e:
        msg = f"Gemini test basarisiz ({key_format_hint()}): {_format_error(e)}"
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
    try:
        raw_text = _generate_text(prompt=prompt, json_mode=True)
        parsed = _extract_json(raw_text)
        if isinstance(parsed, dict):
            parsed = [parsed]
        if not isinstance(parsed, list):
            return []
        return [r for r in parsed if isinstance(r, dict)][:max_recipes]
    except Exception as e:
        msg = f"Gemini hatasi ({key_format_hint()}): {_format_error(e)}"
        print(msg, flush=True)
        if log:
            log(msg)
        return []
