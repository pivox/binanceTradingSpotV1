from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "dev"
    database_url: str = "postgresql+psycopg://user:pass@localhost:5433/tradebot"
    temporal_address: str = "localhost:7233"
    binance_api_key: str = ""
    binance_api_secret: str = ""
    execution_mode: str = "dry_run"
    live_trading_approved: bool = False
    shard_count: int = 8
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    daemon_pid_file: str = "/tmp/ws_candle_daemon.pid"
    daemon_command: str = "python -m tradebot.apps.ws_candle_daemon"
    daemon_start_grace_s: float = 1.0
    daemon_stop_timeout_s: float = 1.0
    chart_max_limit: int = 1000
    rbac_enabled: bool = False
    rbac_admin_users: str = ""
    rbac_operator_users: str = ""
    rbac_status_roles: str = "admin,operator"
    rbac_user_header: str = "X-User"
