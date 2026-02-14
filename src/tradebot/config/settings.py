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
    indicator_history_max_limit: int = 500
    indicator_default_schema_version: str = "1.0.0"
    backfill_max_attempts: int = 5
    backfill_base_backoff_ms: int = 500
    backfill_max_backoff_ms: int = 30_000
    backfill_max_retry_window_ms: int = 300_000
    backfill_cooldown_ms: int = 300_000
    backfill_weight_limit_1m: int = 1200
    backfill_slow_mode_threshold_ratio: float = 0.85
    rbac_enabled: bool = False
    rbac_admin_users: str = ""
    rbac_operator_users: str = ""
    rbac_status_roles: str = "admin,operator"
    rbac_user_header: str = "X-User"
    rbac_trusted_proxy_ips: str = "127.0.0.1,::1"
