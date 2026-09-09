from risk.sizer import size_position


def test_min_margin_rejects_small_position():
    # Genis SL → dusuk notional → marjin $10 altinda kalir
    sized = size_position(ledger_balance=100.0, entry=100.0, sl=95.0)
    assert sized is None


def test_min_margin_accepts_valid_position():
    sized = size_position(ledger_balance=100.0, entry=100.0, sl=98.0)
    assert sized is not None
    assert sized.margin >= 10.0
