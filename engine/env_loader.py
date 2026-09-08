"""Repo kokundeki render.env dosyasini baslangicta yukler."""
from __future__ import annotations

import os
from pathlib import Path

_SKIP_FROM_FILE = frozenset({"GEMINI_API_KEY", "GITHUB_TOKEN", "RENDER_API_KEY"})


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_render_env(*, override: bool = True) -> int:
    """render.env -> os.environ. GEMINI/GITHUB token dosyadan okunmaz."""
    path = _repo_root() / "render.env"
    if not path.is_file():
        return 0
    n = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip()
        if not key or key in _SKIP_FROM_FILE:
            continue
        if override or key not in os.environ:
            os.environ[key] = val
            n += 1
    return n


def bootstrap_env() -> None:
    load_render_env(override=True)
