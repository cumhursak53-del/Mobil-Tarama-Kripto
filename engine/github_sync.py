from __future__ import annotations

import base64
import json
from typing import Optional

from engine.config import GITHUB_BRANCH, GITHUB_REPO, GITHUB_STATE_PATH, GITHUB_TOKEN

try:
    from curl_cffi import requests as http
except Exception:
    import requests as http


def _headers() -> dict:
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "KrpitoMTF-Engine",
    }


def _contents_url(path: str) -> str:
    return f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"


def pull_json(path: str = GITHUB_STATE_PATH) -> Optional[dict]:
    if not GITHUB_TOKEN:
        return None
    try:
        res = http.get(_contents_url(path) + f"?ref={GITHUB_BRANCH}", headers=_headers(), timeout=12)
        if res.status_code != 200:
            return None
        content = res.json().get("content") or ""
        if not content:
            return None
        return json.loads(base64.b64decode(content).decode("utf-8"))
    except Exception:
        return None


def push_json(data: dict, path: str = GITHUB_STATE_PATH, message: str = "Auto update state [MTF Engine]") -> None:
    if not GITHUB_TOKEN:
        return
    try:
        res = http.get(_contents_url(path) + f"?ref={GITHUB_BRANCH}", headers=_headers(), timeout=12)
        sha = res.json().get("sha", "") if res.status_code == 200 else ""
        body = {
            "message": message,
            "content": base64.b64encode(json.dumps(data, indent=2).encode("utf-8")).decode("utf-8"),
            "branch": GITHUB_BRANCH,
        }
        if sha:
            body["sha"] = sha
        http.put(_contents_url(path), headers=_headers(), json=body, timeout=15)
    except Exception as e:
        print(f"GitHub sync hatasi ({path}): {e}", flush=True)


def pull_state() -> Optional[dict]:
    return pull_json(GITHUB_STATE_PATH)


def push_state(data: dict) -> None:
    push_json(data, GITHUB_STATE_PATH)
