"""YouTube RSS + transkript arastirmasi."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Optional

try:
    from curl_cffi import requests as http
except Exception:
    import requests as http

from engine.config import YOUTUBE_CHANNEL_IDS, YOUTUBE_MAX_VIDEOS_PER_RUN, YOUTUBE_VIDEO_IDS
from engine.gemini_client import generate_recipes_from_text, gemini_available
from engine.recipe_validator import validate_recipes

_NS = {"atom": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}


def _research_meta(state: dict) -> dict:
    return state.setdefault(
        "research",
        {
            "processed_videos": [],
            "last_youtube_at": "",
            "last_news_at": "",
            "youtube_recipes": 0,
            "news_recipes": 0,
        },
    )


def _fetch(url: str, timeout: int = 15) -> Optional[str]:
    try:
        r = http.get(url, timeout=timeout, headers={"User-Agent": "KrpitoResearch/1.0"})
        if r.status_code == 200:
            return r.text
    except Exception:
        pass
    return None


def _resolve_handle(handle: str) -> Optional[str]:
    h = handle.strip().lstrip("@")
    if h.startswith("UC") and len(h) >= 20:
        return h
    html = _fetch(f"https://www.youtube.com/@{h}")
    if not html:
        return None
    m = re.search(r'"channelId":"(UC[a-zA-Z0-9_-]{20,})"', html)
    if m:
        return m.group(1)
    m = re.search(r"channel_id=(UC[a-zA-Z0-9_-]{20,})", html)
    return m.group(1) if m else None


def _video_ids_from_rss(channel_id: str, limit: int) -> list[tuple[str, str]]:
    xml = _fetch(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}")
    if not xml:
        return []
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return []
    out = []
    for entry in root.findall("atom:entry", _NS):
        vid_el = entry.find("yt:videoId", _NS)
        title_el = entry.find("atom:title", _NS)
        if vid_el is None or not vid_el.text:
            continue
        title = title_el.text if title_el is not None else vid_el.text
        out.append((vid_el.text, title or vid_el.text))
        if len(out) >= limit:
            break
    return out


def _get_transcript(video_id: str) -> Optional[str]:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

        for langs in (["tr"], ["tr", "en"], ["en"]):
            try:
                chunks = YouTubeTranscriptApi.get_transcript(video_id, languages=langs)
                return " ".join(c["text"] for c in chunks if c.get("text"))
            except (TranscriptsDisabled, NoTranscriptFound):
                continue
        chunks = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join(c["text"] for c in chunks if c.get("text"))
    except Exception:
        return None


def collect_youtube_recipes(state: dict, *, log=None) -> list[dict]:
    if not gemini_available():
        return []
    meta = _research_meta(state)
    processed = set(meta.get("processed_videos") or [])
    candidates: list[tuple[str, str]] = []

    for vid in YOUTUBE_VIDEO_IDS:
        if vid and vid not in processed:
            candidates.append((vid, f"video_{vid}"))

    per_channel = max(1, YOUTUBE_MAX_VIDEOS_PER_RUN // max(1, len(YOUTUBE_CHANNEL_IDS) or 1))
    for ch in YOUTUBE_CHANNEL_IDS:
        cid = _resolve_handle(ch) if not ch.startswith("UC") else ch
        if not cid:
            if log:
                log(f"YouTube kanal cozulemedi: {ch}")
            continue
        for vid, title in _video_ids_from_rss(cid, per_channel):
            if vid not in processed:
                candidates.append((vid, title))

    recipes: list[dict] = []
    seen_ids = set()
    for vid, title in candidates[:YOUTUBE_MAX_VIDEOS_PER_RUN]:
        if vid in seen_ids:
            continue
        seen_ids.add(vid)
        text = _get_transcript(vid)
        if not text or len(text) < 80:
            processed.add(vid)
            continue
        raw = generate_recipes_from_text(
            source_label="YouTube teknik analiz videosu",
            title=title,
            body=text,
            max_recipes=2,
            log=log,
        )
        valid = validate_recipes(raw, source=f"youtube:{vid}")
        if valid:
            for r in valid:
                r["source_ref"] = {"video_id": vid, "title": title[:120]}
            recipes.extend(valid)
            if log:
                log(f"YouTube {vid}: {len(valid)} tarif uretildi")
        processed.add(vid)

    meta["processed_videos"] = list(processed)[-500:]
    if candidates:
        from engine.lab_state import now_tr
        meta["last_youtube_at"] = now_tr()
    meta["youtube_recipes"] = int(meta.get("youtube_recipes") or 0) + len(recipes)
    return recipes
