"""Web arama ve sayfa metni cekme (API key gerektirmez)."""
from __future__ import annotations

import re
from html import unescape
from typing import Optional
from urllib.parse import urlparse

try:
    from curl_cffi import requests as http
except Exception:
    import requests as http  # type: ignore[no-redef]

_USER_AGENT = "Mozilla/5.0 (compatible; KrpitoResearch/1.0; +https://github.com/cumhursak53-del/Mobil-Tarama-Kripto)"
_BLOCK_HOSTS = ("localhost", "127.0.0.1", "0.0.0.0", "169.254.", "10.", "192.168.")


def _safe_url(url: str) -> Optional[str]:
    u = (url or "").strip()
    if not u.startswith(("http://", "https://")):
        return None
    host = (urlparse(u).hostname or "").lower()
    if not host or any(host == b or host.startswith(b) for b in _BLOCK_HOSTS):
        return None
    return u


def search_web(query: str, *, max_results: int = 5, timeout: int = 15) -> list[dict]:
    """DuckDuckGo HTML arama — title, url, snippet."""
    q = (query or "").strip()
    if not q:
        return []
    try:
        r = http.post(
            "https://html.duckduckgo.com/html/",
            data={"q": q},
            headers={"User-Agent": _USER_AGENT},
            timeout=timeout,
        )
        if r.status_code != 200:
            return []
        html = r.text
    except Exception:
        return []

    out: list[dict] = []
    seen: set[str] = set()
    blocks = re.split(r'<div class="result results_links', html)
    for block in blocks[1:]:
        m_url = re.search(r'class="result__a"[^>]*href="([^"]+)"', block)
        m_title = re.search(r'class="result__a"[^>]*>([^<]+)</a>', block)
        m_snip = re.search(r'class="result__snippet"[^>]*>([\s\S]*?)</(?:a|td|div)>', block)
        if not m_url:
            continue
        url = _safe_url(unescape(m_url.group(1)))
        if not url or url in seen:
            continue
        title = unescape(re.sub(r"<[^>]+>", " ", m_title.group(1) if m_title else url)).strip()
        snippet = ""
        if m_snip:
            snippet = unescape(re.sub(r"<[^>]+>", " ", m_snip.group(1))).strip()
        seen.add(url)
        out.append({"title": title[:200], "url": url, "snippet": snippet[:500]})
        if len(out) >= max_results:
            break
    return out


def _html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?is)<!--.*?-->", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fetch_page_text(url: str, *, max_chars: int = 8000, timeout: int = 15) -> str:
    safe = _safe_url(url)
    if not safe:
        return ""
    try:
        r = http.get(safe, timeout=timeout, headers={"User-Agent": _USER_AGENT})
        if r.status_code != 200:
            return ""
        ctype = (r.headers.get("content-type") or "").lower()
        if "html" not in ctype and "text" not in ctype:
            return ""
        text = _html_to_text(r.text)
        return text[:max_chars]
    except Exception:
        return ""


def build_research_document(query: str, hits: list[dict], *, fetch_pages: int = 2) -> str:
    """Arama sonuclari + secili sayfa metinlerini Gemini icin birlestir."""
    lines = [f"Arama sorgusu: {query}", ""]
    for i, hit in enumerate(hits, 1):
        lines.append(f"--- Sonuc {i} ---")
        lines.append(f"Baslik: {hit.get('title', '')}")
        lines.append(f"URL: {hit.get('url', '')}")
        if hit.get("snippet"):
            lines.append(f"Ozet: {hit['snippet']}")
        lines.append("")

    fetched = 0
    for hit in hits:
        if fetched >= fetch_pages:
            break
        body = fetch_page_text(hit.get("url", ""), max_chars=6000)
        if len(body) < 200:
            continue
        fetched += 1
        lines.append(f"--- Sayfa {fetched}: {hit.get('title', '')} ---")
        lines.append(body)
        lines.append("")
    return "\n".join(lines)[:18000]
