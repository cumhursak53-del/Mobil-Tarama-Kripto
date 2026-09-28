from engine.live_transition_report import build_live_transition_report


def _item(strategy, side, verdict, day, pnl=10.0, sl=False):
    return {
        "strategy": strategy,
        "side": side,
        "verdict": verdict,
        "signal_time": f"{day} 12:00:00",
        "pnl_hypo_usd": pnl,
        "hit_sl": sl,
        "hit_tp": verdict == "correct" and not sl,
        "mfe_r": 1.2,
    }


def test_long_and_short_split():
    log = [
        _item("[STRAT: CCI_Cross_Long]", "BUY", "wrong", "2026-09-21", -20),
        _item("[STRAT: CCI_Cross_Short]", "SELL", "correct", "2026-09-21", 15),
    ]
    report = build_live_transition_report(log)
    assert len(report["long_rows"]) == 1
    assert len(report["short_rows"]) == 1
    assert report["long_rows"][0]["Yon"] == "LONG"
    assert report["short_rows"][0]["Yon"] == "SHORT"


def test_candidate_needs_enough_days_and_samples():
    log = []
    for i in range(35):
        log.append(_item("[STRAT: RSI_OverboughtExit_Short]", "SELL", "correct", "2026-09-23", 12))
    report = build_live_transition_report(log)
    row = report["short_rows"][0]
    assert row["Durum"] == "Izle"
    assert "gun 1/2" in row["Not"]


def test_candidate_when_thresholds_met():
    log = []
    for day in ("2026-09-21", "2026-09-22", "2026-09-23"):
        for i in range(12):
            log.append(_item("[STRAT: Mum_Direnc_Short]", "SELL", "correct", day, 20))
    report = build_live_transition_report(log)
    row = report["short_rows"][0]
    assert row["Durum"] == "Canli aday"
    assert row["Biten"] == 36


def test_reject_low_success():
    log = []
    for i in range(20):
        log.append(_item("[STRAT: Dominance_AltLong]", "BUY", "wrong", "2026-09-23", -50, sl=True))
    report = build_live_transition_report(log)
    row = report["long_rows"][0]
    assert row["Durum"] == "Disla"
