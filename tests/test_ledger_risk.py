import os

from risk.sizer import risk_pct_for_ledger


def test_ledger_risk_override(monkeypatch):
    monkeypatch.setenv("LEDGER_RISK_PCT", "Kasa_Fib618:0.05,Kasa_MumOnay:0.048")
    import importlib
    import engine.config as cfg
    import risk.sizer as sizer

    importlib.reload(cfg)
    importlib.reload(sizer)
    assert sizer.risk_pct_for_ledger("Kasa_Fib618") == 0.05
    assert sizer.risk_pct_for_ledger("Kasa_MumOnay") == 0.048
    assert sizer.risk_pct_for_ledger("Kasa_MACD") == cfg.RISK_PCT
