"""Kripto haber RSS arastirmasi + Gemini tarif cikarimi."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Optional

try:
    from curl_cffi import requests as http
except Exception:
    import requests as http

from engine.config import NEWS_MAX_HEADLINES, NEWS_RSS_URLS
from engine.gemini_client import generate_recipes_from_text, gemini_available
from engine.recipe_validator import validate_recipes
from engine.youtube_research import _research_meta


def _fetch(url: str, timeout: int = 15) -> Optional[str]:
    try:
        r = http.get(url, timeout=timeout, headers={"User-Agent": "KrpitoResearch/1.0"})
        if r.status_code == 200:
            return r.text
    except Exception:
        pass
    return None


def _parse_rss(xml: str, limit: int) -> list[tuple[str, str]]:
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return []
    items = root.findall(".//item")
    if not items:
        items = root.findall(".//{http://www.w3.org/2005/Atom}entry")
    out = []
    for item in items[:limit]:
        title = ""
        desc = ""
        t = item.find("title")
        if t is not None and t.text:
            title = t.text.strip()
        d = item.find("description") or item.find("{http://www.w3.org/2005/Atom}summary")
        if d is not None and d.text:
            desc = d.text.strip()[:500]
        link_el = item.find("link")
        link = link_el.text if link_el is not None and link_el.text else ""
        if not title and link:
            title = link
        if title:
            out.append((title, desc))
    return out


def _news_batch_key(headlines: list[tuple[str, str]]) -> str:
    import hashlib
    blob = "|".join(t[0] for t in headlines[:10])
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def collect_news_recipes(state: dict, *, log=None) -> list[dict]:
    if not gemini_available():
        return []
    meta = _research_meta(state)
    processed_batches = set(meta.get("processed_news_batches") or [])

    headlines: list[tuple[str, str]] = []
    for url in NEWS_RSS_URLS:
        xml = _fetch(url)
        if xml:
            headlines.extend(_parse_rss(xml, NEWS_MAX_HEADLINES // max(1, len(NEWS_RSS_URLS))))

    if not headlines:
        return []

    batch_key = _news_batch_key(headlines)
    if batch_key in processed_batches:
        return []

    body_lines = []
    for i, (title, desc) in enumerate(headlines[:NEWS_MAX_HEADLINES], 1):
        body_lines.append(f"{i}. {title}")
        if desc:
            body_lines.append(f"   {desc}")
    body = "\n".join(body_lines)

    raw = generate_recipes_from_text(
        source_label="kripto haber akisi (sentiment ve trend filtresi olarak yorumla)",
        title="Son kripto haberleri",
        body=body,
        max_recipes=3,
    )
    valid = validate_recipes(raw, source=f"news:{batch_key}")
    if valid and log:
        log(f"Haber batch {batch_key}: {len(valid)} tarif")

    processed_batches.add(batch_key)
    meta["processed_news_batches"] = list(processed_batches)[-200:]
    from engine.lab_state import now_tr
    meta["last_news_at"] = now_tr()
    meta["news_recipes"] = int(meta.get("news_recipes") or 0) + len(valid)
    return valid
