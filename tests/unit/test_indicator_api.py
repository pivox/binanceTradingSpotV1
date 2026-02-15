from __future__ import annotations

import asyncio
import json
import sys

from aiohttp.test_utils import make_mocked_request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tradebot.api.app import create_app
from tradebot.api.indicator_repository import IndicatorRepository
from tradebot.config.settings import Settings
from tradebot.infra.db.models import Base


def _build_settings(tmp_path, db_url: str) -> Settings:
    return Settings(
        api_host="127.0.0.1",
        api_port=0,
        database_url=db_url,
        daemon_pid_file=str(tmp_path / "ws_candle_daemon.pid"),
        daemon_command=f'{sys.executable} -c "import time; time.sleep(60)"',
        daemon_stop_timeout_s=0.2,
        indicator_history_max_limit=5,
        indicator_default_schema_version="1.0.0",
    )


def _seed_snapshots(db_url: str, *, count: int = 3) -> None:
    engine = create_engine(db_url, future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    with session_factory() as session:
        repo = IndicatorRepository(session)
        for index in range(count):
            close_time_ms = (index + 1) * 1_000
            rsi_value = 45.0 + (index * 5.0)
            repo.upsert_snapshot(
                symbol="BTCUSDC",
                timeframe="1m",
                close_time_ms=close_time_ms,
                computed_at_ms=close_time_ms + 100,
                schema_version="1.0.0",
                payload={
                    "rsi": {"status": "available", "value": rsi_value},
                    "ema20": {"status": "available", "value": rsi_value + 10.0},
                },
            )
    engine.dispose()


async def _call(
    app,
    method: str,
    path: str,
    headers: dict[str, str] | None = None,
):
    req = make_mocked_request(method, path, app=app, headers=headers)
    req["correlation_id"] = "test-correlation-id"
    resp = await app._handle(req)
    content_type = resp.headers.get("Content-Type", "")
    payload = None
    if resp.body and "application/json" in content_type:
        payload = json.loads(resp.body.decode("utf-8"))
    return resp.status, payload, resp.headers


async def _with_app(settings: Settings, test_fn):
    app = create_app(settings)
    await test_fn(app)


def test_indicators_latest_supports_etag_304(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'indicator_api.db'}"
    _seed_snapshots(db_url)
    settings = _build_settings(tmp_path, db_url)

    async def _case(app):
        status, payload, headers = await _call(
            app, "GET", "/indicators/latest?symbol=BTCUSDC&timeframe=1m"
        )
        assert status == 200
        assert payload["ok"] is True
        assert payload["data"]["schema_version"] == "1.0.0"
        etag = headers.get("ETag")
        assert etag

        status, payload, headers = await _call(
            app,
            "GET",
            "/indicators/latest?symbol=BTCUSDC&timeframe=1m",
            headers={"If-None-Match": etag},
        )
        assert status == 304
        assert payload is None
        assert headers.get("ETag") == etag

    asyncio.run(_with_app(settings, _case))


def test_indicators_latest_on_fresh_db_returns_snapshot_not_found(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'fresh_indicator_api.db'}"
    settings = _build_settings(tmp_path, db_url)

    async def _case(app):
        status, payload, _headers = await _call(
            app, "GET", "/indicators/latest?symbol=BTCUSDC&timeframe=1m"
        )
        assert status == 404
        assert payload["ok"] is False
        assert payload["error"]["code"] == "snapshot_not_found"

    asyncio.run(_with_app(settings, _case))


def test_indicators_history_cursor_pagination(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'indicator_api.db'}"
    _seed_snapshots(db_url)
    settings = _build_settings(tmp_path, db_url)

    async def _case(app):
        status, payload, _ = await _call(
            app, "GET", "/indicators/history?symbol=BTCUSDC&timeframe=1m&limit=2"
        )
        assert status == 200
        assert payload["ok"] is True
        assert payload["data"]["schema_version"] == "1.0.0"
        items = payload["data"]["items"]
        assert [item["close_time"] for item in items] == [3_000, 2_000]
        cursor = payload["data"]["next_cursor"]
        assert cursor

        status, payload, _ = await _call(
            app,
            "GET",
            f"/indicators/history?symbol=BTCUSDC&timeframe=1m&limit=2&cursor={cursor}",
        )
        assert status == 200
        items = payload["data"]["items"]
        assert [item["close_time"] for item in items] == [1_000]
        assert payload["data"]["next_cursor"] is None

    asyncio.run(_with_app(settings, _case))


def test_indicators_history_invalid_cursor_error_payload(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'indicator_api.db'}"
    _seed_snapshots(db_url)
    settings = _build_settings(tmp_path, db_url)

    async def _case(app):
        status, payload, _ = await _call(
            app,
            "GET",
            "/indicators/history?symbol=BTCUSDC&timeframe=1m&cursor=bad",
        )
        assert status == 400
        assert payload["ok"] is False
        assert payload["error"]["code"] == "invalid_cursor"
        assert payload["error"]["categorie"] == "validation"
        assert "action_conseillee" in payload["error"]

    asyncio.run(_with_app(settings, _case))


def test_metrics_endpoint_is_exposed(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'indicator_api.db'}"
    _seed_snapshots(db_url)
    settings = _build_settings(tmp_path, db_url)

    async def _case(app):
        status, _payload, headers = await _call(app, "GET", "/metrics")
        assert status == 200
        content_type = headers.get("Content-Type", "")
        assert "text/plain" in content_type

    asyncio.run(_with_app(settings, _case))


def test_indicators_history_default_limit_is_clamped_by_configured_max(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'indicator_api.db'}"
    _seed_snapshots(db_url, count=8)
    settings = _build_settings(tmp_path, db_url)

    async def _case(app):
        status, payload, _ = await _call(
            app, "GET", "/indicators/history?symbol=BTCUSDC&timeframe=1m"
        )
        assert status == 200
        assert payload["ok"] is True
        items = payload["data"]["items"]
        assert len(items) == 5
        assert payload["data"]["next_cursor"] is not None

    asyncio.run(_with_app(settings, _case))


def test_upsert_snapshot_recomputes_etag_when_payload_changes(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'indicator_api.db'}"
    engine = create_engine(db_url, future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    try:
        with session_factory() as session:
            repo = IndicatorRepository(session)
            first = repo.upsert_snapshot(
                symbol="BTCUSDC",
                timeframe="1m",
                close_time_ms=1_000,
                computed_at_ms=2_000,
                schema_version="1.0.0",
                payload={"rsi": {"status": "available", "value": 40}},
            )

        with session_factory() as session:
            repo = IndicatorRepository(session)
            second = repo.upsert_snapshot(
                symbol="BTCUSDC",
                timeframe="1m",
                close_time_ms=1_000,
                computed_at_ms=2_000,
                schema_version="1.0.0",
                payload={"rsi": {"status": "available", "value": 99}},
            )

        assert first.etag != second.etag
    finally:
        engine.dispose()


def test_indicators_and_metrics_are_rbac_protected(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'indicator_api.db'}"
    _seed_snapshots(db_url)
    settings = Settings(
        api_host="127.0.0.1",
        api_port=0,
        database_url=db_url,
        daemon_pid_file=str(tmp_path / "ws_candle_daemon.pid"),
        daemon_command=f'{sys.executable} -c "import time; time.sleep(60)"',
        daemon_stop_timeout_s=0.2,
        indicator_history_max_limit=5,
        indicator_default_schema_version="1.0.0",
        rbac_enabled=True,
        rbac_admin_users="alice",
        rbac_operator_users="",
        rbac_status_roles="admin",
        rbac_user_header="X-User",
        rbac_trusted_proxy_ips="127.0.0.1",
        rbac_proxy_shared_secret="test-secret",
    )

    async def _case(app):
        status, payload, _ = await _call(
            app, "GET", "/indicators/latest?symbol=BTCUSDC&timeframe=1m"
        )
        assert status == 403
        assert payload["error"]["code"] == "permission_denied"

        status, payload, _ = await _call(
            app,
            "GET",
            "/indicators/latest?symbol=BTCUSDC&timeframe=1m",
            headers={"X-User": "alice", "X-RBAC-Proxy-Token": "test-secret"},
        )
        assert status == 200
        assert payload["ok"] is True

        status, payload, _ = await _call(
            app,
            "GET",
            "/metrics",
            headers={"X-User": "alice", "X-RBAC-Proxy-Token": "test-secret"},
        )
        assert status == 200
        assert payload is None

    asyncio.run(_with_app(settings, _case))
