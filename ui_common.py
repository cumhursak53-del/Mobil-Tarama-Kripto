"""Streamlit ortak veri yukleme ve yenileme kontrolleri."""
from __future__ import annotations

import base64
import io
import json
import os
import sys
from datetime import datetime
from typing import Optional

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pandas as pd
import streamlit as st

try:
    import requests
except Exception:
    requests = None

ENGINE_URL = os.environ.get("ENGINE_URL", "https://mobil-tarama-kripto.onrender.com").rstrip("/")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "cumhursak53-del/Mobil-Tarama-Kripto")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")
STATE_FILE = os.environ.get("STATE_FILE", "state.json")


def _get_json(url: str, headers: Optional[dict] = None, timeout: int = 12):
    if requests is None:
        return None
    try:
        r = requests.get(url, headers=headers or {}, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception:
        return None
    return None


@st.cache_data(ttl=8, show_spinner=False)
def load_data(force_version: int = 0) -> dict:
    del force_version
    if ENGINE_URL:
        data = _get_json(ENGINE_URL)
        if data:
            data["_source"] = f"Render {ENGINE_URL}"
            return data
    local_api = _get_json("http://127.0.0.1:10000", timeout=2)
    if local_api:
        local_api["_source"] = "localhost:10000"
        return local_api
    if GITHUB_TOKEN and requests is not None:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/state.json?ref={GITHUB_BRANCH}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "KrpitoMTF-UI",
        }
        raw = _get_json(url, headers=headers)
        if raw and raw.get("content"):
            try:
                data = json.loads(base64.b64decode(raw["content"]).decode("utf-8"))
                data["_source"] = "GitHub API"
                return data
            except Exception:
                pass
    raw_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/state.json"
    data = _get_json(raw_url)
    if data:
        data["_source"] = "GitHub raw"
        return data
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["_source"] = "local state.json"
            return data
        except Exception:
            pass
    return {
        "ledgers": {},
        "active_positions": {},
        "history": [],
        "signal_log": {},
        "patlama_selale_scan": {},
        "engine_logs": [],
        "equity": 0.0,
        "balance": 0.0,
        "_source": "veri yok",
    }


def setup_page(title: str, icon: str = "📈") -> dict:
    st.set_page_config(page_title=title, page_icon=icon, layout="wide")
    if "refresh_version" not in st.session_state:
        st.session_state.refresh_version = 0
    if "auto_refresh" not in st.session_state:
        st.session_state.auto_refresh = False
    if "refresh_sec" not in st.session_state:
        st.session_state.refresh_sec = 60
    return render_sidebar_refresh()


def render_sidebar_refresh() -> dict:
    with st.sidebar:
        st.subheader("Yenileme")
        st.session_state.auto_refresh = st.toggle(
            "Otomatik yenile",
            value=st.session_state.auto_refresh,
            help="Kapali: tablo donuk kalir, rahat incelersin.",
        )
        st.session_state.refresh_sec = st.selectbox(
            "Aralik (sn)",
            options=[30, 60, 120, 300],
            index=[30, 60, 120, 300].index(st.session_state.refresh_sec)
            if st.session_state.refresh_sec in [30, 60, 120, 300]
            else 1,
            disabled=not st.session_state.auto_refresh,
        )
        if st.button("Simdi yenile", use_container_width=True):
            st.session_state.refresh_version += 1
            st.cache_data.clear()
            st.rerun()
        st.caption(
            "Otomatik yenileme kapaliysa veri sabit kalir. "
            "Incelemeyi bitirince acip yenileyebilirsin."
        )

    if st.session_state.auto_refresh:
        st_autorefresh = getattr(st, "autorefresh", None)
        if st_autorefresh:
            st_autorefresh(interval=int(st.session_state.refresh_sec) * 1000, key="live_refresh")

    return load_data(force_version=st.session_state.refresh_version)


def _pos_rows(active: dict) -> pd.DataFrame:
    rows = []
    for key, p in (active or {}).items():
        if not isinstance(p, dict):
            continue
        rows.append({
            "Sembol": p.get("symbol", key),
            "Kasa": p.get("ledger_name", "-"),
            "Yon": p.get("side"),
            "Giris": p.get("entry_price"),
            "Anlik": p.get("current_price"),
            "SL": p.get("sl_price"),
            "TP": p.get("tp_price"),
            "ROE_%": p.get("roe_pct"),
            "Acik_PnL": p.get("unrealized_pnl"),
            "Marjin": p.get("margin"),
            "Kaldirac": p.get("leverage"),
            "Notional": p.get("notional"),
            "Strateji": p.get("strategy"),
            "Giris_zamani": p.get("entry_time"),
        })
    return pd.DataFrame(rows)


def _ledger_rows(ledgers: dict) -> pd.DataFrame:
    start = 100.0
    rows = [{"Kasa": k, "Bakiye": v, "PnL": float(v) - start} for k, v in (ledgers or {}).items()]
    return pd.DataFrame(rows)


def _history_rows(history: list) -> pd.DataFrame:
    if not history:
        return pd.DataFrame()
    df = pd.DataFrame(history)
    rename = {
        "exit_time": "Cikis_zamani",
        "entry_time": "Giris_zamani",
        "symbol": "Sembol",
        "ledger": "Kasa",
        "side": "Yon",
        "entry": "Giris",
        "exit": "Cikis",
        "pnl": "PnL",
        "r": "R",
        "close_reason": "Neden",
        "strategy": "Strateji",
        "new_balance": "Yeni_bakiye",
    }
    return df.rename(columns={k: v for k, v in rename.items() if k in df.columns})


def _signal_rows(sig_log: dict) -> pd.DataFrame:
    rows = []
    for sym, s in (sig_log or {}).items():
        if not isinstance(s, dict):
            continue
        strats = s.get("strategies") or []
        if isinstance(strats, list):
            strats = " | ".join(str(x) for x in strats)
        rows.append({
            "Sembol": sym,
            "Sinyal_sayisi": s.get("count", 0),
            "Son_yon": s.get("last_side", "-"),
            "Kasa": s.get("last_ledger", "-"),
            "Zaman": s.get("last_time", "-"),
            "Stratejiler": strats,
        })
    return pd.DataFrame(rows)


def patlama_rows(scan: dict) -> pd.DataFrame:
    rows = []
    for sym, s in (scan or {}).items():
        if not isinstance(s, dict):
            continue
        rows.append({
            "Sembol": sym,
            "Patlama_skoru": s.get("long_score", 0),
            "Selale_skoru": s.get("short_score", 0),
            "En_iyi_skor": s.get("best_score", 0),
            "Yon": s.get("best_side", "-"),
            "Patlama_notlari": s.get("long_notes", ""),
            "Selale_notlari": s.get("short_notes", ""),
            "Guncelleme": s.get("updated_at", "-"),
        })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("En_iyi_skor", ascending=False)


def build_excel_bytes(data: dict) -> bytes:
    buf = io.BytesIO()
    ozet = pd.DataFrame([{
        "Kaynak": data.get("_source", "-"),
        "Guncelleme": data.get("updated_at", "-"),
        "Ozsermaye": data.get("equity", 0),
        "Nakit": data.get("balance", 0),
        "Acik_islem": len(data.get("active_positions") or {}),
        "Kapanan_islem": len(data.get("history") or []),
    }])
    sheets = {
        "Ozet": ozet,
        "Kasalar": _ledger_rows(data.get("ledgers") or {}),
        "Acik_Pozisyonlar": _pos_rows(data.get("active_positions") or {}),
        "Islem_Gecmisi": _history_rows(data.get("history") or []),
        "Sinyaller": _signal_rows(data.get("signal_log") or {}),
        "Patlama_Selale": patlama_rows(data.get("patlama_selale_scan") or {}),
        "Motor_Log": pd.DataFrame({"Log": data.get("engine_logs") or []}),
    }
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for name, df in sheets.items():
            out = df if not df.empty else pd.DataFrame({"Bilgi": ["Kayit yok"]})
            out.to_excel(writer, sheet_name=name[:31], index=False)
            ws = writer.sheets[name[:31]]
            for col in ws.columns:
                width = min(max(12, max(len(str(c.value or "")) for c in col) + 2), 48)
                ws.column_dimensions[col[0].column_letter].width = width
    return buf.getvalue()


def source_caption(data: dict) -> str:
    mode = "otomatik acik" if st.session_state.get("auto_refresh") else "otomatik kapali"
    return (
        f"Kaynak: {data.get('_source', '-')} · "
        f"Son guncelleme: {data.get('updated_at', '-')} · "
        f"Yenileme: {mode}"
    )
