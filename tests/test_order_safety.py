"""Bybit emir guvenligi: SL'siz pozisyon kalmaz, kapanis borsa onayi olmadan islenmez."""
from __future__ import annotations

import pytest

from engine.exchange.alerts import clear_alerts, set_notifier
from engine.exchange.bybit_client import BybitClient, BybitError
from engine.exchange.executor import BybitExecutor
from engine.portfolio import Portfolio
from engine.types import Position, Side, Signal


class FakeClient:
    def __init__(self):
        self.fail_stop = False
        self.fail_close = False
        self.hold_open = False
        self.omit_entry_fill = False
        self.position_size = 0.0
        self.stop_loss = None
        self.entry_avg = 100.0
        self.close_avg = 99.0
        self.opens: list[dict] = []
        self.closes: list[dict] = []
        self.stop_calls: list[float | None] = []
        self.position_reads = 0
        self._orders: dict[str, dict] = {}
        self._seq = 0

    def set_leverage(self, symbol: str, leverage: int) -> None:
        return None

    def place_market_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        reduce_only: bool = False,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> dict:
        self._seq += 1
        oid = f"entry-{self._seq}"
        self.opens.append(
            {
                "symbol": symbol,
                "side": side,
                "qty": qty,
                "reduce_only": reduce_only,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
            }
        )
        self.position_size = float(qty)
        if stop_loss and not self.fail_stop:
            self.stop_loss = stop_loss
        self._orders[oid] = {
            "order_id": oid,
            "status": "Filled",
            "avg_price": self.entry_avg,
            "cum_qty": float(qty),
        }
        if self.omit_entry_fill:
            return {"orderId": oid}
        return {
            "orderId": oid,
            "avgPrice": str(self.entry_avg),
            "cumExecQty": str(qty),
            "orderStatus": "Filled",
        }

    def set_trading_stop(self, symbol: str, stop_loss: float | None = None, take_profit: float | None = None):
        self.stop_calls.append(stop_loss)
        if self.fail_stop:
            raise BybitError("stopLoss rejected")
        self.stop_loss = stop_loss
        return {}

    def close_position_market(self, symbol: str, side: str, qty: float) -> dict:
        self.closes.append({"symbol": symbol, "side": side, "qty": qty, "reduce_only": True})
        if self.fail_close:
            raise BybitError("close rejected")
        self._seq += 1
        oid = f"close-{self._seq}"
        if self.hold_open:
            status = "New"
            avg = 0.0
            done = 0.0
        else:
            status = "Filled"
            avg = float(self.close_avg or self.entry_avg)
            done = float(qty)
            self.position_size = 0.0
        self._orders[oid] = {
            "order_id": oid,
            "status": status,
            "avg_price": avg,
            "cum_qty": done,
        }
        self.last_close_id = oid
        return {"orderId": oid, "avgPrice": "" if not avg else str(avg), "cumExecQty": str(done)}

    def get_position_row(self, symbol: str) -> dict:
        self.position_reads += 1
        return {
            "symbol": symbol,
            "size": self.position_size,
            "side": "BUY",
            "entry_price": self.entry_avg,
            "stop_loss": self.stop_loss,
        }

    def get_order(self, symbol: str, order_id: str) -> dict:
        row = self._orders.get(order_id)
        if row:
            return dict(row)
        return {"order_id": order_id, "status": "", "avg_price": 0.0, "cum_qty": 0.0}


def _signal() -> Signal:
    return Signal(
        side=Side.BUY,
        strategy="test",
        ledger="Kasa_Canli",
        reason="test",
        sl_price=90.0,
        tp_price=120.0,
    )


def _pos(symbol: str, **overrides) -> Position:
    data = dict(
        symbol=symbol,
        side=Side.BUY,
        ledger="Kasa_Canli",
        strategy="t",
        entry_price=100.0,
        sl_price=90.0,
        tp_price=120.0,
        margin=10.0,
        notional=100.0,
        leverage=10.0,
        qty=1.0,
        entry_time="2026-01-01 00:00:00",
        current_price=105.0,
        initial_sl=90.0,
        remaining_notional=100.0,
        remaining_qty=1.0,
    )
    data.update(overrides)
    return Position(**data)


@pytest.fixture
def live_pf(monkeypatch, tmp_path):
    monkeypatch.setattr("engine.portfolio.pull_state", lambda: None)
    monkeypatch.setattr("engine.portfolio.load_lab_state", lambda: {})
    monkeypatch.setattr("engine.crew.sync.load_crew_state", lambda: {})
    monkeypatch.setattr("engine.exchange.executor.SL_ATTACH_MAX_ATTEMPTS", 3)
    monkeypatch.setattr("engine.exchange.executor.SL_ATTACH_RETRY_DELAY_SEC", 0.0)
    monkeypatch.setattr("engine.exchange.executor.CLOSE_CONFIRM_TIMEOUT_SEC", 0.0)
    monkeypatch.setattr("engine.exchange.executor.CLOSE_CONFIRM_POLL_SEC", 0.0)
    gate = {"live": False}
    monkeypatch.setattr("engine.portfolio.is_live_exchange", lambda: gate["live"])
    clear_alerts()
    set_notifier(None)
    pf = Portfolio(path=str(tmp_path / "state.json"))
    pf.ledgers["Kasa_Canli"] = 1000.0
    gate["live"] = True
    alerts: list[str] = []
    set_notifier(alerts.append)

    def attach(client: FakeClient) -> FakeClient:
        ex = BybitExecutor(client)
        monkeypatch.setattr("engine.exchange.executor.get_executor", lambda: ex)
        return client

    pf.attach = attach  # type: ignore[attr-defined]
    pf.alerts = alerts  # type: ignore[attr-defined]
    yield pf
    set_notifier(None)
    clear_alerts()


def test_create_order_attaches_stop_on_payload():
    client = BybitClient(api_key="k", api_secret="s", base_url="https://test")
    client._instrument_cache["BTCUSDT"] = {
        "symbol": "BTCUSDT",
        "qty_step": 0.001,
        "min_qty": 0.001,
        "tick_size": 0.1,
    }
    captured: dict = {}

    def _request(method, path, params=None, body=None):
        captured["body"] = body
        return {"orderId": "1"}

    client._request = _request  # type: ignore[method-assign]
    client.place_market_order("BTCUSDT", "BUY", 0.01, stop_loss=90.0, take_profit=110.0)
    body = captured["body"]
    assert body["stopLoss"].startswith("90")
    assert body["takeProfit"].startswith("110")
    assert body["tpslMode"] == "Full"
    assert "reduceOnly" not in body

    def _request_close(method, path, params=None, body=None):
        captured["close"] = body
        return {"orderId": "2"}

    client._request = _request_close  # type: ignore[method-assign]
    client.close_position_market("BTCUSDT", "BUY", 0.01)
    assert captured["close"]["reduceOnly"] is True


def test_stop_fails_then_reduce_only_close_is_verified(live_pf):
    client = live_pf.attach(FakeClient())
    client.fail_stop = True
    client.close_avg = 99.0
    opened = live_pf.try_open("BTCUSDT", _signal(), 100.0)
    assert opened is False
    assert live_pf.positions == {}
    assert client.opens and client.opens[0]["stop_loss"] == 90.0
    assert len(client.stop_calls) == 3
    assert len(client.closes) == 1
    assert client.closes[0]["reduce_only"] is True
    assert client.position_size == 0.0
    assert client.position_reads > 0
    assert live_pf.history[-1]["close_reason"] == "SL_TAKILAMADI"
    assert live_pf.history[-1]["exit"] == 99.0
    assert any("SL takilamadi" in msg for msg in live_pf.alerts)


def test_stop_and_close_fail_flags_position_and_alerts(live_pf):
    client = live_pf.attach(FakeClient())
    client.fail_stop = True
    client.fail_close = True
    live_pf.try_open("BTCUSDT", _signal(), 100.0)
    key = live_pf.pos_key("Kasa_Canli", "BTCUSDT")
    assert key in live_pf.positions
    pos = live_pf.positions[key]
    assert pos.kapanis_dogrulanmadi is True
    assert pos.pending_close_reason == "SL_TAKILAMADI"
    assert not any(h.get("symbol") == "BTCUSDT" and not h.get("partial") for h in live_pf.history)
    saved = live_pf._pos_dict(pos)
    live_pf.positions.clear()
    live_pf._apply_raw({"ledgers": dict(live_pf.ledgers), "active_positions": {key: saved}})
    assert live_pf.positions[key].kapanis_dogrulanmadi is True
    assert live_pf.positions[key].pending_close_reason == "SL_TAKILAMADI"
    assert client.position_size > 0
    assert any("kapanis dogrulanamadi" in msg for msg in live_pf.alerts)


def test_close_not_marked_when_exchange_size_still_open(live_pf):
    client = live_pf.attach(FakeClient())
    client.omit_entry_fill = True
    assert live_pf.try_open("BTCUSDT", _signal(), 100.0) is True
    client.hold_open = True
    closed = live_pf.check_exits("BTCUSDT", 80.0)
    key = live_pf.pos_key("Kasa_Canli", "BTCUSDT")
    assert closed == []
    assert key in live_pf.positions
    assert live_pf.positions[key].kapanis_dogrulanmadi is True
    assert live_pf.positions[key].pending_close_reason == "SL"
    assert client.position_size > 0
    assert len(client.closes) == 1
    assert client.closes[0]["reduce_only"] is True
    assert not any(h.get("symbol") == "BTCUSDT" and not h.get("partial") for h in live_pf.history)
    assert any("kapanis dogrulanamadi" in msg for msg in live_pf.alerts)


def test_close_marked_with_exchange_fill_once_confirmed(live_pf):
    client = live_pf.attach(FakeClient())
    client.omit_entry_fill = True
    assert live_pf.try_open("BTCUSDT", _signal(), 100.0) is True
    client.hold_open = True
    assert live_pf.check_exits("BTCUSDT", 80.0) == []
    key = live_pf.pos_key("Kasa_Canli", "BTCUSDT")
    assert live_pf.positions[key].kapanis_dogrulanmadi is True
    oid = client.last_close_id
    client.position_size = 0.0
    client._orders[oid]["status"] = "Filled"
    client._orders[oid]["avg_price"] = 97.25
    closed = live_pf.reconcile_pending_closes()
    assert key not in live_pf.positions
    assert len(closed) == 1
    assert closed[0].exit == 97.25
    assert closed[0].exit != 80.0
    assert live_pf.history[-1]["exit"] == 97.25
    assert live_pf.history[-1]["close_reason"] == "SL"
    assert len(client.closes) == 1


def test_startup_reconcile_fixes_local_exchange_mismatch(live_pf):
    btc_key = live_pf.pos_key("Kasa_Canli", "BTCUSDT")
    sol_key = live_pf.pos_key("Kasa_Canli", "SOLUSDT")
    live_pf.positions[btc_key] = _pos("BTCUSDT", current_price=105.0)
    live_pf.positions[sol_key] = _pos("SOLUSDT", qty=1.5, remaining_qty=1.5, current_price=100.0)
    notes = live_pf.reconcile_exchange(
        [
            {
                "symbol": "ETHUSDT",
                "side": "SELL",
                "size": 2.0,
                "entry_price": 3000.0,
                "stop_loss": 3100.0,
                "leverage": 10,
            },
            {
                "symbol": "SOLUSDT",
                "side": "BUY",
                "size": 1.5,
                "entry_price": 100.0,
                "stop_loss": 90.0,
                "leverage": 10,
            },
        ],
        ledger="Kasa_Canli",
    )
    assert btc_key not in live_pf.positions
    assert live_pf.history[-1]["symbol"] == "BTCUSDT"
    assert live_pf.history[-1]["close_reason"] == "RECONCILE"
    assert live_pf.history[-1]["exit"] == 105.0
    assert sol_key in live_pf.positions
    assert live_pf.positions[sol_key].kapanis_dogrulanmadi is False
    eth = next(p for p in live_pf.positions.values() if p.symbol == "ETHUSDT")
    assert eth.side == Side.SELL
    assert eth.qty == 2.0
    assert eth.sl_price == 3100.0
    assert any("BTCUSDT" in n for n in notes)
    assert any("ETHUSDT" in n for n in notes)
