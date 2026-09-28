import pandas as pd

from engine.market_commentary import (
    alignment_for_side,
    bias_from_regime,
    build_market_commentary,
    build_round_commentary,
    commentary_allows_side,
    empty_stage_note,
    last_closed_bar_pct,
    note_symbol_stage,
    note_symbol_stages,
    stamp_side_alignment,
)
from engine.types import Side, Stage
from shared.ui_data import market_commentary_rows, signal_log_rows, signal_watch_rows


def test_down_market_names_shorts_and_keeps_signals():
    note = build_market_commentary(
        btc_stage="declining",
        dominance={"btc_chg": -1.8, "btc_d": 57.4, "btc_d_chg": 0.25, "usdt_d": 4.2, "usdt_d_chg": 0.2},
        stage_counts={"declining": 300, "advancing": 40},
    )
    assert note["regime"] == "dusus"
    assert "düşüş evresi satışı" in note["text"]
    assert "Dominance alt yükselişi" in note["text"]
    assert "sinyal üretmeye devam eder" in note["text"]


def test_bitcoin_up_with_rising_dominance_is_not_alt_season():
    note = build_market_commentary(
        btc_stage="advancing",
        dominance={"btc_chg": 2.0, "btc_d": 58.0, "btc_d_chg": 0.4, "usdt_d": 4.0, "usdt_d_chg": 0.0},
        stage_counts={"declining": 80, "advancing": 70},
    )
    assert note["regime"] == "bitcoin_lider"
    assert "Bitcoin'de kalıyor" in note["text"]
    assert "Dominance alt yükselişi" in note["zayif"]


def test_rising_alts_when_dominance_falls():
    note = build_market_commentary(
        btc_stage="advancing",
        dominance={"btc_chg": 1.2, "btc_d": 54.0, "btc_d_chg": -0.3, "usdt_d": 3.8, "usdt_d_chg": -0.2},
        stage_counts={"advancing": 250, "declining": 40},
    )
    assert note["regime"] == "yukselis"
    assert "yükseliş evresi alışı" in note["text"]
    assert "düşüş evresi satışı" in note["zayif"]


def test_missing_dominance_change_is_not_invented():
    note = build_market_commentary(
        btc_stage="declining",
        dominance={"btc_chg": -0.4, "btc_d": 56.0, "usdt_d": 4.1},
        stage_counts={"declining": 10, "advancing": 2},
    )
    assert "bir önceki taramaya göre" not in note["text"]
    assert note["btc_d_chg"] is None


def test_conflict_stays_mixed():
    note = build_market_commentary(
        btc_stage="advancing",
        dominance={"btc_d": 55.0, "btc_d_chg": -0.4, "usdt_d": 4.0, "usdt_d_chg": 0.3},
        stage_counts={"declining": 200, "advancing": 30},
    )
    assert note["regime"] == "karisik"
    assert note["uygun"] == []
    assert "Keskin bir uygun" in note["text"]


def test_commentary_rows_newest_first():
    note = build_market_commentary(
        btc_stage="declining",
        dominance={"btc_d": 57.0},
        stage_counts={"declining": 10},
    )
    note["round_end"] = "2026-09-24 13:00:00"
    df = market_commentary_rows([note])
    assert len(df) == 1
    assert df.iloc[0]["Rejim"] == "dusus"
    assert "sinyal üretmeye devam eder" in str(df.iloc[0]["Yorum"])


def test_note_symbol_stage_skips_eth_and_keeps_btc():
    bucket = {"btc_stage": None, "counts": {}}
    note_symbol_stage("BTCUSDT", "declining", bucket)
    note_symbol_stage("ETHUSDT", "advancing", bucket)
    note_symbol_stage("SOLUSDT", "declining", bucket)
    assert bucket["btc_stage"] == "declining"
    assert bucket["counts"] == {"declining": 1}


def test_bias_from_regime():
    assert bias_from_regime("yukselis") == "long"
    assert bias_from_regime("dusus") == "short"
    assert bias_from_regime("bitcoin_lider") == "short"
    assert bias_from_regime("karisik") == "notr"
    assert bias_from_regime("belirsiz") == "notr"


def test_build_market_commentary_sets_bias():
    down = build_market_commentary(
        btc_stage="declining",
        dominance={"btc_chg": -1.8, "btc_d": 57.4, "btc_d_chg": 0.25, "usdt_d": 4.2, "usdt_d_chg": 0.2},
        stage_counts={"declining": 300, "advancing": 40},
    )
    up = build_market_commentary(
        btc_stage="advancing",
        dominance={"btc_chg": 1.2, "btc_d": 54.0, "btc_d_chg": -0.3, "usdt_d": 3.8, "usdt_d_chg": -0.2},
        stage_counts={"advancing": 250, "declining": 40},
    )
    assert down["bias"] == "short"
    assert up["bias"] == "long"


def test_15m_stage_sentence_uses_that_timeframe():
    note = build_market_commentary(
        btc_stage="declining",
        dominance={"btc_chg": -0.4, "btc_d": 57.0},
        stage_counts={"declining": 10},
        tf="15m",
    )
    assert "15 dakikalık grafikte" in note["text"]
    assert "son 15 dakikada" in note["text"]
    assert note["tf"] == "15m"


def test_round_commentary_has_four_tfs_and_trade_bias():
    stage_note = empty_stage_note()
    stage_note["4h"] = {
        "btc_stage": "advancing",
        "counts": {"advancing": 250, "declining": 40},
        "btc_chg": 0.8,
    }
    stage_note["1d"] = {
        "btc_stage": "declining",
        "counts": {"declining": 300, "advancing": 40},
        "btc_chg": None,
    }
    pack = build_round_commentary(
        stage_note=stage_note,
        dominance={"btc_chg": -1.8, "btc_d": 57.4, "btc_d_chg": 0.25, "usdt_d": 4.2, "usdt_d_chg": 0.2},
        trade_tf="4h",
    )
    assert set(pack["by_tf"]) == {"15m", "1h", "4h", "1d"}
    assert pack["trade_tf"] == "4h"
    assert pack["trade_bias"] == pack["by_tf"]["4h"]["bias"]
    assert pack["by_tf"]["4h"]["btc_chg"] == 0.8
    assert pack["by_tf"]["1d"]["regime"] == "dusus"
    df = market_commentary_rows([pack])
    assert "TF" in df.columns
    assert "Yon" in df.columns
    assert set(df["TF"]) == {"15m", "1s", "4s", "1g"}
    assert df.attrs["trade_tf"] == "4h"


def test_legacy_commentary_row_still_one_line():
    note = build_market_commentary(
        btc_stage="declining",
        dominance={"btc_d": 57.0},
        stage_counts={"declining": 10},
    )
    df = market_commentary_rows([note])
    assert len(df) == 1
    assert df.iloc[0]["TF"] == "1g"


def test_alignment_for_side():
    assert alignment_for_side(Side.BUY, "long") == "Uyumlu"
    assert alignment_for_side(Side.SELL, "short") == "Uyumlu"
    assert alignment_for_side("BUY", "short") == "Karsi"
    assert alignment_for_side("SELL", "long") == "Karsi"
    assert alignment_for_side(Side.BUY, "notr") == "Notr"


def test_stamp_and_signal_columns():
    pack = build_round_commentary(
        stage_note={
            "4h": {
                "btc_stage": "declining",
                "counts": {"declining": 300, "advancing": 40},
                "btc_chg": -0.5,
            }
        },
        dominance={"btc_d": 57.4, "btc_d_chg": 0.25, "usdt_d": 4.2, "usdt_d_chg": 0.2, "btc_chg": -1.8},
        trade_tf="4h",
    )
    stamp = stamp_side_alignment(Side.SELL, pack)
    assert stamp["piyasa_bias"] == pack["trade_bias"]
    if pack["trade_bias"] == "short":
        assert stamp["piyasa_uyum"] == "Uyumlu"
    assert "4s:" in stamp["piyasa_uyum_ozet"]
    rows = signal_log_rows({
        "AAAUSDT": {
            "count": 1,
            "last_side": "SELL",
            "last_ledger": "Kasa_SMC",
            "last_piyasa_bias": stamp["piyasa_bias"],
            "last_piyasa_uyum": stamp["piyasa_uyum"],
            "last_piyasa_uyum_ozet": stamp["piyasa_uyum_ozet"],
            "strategies": ["SMC_Short"],
        }
    })
    assert rows.iloc[0]["Piyasa_uyum"] == stamp["piyasa_uyum"]
    watch = signal_watch_rows([{
        "symbol": "AAAUSDT",
        "strategy": "SMC_Short",
        "side": "SELL",
        "entry": 1,
        "sl_price": 1.1,
        "tp_price": 0.9,
        "piyasa_uyum": stamp["piyasa_uyum"],
        "piyasa_bias": stamp["piyasa_bias"],
        "piyasa_uyum_ozet": stamp["piyasa_uyum_ozet"],
        "signal_time": "2026-09-28 12:00:00",
        "watch_until": "2026-09-29 12:00:00",
        "last_price": 1,
        "post_high": 1,
        "post_low": 1,
        "notional": 100,
        "leverage": 10,
        "notional_levered": True,
    }])
    assert watch.iloc[0]["Piyasa_uyum"] == stamp["piyasa_uyum"]


def test_commentary_allows_side_off_by_default():
    assert commentary_allows_side(Side.SELL, {"trade_bias": "long"}) is True
    assert commentary_allows_side(Side.SELL, {"trade_bias": "long"}, enabled=False) is True
    assert commentary_allows_side(Side.SELL, {"trade_bias": "long"}, enabled=True) is False
    assert commentary_allows_side(Side.BUY, {"trade_bias": "long"}, enabled=True) is True
    assert commentary_allows_side(Side.SELL, {"trade_bias": "short"}, enabled=True) is True
    assert commentary_allows_side(Side.BUY, {"trade_bias": "notr"}, enabled=True) is True
    assert commentary_allows_side(Side.SELL, {"trade_bias": "notr"}, enabled=True) is True


def test_last_closed_bar_pct():
    df = pd.DataFrame({"close": [100.0, 99.0]})
    assert last_closed_bar_pct(df) == -1.0


def test_note_symbol_stages_nested(monkeypatch):
    monkeypatch.setattr("structure.core.market_stage", lambda df: Stage.DECLINING)
    bucket = empty_stage_note()
    df = pd.DataFrame({"close": [100.0, 99.0], "sma200": [100.0, 100.0]})
    frames = {tf: df for tf in ("15m", "1h", "4h", "1d")}
    note_symbol_stages("SOLUSDT", frames, bucket)
    note_symbol_stages("ETHUSDT", frames, bucket)
    note_symbol_stages("BTCUSDT", frames, bucket)
    assert bucket["15m"]["counts"] == {"declining": 1}
    assert bucket["15m"]["btc_stage"] == "declining"
    assert bucket["15m"]["btc_chg"] == -1.0
    assert bucket["1d"]["btc_chg"] is None
