"""Unit tests for backtesting API routes."""

from __future__ import annotations

import asyncio
import json
import sys
import uuid

import pytest
from aiohttp.test_utils import make_mocked_request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tradebot.api.app import create_app
from tradebot.config.settings import Settings
from tradebot.infra.db.models import Base, BacktestRun, BacktestTradeRecord
import tradebot.infra.db.engine as _db_engine_module


@pytest.fixture(autouse=True)
def reset_db_singleton():
    """Reset the SQLAlchemy session factory singleton before each test."""
    _db_engine_module._engine = None
    _db_engine_module._session_factory = None
    yield
    _db_engine_module._engine = None
    _db_engine_module._session_factory = None


def _build_settings(tmp_path, db_url: str) -> Settings:
    return Settings(
        api_host="127.0.0.1",
        api_port=0,
        database_url=db_url,
        daemon_pid_file=str(tmp_path / "ws_candle_daemon.pid"),
        daemon_command=f'{sys.executable} -c "import time; time.sleep(60)"',
        daemon_stop_timeout_s=0.2,
    )


def _init_db(db_url: str):
    engine = create_engine(db_url, future=True)
    Base.metadata.create_all(engine)
    engine.dispose()


def _session_factory(db_url: str):
    engine = create_engine(db_url, future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def _seed_run(sf, run_id=None, symbol="BTCUSDC", closed_trades=25, passes=True):
    rid = run_id or str(uuid.uuid4())
    with sf() as s:
        s.add(
            BacktestRun(
                id=rid,
                symbol=symbol,
                from_ms=1_700_000_000_000,
                to_ms=1_700_100_000_000,
                profile="regular",
                config_json={"profile": "regular", "min_closed_trades": 20},
                total_trades=closed_trades + 2,
                closed_trades=closed_trades,
                winning_trades=int(closed_trades * 0.6),
                winrate=0.6,
                profit_factor=1.8,
                max_drawdown_pct=5.0,
                expectancy_r=0.5,
                avg_mfe_pct=2.0,
                avg_mae_pct=1.0,
                passes_phase_gate=passes,
            )
        )
        s.commit()
    return rid


_trade_id_counter = 0


def _seed_trade(sf, run_id, pnl_r=1.5, exit_reason="TP"):
    global _trade_id_counter
    _trade_id_counter += 1
    with sf() as s:
        s.add(
            BacktestTradeRecord(
                id=_trade_id_counter,
                run_id=run_id,
                symbol="BTCUSDC",
                entry_time_ms=1_700_000_100_000,
                entry_price=40000.0,
                stop_loss=39000.0,
                take_profit=41500.0,
                sl_method="PIVOT",
                exit_time_ms=1_700_000_200_000 if exit_reason != "OPEN" else None,
                exit_price=41500.0
                if exit_reason == "TP"
                else (39000.0 if exit_reason == "SL" else None),
                exit_reason=exit_reason,
                pnl_r=pnl_r if exit_reason != "OPEN" else None,
                mfe_pct=2.0,
                mae_pct=0.5,
                signal_score=75,
                signal_context_json={"4h": {"trend": True}},
            )
        )
        s.commit()


async def _call(app, method: str, path: str, body=None):
    if body is not None:
        data = json.dumps(body).encode()
        req = make_mocked_request(
            method,
            path,
            app=app,
            headers={"Content-Type": "application/json"},
        )
        req._payload = data
        req.content._read_nowait = lambda: data
    else:
        req = make_mocked_request(method, path, app=app)
    req["correlation_id"] = "test-cid"
    resp = await app._handle(req)
    raw = resp.body
    if raw:
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            payload = raw.decode("utf-8")
    else:
        payload = None
    return resp.status, payload


async def _post_json(app, path: str, body: dict):
    """POST with JSON body using aiohttp TestClient approach."""
    req = make_mocked_request("POST", path, app=app)
    req["correlation_id"] = "test-cid"
    # Inject body via a custom read method
    raw = json.dumps(body).encode()

    async def _read():
        return raw

    req._payload = type("P", (), {"read": staticmethod(_read)})()
    resp = await app._handle(req)
    raw_resp = resp.body
    if raw_resp:
        try:
            payload = json.loads(raw_resp.decode("utf-8"))
        except Exception:
            payload = raw_resp.decode("utf-8")
    else:
        payload = None
    return resp.status, payload


# ---------------------------------------------------------------------------
# GET /backtesting/readiness
# ---------------------------------------------------------------------------


class TestReadinessEndpoint:
    def test_missing_symbol(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/bt.db"
        _init_db(db_url)
        settings = _build_settings(tmp_path, db_url)

        async def _case(app):
            status, payload = await _call(
                app,
                "GET",
                "/backtesting/readiness?from_ms=1700000000000&to_ms=1700001000000",
            )
            assert status == 400
            assert payload["ok"] is False

        asyncio.run(_case(create_app(settings)))

    def test_invalid_symbol(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/bt.db"
        _init_db(db_url)
        settings = _build_settings(tmp_path, db_url)

        async def _case(app):
            status, payload = await _call(
                app,
                "GET",
                "/backtesting/readiness?symbol=btc_usdc&from_ms=1700000000000&to_ms=1700001000000",
            )
            assert status == 400

        asyncio.run(_case(create_app(settings)))

    def test_missing_dates(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/bt.db"
        _init_db(db_url)
        settings = _build_settings(tmp_path, db_url)

        async def _case(app):
            status, payload = await _call(
                app, "GET", "/backtesting/readiness?symbol=BTCUSDC"
            )
            assert status == 400

        asyncio.run(_case(create_app(settings)))

    def test_from_gte_to(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/bt.db"
        _init_db(db_url)
        settings = _build_settings(tmp_path, db_url)

        async def _case(app):
            status, payload = await _call(
                app,
                "GET",
                "/backtesting/readiness?symbol=BTCUSDC&from_ms=1700001000000&to_ms=1700000000000",
            )
            assert status == 400

        asyncio.run(_case(create_app(settings)))

    def test_happy_path_empty_db(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/bt.db"
        _init_db(db_url)
        settings = _build_settings(tmp_path, db_url)

        async def _case(app):
            status, payload = await _call(
                app,
                "GET",
                "/backtesting/readiness?symbol=BTCUSDC&from_ms=1700000000000&to_ms=1700007200000",
            )
            assert status == 200
            assert payload["ok"] is True
            d = payload["data"]
            assert d["symbol"] == "BTCUSDC"
            assert d["status"] == "blocked"
            assert len(d["timeframes"]) == 5

        asyncio.run(_case(create_app(settings)))

    def test_range_too_large(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/bt.db"
        _init_db(db_url)
        settings = _build_settings(tmp_path, db_url)
        _MS_366_DAYS = 366 * 24 * 3_600_000

        async def _case(app):
            status, payload = await _call(
                app,
                "GET",
                f"/backtesting/readiness?symbol=BTCUSDC&from_ms=1000000000000&to_ms={1000000000000 + _MS_366_DAYS}",
            )
            assert status == 400

        asyncio.run(_case(create_app(settings)))


# ---------------------------------------------------------------------------
# GET /backtesting/runs
# ---------------------------------------------------------------------------


class TestListRunsEndpoint:
    def test_empty_list(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/bt.db"
        _init_db(db_url)
        settings = _build_settings(tmp_path, db_url)

        async def _case(app):
            status, payload = await _call(app, "GET", "/backtesting/runs")
            assert status == 200
            assert payload["ok"] is True
            assert payload["data"]["items"] == []
            assert payload["data"]["next_cursor"] is None

        asyncio.run(_case(create_app(settings)))

    def test_list_with_runs(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/bt.db"
        sf = _session_factory(db_url)
        rid = _seed_run(sf)
        settings = _build_settings(tmp_path, db_url)

        async def _case(app):
            status, payload = await _call(app, "GET", "/backtesting/runs")
            assert status == 200
            assert len(payload["data"]["items"]) == 1
            assert payload["data"]["items"][0]["run_id"] == rid

        asyncio.run(_case(create_app(settings)))

    def test_filter_by_symbol(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/bt.db"
        sf = _session_factory(db_url)
        _seed_run(sf, symbol="BTCUSDC")
        _seed_run(sf, symbol="ETHUSDC")
        settings = _build_settings(tmp_path, db_url)

        async def _case(app):
            status, payload = await _call(
                app, "GET", "/backtesting/runs?symbol=ETHUSDC"
            )
            assert status == 200
            items = payload["data"]["items"]
            assert all(i["symbol"] == "ETHUSDC" for i in items)

        asyncio.run(_case(create_app(settings)))

    def test_invalid_limit(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/bt.db"
        _init_db(db_url)
        settings = _build_settings(tmp_path, db_url)

        async def _case(app):
            status, payload = await _call(app, "GET", "/backtesting/runs?limit=200")
            assert status == 400

        asyncio.run(_case(create_app(settings)))


# ---------------------------------------------------------------------------
# GET /backtesting/runs/{run_id}
# ---------------------------------------------------------------------------


class TestGetRunEndpoint:
    def test_not_found(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/bt.db"
        _init_db(db_url)
        settings = _build_settings(tmp_path, db_url)

        async def _case(app):
            status, payload = await _call(
                app, "GET", "/backtesting/runs/nonexistent-id"
            )
            assert status == 404
            assert payload["ok"] is False

        asyncio.run(_case(create_app(settings)))

    def test_found_with_verdict(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/bt.db"
        sf = _session_factory(db_url)
        rid = _seed_run(sf, passes=True)
        settings = _build_settings(tmp_path, db_url)

        async def _case(app):
            status, payload = await _call(app, "GET", f"/backtesting/runs/{rid}")
            assert status == 200
            assert payload["ok"] is True
            d = payload["data"]
            assert d["run_id"] == rid
            assert d["verdict"] == "PASS"

        asyncio.run(_case(create_app(settings)))

    def test_verdict_inconclusive_few_trades(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/bt.db"
        sf = _session_factory(db_url)
        rid = _seed_run(sf, closed_trades=5, passes=False)
        settings = _build_settings(tmp_path, db_url)

        async def _case(app):
            status, payload = await _call(app, "GET", f"/backtesting/runs/{rid}")
            assert status == 200
            assert payload["data"]["verdict"] == "INCONCLUSIVE"

        asyncio.run(_case(create_app(settings)))

    def test_verdict_fail(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/bt.db"
        sf = _session_factory(db_url)
        rid = _seed_run(sf, closed_trades=25, passes=False)
        settings = _build_settings(tmp_path, db_url)

        async def _case(app):
            status, payload = await _call(app, "GET", f"/backtesting/runs/{rid}")
            assert status == 200
            assert payload["data"]["verdict"] == "FAIL"

        asyncio.run(_case(create_app(settings)))


# ---------------------------------------------------------------------------
# GET /backtesting/runs/{run_id}/trades
# ---------------------------------------------------------------------------


class TestListTradesEndpoint:
    def test_empty_trades(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/bt.db"
        sf = _session_factory(db_url)
        rid = _seed_run(sf)
        settings = _build_settings(tmp_path, db_url)

        async def _case(app):
            status, payload = await _call(app, "GET", f"/backtesting/runs/{rid}/trades")
            assert status == 200
            assert payload["data"]["items"] == []

        asyncio.run(_case(create_app(settings)))

    def test_returns_trades(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/bt.db"
        sf = _session_factory(db_url)
        rid = _seed_run(sf)
        _seed_trade(sf, rid, pnl_r=1.5, exit_reason="TP")
        _seed_trade(sf, rid, pnl_r=-1.0, exit_reason="SL")
        settings = _build_settings(tmp_path, db_url)

        async def _case(app):
            status, payload = await _call(app, "GET", f"/backtesting/runs/{rid}/trades")
            assert status == 200
            assert len(payload["data"]["items"]) == 2

        asyncio.run(_case(create_app(settings)))

    def test_filter_result_win(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/bt.db"
        sf = _session_factory(db_url)
        rid = _seed_run(sf)
        _seed_trade(sf, rid, pnl_r=1.5, exit_reason="TP")
        _seed_trade(sf, rid, pnl_r=-1.0, exit_reason="SL")
        settings = _build_settings(tmp_path, db_url)

        async def _case(app):
            status, payload = await _call(
                app, "GET", f"/backtesting/runs/{rid}/trades?result=win"
            )
            assert status == 200
            items = payload["data"]["items"]
            assert len(items) == 1
            assert items[0]["pnl_r"] > 0

        asyncio.run(_case(create_app(settings)))

    def test_filter_reason_sl(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/bt.db"
        sf = _session_factory(db_url)
        rid = _seed_run(sf)
        _seed_trade(sf, rid, pnl_r=1.5, exit_reason="TP")
        _seed_trade(sf, rid, pnl_r=-1.0, exit_reason="SL")
        settings = _build_settings(tmp_path, db_url)

        async def _case(app):
            status, payload = await _call(
                app, "GET", f"/backtesting/runs/{rid}/trades?reason=SL"
            )
            assert status == 200
            items = payload["data"]["items"]
            assert all(i["exit_reason"] == "SL" for i in items)

        asyncio.run(_case(create_app(settings)))

    def test_invalid_result_filter(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/bt.db"
        _init_db(db_url)
        settings = _build_settings(tmp_path, db_url)

        async def _case(app):
            status, payload = await _call(
                app, "GET", "/backtesting/runs/someid/trades?result=invalid"
            )
            assert status == 400

        asyncio.run(_case(create_app(settings)))


# ---------------------------------------------------------------------------
# GET /backtesting/runs/{run_id}/report
# ---------------------------------------------------------------------------


class TestReportEndpoint:
    def test_not_found(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/bt.db"
        _init_db(db_url)
        settings = _build_settings(tmp_path, db_url)

        async def _case(app):
            status, payload = await _call(app, "GET", "/backtesting/runs/nope/report")
            assert status == 404

        asyncio.run(_case(create_app(settings)))

    def test_json_format(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/bt.db"
        sf = _session_factory(db_url)
        rid = _seed_run(sf)
        _seed_trade(sf, rid)
        settings = _build_settings(tmp_path, db_url)

        async def _case(app):
            status, payload = await _call(
                app, "GET", f"/backtesting/runs/{rid}/report?format=json"
            )
            assert status == 200
            assert payload["ok"] is True
            d = payload["data"]
            assert "trades" in d
            assert len(d["trades"]) == 1

        asyncio.run(_case(create_app(settings)))

    def test_markdown_format(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/bt.db"
        sf = _session_factory(db_url)
        rid = _seed_run(sf)
        _seed_trade(sf, rid)
        settings = _build_settings(tmp_path, db_url)

        async def _case(app):
            status, body = await _call(
                app, "GET", f"/backtesting/runs/{rid}/report?format=markdown"
            )
            assert status == 200
            assert isinstance(body, str)
            assert "# Backtest Report" in body

        asyncio.run(_case(create_app(settings)))

    def test_invalid_format(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/bt.db"
        _init_db(db_url)
        settings = _build_settings(tmp_path, db_url)

        async def _case(app):
            status, payload = await _call(
                app, "GET", "/backtesting/runs/someid/report?format=csv"
            )
            assert status == 400

        asyncio.run(_case(create_app(settings)))


# ---------------------------------------------------------------------------
# GET /backtesting
# ---------------------------------------------------------------------------


class TestBacktestingStaticPage:
    def test_backtesting_html_route_exists(self, tmp_path):
        db_url = f"sqlite:///{tmp_path}/bt.db"
        _init_db(db_url)
        settings = _build_settings(tmp_path, db_url)

        async def _case(app):
            # FileResponse doesn't go through _handle the same way;
            # just verify the route is registered
            routes = [r.resource.canonical for r in app.router.routes()]
            assert "/backtesting" in routes

        asyncio.run(_case(create_app(settings)))
