from engine.smc_trade_analysis import smc_block_reason, smc_summary_stats


def test_smc_block_low_score():
    row = {"long_score": 3, "short_score": 2, "long_notes": "", "short_notes": ""}
    side, reason = smc_block_reason(row)
    assert side is None
    assert "skor" in reason


def test_smc_summary_counts():
    scan = {
        "A": {
            "long_score": 8,
            "short_score": 2,
            "long_notes": "OB_retest | candle_confirm | killzone:london",
            "short_notes": "",
            "hierarchy_long": True,
            "confluence_long": 6,
            "setup_grade_long": "A",
            "ob_fvg_valid_long": True,
            "session": "london_open",
            "external_event": "none",
            "internal_event": "none",
            "trend": "bull",
        },
        "B": {"long_score": 2, "short_score": 1, "long_notes": "", "short_notes": ""},
    }
    stats = smc_summary_stats(scan)
    assert stats["taranan"] == 2
    assert stats["trade_ok"] >= 1
