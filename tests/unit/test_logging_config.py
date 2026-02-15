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
