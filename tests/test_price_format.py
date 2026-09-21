from shared.price_format import format_price, format_price_symbol


def test_format_price_tiny_not_zero():
    assert format_price(0.00001234) == "0.00001234"
    assert format_price(0.00005) == "0.00005"
    assert format_price(0.00001234) != "0.0000"


def test_format_price_symbol_uses_string():
    # Cached or network — at minimum falls back without crash
    out = format_price_symbol("BTCUSDT", 97500.5)
    assert out and out != "-"


def test_live_monitor_old_bug_fixed():
    from shared.price_format import format_price as fp

    assert fp(0.00001234) != "0.0000"
    assert fp(0.00005) != "0.05"
