"""Tests for place_order execution mode guards."""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tradebot.domain.models.order_intent import (
    OrderIntent as DomainOrderIntent,
    OrderIntentStatus,
    OrderType,
    Side,
)
from tradebot.temporal_app.activities import place_order
from tradebot.temporal_app.types import OrderIntent


def _temporal_intent() -> OrderIntent:
    return OrderIntent(
        intent_key="k",
        symbol="BTCUSDC",
        side="BUY",
        timeframe="1m",
        open_time_ms=0,
        payload={},
    )


def _domain_intent(status: OrderIntentStatus = OrderIntentStatus.PENDING) -> DomainOrderIntent:
    return DomainOrderIntent(
        id="intent-001",
        intent_key="k",
        symbol="BTCUSDC",
        side=Side.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("0.01"),
        price=Decimal("50000"),
        status=status,
    )


@contextmanager
def _mock_db(domain_intent: DomainOrderIntent):
    """Patch create_session_factory + OrderIntentRepoSql to avoid real DB."""
    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)

    mock_factory = MagicMock(return_value=mock_session)

    mock_repo = MagicMock()
    mock_repo.get_by_intent_key.return_value = domain_intent
    mock_repo.update_status.return_value = None

    with (
        patch("tradebot.temporal_app.activities.create_session_factory", return_value=mock_factory),
        patch("tradebot.temporal_app.activities.OrderIntentRepoSql", return_value=mock_repo),
    ):
        yield mock_repo


def test_default_backtesting(monkeypatch):
    monkeypatch.setenv("EXECUTION_MODE", "backtesting")
    monkeypatch.delenv("LIVE_TRADING_APPROVED", raising=False)
    with _mock_db(_domain_intent()):
        out = asyncio.run(place_order(_temporal_intent()))
    assert out["mode"] == "backtesting"


def test_live_blocked_without_approval(monkeypatch):
    monkeypatch.setenv("EXECUTION_MODE", "live")
    monkeypatch.setenv("LIVE_TRADING_APPROVED", "false")
    with pytest.raises(RuntimeError):
        asyncio.run(place_order(_temporal_intent()))


def test_live_allowed_with_approval(monkeypatch):
    monkeypatch.setenv("EXECUTION_MODE", "live")
    monkeypatch.setenv("LIVE_TRADING_APPROVED", "true")

    mock_resp = MagicMock()
    mock_resp.data = {"orderId": 123456}

    mock_client = AsyncMock()
    mock_client.place_order = AsyncMock(return_value=mock_resp)
    mock_client.close = AsyncMock()

    with (
        _mock_db(_domain_intent()),
        patch("tradebot.temporal_app.activities.BinanceRestClient", return_value=mock_client),
    ):
        out = asyncio.run(place_order(_temporal_intent()))
    assert out["mode"] == "live"


def test_dry_run_alias_maps_to_backtesting(monkeypatch):
    monkeypatch.setenv("EXECUTION_MODE", "dry_run")
    monkeypatch.delenv("LIVE_TRADING_APPROVED", raising=False)
    with _mock_db(_domain_intent()):
        out = asyncio.run(place_order(_temporal_intent()))
    assert out["mode"] == "backtesting"
