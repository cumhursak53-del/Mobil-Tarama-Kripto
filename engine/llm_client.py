"""LLM provider abstraction — Gemini (cloud) ve Ollama (local)."""
from __future__ import annotations

import base64
import json
import re
import time
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

from engine.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_MODEL_FALLBACKS,
    GEMINI_QUOTA_COOLDOWN_SEC,
    GEMINI_RESEARCH_FALLBACK_FIRST,
    GEMINI_RETRY_DELAY_SEC,
    GEMINI_RETRY_MAX,
    LLM_PROVIDER,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OLLAMA_VISION_MODEL,
)

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
- {"type":"smc","tf":"4h"|"1h"|"15m","kind":"bos_bull"|"bos_bear"|"choch_bull"|"choch_bear"|"internal_bos_bull"|"external_bos_bull"|"ob_bull_retest"|"ob_bear_retest"|"breaker_bull_retest"|"breaker_bear_retest"|"mitigation_bull"|"mitigation_bear"|"fvg_bull_active"|"fvg_bear_active"|"sweep_bull"|"sweep_bear"|"weak_low_swept"|"weak_high_swept"|"discount"|"premium"|"trend_bull"|"trend_bear"|"smc_score_long"|"smc_score_short","min":5}

Long strateji: long_rules dolu, short_rules bos veya zayif.
Short strateji: short_rules dolu.
Her tarifte en az 2 long veya 2 short kural. Belirsiz metin varsa bos array don.
"""

_genai_client: Any = None
_last_model_used = GEMINI_MODEL if LLM_PROVIDER == "gemini" else OLLAMA_MODEL
_quota_blocked_until: float = 0.0
_ollama_checked_at: float = 0.0
_ollama_available: bool | None = None


def _provider_label() -> str:
    return "Ollama" if LLM_PROVIDER == "ollama" else "Gemini"


def _gemini_key_ok() -> bool:
    return len((GEMINI_API_KEY or "").strip()) > 10


def _ollama_ping() -> bool:
    global _ollama_checked_at, _ollama_available
    now = time.time()
    if _ollama_available is not None and now - _ollama_checked_at < 30:
        return _ollama_available
    try:
        res = http.get(f"{OLLAMA_BASE_URL.rstrip('/')}/api/tags", timeout=4)
        _ollama_available = res.status_code == 200
    except Exception:
        _ollama_available = False
    _ollama_checked_at = now
    return bool(_ollama_available)


def llm_provider() -> str:
    return LLM_PROVIDER


def llm_available() -> bool:
    if LLM_PROVIDER == "ollama":
        return _ollama_ping()
    return _gemini_key_ok()


def llm_usable() -> bool:
    if not llm_available():
        return False
    if LLM_PROVIDER == "ollama":
        return True
    return time.time() >= _quota_blocked_until


def gemini_available() -> bool:
    """Geriye uyum: Ollama modunda Ollama erisilebilirligini dondurur."""
    return llm_available()


def gemini_usable() -> bool:
    return llm_usable()


def _mark_quota_exhausted(log: LogFn | None = None) -> None:
    global _quota_blocked_until
    _quota_blocked_until = time.time() + max(300, GEMINI_QUOTA_COOLDOWN_SEC)
    if log:
        log(
            f"Gemini kota doldu — arastirma {GEMINI_QUOTA_COOLDOWN_SEC // 3600}saat bekletildi "
            f"(tarama devam ediyor)"
        )


def key_format_hint() -> str:
    if LLM_PROVIDER == "ollama":
        return f"ollama ({OLLAMA_MODEL})"
    key = (GEMINI_API_KEY or "").strip()
    if key.startswith("AQ."):
        return "auth (AQ.)"
    if key.startswith("AIza"):
        return "legacy (AIza)"
    return "custom"


def last_model_used() -> str:
    return _last_model_used


def _api_key() -> str:
    return GEMINI_API_KEY.strip()


def _model_chain(*, research: bool = False) -> list[str]:
    primary = GEMINI_MODEL.strip()
    fallbacks = [m for m in GEMINI_MODEL_FALLBACKS if m and m != primary]
    if research and GEMINI_RESEARCH_FALLBACK_FIRST and fallbacks:
        chain = fallbacks + [primary]
    else:
        chain = [primary]
        for model in fallbacks:
            if model not in chain:
                chain.append(model)
    return chain


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


def _error_kind(exc: Exception) -> str:
    msg = str(exc).upper()
    if "401" in msg or "UNAUTHENTICATED" in msg or "ACCESS_TOKEN" in msg:
        return "auth"
    if "404" in msg or "NOT_FOUND" in msg or "NO LONGER AVAILABLE" in msg:
        return "model"
    if "RESOURCE_EXHAUSTED" in msg and (
        "QUOTA" in msg or "EXCEEDED YOUR CURRENT QUOTA" in msg
    ):
        return "quota"
    if any(
        token in msg
        for token in (
            "503",
            "429",
            "500",
            "UNAVAILABLE",
            "HIGH DEMAND",
            "OVERLOADED",
            "TRY AGAIN",
        )
    ):
        return "retry"
    return "fatal"


def _generate_text_ollama(
    *,
    prompt: str,
    json_mode: bool = False,
    model: str | None = None,
    image_bytes: bytes | None = None,
    log: LogFn | None = None,
) -> str:
    global _last_model_used
    use_model = (model or OLLAMA_VISION_MODEL if image_bytes else model or OLLAMA_MODEL).strip()
    msg: dict[str, Any] = {"role": "user", "content": prompt}
    if image_bytes:
        msg["images"] = [base64.b64encode(image_bytes).decode("ascii")]
    payload: dict[str, Any] = {
        "model": use_model,
        "messages": [msg],
        "stream": False,
    }
    if json_mode:
        payload["format"] = "json"
    url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat"
    res = http.post(url, json=payload, timeout=180)
    if res.status_code != 200:
        raise RuntimeError(f"Ollama HTTP {res.status_code}: {res.text[:180]}")
    data = res.json()
    text = (data.get("message") or {}).get("content") or data.get("response") or ""
    text = str(text).strip()
    if not text:
        raise RuntimeError("Ollama bos yanit dondurdu")
    _last_model_used = use_model
    if log and use_model != OLLAMA_MODEL:
        log(f"Ollama model: {use_model}")
    return text


def _generate_text_sdk(*, prompt: str, model: str, json_mode: bool = False) -> str:
    client = _sdk_client()
    config = None
    if json_mode and genai_types is not None:
        config = genai_types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json",
        )
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=config,
    )
    text = (getattr(response, "text", None) or "").strip()
    if text:
        return text
    raise RuntimeError("Gemini bos yanit dondurdu")


def _generate_text_rest(*, prompt: str, model: str, json_mode: bool = False) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
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


def _try_once_gemini(*, prompt: str, model: str, json_mode: bool) -> str:
    errors: list[str] = []
    if genai is not None:
        try:
            return _generate_text_sdk(prompt=prompt, model=model, json_mode=json_mode)
        except Exception as e:
            errors.append(f"SDK: {_format_error(e)}")
            if _error_kind(e) != "retry":
                raise RuntimeError(errors[-1]) from e
    try:
        return _generate_text_rest(prompt=prompt, model=model, json_mode=json_mode)
    except Exception as e:
        errors.append(f"REST: {_format_error(e)}")
        raise RuntimeError(" | ".join(errors)) from e


def _generate_text_gemini(
    *,
    prompt: str,
    json_mode: bool = False,
    log: LogFn | None = None,
    research: bool = False,
) -> str:
    global _last_model_used
    if not llm_usable():
        raise RuntimeError("Gemini kota beklemede")
    errors: list[str] = []

    for model in _model_chain(research=research):
        for attempt in range(max(1, GEMINI_RETRY_MAX)):
            try:
                text = _try_once_gemini(prompt=prompt, model=model, json_mode=json_mode)
                _last_model_used = model
                if model != GEMINI_MODEL and log:
                    log(f"Gemini yedek model: {model}")
                if attempt > 0 and log:
                    log(f"Gemini yeniden deneme basarili ({model}, deneme {attempt + 1})")
                return text
            except Exception as e:
                kind = _error_kind(e)
                err = f"{model}: {_format_error(e)}"
                errors.append(err)

                if kind == "auth":
                    raise RuntimeError(err) from e
                if kind == "quota":
                    _mark_quota_exhausted(log)
                    raise RuntimeError("Gemini kota doldu") from e
                if kind == "model":
                    break
                if kind == "retry" and attempt < GEMINI_RETRY_MAX - 1:
                    wait = GEMINI_RETRY_DELAY_SEC * (2 ** attempt)
                    if log:
                        log(
                            f"Gemini gecici yogunluk ({model}) — "
                            f"{int(wait)}sn sonra yeniden ({attempt + 2}/{GEMINI_RETRY_MAX})"
                        )
                    time.sleep(wait)
                    continue
                break

    raise RuntimeError(" | ".join(errors[-4:]))


def _generate_text(
    *,
    prompt: str,
    json_mode: bool = False,
    log: LogFn | None = None,
    research: bool = False,
) -> str:
    if LLM_PROVIDER == "ollama":
        if not llm_usable():
            raise RuntimeError("Ollama erisilemiyor")
        return _generate_text_ollama(prompt=prompt, json_mode=json_mode, log=log)
    return _generate_text_gemini(prompt=prompt, json_mode=json_mode, log=log, research=research)


def test_llm_connection(log: LogFn | None = None) -> bool:
    if not llm_available():
        return False
    try:
        _generate_text(prompt="OK", json_mode=False, log=log)
        if log:
            log(f"{_provider_label()} baglantisi OK ({key_format_hint()}, model {last_model_used()})")
        return True
    except Exception as e:
        msg = f"{_provider_label()} test basarisiz ({key_format_hint()}): {_format_error(e)}"
        print(msg, flush=True)
        if log:
            log(msg)
        return False


def test_gemini_connection(log: LogFn | None = None) -> bool:
    return test_llm_connection(log=log)


def generate_recipes_from_text(
    *,
    source_label: str,
    title: str,
    body: str,
    max_recipes: int = 3,
    log: LogFn | None = None,
) -> list[dict]:
    if not llm_available():
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
        raw_text = _generate_text(prompt=prompt, json_mode=True, log=log, research=True)
        parsed = _extract_json(raw_text)
        if isinstance(parsed, dict):
            parsed = [parsed]
        if not isinstance(parsed, list):
            return []
        return [r for r in parsed if isinstance(r, dict)][:max_recipes]
    except Exception as e:
        kind = _error_kind(e) if LLM_PROVIDER == "gemini" else "fatal"
        if kind == "quota":
            msg = "Gemini kota doldu — arastirma atlandi (tarama devam ediyor)"
        elif kind == "retry":
            msg = f"{_provider_label()} gecici yogunluk — arastirma atlandi (combinator devam ediyor)"
        else:
            msg = f"{_provider_label()} hatasi ({key_format_hint()}): {_format_error(e)}"
        print(msg, flush=True)
        if log:
            log(msg)
        return []


def suggest_web_queries(
    *,
    already_done: list[str] | None = None,
    limit: int = 2,
    log: LogFn | None = None,
) -> list[str]:
    if not llm_available():
        return []
    done = already_done or []
    prompt = f"""Sen kripto vadeli islem strateji arastirmacisisin.
Asagidaki konularda internette aranacak {limit} farkli Ingilizce arama sorgusu uret.
Sorgular teknik, backtest edilebilir kurallar icermeli (indikator, SMC, yapı, hacim vb.).

Daha once islenmis sorgu hash/id listesi (tekrarlama): {done[:15]}

Cikti: JSON array of strings, ornek: ["query one", "query two"]
Sadece JSON array, baska metin yok.
"""
    try:
        raw_text = _generate_text(prompt=prompt, json_mode=True, log=log, research=True)
        parsed = _extract_json(raw_text)
        if isinstance(parsed, str):
            return [parsed.strip()][:limit]
        if not isinstance(parsed, list):
            return []
        out = []
        for item in parsed:
            if isinstance(item, str) and item.strip():
                out.append(item.strip()[:160])
            elif isinstance(item, dict) and item.get("query"):
                out.append(str(item["query"]).strip()[:160])
            if len(out) >= limit:
                break
        return out
    except Exception as e:
        if log:
            log(f"Web sorgu onerisi hatasi: {_format_error(e)}")
        return []


def generate_smc_commentary(
    *,
    symbol: str,
    timeframe: str,
    analysis: dict,
    log: LogFn | None = None,
) -> str:
    if not llm_available():
        return f"{_provider_label()} erisilemiyor — yorum yapilamiyor."
    prompt = f"""Sen deneyimli bir Smart Money Concepts (SMC) analistsin.
Sembol: {symbol} | Timeframe: {timeframe}

Motor ciktisi (JSON):
{json.dumps(analysis, ensure_ascii=False, indent=2)}

Gorev: Turkce, net ve kisa (5-8 cumle):
1) Mevcut yapı (trend, external/internal olay)
2) Premium/discount/OTE konumu
3) Aktif zone'lar (OB, breaker, FVG, likidite)
4) Long ve short icin olasi senaryo
5) Setup grade ve islem icin dikkat (risk)

Sadece verilen metrikleri kullan; uydurma fiyat veya haber ekleme.
"""
    try:
        return _generate_text(prompt=prompt, json_mode=False, log=log).strip()
    except Exception as e:
        return f"{_provider_label()} yorum hatasi: {_format_error(e)}"


def _generate_vision_gemini(
    *,
    prompt: str,
    image_bytes: bytes,
    log: LogFn | None = None,
) -> str:
    global _last_model_used
    errors: list[str] = []
    for model in _model_chain():
        try:
            if genai is not None and genai_types is not None:
                client = _sdk_client()
                response = client.models.generate_content(
                    model=model,
                    contents=[
                        genai_types.Content(
                            role="user",
                            parts=[
                                genai_types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                                genai_types.Part.from_text(text=prompt),
                            ],
                        )
                    ],
                )
                text = (getattr(response, "text", None) or "").strip()
                if text:
                    _last_model_used = model
                    return text
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            payload = {
                "contents": [{
                    "parts": [
                        {"inline_data": {"mime_type": "image/png", "data": base64.b64encode(image_bytes).decode()}},
                        {"text": prompt},
                    ]
                }]
            }
            res = http.post(url, headers=_gemini_headers(), json=payload, timeout=90)
            if res.status_code != 200:
                raise RuntimeError(f"HTTP {res.status_code}: {res.text[:180]}")
            parts = res.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])
            text = parts[0].get("text", "") if parts else ""
            if text:
                _last_model_used = model
                return text.strip()
            raise RuntimeError("Gemini bos vision yaniti")
        except Exception as e:
            errors.append(f"{model}: {_format_error(e)}")
            if _error_kind(e) == "auth":
                raise
    raise RuntimeError(" | ".join(errors[-3:]))


def _generate_vision(
    *,
    prompt: str,
    image_bytes: bytes,
    log: LogFn | None = None,
) -> str:
    if LLM_PROVIDER == "ollama":
        try:
            return _generate_text_ollama(
                prompt=prompt,
                image_bytes=image_bytes,
                model=OLLAMA_VISION_MODEL,
                log=log,
            )
        except Exception as e:
            if log:
                log(f"Ollama vision basarisiz, metin moduna dusuluyor: {_format_error(e)}")
            return _generate_text_ollama(prompt=prompt, log=log)
    return _generate_vision_gemini(prompt=prompt, image_bytes=image_bytes, log=log)


def generate_smc_vision_commentary(
    *,
    symbol: str,
    timeframe: str,
    analysis: dict,
    image_bytes: bytes,
    log: LogFn | None = None,
) -> str:
    if not llm_available():
        return f"{_provider_label()} erisilemiyor."
    prompt = f"""Sen LuxAlgo SMC uzmanisin. Ekte {symbol} {timeframe} mum grafigi var (OB, FVG, OTE, BOS etiketleri cizili).

Motor metrikleri:
{json.dumps(analysis, ensure_ascii=False, indent=2)}

Gorev — Turkce, 6-10 cumle:
1) Grafikte gordugun yapı (BOS/CHoCH, zone'lar)
2) Premium/discount/OTE konumu
3) Long ve short senaryo + hangi grade (A/B/C) mantikli
4) Risk ve invalidation seviyesi

Grafik + metrikleri birlikte kullan; uydurma haber ekleme.
"""
    try:
        return _generate_vision(prompt=prompt, image_bytes=image_bytes, log=log)
    except Exception as e:
        return f"{_provider_label()} vision hatasi: {_format_error(e)}"


def generate_narrative_summary(*, brief: str, results: list[dict], log: LogFn | None = None) -> str:
    """Crew pipeline icin kisa Turkce ozet (CrewAI yerine dogrudan LLM)."""
    if not llm_available():
        return ""
    top = results[:3]
    prompt = (
        f"Backtest sonuclarini Turkce 3-5 cumle ile ozetle.\n"
        f"Arastirma: {brief[:2000]}\nSonuclar: {json.dumps(top, ensure_ascii=False)[:3000]}"
    )
    try:
        return _generate_text(prompt=prompt, json_mode=False, log=log).strip()
    except Exception as e:
        if log:
            log(f"Narrative ozet atlandi: {_format_error(e)}")
        return ""
