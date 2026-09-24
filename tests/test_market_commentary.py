from engine.market_commentary import build_market_commentary, note_symbol_stage
from shared.ui_data import market_commentary_rows


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
