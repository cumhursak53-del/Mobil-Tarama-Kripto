from engine.btc_relative import btc_relative_change, format_btc_relative_log


def test_ratio_coin_over_btc():
    changes = {"BTCUSDT": -2.0, "ETHUSDT": -4.0}
    rel = btc_relative_change("ETHUSDT", changes)
    assert rel["coin_chg_24h"] == -4.0
    assert rel["btc_chg_24h"] == -2.0
    assert rel["btc_rel_ratio"] == 2.0


def test_ratio_none_when_btc_flat():
    changes = {"BTCUSDT": 0.02, "ETHUSDT": 3.0}
    rel = btc_relative_change("ETHUSDT", changes)
    assert rel["btc_rel_ratio"] is None


def test_log_format():
    txt = format_btc_relative_log({"coin_chg_24h": 3.5, "btc_chg_24h": -1.0, "btc_rel_ratio": -3.5})
    assert "coin24 +3.50%" in txt
    assert "btc24 -1.00%" in txt
    assert "btc_oran -3.500" in txt
