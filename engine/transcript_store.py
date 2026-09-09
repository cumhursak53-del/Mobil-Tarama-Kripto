"""Onceden indirilmis YouTube transkriptleri — Render IP engelini asmak icin."""
from __future__ import annotations

import json
import os

TRANSCRIPT_DIR = os.environ.get("TRANSCRIPT_DIR", "research/transcripts")


def load_transcript(video_id: str) -> str | None:
    if not video_id:
        return None
    base = os.path.join(TRANSCRIPT_DIR, video_id)
    for ext in (".txt", ".json"):
        path = base + ext
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = f.read().strip()
        except OSError:
            continue
        if ext == ".json":
            try:
                data = json.loads(raw)
                if isinstance(data, dict):
                    text = data.get("text") or data.get("transcript") or ""
                    return str(text).strip() or None
            except json.JSONDecodeError:
                pass
        if len(raw) >= 80:
            return raw
    return None
