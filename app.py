import json
import os
import base64

from typing import Optional

import pandas as pd
import streamlit as st

try:
    import requests
except Exception:
    requests = None

st.set_page_config(page_title="Krpito MTF Canlı Simülasyon", page_icon="📈", layout="wide")

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


@st.cache_data(ttl=8)
def load_data() -> dict:
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
        headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json", "User-Agent": "KrpitoMTF-UI"}
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
        "engine_logs": [],
        "equity": 0.0,
        "balance": 0.0,
        "_source": "veri yok",
    }


st_autorefresh = getattr(st, "autorefresh", None)
if st_autorefresh:
    st_autorefresh(interval=10_000, key="live_refresh")
else:
    st.markdown("<meta http-equiv='refresh' content='10'>", unsafe_allow_html=True)

data = load_data()
ledgers = data.get("ledgers") or {}
active = data.get("active_positions") or {}
history = data.get("history") or []
sig_log = data.get("signal_log") or {}
logs = data.get("engine_logs") or []
equity = float(data.get("equity") or 0)
cash = float(data.get("balance") or sum(ledgers.values()) if ledgers else 0)
if not equity:
    equity = cash + sum(float(p.get("margin") or 0) for p in active.values())
unreal = sum(float(p.get("unrealized_pnl") or 0) for p in active.values())

st.title("Canlı piyasa simülasyonu")
st.caption(f"Kaynak: {data.get('_source', '-')} · Son güncelleme: {data.get('updated_at', '-')} · 10 sn yenileme")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Toplam özsermaye", f"${equity:,.2f}")
c2.metric("Nakit (kasalar)", f"${cash:,.2f}")
c3.metric("Açık işlem", f"{len(active)}")
c4.metric("Açık PnL", f"${unreal:+,.2f}")
c5.metric("Kapanan işlem", f"{len(history)}")

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Açık pozisyonlar", "Kasalar", "İşlem geçmişi", "Sinyal günlüğü", "Motor log"]
)

with tab1:
    if active:
        rows = []
        for key, p in active.items():
            rows.append({
                "Sembol": p.get("symbol", key),
                "Kasa": p.get("ledger_name", "-"),
                "Yön": p.get("side"),
                "Giriş": p.get("entry_price"),
                "Anlık": p.get("current_price"),
                "SL": p.get("sl_price"),
                "TP": p.get("tp_price"),
                "ROE %": p.get("roe_pct"),
                "Açık PnL": p.get("unrealized_pnl"),
                "Marjin": p.get("margin"),
                "Kaldıraç": p.get("leverage"),
                "Strateji": p.get("strategy"),
                "Giriş zamanı": p.get("entry_time"),
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Açık pozisyon yok. Motor piyasa taradıkça burası dolacak.")

with tab2:
    if ledgers:
        start = 100.0
        rows = [{"Kasa": k, "Bakiye": v, "PnL": v - start} for k, v in ledgers.items()]
        df = pd.DataFrame(rows).sort_values("Bakiye", ascending=False)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.bar_chart(df.set_index("Kasa")["Bakiye"])
    else:
        st.info("Kasa verisi yok.")

with tab3:
    if history:
        df_h = pd.DataFrame(history)
        cols = [c for c in ["exit_time", "symbol", "ledger", "side", "entry", "exit", "pnl", "r", "close_reason", "strategy"] if c in df_h.columns]
        st.dataframe(df_h[cols].iloc[::-1], use_container_width=True, hide_index=True)
        curve = data.get("equity_curve") or []
        if curve:
            cdf = pd.DataFrame(curve)
            if "time" in cdf.columns and "equity" in cdf.columns:
                cdf = cdf.set_index("time")
                st.line_chart(cdf["equity"])
        elif "new_balance" in df_h.columns:
            st.line_chart(df_h.set_index("exit_time")["new_balance"])
    else:
        st.info("Henüz kapanan işlem yok.")

with tab4:
    if sig_log:
        rows = []
        for sym, s in sig_log.items():
            strats = s.get("strategies") or []
            if isinstance(strats, list):
                strats = ", ".join(strats[-6:])
            rows.append({
                "Sembol": sym,
                "Sinyal": s.get("count", 0),
                "Son yön": s.get("last_side") or s.get("last_side", "-"),
                "Kasa": s.get("last_ledger", "-"),
                "Zaman": s.get("last_time", "-"),
                "Stratejiler": strats,
            })
        df_s = pd.DataFrame(rows).sort_values("Sinyal", ascending=False)
        st.dataframe(df_s, use_container_width=True, hide_index=True)
    else:
        st.info("Sinyal günlüğü boş.")

with tab5:
    if logs:
        st.code("\n".join(logs[-80:]))
    else:
        st.info("Log yok. Render motoru çalışıyor mu?")
