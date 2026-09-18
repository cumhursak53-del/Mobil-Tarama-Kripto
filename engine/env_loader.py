"""Repo kokundeki local.env ve render.env dosyalarini baslangicta yukler."""
from __future__ import annotations

import os
from pathlib import Path

_SKIP_FROM_FILE = frozenset({
    "GEMINI_API_KEY",
    "GITHUB_TOKEN",
    "RENDER_API_KEY",
    "BYBIT_API_KEY",
    "BYBIT_API_SECRET",
})


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_env_file(path: Path, *, override: bool) -> int:
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


def load_local_env(*, override: bool = True) -> int:
    """local.env -> os.environ (masaustu / Ollama gelistirme)."""
    return _load_env_file(_repo_root() / "local.env", override=override)


def load_render_env(*, override: bool = True) -> int:
    """render.env -> os.environ. GEMINI/GITHUB token dosyadan okunmaz."""
    return _load_env_file(_repo_root() / "render.env", override=override)


def load_live_env(*, override: bool = True) -> int:
    """live.env -> os.environ (Bybit canli motor)."""
    return _load_env_file(_repo_root() / "live.env", override=override)


def bootstrap_env(*, live: bool = False) -> None:
    """local.env (varsa) sonra render.env yukler; live=True ise live.env."""
    load_local_env(override=True)
    if live:
        load_live_env(override=True)
    load_render_env(override=True)
