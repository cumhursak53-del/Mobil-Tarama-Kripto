from strategies.registry import live_strategies, live_strategy_ledgers


def test_live_strategies_includes_standard_kasas_excludes_lab():
    strats = live_strategies()
    ledgers = live_strategy_ledgers()
    assert len(strats) >= 30
    assert "Kasa_Hacim" in ledgers
    assert "Kasa_PiyasaEvresi" in ledgers
    assert "Kasa_SMC" in ledgers
    assert not any(x.startswith("Kasa_Lab_") for x in ledgers)
