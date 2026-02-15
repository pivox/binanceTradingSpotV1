import asyncio
import json
import subprocess
import sys

from aiohttp.test_utils import make_mocked_request

from tradebot.api.app import CONTROLLER_KEY, create_app
from tradebot.config.settings import Settings


async def _call(
    app,
    method: str,
    path: str,
    headers: dict | None = None,
    json_body: dict | list | str | int | float | bool | None = None,
    raw_body: bytes | None = None,
):
    body = raw_body
    req_headers = dict(headers or {})
    if json_body is not None:
        body = json.dumps(json_body).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")
    req = make_mocked_request(method, path, app=app, headers=req_headers)
    if body is not None:
        req._read_bytes = body
    req["correlation_id"] = "test-correlation-id"
    resp = await app._handle(req)
    payload = json.loads(resp.body.decode("utf-8")) if resp.body else None
    return resp.status, payload


async def _with_app(tmp_path, test_fn, settings: Settings | None = None):
    if settings is None:
        settings = Settings(
            api_host="127.0.0.1",
            api_port=0,
            database_url=f"sqlite:///{tmp_path / 'daemon_api.db'}",
            daemon_pid_file=str(tmp_path / "ws_candle_daemon.pid"),
            daemon_command=f'{sys.executable} -c "import time; time.sleep(60)"',
            daemon_stop_timeout_s=0.2,
            execution_mode="backtesting",
        )
    app = create_app(settings)
    await test_fn(app)


def test_status_start_stop(tmp_path):
    async def _case(app):
        status, payload = await _call(app, "GET", "/daemon/status")
        assert status == 200
        assert payload["ok"] is True
        assert payload["data"]["status"] == "stopped"
        assert payload["data"]["pid"] is None

        status, payload = await _call(app, "POST", "/daemon/start")
        assert status == 200
        assert payload["ok"] is True
        assert payload["data"]["status"] == "running"
        assert payload["data"]["pid"] is not None

        status, payload = await _call(app, "GET", "/daemon/status")
        assert status == 200
        assert payload["ok"] is True
        assert payload["data"]["status"] == "running"

        status, payload = await _call(app, "POST", "/daemon/stop")
        assert status == 200
        assert payload["ok"] is True
        assert payload["data"]["status"] == "stopped"

    asyncio.run(_with_app(tmp_path, _case))


def test_already_running(tmp_path):
    async def _case(app):
        status, _ = await _call(app, "POST", "/daemon/start")
        assert status == 200

        status, payload = await _call(app, "POST", "/daemon/start")
        assert status == 409
        assert payload["ok"] is False
        assert payload["error"]["code"] == "already_running"

        await _call(app, "POST", "/daemon/stop")

    asyncio.run(_with_app(tmp_path, _case))


def test_already_stopped(tmp_path):
    async def _case(app):
        status, payload = await _call(app, "POST", "/daemon/stop")
        assert status == 409
        assert payload["ok"] is False
        assert payload["error"]["code"] == "already_stopped"

    asyncio.run(_with_app(tmp_path, _case))


def test_process_not_found(tmp_path):
    async def _case(app):
        pid_path = tmp_path / "stale.pid"
        proc = subprocess.Popen([sys.executable, "-c", "print('x')"])
        proc.wait(timeout=5)
        pid_path.write_text(str(proc.pid), encoding="utf-8")
        app[CONTROLLER_KEY].pid_file = str(pid_path)

        status, payload = await _call(app, "POST", "/daemon/stop")
        assert status == 404
        assert payload["ok"] is False
        assert payload["error"]["code"] == "process_not_found"

    asyncio.run(_with_app(tmp_path, _case))


def test_rbac_denies_without_role(tmp_path):
    settings = Settings(
        api_host="127.0.0.1",
        api_port=0,
        database_url=f"sqlite:///{tmp_path / 'daemon_api.db'}",
        daemon_pid_file=str(tmp_path / "ws_candle_daemon.pid"),
        daemon_command=f'{sys.executable} -c "import time; time.sleep(60)"',
        daemon_stop_timeout_s=0.2,
        rbac_enabled=True,
        rbac_admin_users="alice",
        rbac_operator_users="bob",
        rbac_status_roles="admin,operator",
        rbac_user_header="X-User",
        rbac_proxy_shared_secret="test-secret",
    )

    async def _case(app):
        status, payload = await _call(
            app,
            "POST",
            "/daemon/start",
            headers={"X-User": "mallory", "X-RBAC-Proxy-Token": "test-secret"},
        )
        assert status == 403
        assert payload["error"]["code"] == "permission_denied"

        status, payload = await _call(
            app,
            "GET",
            "/daemon/status",
            headers={"X-User": "mallory", "X-RBAC-Proxy-Token": "test-secret"},
        )
        assert status == 403
        assert payload["error"]["code"] == "permission_denied"

    asyncio.run(_with_app(tmp_path, _case, settings=settings))


def test_rbac_allows_admin(tmp_path):
    settings = Settings(
        api_host="127.0.0.1",
        api_port=0,
        database_url=f"sqlite:///{tmp_path / 'daemon_api.db'}",
        daemon_pid_file=str(tmp_path / "ws_candle_daemon.pid"),
        daemon_command=f'{sys.executable} -c "import time; time.sleep(60)"',
        daemon_stop_timeout_s=0.2,
        rbac_enabled=True,
        rbac_admin_users="alice",
        rbac_operator_users="",
        rbac_status_roles="admin",
        rbac_user_header="X-User",
        rbac_proxy_shared_secret="test-secret",
    )

    async def _case(app):
        status, payload = await _call(
            app,
            "POST",
            "/daemon/start",
            headers={"X-User": "alice", "X-RBAC-Proxy-Token": "test-secret"},
        )
        assert status == 200
        assert payload["ok"] is True

        status, payload = await _call(
            app,
            "POST",
            "/daemon/stop",
            headers={"X-User": "alice", "X-RBAC-Proxy-Token": "test-secret"},
        )
        assert status == 200
        assert payload["ok"] is True

        status, payload = await _call(
            app,
            "GET",
            "/daemon/status",
            headers={"X-User": "alice", "X-RBAC-Proxy-Token": "test-secret"},
        )
        assert status == 200
        assert payload["ok"] is True

    asyncio.run(_with_app(tmp_path, _case, settings=settings))


def test_permissions_endpoint_reports_effective_permissions(tmp_path):
    settings = Settings(
        api_host="127.0.0.1",
        api_port=0,
        database_url=f"sqlite:///{tmp_path / 'daemon_api.db'}",
        daemon_pid_file=str(tmp_path / "ws_candle_daemon.pid"),
        daemon_command=f'{sys.executable} -c "import time; time.sleep(60)"',
        daemon_stop_timeout_s=0.2,
        rbac_enabled=True,
        rbac_admin_users="alice",
        rbac_operator_users="bob",
        rbac_status_roles="admin,operator",
        rbac_user_header="X-User",
        rbac_proxy_shared_secret="test-secret",
    )

    async def _case(app):
        status, payload = await _call(
            app,
            "GET",
            "/daemon/permissions",
            headers={"X-User": "alice", "X-RBAC-Proxy-Token": "test-secret"},
        )
        assert status == 200
        assert payload["ok"] is True
        assert payload["data"]["user"] == "alice"
        assert payload["data"]["can_read_status"] is True
        assert payload["data"]["can_start"] is True
        assert payload["data"]["can_stop"] is True
        assert payload["data"]["can_switch_mode"] is True

        status, payload = await _call(
            app,
            "GET",
            "/daemon/permissions",
            headers={"X-User": "bob", "X-RBAC-Proxy-Token": "test-secret"},
        )
        assert status == 200
        assert payload["ok"] is True
        assert payload["data"]["user"] == "bob"
        assert payload["data"]["can_read_status"] is True
        assert payload["data"]["can_start"] is True
        assert payload["data"]["can_stop"] is True
        assert payload["data"]["can_switch_mode"] is False

        status, payload = await _call(
            app,
            "GET",
            "/daemon/permissions",
            headers={"X-User": "mallory", "X-RBAC-Proxy-Token": "test-secret"},
        )
        assert status == 200
        assert payload["ok"] is True
        assert payload["data"]["user"] == "mallory"
        assert payload["data"]["can_read_status"] is False
        assert payload["data"]["can_start"] is False
        assert payload["data"]["can_stop"] is False
        assert payload["data"]["can_switch_mode"] is False

    asyncio.run(_with_app(tmp_path, _case, settings=settings))


def test_mode_switch_rejects_non_object_payload(tmp_path):
    async def _case(app):
        status, payload = await _call(
            app,
            "POST",
            "/daemon/mode",
            json_body=["live"],
        )
        assert status == 400
        assert payload["ok"] is False
        assert payload["error"]["code"] == "invalid_request"

        status, payload = await _call(
            app,
            "POST",
            "/daemon/mode",
            json_body="live",
        )
        assert status == 400
        assert payload["ok"] is False
        assert payload["error"]["code"] == "invalid_request"

    asyncio.run(_with_app(tmp_path, _case))


def test_mode_status_and_switch(tmp_path):
    async def _case(app):
        status, payload = await _call(app, "GET", "/daemon/mode")
        assert status == 200
        assert payload["ok"] is True
        assert payload["data"]["mode"] == "backtesting"
        assert payload["data"]["modes"] == ["backtesting", "live"]

        status, payload = await _call(app, "POST", "/daemon/mode", json_body={})
        assert status == 400
        assert payload["ok"] is False

        status, payload = await _call(
            app,
            "POST",
            "/daemon/mode",
            json_body={"mode": "live"},
        )
        assert status == 200
        assert payload["data"]["mode"] == "live"

        status, payload = await _call(app, "GET", "/daemon/mode")
        assert status == 200
        assert payload["data"]["mode"] == "live"

    asyncio.run(_with_app(tmp_path, _case))


def test_mode_switch_denied_for_non_admin_when_rbac_enabled(tmp_path):
    settings = Settings(
        api_host="127.0.0.1",
        api_port=0,
        database_url=f"sqlite:///{tmp_path / 'daemon_api.db'}",
        daemon_pid_file=str(tmp_path / "ws_candle_daemon.pid"),
        daemon_command=f'{sys.executable} -c "import time; time.sleep(60)"',
        daemon_stop_timeout_s=0.2,
        rbac_enabled=True,
        rbac_admin_users="alice",
        rbac_operator_users="bob",
        rbac_status_roles="admin,operator",
        rbac_user_header="X-User",
        rbac_proxy_shared_secret="test-secret",
    )

    async def _case(app):
        status, payload = await _call(
            app,
            "POST",
            "/daemon/mode",
            headers={"X-User": "bob", "X-RBAC-Proxy-Token": "test-secret"},
            json_body={"mode": "live"},
        )
        assert status == 403
        assert payload["ok"] is False
        assert payload["error"]["code"] == "permission_denied"

    asyncio.run(_with_app(tmp_path, _case, settings=settings))
