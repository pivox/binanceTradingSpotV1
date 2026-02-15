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


def test_validate_stream_selection_hard_cap(monkeypatch):
    monkeypatch.setenv("USDC_STREAMS_HARD_CAP", "2")
    with pytest.raises(RuntimeError, match="USDC_STREAMS_HARD_CAP"):
        daemon.validate_stream_selection(["BTCUSDC", "ETHUSDC", "SOLUSDC"])


def test_compute_reconnect_delay_is_bounded():
    assert daemon.compute_reconnect_delay_s(1, 2, 30) == 2
    assert daemon.compute_reconnect_delay_s(2, 2, 30) == 4
    assert daemon.compute_reconnect_delay_s(3, 2, 30) == 8
    assert daemon.compute_reconnect_delay_s(6, 2, 30) == 30


def test_log_reconnect_observability(monkeypatch):
    class DummyLogger:
        def __init__(self):
            self.events = []

        def warning(self, event, **kwargs):
            self.events.append((event, kwargs))

    logger = DummyLogger()
    before = daemon.WS_RECONNECT_TOTAL._value.get()
    daemon.log_reconnect_observability(
        logger,
        attempt=3,
        delay_s=8,
        error="RuntimeError('ws down')",
        streams=42,
    )
    after = daemon.WS_RECONNECT_TOTAL._value.get()
    assert after == before + 1
    assert logger.events[0][0] == "ws_reconnect_scheduled"
    assert logger.events[0][1]["attempt"] == 3
    assert logger.events[0][1]["delay_s"] == 8
    assert logger.events[0][1]["streams"] == 42


def test_log_boot_observability_slow_increments_metric():
    class DummyLogger:
        def __init__(self):
            self.info_events = []
            self.warn_events = []

        def info(self, event, **kwargs):
            self.info_events.append((event, kwargs))

        def warning(self, event, **kwargs):
            self.warn_events.append((event, kwargs))

    logger = DummyLogger()
    before = daemon.WS_BOOT_SLOW_TOTAL._value.get()
    daemon.log_boot_observability(
        logger,
        streams=10,
        symbols_ms=100,
        subscribe_ms=100,
        boot_ms=7000,
        boot_warn_ms=5000,
    )
    after = daemon.WS_BOOT_SLOW_TOTAL._value.get()
    assert after == before + 1
    assert logger.info_events[0][0] == "ws_boot_complete"
    assert logger.warn_events[0][0] == "ws_boot_slow"
