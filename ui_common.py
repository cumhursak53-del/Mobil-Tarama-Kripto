"""Streamlit ortak veri yukleme ve yenileme kontrolleri."""
from __future__ import annotations

import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

from shared import ui_data
from shared.ui_data import (  # noqa: F401
    REFRESH_SEC_OPTIONS,
    build_excel_bytes,
    crew_recipe_rows,
    crew_result_rows,
    engine_status,
    format_price,
    format_price_symbol,
    ledger_daily_performance_rows,
    ledger_live_candidate_rows,
    ledger_summary_rows,
    minutes_since_update,
    patlama_rows,
    post_exit_analysis_rows,
    post_exit_watch_rows,
    signal_log_rows,
    signal_outcome_rows,
    signal_watch_rows,
    smc_rows,
    source_caption as _source_caption,
)


def source_caption(data: dict) -> str:
    return _source_caption(data, auto_refresh=st.session_state.get("auto_refresh"))


def init_refresh_persistence() -> None:
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


@st.cache_data(ttl=8, show_spinner=False)
def _cached_load_data(force_version: int = 0) -> dict:
    return ui_data.load_data(force_version=force_version)


@st.cache_data(ttl=8, show_spinner=False)
def _cached_load_lab_data(force_version: int = 0) -> dict:
    return ui_data.load_lab_data(force_version=force_version)


@st.cache_data(ttl=8, show_spinner=False)
def _cached_load_crew_data(force_version: int = 0) -> dict:
    return ui_data.load_crew_data(force_version=force_version)


def get_engine_data() -> dict:
    if "refresh_version" not in st.session_state:
        st.session_state.refresh_version = 0
    return _cached_load_data(force_version=st.session_state.refresh_version)


def run_autorefresh() -> None:
    if st.session_state.get("auto_refresh") and st_autorefresh is not None:
        st_autorefresh(
            interval=int(st.session_state.refresh_sec) * 1000,
            key="krpito_live_refresh",
        )


def setup_page(title: str, icon: str = "📈") -> dict:
    return render_sidebar_refresh()


def render_sidebar_refresh() -> dict:
    return get_engine_data()


def load_lab_data(force_version: int = 0) -> dict:
    return _cached_load_lab_data(force_version=force_version)


def load_crew_data(force_version: int = 0) -> dict:
    return _cached_load_crew_data(force_version=force_version)
