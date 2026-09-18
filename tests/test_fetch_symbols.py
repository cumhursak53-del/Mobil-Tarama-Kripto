from engine.data import is_crypto_linear_instrument


def test_crypto_perpetual_allowed():
    assert is_crypto_linear_instrument(
        {"symbol": "BTCUSDT", "contractType": "LinearPerpetual", "symbolType": ""}
    )
    assert is_crypto_linear_instrument(
        {"symbol": "DOGEUSDT", "contractType": "LinearPerpetual", "symbolType": "innovation"}
    )


def test_tradfi_excluded():
    assert not is_crypto_linear_instrument(
        {"symbol": "AAPLUSDT", "contractType": "LinearPerpetual", "symbolType": "stock"}
    )
    assert not is_crypto_linear_instrument(
        {"symbol": "XAUUSDT", "contractType": "LinearPerpetual", "symbolType": "commodity"}
    )
    assert not is_crypto_linear_instrument(
        {"symbol": "BTC-28MAR25", "contractType": "LinearFutures", "symbolType": ""}
    )
