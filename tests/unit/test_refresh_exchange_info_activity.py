from __future__ import annotations

import asyncio

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from tradebot.infra.db.models import Base, ExchangeInfoCache
from tradebot.temporal_app import activities as act


def _session_factory(db_url: str):
    engine = create_engine(db_url, future=True)
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, autocommit=False, autoflush=False)


def test_refresh_exchange_info_caches_symbol_filters(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'refresh_exchange_info.db'}"
    engine, sf = _session_factory(db_url)
    try:
        monkeypatch.setenv("DATABASE_URL", db_url)

        async def _fake_fetch(
            _http_session,
            *,
            base_url: str,
        ) -> act._HttpObjectResult:
            del base_url
            return act._HttpObjectResult(
                status=200,
                headers={"X-MBX-USED-WEIGHT-1M": "20"},
                payload={
                    "timezone": "UTC",
                    "serverTime": 1700000000000,
                    "symbols": [
                        {
                            "symbol": "BTCUSDC",
                            "status": "TRADING",
                            "baseAsset": "BTC",
                            "quoteAsset": "USDC",
                            "orderTypes": ["LIMIT", "MARKET"],
                            "permissions": ["SPOT"],
                            "filters": [
                                {
                                    "filterType": "PRICE_FILTER",
                                    "minPrice": "0.01000000",
                                    "maxPrice": "1000000.00000000",
                                    "tickSize": "0.01000000",
                                },
                                {
                                    "filterType": "LOT_SIZE",
                                    "minQty": "0.00001000",
                                    "maxQty": "9000.00000000",
                                    "stepSize": "0.00001000",
                                },
                                {
                                    "filterType": "MIN_NOTIONAL",
                                    "minNotional": "5.00000000",
                                },
                            ],
                        }
                    ],
                },
            )

        monkeypatch.setattr(act, "_fetch_binance_exchange_info", _fake_fetch)

        out = asyncio.run(act.refresh_exchange_info())
        assert out["ok"] is True
        assert out["symbols_total"] == 1
        assert out["symbols_trading"] == 1
        assert out["symbols_usdc"] == 1
        assert out["inserted"] == 1
        assert out["updated"] == 0
        assert out["used_weight_1m"] == 20

        with sf() as session:
            row = session.scalar(
                select(ExchangeInfoCache).where(ExchangeInfoCache.symbol == "BTCUSDC")
            )
            assert row is not None
            assert row.status == "TRADING"
            assert row.base_asset == "BTC"
            assert row.quote_asset == "USDC"
            assert float(row.price_tick_size) == 0.01
            assert float(row.qty_step_size) == 0.00001
            assert float(row.min_notional) == 5.0
            assert row.order_types_json == ["LIMIT", "MARKET"]
    finally:
        engine.dispose()


def test_refresh_exchange_info_updates_existing_symbol(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'refresh_exchange_info_update.db'}"
    engine, sf = _session_factory(db_url)
    try:
        with sf() as session:
            session.add(
                ExchangeInfoCache(
                    symbol="BTCUSDC",
                    status="TRADING",
                    base_asset="BTC",
                    quote_asset="USDC",
                    price_tick_size=0.01,
                    price_min=0.01,
                    price_max=1000000.0,
                    qty_step_size=0.00001,
                    qty_min=0.00001,
                    qty_max=9000.0,
                    min_notional=5.0,
                    max_notional=None,
                    order_types_json=["LIMIT"],
                    permissions_json=["SPOT"],
                    filters_json=[],
                    payload_json={"symbol": "BTCUSDC"},
                    fetched_at_ms=1,
                )
            )
            session.commit()

        monkeypatch.setenv("DATABASE_URL", db_url)

        async def _fake_fetch(
            _http_session,
            *,
            base_url: str,
        ) -> act._HttpObjectResult:
            del base_url
            return act._HttpObjectResult(
                status=200,
                headers={"X-MBX-USED-WEIGHT-1M": "21"},
                payload={
                    "symbols": [
                        {
                            "symbol": "BTCUSDC",
                            "status": "BREAK",
                            "baseAsset": "BTC",
                            "quoteAsset": "USDC",
                            "orderTypes": ["LIMIT"],
                            "permissions": ["SPOT"],
                            "filters": [
                                {
                                    "filterType": "PRICE_FILTER",
                                    "minPrice": "0.10000000",
                                    "maxPrice": "1000000.00000000",
                                    "tickSize": "0.10000000",
                                }
                            ],
                        }
                    ]
                },
            )

        monkeypatch.setattr(act, "_fetch_binance_exchange_info", _fake_fetch)

        out = asyncio.run(act.refresh_exchange_info())
        assert out["ok"] is True
        assert out["inserted"] == 0
        assert out["updated"] == 1

        with sf() as session:
            row = session.scalar(
                select(ExchangeInfoCache).where(ExchangeInfoCache.symbol == "BTCUSDC")
            )
            assert row is not None
            assert row.status == "BREAK"
            assert float(row.price_tick_size) == 0.1
    finally:
        engine.dispose()
