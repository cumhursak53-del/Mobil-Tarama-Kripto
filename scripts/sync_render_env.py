#!/usr/bin/env python3
"""render.env dosyasini Render Worker servisine uygular."""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / "render.env"
SERVICE_NAME = os.environ.get("RENDER_SERVICE_NAME", "mobil-tarama-kripto")
API_BASE = "https://api.render.com/v1"


def _load_render_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if key:
            out[key] = val
    return out


def _api(method: str, path: str, api_key: str, body: dict | list | None = None) -> object:
    url = f"{API_BASE}{path}"
    data = None
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def _find_service(api_key: str) -> dict:
    rows = _api("GET", "/services?limit=100", api_key)
    if not isinstance(rows, list):
        raise RuntimeError("Render servis listesi alinamadi")
    for row in rows:
        svc = row.get("service") or {}
        name = svc.get("name") or ""
        details = svc.get("serviceDetails") or {}
        url = details.get("url") or ""
        if name == SERVICE_NAME or SERVICE_NAME in url:
            return svc
    raise RuntimeError(f"Render servisi bulunamadi: {SERVICE_NAME}")


def sync(*, deploy: bool = False) -> None:
    api_key = (os.environ.get("RENDER_API_KEY") or "").strip()
    if not api_key:
        msg = (
            "RENDER_API_KEY tanimli degil.\n"
            "GitHub -> Settings -> Secrets and variables -> Actions -> New repository secret\n"
            "  Ad: RENDER_API_KEY\n"
            "  Deger: Render Dashboard -> Account Settings -> API Keys -> Create (rnd_...)\n"
            "Sonra Actions -> Sync Render env -> Re-run workflow"
        )
        print(msg, file=sys.stderr)
        sys.exit(0 if os.environ.get("GITHUB_ACTIONS") != "true" else 1)

    file_vars = _load_render_env(ENV_FILE)
    if not file_vars:
        print(f"render.env bos veya yok: {ENV_FILE}", file=sys.stderr)
        sys.exit(1)

    gemini = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if gemini:
        file_vars["GEMINI_API_KEY"] = gemini

    svc = _find_service(api_key)
    sid = svc["id"]
    print(f"Servis: {svc.get('name')} ({sid})")

    existing_rows = _api("GET", f"/services/{sid}/env-vars", api_key)
    merged: dict[str, str] = {}
    if isinstance(existing_rows, list):
        for row in existing_rows:
            ev = row.get("envVar") or {}
            k = ev.get("key")
            if k:
                merged[k] = ev.get("value") or ""

    merged.update(file_vars)
    payload = [{"key": k, "value": v} for k, v in sorted(merged.items())]
    _api("PUT", f"/services/{sid}/env-vars", api_key, payload)
    print(f"Env guncellendi: {len(file_vars)} dosya + mevcut birlestirme (toplam {len(payload)})")

    if deploy:
        _api("POST", f"/services/{sid}/deploys", api_key, {})
        print(f"Deploy tetiklendi: https://{SERVICE_NAME}.onrender.com")


def main() -> None:
    p = argparse.ArgumentParser(description="render.env -> Render Worker")
    p.add_argument("--deploy", action="store_true", help="Env sonrasi deploy tetikle")
    args = p.parse_args()
    try:
        sync(deploy=args.deploy)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        print(f"Render API hatasi HTTP {e.code}: {body}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Hata: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
