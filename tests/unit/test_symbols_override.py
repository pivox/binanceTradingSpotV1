import asyncio
import pytest

from tradebot.apps.ws_candle_daemon import (
    get_pool,
    parse_symbols_override,
    load_symbols,
    subscribe_in_chunks,
)


def test_parse_symbols_override_valid():
    raw = "btcusdc, ethusdc ,SOLusdc"
    out = parse_symbols_override(raw)
    assert out == ["BTCUSDC", "ETHUSDC", "SOLUSDC"]


def test_parse_symbols_override_empty():
    assert parse_symbols_override("") == []


def test_parse_symbols_override_invalid():
    with pytest.raises(RuntimeError):
        parse_symbols_override(" , , ")


def test_load_symbols_override(monkeypatch):
    monkeypatch.setenv("SYMBOLS", "BTCUSDC,ETHUSDC")
    out = asyncio.run(load_symbols())
    assert out == ["BTCUSDC", "ETHUSDC"]


def test_subscribe_chunking():
    class DummyWS:
        def __init__(self):
            self.sent = []

        async def send(self, data):
            self.sent.append(data)

    async def _run():
        ws = DummyWS()
        symbols = [f"S{i}USDC" for i in range(450)]
        await subscribe_in_chunks(ws, symbols, chunk_size=200)
        return ws.sent

    sent = asyncio.run(_run())
    assert len(sent) == 3


def test_get_pool_normalizes_sqlalchemy_url(monkeypatch):
    import tradebot.apps.ws_candle_daemon as daemon

    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/tradebot"
    )

    seen = {}

    async def fake_create_pool(dsn, min_size, max_size):
        seen["dsn"] = dsn
        seen["min_size"] = min_size
        seen["max_size"] = max_size
        return object()

    monkeypatch.setattr(daemon.asyncpg, "create_pool", fake_create_pool)

    pool = asyncio.run(get_pool())
    assert pool is not None
    assert seen["dsn"] == "postgresql://user:pass@localhost:5432/tradebot"
    assert seen["min_size"] == 1
    assert seen["max_size"] == 10
