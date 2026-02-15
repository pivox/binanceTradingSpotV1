import pytest

from tradebot.api.app import create_app
from tradebot.config.settings import Settings
from tradebot.observability.logging import resolve_log_level


def _base_settings(tmp_path, **overrides):
    data = {
        "api_host": "127.0.0.1",
        "api_port": 0,
        "database_url": f"sqlite:///{tmp_path / 'logging.db'}",
        "daemon_pid_file": str(tmp_path / "ws_candle_daemon.pid"),
        "daemon_command": "python -V",
    }
    data.update(overrides)
    return Settings(**data)


def test_resolve_log_level_accepts_supported_levels():
    assert resolve_log_level("debug") == 10
    assert resolve_log_level("INFO") == 20
    assert resolve_log_level(" warning ") == 30
    assert resolve_log_level("ERROR") == 40
    assert resolve_log_level("CRITICAL") == 50


def test_resolve_log_level_rejects_invalid_level():
    with pytest.raises(ValueError, match="Invalid log level"):
        resolve_log_level("TRACE")


def test_create_app_rejects_invalid_global_log_level(tmp_path):
    settings = _base_settings(tmp_path, log_level="TRACE")
    with pytest.raises(ValueError, match="Invalid log level"):
        create_app(settings)


def test_create_app_rejects_invalid_api_log_level(tmp_path):
    settings = _base_settings(tmp_path, log_level="INFO", api_log_level="TRACE")
    with pytest.raises(ValueError, match="Invalid log level"):
        create_app(settings)


def test_daemon_main_prefers_daemon_log_level_env(monkeypatch):
    from tradebot.apps import ws_candle_daemon

    observed: dict[str, object] = {}
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.setenv("DAEMON_LOG_LEVEL", "DEBUG")
    monkeypatch.setattr(ws_candle_daemon, "load_dotenv", lambda: None)
    monkeypatch.setattr(
        ws_candle_daemon,
        "configure_logging",
        lambda *, level: observed.setdefault("level", level),
    )

    async def fake_ws_loop() -> None:
        return None

    monkeypatch.setattr(ws_candle_daemon, "ws_loop", fake_ws_loop)

    def fake_asyncio_run(coro):
        observed["is_coro"] = hasattr(coro, "__await__")
        coro.close()

    monkeypatch.setattr(ws_candle_daemon.asyncio, "run", fake_asyncio_run)
    ws_candle_daemon.main()

    assert observed["level"] == "DEBUG"
    assert observed["is_coro"] is True


def test_daemon_main_does_not_validate_unrelated_settings(monkeypatch):
    from tradebot.apps import ws_candle_daemon

    observed: dict[str, object] = {}
    monkeypatch.setenv("API_PORT", "not-an-int")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.delenv("DAEMON_LOG_LEVEL", raising=False)
    monkeypatch.setattr(ws_candle_daemon, "load_dotenv", lambda: None)
    monkeypatch.setattr(
        ws_candle_daemon,
        "configure_logging",
        lambda *, level: observed.setdefault("level", level),
    )

    async def fake_ws_loop() -> None:
        return None

    monkeypatch.setattr(ws_candle_daemon, "ws_loop", fake_ws_loop)

    def fake_asyncio_run(coro):
        observed["is_coro"] = hasattr(coro, "__await__")
        coro.close()

    monkeypatch.setattr(ws_candle_daemon.asyncio, "run", fake_asyncio_run)
    ws_candle_daemon.main()

    assert observed["level"] == "INFO"
    assert observed["is_coro"] is True
