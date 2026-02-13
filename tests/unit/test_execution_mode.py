import asyncio
import pytest

from tradebot.temporal_app.activities import place_order
from tradebot.temporal_app.types import OrderIntent


def _intent() -> OrderIntent:
    return OrderIntent(
        intent_key="k",
        symbol="BTCUSDC",
        side="BUY",
        timeframe="1m",
        open_time_ms=0,
        payload={},
    )


def test_default_dry_run(monkeypatch):
    monkeypatch.setenv("EXECUTION_MODE", "dry_run")
    monkeypatch.delenv("LIVE_TRADING_APPROVED", raising=False)
    out = asyncio.run(place_order(_intent()))
    assert out["mode"] == "dry_run"


def test_live_blocked_without_approval(monkeypatch):
    monkeypatch.setenv("EXECUTION_MODE", "live")
    monkeypatch.setenv("LIVE_TRADING_APPROVED", "false")
    with pytest.raises(RuntimeError):
        asyncio.run(place_order(_intent()))


def test_live_allowed_with_approval(monkeypatch):
    monkeypatch.setenv("EXECUTION_MODE", "live")
    monkeypatch.setenv("LIVE_TRADING_APPROVED", "true")
    out = asyncio.run(place_order(_intent()))
    assert out["mode"] == "live"
