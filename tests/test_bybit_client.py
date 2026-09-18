from __future__ import annotations

import hashlib
import hmac
from unittest.mock import MagicMock, patch

import pytest

from engine.exchange.bybit_client import BybitClient, BybitError


def test_sign_deterministic():
    client = BybitClient(api_key="key", api_secret="secret", base_url="https://test")
    sig = client._sign('{"a":1}', "1234567890")
    raw = "1234567890key5000" + '{"a":1}'
    expected = hmac.new(b"secret", raw.encode(), hashlib.sha256).hexdigest()
    assert sig == expected


def test_format_qty_rounds_to_step():
    client = BybitClient(api_key="k", api_secret="s", base_url="https://test")
    client._instrument_cache["BTCUSDT"] = {
        "symbol": "BTCUSDT",
        "qty_step": 0.001,
        "min_qty": 0.001,
        "tick_size": 0.1,
    }
    assert client.format_qty("BTCUSDT", 0.123456) == "0.123"


def test_request_raises_on_api_error():
    client = BybitClient(api_key="k", api_secret="s", base_url="https://test")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"retCode": 10001, "retMsg": "fail", "result": {}}
    with patch("engine.exchange.bybit_client.requests.post", return_value=mock_resp):
        with pytest.raises(BybitError, match="fail"):
            client._request("POST", "/v5/order/create", body={"x": 1})


def test_paper_executor_open():
    from engine.exchange.executor import PaperExecutor
    from engine.types import Side, Signal
    from risk.sizer import SizedTrade

    ex = PaperExecutor()
    sig = Signal(
        side=Side.BUY,
        strategy="test",
        ledger="Kasa_Hacim",
        reason="test",
        sl_price=90.0,
        tp_price=110.0,
    )
    sized = SizedTrade(margin=10, notional=100, leverage=10, qty=1.0, risk_usd=3.5)
    fill = ex.open_position("BTCUSDT", sig, sized, 100.0)
    assert fill.ok
    assert fill.fill_price == 100.0
