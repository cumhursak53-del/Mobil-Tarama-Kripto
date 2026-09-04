from __future__ import annotations

import base64
import json
import time
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
        res = http.get(_contents_url(path) + f"?ref={GITHUB_BRANCH}", headers=_headers(), timeout=15)
        if res.status_code != 200:
            print(f"GitHub pull {path}: HTTP {res.status_code}", flush=True)
            return None
        content = res.json().get("content") or ""
        if not content:
            return None
        return json.loads(base64.b64decode(content).decode("utf-8"))
    except Exception as e:
        print(f"GitHub pull hatasi ({path}): {e}", flush=True)
        return None


def push_json(
    data: dict,
    path: str = GITHUB_STATE_PATH,
    message: str = "Auto update state [MTF Engine]",
    retries: int = 3,
) -> bool:
    if not GITHUB_TOKEN:
        print("GitHub push atlandi: GITHUB_TOKEN yok", flush=True)
        return False
    payload = json.dumps(data, indent=2).encode("utf-8")
    for attempt in range(retries):
        try:
            res = http.get(_contents_url(path) + f"?ref={GITHUB_BRANCH}", headers=_headers(), timeout=15)
            sha = res.json().get("sha", "") if res.status_code == 200 else ""
            body = {
                "message": message,
                "content": base64.b64encode(payload).decode("utf-8"),
                "branch": GITHUB_BRANCH,
            }
            if sha:
                body["sha"] = sha
            put = http.put(_contents_url(path), headers=_headers(), json=body, timeout=20)
            if put.status_code in (200, 201):
                return True
            print(f"GitHub push {path}: HTTP {put.status_code} (deneme {attempt + 1})", flush=True)
            if put.status_code == 409:
                time.sleep(0.5)
                continue
        except Exception as e:
            print(f"GitHub push hatasi ({path}): {e}", flush=True)
        time.sleep(0.5)
    return False


def pull_state() -> Optional[dict]:
    return pull_json(GITHUB_STATE_PATH)


def push_state(data: dict) -> bool:
    return push_json(data, GITHUB_STATE_PATH)
