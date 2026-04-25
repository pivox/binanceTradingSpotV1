from __future__ import annotations

import asyncio
import os

import asyncpg
from dotenv import load_dotenv

from tradebot.infra.binance.ws_user import BinanceWsUser
from tradebot.observability.logging import configure_logging

BINANCE_WS_URL = "wss://stream.binance.com:9443/ws"
BINANCE_REST_URL = "https://api.binance.com"


async def _get_pool() -> asyncpg.Pool:
    db = os.environ.get("DATABASE_URL", "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL env is required")
    # Strip SQLAlchemy driver prefix so asyncpg can connect
    if db.startswith("postgresql+"):
        db = "postgresql://" + db.split("://", 1)[1]
    elif db.startswith("postgres+"):
        db = "postgres://" + db.split("://", 1)[1]
    return await asyncpg.create_pool(db, min_size=1, max_size=5)


async def _main_async() -> None:
    api_key = os.environ.get("BINANCE_API_KEY", "").strip()
    api_secret = os.environ.get("BINANCE_API_SECRET", "").strip()
    if not api_key or not api_secret:
        raise RuntimeError("BINANCE_API_KEY and BINANCE_API_SECRET must be set")

    ws_url = (
        os.environ.get("BINANCE_WS_URL", BINANCE_WS_URL).strip() or BINANCE_WS_URL
    )
    rest_url = (
        os.environ.get("BINANCE_REST_URL", BINANCE_REST_URL).strip() or BINANCE_REST_URL
    )
    shard_count = int(os.environ.get("SHARD_COUNT", "8"))

    pool = await _get_pool()
    client = BinanceWsUser(
        api_key=api_key,
        api_secret=api_secret,
        ws_url=ws_url,
        rest_url=rest_url,
        pool=pool,
        shard_count=shard_count,
    )
    await client.run()


def main() -> None:
    load_dotenv()
    log_level = (
        os.environ.get("DAEMON_LOG_LEVEL", "").strip()
        or os.environ.get("LOG_LEVEL", "").strip()
        or "INFO"
    )
    configure_logging(level=log_level)
    asyncio.run(_main_async())


if __name__ == "__main__":
    main()
