import asyncio
import json
import os
import time
import zlib
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import asyncpg
import aiohttp
from dotenv import load_dotenv
import structlog
import websockets

from tradebot.config.settings import Settings
from tradebot.observability.logging import configure_logging
from tradebot.observability.metrics import (
    WS_BOOT_SLOW_TOTAL,
    WS_RECONNECT_TOTAL,
    WS_STREAMS_SELECTED,
)

BINANCE_WS_URL = "wss://stream.binance.com:9443/ws"
BINANCE_REST_URL = "https://api.binance.com"
MIN_MS = 60_000

TF_MS = {
    "1m": 60_000,
    "5m": 5 * 60_000,
    "15m": 15 * 60_000,
    "1h": 60 * 60_000,
    "4h": 4 * 60 * 60_000,
}
DERIVED_TFS = ["5m", "15m", "1h", "4h"]


def stable_shard(symbol: str, shard_count: int) -> int:
    return zlib.crc32(symbol.encode("utf-8")) % shard_count


def env_int(name: str, default: int) -> int:
    v = os.environ.get(name)
    return default if v is None or v.strip() == "" else int(v)


def env_positive_int(name: str, default: int) -> int:
    v = os.environ.get(name)
    if v is None or v.strip() == "":
        return default
    try:
        value = int(v)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if value <= 0:
        raise RuntimeError(f"{name} must be > 0")
    return value


async def fetch_24h_tickers(base_url: str) -> List[dict]:
    url = f"{base_url}/api/v3/ticker/24hr"
    timeout = aiohttp.ClientTimeout(total=10)
    logger = structlog.get_logger()
    start = time.monotonic()
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                duration_ms = int((time.monotonic() - start) * 1000)
                logger.error(
                    "binance_api_error",
                    endpoint="/api/v3/ticker/24hr",
                    base_url=base_url,
                    status=resp.status,
                    duration_ms=duration_ms,
                )
                raise RuntimeError(f"binance api error status={resp.status}")
            data = await resp.json()
            if not isinstance(data, list):
                duration_ms = int((time.monotonic() - start) * 1000)
                logger.error(
                    "binance_api_invalid_response",
                    endpoint="/api/v3/ticker/24hr",
                    base_url=base_url,
                    duration_ms=duration_ms,
                )
                raise RuntimeError("binance api invalid response")
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.info(
                "binance_24h_tickers_ok", count=len(data), duration_ms=duration_ms
            )
            return data


def parse_symbols_override(raw: str) -> List[str]:
    if not raw:
        return []
    symbols = [s.strip().upper() for s in raw.split(",") if s.strip()]
    if not symbols:
        raise RuntimeError("SYMBOLS env is empty (example: BTCUSDT,ETHUSDT,...)")
    return symbols


async def load_symbols() -> List[str]:
    override = parse_symbols_override(os.environ.get("SYMBOLS", "").strip())
    logger = structlog.get_logger()
    if override:
        logger.info(
            "symbols_override_active", count=len(override), symbols=override[:10]
        )
        return override

    base_url = (
        os.environ.get("BINANCE_REST_URL", BINANCE_REST_URL).strip() or BINANCE_REST_URL
    )
    try:
        tickers = await fetch_24h_tickers(base_url)
    except Exception as exc:
        logger.error(
            "binance_24h_tickers_failed",
            error=str(exc),
            base_url=base_url,
            endpoint="/api/v3/ticker/24hr",
        )
        raise RuntimeError("binance api unavailable") from exc

    limit = env_positive_int("USDC_PAIRS_LIMIT", 200)
    symbols_with_volume = []
    for t in tickers:
        if not isinstance(t, dict):
            continue
        symbol = str(t.get("symbol", "")).upper()
        if symbol.endswith("USDC"):
            try:
                volume = float(t.get("quoteVolume", 0.0))
            except (TypeError, ValueError):
                volume = 0.0
            symbols_with_volume.append((symbol, volume))

    if not symbols_with_volume:
        logger.error("binance_24h_tickers_empty", base_url=base_url)
        raise RuntimeError("no USDC symbols returned")

    symbols_with_volume.sort(key=lambda item: (-item[1], item[0]))
    symbols = [s for s, _ in symbols_with_volume[:limit]]

    logger.info(
        "binance_24h_tickers_loaded",
        count=len(symbols),
        limit=limit,
        top=symbols[:5],
        base_url=base_url,
    )
    return symbols


@dataclass
class Candle:
    symbol: str
    timeframe: str
    open_time_ms: int
    close_time_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    is_partial: bool = False


@dataclass
class AggState:
    bucket_start_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    last_close_time_ms: int
    count_1m: int
    is_partial: bool = False

    def to_candle(self, symbol: str, tf: str) -> Candle:
        return Candle(
            symbol=symbol,
            timeframe=tf,
            open_time_ms=self.bucket_start_ms,
            close_time_ms=self.last_close_time_ms,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            volume=self.volume,
            is_partial=self.is_partial,
        )


class MultiTfAggregator:
    """
    Aggregate only from closed 1m candles.
    If a 1m gap is detected, mark aggregates as partial and log a gap request.
    """

    def __init__(self) -> None:
        self.last_1m_open: Optional[int] = None
        self.states: Dict[str, Optional[AggState]] = {tf: None for tf in DERIVED_TFS}

    def on_closed_1m(
        self, c1m: Candle
    ) -> Tuple[List[Candle], Optional[Tuple[int, int]]]:
        closed_out: List[Candle] = []
        gap: Optional[Tuple[int, int]] = None

        if self.last_1m_open is not None:
            expected = self.last_1m_open + MIN_MS
            if c1m.open_time_ms != expected:
                gap = (expected, c1m.open_time_ms)
                for tf in DERIVED_TFS:
                    st = self.states.get(tf)
                    if st is not None:
                        st.is_partial = True

        self.last_1m_open = c1m.open_time_ms

        for tf in DERIVED_TFS:
            tf_ms = TF_MS[tf]
            bucket = c1m.open_time_ms - (c1m.open_time_ms % tf_ms)
            st = self.states[tf]

            if st is not None and st.bucket_start_ms != bucket:
                closed_out.append(st.to_candle(c1m.symbol, tf))
                st = None

            if st is None:
                st = AggState(
                    bucket_start_ms=bucket,
                    open=c1m.open,
                    high=c1m.high,
                    low=c1m.low,
                    close=c1m.close,
                    volume=c1m.volume,
                    last_close_time_ms=c1m.close_time_ms,
                    count_1m=1,
                    is_partial=False,
                )
                self.states[tf] = st
            else:
                st.high = max(st.high, c1m.high)
                st.low = min(st.low, c1m.low)
                st.close = c1m.close
                st.volume += c1m.volume
                st.last_close_time_ms = c1m.close_time_ms
                st.count_1m += 1

            if ((c1m.open_time_ms + MIN_MS) % tf_ms) == 0:
                closed_out.append(st.to_candle(c1m.symbol, tf))
                self.states[tf] = None

        return closed_out, gap


UPSERT_CANDLE_SQL = """
INSERT INTO candles(symbol, timeframe, open_time_ms, close_time_ms, open, high, low, close, volume, is_partial, shard_id)
VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
ON CONFLICT(symbol, timeframe, open_time_ms) DO UPDATE
SET close_time_ms = EXCLUDED.close_time_ms,
    open = EXCLUDED.open,
    high = EXCLUDED.high,
    low  = EXCLUDED.low,
    close= EXCLUDED.close,
    volume = EXCLUDED.volume,
    is_partial = EXCLUDED.is_partial,
    shard_id = EXCLUDED.shard_id,
    updated_at = now()
"""

INSERT_EVENT_SQL = """
INSERT INTO candle_close_event(symbol, timeframe, open_time_ms, shard_id)
VALUES($1,$2,$3,$4)
ON CONFLICT(symbol, timeframe, open_time_ms) DO NOTHING
"""

INSERT_GAP_SQL = """
INSERT INTO candle_gap_request(symbol, from_open_time_ms, to_open_time_ms)
VALUES($1,$2,$3)
"""


async def get_pool() -> asyncpg.Pool:
    db = os.environ.get("DATABASE_URL", "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL env is empty")

    # SQLAlchemy URLs may include a driver suffix (e.g. postgresql+psycopg://).
    if db.startswith("postgresql+"):
        db = "postgresql://" + db.split("://", 1)[1]
    elif db.startswith("postgres+"):
        db = "postgres://" + db.split("://", 1)[1]

    return await asyncpg.create_pool(db, min_size=1, max_size=10)


async def persist_candles_and_events(
    pool: asyncpg.Pool, candles: List[Candle], shard_count: int
) -> None:
    if not candles:
        return

    async with pool.acquire() as conn:
        async with conn.transaction():
            for c in candles:
                sid = stable_shard(c.symbol, shard_count)
                await conn.execute(
                    UPSERT_CANDLE_SQL,
                    c.symbol,
                    c.timeframe,
                    c.open_time_ms,
                    c.close_time_ms,
                    c.open,
                    c.high,
                    c.low,
                    c.close,
                    c.volume,
                    c.is_partial,
                    sid,
                )
                await conn.execute(
                    INSERT_EVENT_SQL, c.symbol, c.timeframe, c.open_time_ms, sid
                )


async def persist_gap(
    pool: asyncpg.Pool, symbol: str, gap_from: int, gap_to: int
) -> None:
    async with pool.acquire() as conn:
        await conn.execute(INSERT_GAP_SQL, symbol, gap_from, gap_to)


async def subscribe_in_chunks(ws, symbols: List[str], chunk_size: int = 200) -> None:
    """
    Binance limits incoming client messages to 5/s.
    Send SUBSCRIBE in chunks + short sleep.
    """
    streams = [f"{s.lower()}@kline_1m" for s in symbols]
    logger = structlog.get_logger()
    msg_id = 1
    for i in range(0, len(streams), chunk_size):
        part = streams[i : i + chunk_size]
        msg = {"method": "SUBSCRIBE", "params": part, "id": msg_id}
        await ws.send(json.dumps(msg))
        msg_id += 1
        logger.info("ws_subscribe_chunk", size=len(part), sent=msg_id - 1)
        await asyncio.sleep(0.25)


def validate_stream_selection(symbols: List[str]) -> int:
    hard_cap = env_positive_int("USDC_STREAMS_HARD_CAP", 1000)
    streams_count = len(symbols)
    if streams_count > hard_cap:
        raise RuntimeError(
            f"selected streams exceed USDC_STREAMS_HARD_CAP ({streams_count}>{hard_cap})"
        )
    return hard_cap


def compute_reconnect_delay_s(attempt: int, base_delay_s: int, max_delay_s: int) -> int:
    if attempt <= 1:
        return max(1, min(base_delay_s, max_delay_s))
    return min(max_delay_s, base_delay_s * (2 ** (attempt - 1)))


def log_boot_observability(
    logger,
    *,
    streams: int,
    symbols_ms: int,
    subscribe_ms: int,
    boot_ms: int,
    boot_warn_ms: int,
) -> None:
    WS_STREAMS_SELECTED.set(streams)
    logger.info(
        "ws_boot_complete",
        streams=streams,
        symbols_ms=symbols_ms,
        subscribe_ms=subscribe_ms,
        boot_ms=boot_ms,
    )
    if boot_ms > boot_warn_ms:
        WS_BOOT_SLOW_TOTAL.inc()
        logger.warning(
            "ws_boot_slow",
            boot_ms=boot_ms,
            threshold_ms=boot_warn_ms,
            streams=streams,
        )


def log_reconnect_observability(
    logger, *, attempt: int, delay_s: int, error: str, streams: int
) -> None:
    WS_RECONNECT_TOTAL.inc()
    logger.warning(
        "ws_reconnect_scheduled",
        attempt=attempt,
        delay_s=delay_s,
        previous_error=error,
        streams=streams,
    )


def parse_closed_1m(msg: dict) -> Optional[Candle]:
    if msg.get("e") != "kline":
        return None
    k = msg.get("k")
    if not isinstance(k, dict):
        return None
    if not k.get("x"):
        return None

    symbol = str(k["s"]).upper()
    open_time_ms = int(k["t"])
    close_time_ms = int(k["T"])

    o = float(k["o"])
    h = float(k["h"])
    low = float(k["l"])
    c = float(k["c"])
    v = float(k["v"])

    return Candle(
        symbol=symbol,
        timeframe="1m",
        open_time_ms=open_time_ms,
        close_time_ms=close_time_ms,
        open=o,
        high=h,
        low=low,
        close=c,
        volume=v,
        is_partial=False,
    )


async def ws_loop() -> None:
    shard_count = env_int("SHARD_COUNT", 8)
    pool = await get_pool()
    logger = structlog.get_logger()
    first_boot = True
    boot_warn_ms = env_positive_int("BOOT_WARN_MS", 5000)
    reconnect_base_delay_s = env_positive_int("WS_RECONNECT_BASE_DELAY_S", 2)
    reconnect_max_delay_s = env_positive_int("WS_RECONNECT_MAX_DELAY_S", 30)
    reconnect_attempt = 0
    last_streams = 0

    while True:
        try:
            boot_start = time.monotonic()
            symbols = await load_symbols()
            validate_stream_selection(symbols)
            last_streams = len(symbols)
            symbols_ms = int((time.monotonic() - boot_start) * 1000)
            aggs: Dict[str, MultiTfAggregator] = {
                s: MultiTfAggregator() for s in symbols
            }
            first_boot = False
            async with websockets.connect(
                BINANCE_WS_URL,
                ping_interval=20,
                ping_timeout=20,
                max_queue=10_000,
            ) as ws:
                subscribe_start = time.monotonic()
                await subscribe_in_chunks(ws, symbols, chunk_size=200)
                subscribe_ms = int((time.monotonic() - subscribe_start) * 1000)
                boot_ms = int((time.monotonic() - boot_start) * 1000)
                log_boot_observability(
                    logger,
                    streams=len(symbols),
                    symbols_ms=symbols_ms,
                    subscribe_ms=subscribe_ms,
                    boot_ms=boot_ms,
                    boot_warn_ms=boot_warn_ms,
                )
                reconnect_attempt = 0

                async for raw in ws:
                    msg = json.loads(raw)

                    if "result" in msg and "id" in msg and msg.get("result") is None:
                        continue

                    c1m = parse_closed_1m(msg)
                    if c1m is None:
                        continue

                    to_persist: List[Candle] = [c1m]

                    agg = aggs.get(c1m.symbol)
                    if agg is None:
                        agg = MultiTfAggregator()
                        aggs[c1m.symbol] = agg

                    derived_closed, gap = agg.on_closed_1m(c1m)
                    to_persist.extend(derived_closed)

                    await persist_candles_and_events(pool, to_persist, shard_count)

                    if gap is not None:
                        gap_from, gap_to = gap
                        await persist_gap(pool, c1m.symbol, gap_from, gap_to)
                        logger.warning(
                            "gap_detected",
                            symbol=c1m.symbol,
                            gap_from=gap_from,
                            gap_to=gap_to,
                        )

        except Exception as e:
            error = repr(e)
            logger.error("ws_disconnected", error=error)
            if first_boot:
                raise
            reconnect_attempt += 1
            delay_s = compute_reconnect_delay_s(
                reconnect_attempt, reconnect_base_delay_s, reconnect_max_delay_s
            )
            log_reconnect_observability(
                logger,
                attempt=reconnect_attempt,
                delay_s=delay_s,
                error=error,
                streams=last_streams,
            )
            await asyncio.sleep(delay_s)


def main() -> None:
    load_dotenv()
    settings = Settings()
    daemon_log_level = settings.daemon_log_level or settings.log_level
    configure_logging(level=daemon_log_level)
    asyncio.run(ws_loop())


if __name__ == "__main__":
    main()
