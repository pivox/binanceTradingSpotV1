import asyncio

import pytest

from tradebot.apps import ws_candle_daemon as daemon


def _tickers():
    return [
        {"symbol": "AAAUSDT", "quoteVolume": "999"},
        {"symbol": "bbbUsdc", "quoteVolume": "100"},
        {"symbol": "zzzusdc", "quoteVolume": 100},
        {"symbol": "cccUSDC", "quoteVolume": "50"},
        {"symbol": "bad", "quoteVolume": None},
    ]


def test_load_symbols_dynamic_filters_orders_limits(monkeypatch):
    monkeypatch.delenv("SYMBOLS", raising=False)
    monkeypatch.setenv("USDC_PAIRS_LIMIT", "2")

    async def fake_fetch(_base_url):
        return _tickers()

    monkeypatch.setattr(daemon, "fetch_24h_tickers", fake_fetch)

    out = asyncio.run(daemon.load_symbols())
    assert out == ["BBBUSDC", "ZZZUSDC"]


def test_load_symbols_invalid_limit_zero(monkeypatch):
    monkeypatch.delenv("SYMBOLS", raising=False)
    monkeypatch.setenv("USDC_PAIRS_LIMIT", "0")

    async def fake_fetch(_base_url):
        return _tickers()

    monkeypatch.setattr(daemon, "fetch_24h_tickers", fake_fetch)

    with pytest.raises(RuntimeError, match="USDC_PAIRS_LIMIT must be > 0"):
        asyncio.run(daemon.load_symbols())


def test_load_symbols_invalid_limit_non_numeric(monkeypatch):
    monkeypatch.delenv("SYMBOLS", raising=False)
    monkeypatch.setenv("USDC_PAIRS_LIMIT", "nope")

    async def fake_fetch(_base_url):
        return _tickers()

    monkeypatch.setattr(daemon, "fetch_24h_tickers", fake_fetch)

    with pytest.raises(RuntimeError, match="USDC_PAIRS_LIMIT must be an integer"):
        asyncio.run(daemon.load_symbols())


def test_ws_loop_fails_fast_on_first_boot(monkeypatch):
    async def fake_pool():
        return object()

    async def boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(daemon, "get_pool", fake_pool)
    monkeypatch.setattr(daemon, "load_symbols", boom)

    with pytest.raises(RuntimeError):
        asyncio.run(daemon.ws_loop())
