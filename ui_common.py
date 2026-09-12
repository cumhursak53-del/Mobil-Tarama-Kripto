"""Streamlit ortak veri yukleme ve yenileme kontrolleri."""
from __future__ import annotations

import base64
import io
import json
import os
import sys
from collections import defaultdict
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

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

REFRESH_SEC_OPTIONS = [30, 60, 120, 300]


def format_price(v: float | None) -> str:
    """Dusuk fiyatli coinlerde bilimsel gosterim yerine tam ondalik."""
    if v is None:
        return "-"
    try:
        val = float(v)
    except (TypeError, ValueError):
        return str(v)
    if val == 0:
        return "0"
    av = abs(val)
    if av >= 1000:
        return f"{val:,.4f}".rstrip("0").rstrip(".")
    if av >= 1:
        decimals = 6
    elif av >= 0.0001:
        decimals = 8
    else:
        decimals = 12
    text = f"{val:.{decimals}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text

ENGINE_URL = os.environ.get("ENGINE_URL", "https://mobil-tarama-kripto.onrender.com").rstrip("/")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "cumhursak53-del/Mobil-Tarama-Kripto")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")
STATE_FILE = os.environ.get("STATE_FILE", "state.json")
LAB_STATE_FILE = os.environ.get("LAB_STATE_FILE", "lab_state.json")
CREW_STATE_FILE = os.environ.get("CREW_STATE_FILE", "crew_state.json")


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
        "lab_candidates": [],
        "lab_summary": {},
        "equity": 0.0,
        "balance": 0.0,
        "_source": "veri yok",
    }


def _fetch_github_json(path: str) -> Optional[dict]:
    if requests is None:
        return None
    if GITHUB_TOKEN:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}?ref={GITHUB_BRANCH}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "KrpitoMTF-UI",
        }
        raw = _get_json(url, headers=headers)
        if raw and raw.get("content"):
            try:
                return json.loads(base64.b64decode(raw["content"]).decode("utf-8"))
            except Exception:
                pass
    raw_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/{path}"
    return _get_json(raw_url)


@st.cache_data(ttl=8, show_spinner=False)
def load_lab_data(force_version: int = 0) -> dict:
    del force_version
    data = _fetch_github_json(LAB_STATE_FILE)
    if data:
        data["_source"] = "GitHub lab_state.json"
        return data
    if os.path.exists(LAB_STATE_FILE):
        try:
            with open(LAB_STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["_source"] = "local lab_state.json"
            return data
        except Exception:
            pass
    return {
        "schema_version": 1,
        "recipes": [],
        "backtests": [],
        "candidates": [],
        "updated_at": "",
        "_source": "lab verisi yok",
    }


@st.cache_data(ttl=8, show_spinner=False)
def load_crew_data(force_version: int = 0) -> dict:
    del force_version
    data = _fetch_github_json(CREW_STATE_FILE)
    if data:
        data["_source"] = "GitHub crew_state.json"
        return data
    if os.path.exists(CREW_STATE_FILE):
        try:
            with open(CREW_STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["_source"] = "local crew_state.json"
            return data
        except Exception:
            pass
    return {
        "schema_version": 1,
        "recipes": [],
        "backtests": [],
        "daily_runs": [],
        "pipeline": {},
        "updated_at": "",
        "_source": "crew verisi yok",
    }


def crew_result_rows(results: list | None, target_pct: float = 20.0) -> pd.DataFrame:
    rows = []
    for r in results or []:
        if not isinstance(r, dict):
            continue
        pct = float(r.get("test_best_day_pct") or 0)
        rows.append({
            "Strateji": r.get("recipe_name", r.get("recipe_id", "-")),
            "En_iyi_gun_pct": pct,
            "Gun_ge_20": r.get("days_ge_target", 0),
            "Test_PF": r.get("test_pf"),
            "Trades": r.get("test_trades"),
            "Max_DD_pct": round(float(r.get("max_dd") or 0) * 100, 1),
            "Sembol": r.get("best_symbol", "-"),
            "Gecti": "Evet" if r.get("passed") else "Hayir",
            "Neden": r.get("reason", "-"),
            "Hedef": f">={target_pct:.0f}%",
        })
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    return df.sort_values("En_iyi_gun_pct", ascending=False)


def crew_recipe_rows(recipes: list | None) -> pd.DataFrame:
    rows = []
    for r in recipes or []:
        if not isinstance(r, dict):
            continue
        rows.append({
            "ID": r.get("id"),
            "Ad": r.get("name"),
            "Kaynak": r.get("source", "-"),
            "Entry_TF": r.get("entry_tf", "1h"),
            "TP_R": r.get("tp_r", "-"),
            "Long_kural": len(r.get("long_rules") or []),
            "Short_kural": len(r.get("short_rules") or []),
        })
    return pd.DataFrame(rows)


def minutes_since_update(ts: Optional[str]) -> Optional[float]:
    if not ts:
        return None
    try:
        from engine.config import TR_TZ
        dt = datetime.strptime(str(ts)[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=TR_TZ)
        now = datetime.now(TR_TZ)
        return (now - dt).total_seconds() / 60.0
    except Exception:
        return None


def engine_status(data: dict) -> tuple[str, str, str]:
    """Durum metni, renk anahtari, aciklama."""
    mins = minutes_since_update(data.get("updated_at"))
    logs = data.get("engine_logs") or []
    has_heartbeat = any("Calisiyor" in str(x) for x in logs[-20:])
    if mins is None:
        return "Bilinmiyor", "offline", "Motor guncelleme zamani gelmedi."
    if mins <= 5 and (has_heartbeat or len(logs) > 0):
        return "Calisiyor", "ok", f"Son guncelleme {mins:.0f} dk once."
    if mins <= 15:
        return "Yavas", "warn", f"Son guncelleme {mins:.0f} dk once; motor uyuyor olabilir."
    return "Durdu / erisilemiyor", "offline", f"Son guncelleme {mins:.0f} dk once."


def setup_page(title: str, icon: str = "📈") -> dict:
    """Geriye donuk uyumluluk; yeni ekranlar render_sidebar_refresh kullanir."""
    return render_sidebar_refresh()


def init_refresh_persistence() -> None:
    """URL + tarayici localStorage ile yenileme tercihlerini kalici tut."""
    if st.session_state.get("_refresh_persistence_ready"):
        return

    import streamlit.components.v1 as components

    components.html(
        """
<script>
(function () {
  const p = new URLSearchParams(window.location.search);
  if (p.has("auto_refresh")) {
    localStorage.setItem("krpito_auto_refresh", p.get("auto_refresh") || "0");
    localStorage.setItem("krpito_refresh_sec", p.get("refresh_sec") || "60");
    return;
  }
  const saved = localStorage.getItem("krpito_auto_refresh");
  if (saved === null) return;
  p.set("auto_refresh", saved);
  p.set("refresh_sec", localStorage.getItem("krpito_refresh_sec") || "60");
  if (!sessionStorage.getItem("krpito_refresh_restore")) {
    sessionStorage.setItem("krpito_refresh_restore", "1");
    window.location.search = p.toString();
  }
})();
</script>
        """,
        height=0,
        width=0,
    )

    qp = st.query_params
    auto_raw = qp.get("auto_refresh")
    sec_raw = qp.get("refresh_sec")

    if auto_raw is not None:
        st.session_state.auto_refresh = str(auto_raw).lower() in ("1", "true", "yes", "on")
    elif "auto_refresh" not in st.session_state:
        st.session_state.auto_refresh = False

    if sec_raw is not None:
        try:
            st.session_state.refresh_sec = int(sec_raw)
        except (TypeError, ValueError):
            st.session_state.refresh_sec = 60
    elif "refresh_sec" not in st.session_state:
        st.session_state.refresh_sec = 60

    if st.session_state.refresh_sec not in REFRESH_SEC_OPTIONS:
        st.session_state.refresh_sec = 60

    if "refresh_version" not in st.session_state:
        st.session_state.refresh_version = 0

    st.session_state._refresh_persistence_ready = True


def _sync_refresh_prefs_to_url() -> None:
    st.query_params["auto_refresh"] = "1" if st.session_state.auto_refresh else "0"
    st.query_params["refresh_sec"] = str(st.session_state.refresh_sec)


def render_global_sidebar() -> None:
    """Tum sayfalarda ortak yenileme paneli."""
    init_refresh_persistence()

    with st.sidebar:
        st.subheader("Yenileme")
        st.toggle(
            "Otomatik yenile",
            key="auto_refresh",
            help="Tercihin kaydedilir; sayfa yenilense de acik kalir.",
        )
        st.selectbox(
            "Aralik (sn)",
            options=REFRESH_SEC_OPTIONS,
            key="refresh_sec",
            disabled=not st.session_state.auto_refresh,
        )
        if st.button("Simdi yenile", use_container_width=True):
            st.session_state.refresh_version += 1
            st.cache_data.clear()
            st.rerun()
        st.caption(
            "Otomatik yenileme kapaliysa veri sabit kalir. "
            "Acik biraktiginda tercih tarayicida saklanir."
        )

    _sync_refresh_prefs_to_url()


def run_autorefresh() -> None:
    if st.session_state.get("auto_refresh") and st_autorefresh is not None:
        st_autorefresh(
            interval=int(st.session_state.refresh_sec) * 1000,
            key="krpito_live_refresh",
        )


def get_engine_data() -> dict:
    if "refresh_version" not in st.session_state:
        st.session_state.refresh_version = 0
    return load_data(force_version=st.session_state.refresh_version)


def render_sidebar_refresh() -> dict:
    """Geriye donuk uyumluluk."""
    return get_engine_data()


def _pos_rows(active: dict) -> pd.DataFrame:
    rows = []
    for key, p in (active or {}).items():
        if not isinstance(p, dict):
            continue
        rows.append({
            "Sembol": p.get("symbol", key),
            "Kasa": p.get("ledger_name", "-"),
            "Yon": p.get("side"),
            "Giris": format_price(p.get("entry_price")),
            "Anlik": format_price(p.get("current_price")),
            "SL": format_price(p.get("sl_price")),
            "TP": format_price(p.get("tp_price")),
            "ROE_%": p.get("roe_pct"),
            "Acik_PnL": p.get("unrealized_pnl"),
            "Marjin": p.get("margin"),
            "Kaldirac": p.get("leverage"),
            "Notional": p.get("notional"),
            "Strateji": p.get("strategy"),
            "Giris_zamani": p.get("entry_time"),
        })
    return pd.DataFrame(rows)


def ledger_summary_rows(
    ledgers: dict | None,
    active: dict | None = None,
    history: list | None = None,
    start: float | None = None,
) -> pd.DataFrame:
    """Kasa ozeti: Bakiye (kapanan), PnL (kapanan+acik), Total (gercek zamanli)."""
    from engine.config import KASA_START_USD

    start_val = float(start if start is not None else KASA_START_USD)
    closed_pnl_by: dict[str, float] = defaultdict(float)
    closed_count_by: dict[str, int] = defaultdict(int)
    for h in history or []:
        if isinstance(h, dict) and h.get("ledger"):
            ledger = str(h["ledger"])
            closed_pnl_by[ledger] += float(h.get("pnl") or 0)
            closed_count_by[ledger] += 1

    unreal_by: dict[str, float] = defaultdict(float)
    margin_by: dict[str, float] = defaultdict(float)
    open_count_by: dict[str, int] = defaultdict(int)
    for p in (active or {}).values():
        if not isinstance(p, dict):
            continue
        ledger = str(p.get("ledger_name") or "")
        if not ledger:
            continue
        open_count_by[ledger] += 1
        unreal_by[ledger] += float(p.get("unrealized_pnl") or 0)
        margin_by[ledger] += float(p.get("margin") or 0)

    all_ledgers = (
        set(ledgers or {})
        | set(closed_pnl_by)
        | set(closed_count_by)
        | set(unreal_by)
        | set(margin_by)
        | set(open_count_by)
    )
    rows = []
    for k in sorted(all_ledgers):
        closed = closed_pnl_by.get(k, 0.0)
        unreal = unreal_by.get(k, 0.0)
        bakiye = start_val + closed
        pnl = closed + unreal
        cash = float((ledgers or {}).get(k, bakiye))
        total = cash + margin_by.get(k, 0.0) + unreal
        rows.append({
            "Kasa": k,
            "Acik": open_count_by.get(k, 0),
            "Kapali": closed_count_by.get(k, 0),
            "Bakiye": round(bakiye, 2),
            "PnL": round(pnl, 2),
            "Total": round(total, 2),
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("Total", ascending=False)
    return df


def _ledger_rows(data: dict) -> pd.DataFrame:
    return ledger_summary_rows(
        data.get("ledgers") or {},
        data.get("active_positions") or {},
        data.get("history") or [],
    )


def _side_label(side: str) -> str:
    return "LONG" if str(side).upper() == "BUY" else "SHORT"


def _parse_trade_date(value) -> str | None:
    if value is None or value == "":
        return None
    try:
        return pd.to_datetime(value).date().isoformat()
    except Exception:
        return None


def ledger_daily_performance_rows(
    history: list | None,
    active: dict | None = None,
    start: float | None = None,
) -> pd.DataFrame:
    """Kasa + yon + gun: kapali ve acik PnL (acik = giris gunune yazilir)."""
    from engine.config import KASA_START_USD

    start_val = float(start if start is not None else KASA_START_USD)
    buckets: dict[tuple[str, str, str], dict] = {}

    def _bucket(day: str, kasa: str, yon: str) -> dict:
        key = (day, kasa, yon)
        return buckets.setdefault(
            key,
            {"Kapali": 0, "Acik": 0, "Kapali_PnL": 0.0, "Acik_PnL": 0.0},
        )

    for h in history or []:
        if not isinstance(h, dict) or not h.get("ledger"):
            continue
        day = _parse_trade_date(h.get("exit_time"))
        if not day:
            continue
        row = _bucket(day, str(h["ledger"]), _side_label(h.get("side", "")))
        row["Kapali"] += 1
        row["Kapali_PnL"] += float(h.get("pnl") or 0)

    for p in (active or {}).values():
        if not isinstance(p, dict) or not p.get("ledger_name"):
            continue
        day = _parse_trade_date(p.get("entry_time"))
        if not day:
            continue
        row = _bucket(day, str(p["ledger_name"]), _side_label(p.get("side", "")))
        row["Acik"] += 1
        row["Acik_PnL"] += float(p.get("unrealized_pnl") or 0)

    rows = []
    for (day, kasa, yon), v in buckets.items():
        gunluk = v["Kapali_PnL"] + v["Acik_PnL"]
        rows.append({
            "Tarih": day,
            "Kasa": kasa,
            "Yon": yon,
            "Kapali": v["Kapali"],
            "Acik": v["Acik"],
            "Kapali_PnL": round(v["Kapali_PnL"], 2),
            "Acik_PnL": round(v["Acik_PnL"], 2),
            "Gunluk_PnL": round(gunluk, 2),
            "Gunluk_pct": round(gunluk / start_val * 100, 2),
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["Tarih", "Gunluk_pct"], ascending=[False, False])
    return df


def ledger_live_candidate_rows(
    daily: pd.DataFrame,
    *,
    min_pct: float | None = None,
    min_closed: int | None = None,
    exclude_lab: bool = True,
) -> pd.DataFrame:
    """En az bir gun >= hedef % olan kasa+yon ozeti (canli aday adayi)."""
    from engine.config import DAILY_CANDIDATE_MIN_CLOSED, DAILY_PNL_TARGET_PCT

    target = float(min_pct if min_pct is not None else DAILY_PNL_TARGET_PCT)
    min_trades = int(min_closed if min_closed is not None else DAILY_CANDIDATE_MIN_CLOSED)
    if daily.empty:
        return pd.DataFrame()
    agg = (
        daily.groupby(["Kasa", "Yon"], as_index=False)
        .agg(
            Gun=("Tarih", "nunique"),
            Toplam_PnL=("Gunluk_PnL", "sum"),
            En_iyi_gun_pct=("Gunluk_pct", "max"),
            Gun_15plus=("Gunluk_pct", lambda s: int((s >= target).sum())),
            Islem_kapali=("Kapali", "sum"),
        )
    )
    agg = agg[agg["En_iyi_gun_pct"] >= target]
    agg = agg[agg["Islem_kapali"] >= min_trades]
    if exclude_lab:
        agg = agg[~agg["Kasa"].astype(str).str.startswith("Kasa_Lab_")]
    agg = agg.sort_values(["Yon", "En_iyi_gun_pct"], ascending=[True, False])
    agg["Lab"] = agg["Kasa"].astype(str).str.startswith("Kasa_Lab_")
    return agg.reset_index(drop=True)


def _history_rows(history: list) -> pd.DataFrame:
    if not history:
        return pd.DataFrame()
    df = pd.DataFrame(history)
    for col in ("entry", "exit"):
        if col in df.columns:
            df[col] = df[col].apply(format_price)
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


def signal_log_rows(sig_log: dict, *, strategies_tail: int | None = 6) -> pd.DataFrame:
    rows = []
    for sym, s in (sig_log or {}).items():
        if str(sym).startswith("_") or not isinstance(s, dict):
            continue
        strats = s.get("strategies") or []
        if isinstance(strats, list):
            if strategies_tail is not None and len(strats) > strategies_tail:
                strats = ", ".join(str(x) for x in strats[-strategies_tail:])
            else:
                strats = ", ".join(str(x) for x in strats)
        rows.append({
            "Sembol": sym,
            "Sinyal": s.get("count", 0),
            "Son yon": s.get("last_side", "-"),
            "Kasa": s.get("last_ledger", "-"),
            "Ilk sinyal": s.get("first_time") or "-",
            "Son sinyal": s.get("last_time") or "-",
            "Stratejiler": strats,
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("Sinyal", ascending=False)
    return df


def _signal_rows(sig_log: dict) -> pd.DataFrame:
    df = signal_log_rows(sig_log, strategies_tail=None)
    if df.empty:
        return df
    return df.rename(columns={
        "Sinyal": "Sinyal_sayisi",
        "Son yon": "Son_yon",
        "Ilk sinyal": "Ilk_sinyal",
        "Son sinyal": "Son_sinyal",
    })


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


def smc_rows(scan: dict) -> pd.DataFrame:
    rows = []
    for sym, s in (scan or {}).items():
        if not isinstance(s, dict):
            continue
        rows.append({
            "Sembol": sym,
            "Long_skoru": s.get("long_score", 0),
            "Short_skoru": s.get("short_score", 0),
            "En_iyi_skor": s.get("best_score", 0),
            "Yon": s.get("best_side", "-"),
            "Long_grade": s.get("setup_grade_long", "-"),
            "Short_grade": s.get("setup_grade_short", "-"),
            "Long_conf": s.get("confluence_long", 0),
            "Short_conf": s.get("confluence_short", 0),
            "Trend": s.get("trend", "-"),
            "Session": s.get("session", "-"),
            "Killzone": "E" if s.get("killzone") else "-",
            "Dis_olay": s.get("external_event", s.get("last_event", "-")),
            "Ic_olay": s.get("internal_event", "-"),
            "Long_notlari": s.get("long_notes", ""),
            "Short_notlari": s.get("short_notes", ""),
            "Bull_OB": s.get("bull_ob_count", 0),
            "Bear_OB": s.get("bear_ob_count", 0),
            "Breaker_L": s.get("breaker_bull", 0),
            "Breaker_S": s.get("breaker_bear", 0),
            "IFVG_L": s.get("ifvg_bull", 0),
            "IFVG_S": s.get("ifvg_bear", 0),
            "OTE_L": "E" if s.get("in_ote_long") else "-",
            "OTE_S": "E" if s.get("in_ote_short") else "-",
            "Induce_L": "E" if s.get("inducement_bull") else "-",
            "Induce_S": "E" if s.get("inducement_bear") else "-",
            "Tepe_guc": s.get("swing_high_strength", "-"),
            "Dip_guc": s.get("swing_low_strength", "-"),
            "Aktif_FVG_L": s.get("active_fvg_bull", 0),
            "Aktif_FVG_S": s.get("active_fvg_bear", 0),
            "Sweep_L": "E" if s.get("sweep_bull") else "-",
            "Sweep_S": "E" if s.get("sweep_bear") else "-",
            "Guncelleme": s.get("updated_at", "-"),
        })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("En_iyi_skor", ascending=False)


def post_exit_analysis_rows(log: list | None) -> pd.DataFrame:
    if not log:
        return pd.DataFrame()
    rows = []
    for a in log:
        if not isinstance(a, dict):
            continue
        recs = a.get("recommendations") or []
        rows.append({
            "Tarih": a.get("exit_time"),
            "Sembol": a.get("symbol"),
            "Kasa": a.get("ledger"),
            "Yon": a.get("side"),
            "Kapanis": a.get("close_reason"),
            "PnL": a.get("pnl"),
            "MFE_islem": a.get("mfe_in_r"),
            "MAE_islem": a.get("mae_in_r"),
            "MFE_sonrasi": a.get("mfe_post_usd"),
            "SL_karar": a.get("sl_verdict"),
            "TP_karar": a.get("tp_verdict"),
            "Kacirilan_USD": a.get("missed_upside_usd"),
            "Optimal_fark_pct": a.get("optimal_vs_actual_pct"),
            "Oneri": " | ".join(recs) if recs else "",
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("Tarih", ascending=False)
    return df


def post_exit_watch_rows(watchlist: list | None) -> pd.DataFrame:
    if not watchlist:
        return pd.DataFrame()
    from datetime import datetime
    from engine.config import TR_TZ
    from engine.post_exit import parse_tr_ts

    rows = []
    now = datetime.now(TR_TZ)
    for w in watchlist:
        until = parse_tr_ts(str(w.get("watch_until") or ""))
        remain_h = max(0.0, (until - now).total_seconds() / 3600) if until else 0.0
        rows.append({
            "Sembol": w.get("symbol"),
            "Kasa": w.get("ledger"),
            "Yon": w.get("side"),
            "Cikis": w.get("exit"),
            "Kapanis": w.get("close_reason"),
            "Kalan_saat": round(remain_h, 1),
            "Post_yuksek": w.get("post_high"),
            "Post_dusuk": w.get("post_low"),
            "Son_fiyat": w.get("last_price"),
        })
    return pd.DataFrame(rows)


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
    daily = ledger_daily_performance_rows(
        data.get("history") or [],
        data.get("active_positions") or {},
    )
    from engine.trade_analysis import ledger_analysis_summary

    analysis_log = data.get("post_exit_log") or []
    sheets = {
        "Ozet": ozet,
        "Kasalar": _ledger_rows(data),
        "Gunluk_Performans": daily,
        "Canli_Adaylar": ledger_live_candidate_rows(daily),
        "Islem_Analizi": post_exit_analysis_rows(analysis_log),
        "Kasa_Analiz_Ozeti": ledger_analysis_summary(analysis_log),
        "Acik_Pozisyonlar": _pos_rows(data.get("active_positions") or {}),
        "Islem_Gecmisi": _history_rows(data.get("history") or []),
        "Sinyaller": _signal_rows(data.get("signal_log") or {}),
        "Patlama_Selale": patlama_rows(data.get("patlama_selale_scan") or {}),
        "SMC_Tarama": smc_rows(data.get("smc_scan") or {}),
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
