import asyncio
import json
import sys
from decimal import Decimal

from aiohttp.test_utils import make_mocked_request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tradebot.api.app import create_app
from tradebot.config.settings import Settings
from tradebot.infra.db.models import Base, Candle


def _build_settings(tmp_path, db_url: str) -> Settings:
    return Settings(
        api_host="127.0.0.1",
        api_port=0,
        database_url=db_url,
        daemon_pid_file=str(tmp_path / "ws_candle_daemon.pid"),
        daemon_command=f'{sys.executable} -c "import time; time.sleep(60)"',
        daemon_stop_timeout_s=0.2,
    )


def _seed_candles(db_url: str) -> None:
    engine = create_engine(db_url, future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    with session_factory() as session:
        session.add_all(
            [
                Candle(
                    symbol="BTCUSDC",
                    timeframe="1m",
                    open_time_ms=1_000,
                    close_time_ms=1_999,
                    open=Decimal("100"),
                    high=Decimal("101"),
                    low=Decimal("99"),
                    close=Decimal("100.5"),
                    volume=Decimal("10"),
                    is_partial=False,
                    shard_id=1,
                ),
                Candle(
                    symbol="BTCUSDC",
                    timeframe="1m",
                    open_time_ms=2_000,
                    close_time_ms=2_999,
                    open=Decimal("101"),
                    high=Decimal("102"),
                    low=Decimal("100"),
                    close=Decimal("101.5"),
                    volume=Decimal("12"),
                    is_partial=False,
                    shard_id=1,
                ),
                Candle(
                    symbol="BTCUSDC",
                    timeframe="1m",
                    open_time_ms=3_000,
                    close_time_ms=3_999,
                    open=Decimal("102"),
                    high=Decimal("103"),
                    low=Decimal("101"),
                    close=Decimal("102.5"),
                    volume=Decimal("13"),
                    is_partial=False,
                    shard_id=1,
                ),
                Candle(
                    symbol="BTCUSDC",
                    timeframe="1m",
                    open_time_ms=4_000,
                    close_time_ms=4_999,
                    open=Decimal("103"),
                    high=Decimal("104"),
                    low=Decimal("102"),
                    close=Decimal("103.5"),
                    volume=Decimal("14"),
                    is_partial=False,
                    shard_id=1,
                ),
                Candle(
                    symbol="BTCUSDC",
                    timeframe="5m",
                    open_time_ms=5_000,
                    close_time_ms=5_999,
                    open=Decimal("104"),
                    high=Decimal("105"),
                    low=Decimal("103"),
                    close=Decimal("104.5"),
                    volume=Decimal("15"),
                    is_partial=False,
                    shard_id=1,
                ),
                Candle(
                    symbol="ETHUSDC",
                    timeframe="5m",
                    open_time_ms=2_500,
                    close_time_ms=2_999,
                    open=Decimal("200"),
                    high=Decimal("201"),
                    low=Decimal("199"),
                    close=Decimal("200.5"),
                    volume=Decimal("20"),
                    is_partial=False,
                    shard_id=1,
                ),
            ]
        )
        session.commit()
    engine.dispose()


def _init_db(db_url: str) -> None:
    engine = create_engine(db_url, future=True)
    Base.metadata.create_all(engine)
    engine.dispose()


async def _call(app, method: str, path: str):
    req = make_mocked_request(method, path, app=app)
    req["correlation_id"] = "test-correlation-id"
    resp = await app._handle(req)
    payload = json.loads(resp.body.decode("utf-8")) if resp.body else None
    return resp.status, payload


async def _with_app(settings: Settings, test_fn):
    app = create_app(settings)
    await test_fn(app)


def test_chart_symbols_and_timeframes(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'chart.db'}"
    _seed_candles(db_url)
    settings = _build_settings(tmp_path, db_url)

    async def _case(app):
        status, payload = await _call(app, "GET", "/chart/symbols")
        assert status == 200
        assert payload["ok"] is True
        assert payload["data"] == ["BTCUSDC", "ETHUSDC"]

        status, payload = await _call(app, "GET", "/chart/timeframes")
        assert status == 200
        assert payload["ok"] is True
        assert payload["data"] == ["1m", "5m"]

        status, payload = await _call(app, "GET", "/chart/timeframes?symbol=BTCUSDC")
        assert status == 200
        assert payload["ok"] is True
        assert payload["data"] == ["1m", "5m"]

    asyncio.run(_with_app(settings, _case))


def test_chart_candles_returns_latest_window_sorted_asc(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'chart.db'}"
    _seed_candles(db_url)
    settings = _build_settings(tmp_path, db_url)

    async def _case(app):
        status, payload = await _call(
            app,
            "GET",
            "/chart/candles?symbol=BTCUSDC&timeframe=1m&limit=2",
        )
        assert status == 200
        assert payload["ok"] is True
        assert [item["open_time_ms"] for item in payload["data"]] == [3_000, 4_000]

        candle = payload["data"][0]
        assert set(candle.keys()) == {
            "open",
            "high",
            "low",
            "close",
            "open_time_ms",
            "close_time_ms",
            "volume",
            "is_partial",
        }

    asyncio.run(_with_app(settings, _case))


def test_chart_candles_from_open_time_ms_is_strict(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'chart.db'}"
    _seed_candles(db_url)
    settings = _build_settings(tmp_path, db_url)

    async def _case(app):
        status, payload = await _call(
            app,
            "GET",
            "/chart/candles?symbol=BTCUSDC&timeframe=1m&from_open_time_ms=2000",
        )
        assert status == 200
        assert payload["ok"] is True
        assert [item["open_time_ms"] for item in payload["data"]] == [3_000, 4_000]

    asyncio.run(_with_app(settings, _case))


def test_chart_empty_state(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'chart.db'}"
    _init_db(db_url)
    settings = _build_settings(tmp_path, db_url)

    async def _case(app):
        status, payload = await _call(app, "GET", "/chart/symbols")
        assert status == 200
        assert payload["ok"] is True
        assert payload["data"] == []

        status, payload = await _call(
            app, "GET", "/chart/candles?symbol=BTCUSDC&timeframe=1m"
        )
        assert status == 200
        assert payload["ok"] is True
        assert payload["data"] == []

    asyncio.run(_with_app(settings, _case))


def test_chart_validation_errors(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'chart.db'}"
    _init_db(db_url)
    settings = _build_settings(tmp_path, db_url)

    async def _case(app):
        status, payload = await _call(app, "GET", "/chart/timeframes?symbol=BTC-USDC")
        assert status == 400
        assert payload["ok"] is False
        assert payload["error"]["code"] == "invalid_request"

        status, payload = await _call(app, "GET", "/chart/candles?timeframe=1m")
        assert status == 400
        assert payload["ok"] is False
        assert payload["error"]["code"] == "invalid_request"

        status, payload = await _call(
            app, "GET", "/chart/candles?symbol=BTCUSDC&timeframe=1m&limit=0"
        )
        assert status == 400
        assert payload["ok"] is False
        assert payload["error"]["code"] == "invalid_request"

        status, payload = await _call(
            app,
            "GET",
            "/chart/candles?symbol=BTCUSDC&timeframe=1m&from_open_time_ms=-1",
        )
        assert status == 400
        assert payload["ok"] is False
        assert payload["error"]["code"] == "invalid_request"

    asyncio.run(_with_app(settings, _case))
