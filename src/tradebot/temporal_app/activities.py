from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import timezone
from temporalio import activity
from typing import Any, Optional

import aiohttp
from sqlalchemy import delete, select, text

from .types import (
    CandleCloseEvent,
    IndicatorSnapshot,
    MtfState,
    OrderIntent,
    Position,
    Timeframe,
)
from tradebot.config.settings import Settings
from tradebot.infra.db.engine import create_session_factory
from tradebot.infra.db.models import BackfillJob, CandleGapRequest, ExchangeInfoCache
from tradebot.infra.db.repositories.backfill_repo_sql import (
    BackfillRepoSql,
    BackfillRetryPolicy,
    timeframe_to_ms,
)

BINANCE_REST_URL = "https://api.binance.com"
MAX_KLINES_PER_REQUEST = 1_000
GAP_REQUEST_BATCH_LIMIT = 500
READY_JOBS_BATCH_LIMIT = 100
SUPPORTED_GAP_REQUEST_TIMEFRAMES = ("1m",)
DETECT_RECONCILE_TIMEFRAMES = ("1m", "5m", "15m", "1h", "4h")
DEFAULT_RECONCILE_SYMBOLS = ("BTCUSDC",)
UPSERT_CANDLE_SQL = """
INSERT INTO candles(
    symbol,
    timeframe,
    open_time_ms,
    close_time_ms,
    open,
    high,
    low,
    close,
    volume,
    is_partial,
    shard_id
)
VALUES(
    :symbol,
    :timeframe,
    :open_time_ms,
    :close_time_ms,
    :open,
    :high,
    :low,
    :close,
    :volume,
    :is_partial,
    :shard_id
)
ON CONFLICT(symbol, timeframe, open_time_ms) DO UPDATE
SET close_time_ms = excluded.close_time_ms,
    open = excluded.open,
    high = excluded.high,
    low = excluded.low,
    close = excluded.close,
    volume = excluded.volume,
    is_partial = excluded.is_partial,
    shard_id = excluded.shard_id
"""


@dataclass(frozen=True)
class _HttpResult:
    status: int
    headers: dict[str, str]
    payload: list[Any]


@dataclass(frozen=True)
class _HttpObjectResult:
    status: int
    headers: dict[str, str]
    payload: dict[str, Any]


class _BinanceHttpError(RuntimeError):
    def __init__(self, status: int, headers: dict[str, str], message: str) -> None:
        super().__init__(message)
        self.status = status
        self.headers = headers


def _backfill_policy_from_settings(settings: Settings) -> BackfillRetryPolicy:
    return BackfillRetryPolicy(
        max_attempts=settings.backfill_max_attempts,
        base_backoff_ms=settings.backfill_base_backoff_ms,
        max_backoff_ms=settings.backfill_max_backoff_ms,
        max_retry_window_ms=settings.backfill_max_retry_window_ms,
        cooldown_ms=settings.backfill_cooldown_ms,
        weight_limit_1m=settings.backfill_weight_limit_1m,
        slow_mode_threshold_ratio=settings.backfill_slow_mode_threshold_ratio,
    )


def _now_ms() -> int:
    return int(time.time() * 1000)


def _normalize_gap_request_window(
    *,
    from_open_time_ms: int,
    to_open_time_ms: int,
) -> tuple[int, int] | None:
    # candle_gap_request stores [from, to) in 1m granularity.
    end_inclusive = to_open_time_ms - timeframe_to_ms("1m")
    if end_inclusive < from_open_time_ms:
        return None
    return from_open_time_ms, end_inclusive


def _build_gaps_from_requests(
    requests: list[CandleGapRequest],
) -> dict[tuple[str, str], list[tuple[int, int]]]:
    by_symbol_tf: dict[tuple[str, str], list[tuple[int, int]]] = {}
    for req in requests:
        normalized = _normalize_gap_request_window(
            from_open_time_ms=int(req.from_open_time_ms),
            to_open_time_ms=int(req.to_open_time_ms),
        )
        if normalized is None:
            continue
        symbol = str(req.symbol).upper()
        for timeframe in SUPPORTED_GAP_REQUEST_TIMEFRAMES:
            by_symbol_tf.setdefault((symbol, timeframe), []).append(normalized)
    return by_symbol_tf


def _target_symbols_for_detection() -> set[str]:
    raw = os.environ.get("RECONCILE_SYMBOLS", "").strip()
    if raw:
        symbols = {item.strip().upper() for item in raw.split(",") if item.strip()}
        return {item for item in symbols if item}
    return set(DEFAULT_RECONCILE_SYMBOLS)


async def _fetch_binance_klines_batch(
    http_session: aiohttp.ClientSession,
    *,
    base_url: str,
    symbol: str,
    timeframe: str,
    start_time_ms: int,
    end_time_ms: int,
) -> _HttpResult:
    url = f"{base_url}/api/v3/klines"
    params = {
        "symbol": symbol,
        "interval": timeframe,
        "startTime": start_time_ms,
        "endTime": end_time_ms,
        "limit": MAX_KLINES_PER_REQUEST,
    }
    async with http_session.get(url, params=params) as response:
        headers = {str(k): str(v) for k, v in response.headers.items()}
        if response.status != 200:
            message = (await response.text())[:300]
            raise _BinanceHttpError(response.status, headers, message)
        payload = await response.json()
        if not isinstance(payload, list):
            raise RuntimeError("binance /api/v3/klines returned invalid payload")
        return _HttpResult(status=200, headers=headers, payload=payload)


async def _fetch_binance_exchange_info(
    http_session: aiohttp.ClientSession,
    *,
    base_url: str,
) -> _HttpObjectResult:
    url = f"{base_url}/api/v3/exchangeInfo"
    async with http_session.get(url) as response:
        headers = {str(k): str(v) for k, v in response.headers.items()}
        if response.status != 200:
            message = (await response.text())[:300]
            raise _BinanceHttpError(response.status, headers, message)
        payload = await response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("binance /api/v3/exchangeInfo returned invalid payload")
        return _HttpObjectResult(status=200, headers=headers, payload=payload)


def _as_float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _symbol_filter_map(filters: Any) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not isinstance(filters, list):
        return out
    for item in filters:
        if not isinstance(item, dict):
            continue
        filter_type = str(item.get("filterType", "")).strip().upper()
        if not filter_type:
            continue
        out[filter_type] = item
    return out


def _build_exchange_info_rows(
    payload: dict[str, Any], fetched_at_ms: int
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    symbols_payload = payload.get("symbols")
    if not isinstance(symbols_payload, list):
        raise RuntimeError("binance /api/v3/exchangeInfo missing symbols[]")

    rows_by_symbol: dict[str, dict[str, Any]] = {}
    trading_symbols = 0
    usdc_symbols = 0
    invalid_entries = 0

    for raw_symbol in symbols_payload:
        if not isinstance(raw_symbol, dict):
            invalid_entries += 1
            continue
        symbol = str(raw_symbol.get("symbol", "")).upper().strip()
        if not symbol:
            invalid_entries += 1
            continue

        status = str(raw_symbol.get("status", "UNKNOWN")).upper()
        base_asset = str(raw_symbol.get("baseAsset", "")).upper()
        quote_asset = str(raw_symbol.get("quoteAsset", "")).upper()
        if status == "TRADING":
            trading_symbols += 1
        if quote_asset == "USDC":
            usdc_symbols += 1

        filters_raw = raw_symbol.get("filters")
        filters = filters_raw if isinstance(filters_raw, list) else []
        filter_map = _symbol_filter_map(filters)

        price_filter = _as_dict(filter_map.get("PRICE_FILTER"))
        lot_size_filter = _as_dict(filter_map.get("LOT_SIZE"))
        market_lot_size_filter = _as_dict(filter_map.get("MARKET_LOT_SIZE"))
        notional_filter = _as_dict(filter_map.get("NOTIONAL"))
        min_notional_filter = _as_dict(filter_map.get("MIN_NOTIONAL"))

        qty_filter = lot_size_filter or market_lot_size_filter

        min_notional = _as_float_or_none(min_notional_filter.get("minNotional"))
        if min_notional is None:
            min_notional = _as_float_or_none(notional_filter.get("minNotional"))

        rows_by_symbol[symbol] = {
            "symbol": symbol,
            "status": status,
            "base_asset": base_asset,
            "quote_asset": quote_asset,
            "price_tick_size": _as_float_or_none(price_filter.get("tickSize")),
            "price_min": _as_float_or_none(price_filter.get("minPrice")),
            "price_max": _as_float_or_none(price_filter.get("maxPrice")),
            "qty_step_size": _as_float_or_none(qty_filter.get("stepSize")),
            "qty_min": _as_float_or_none(qty_filter.get("minQty")),
            "qty_max": _as_float_or_none(qty_filter.get("maxQty")),
            "min_notional": min_notional,
            "max_notional": _as_float_or_none(notional_filter.get("maxNotional")),
            "order_types_json": raw_symbol.get("orderTypes")
            if isinstance(raw_symbol.get("orderTypes"), list)
            else [],
            "permissions_json": raw_symbol.get("permissions")
            if isinstance(raw_symbol.get("permissions"), list)
            else [],
            "filters_json": filters,
            "payload_json": raw_symbol,
            "fetched_at_ms": fetched_at_ms,
        }

    rows = list(rows_by_symbol.values())
    return rows, {
        "symbols_total": len(rows),
        "symbols_trading": trading_symbols,
        "symbols_usdc": usdc_symbols,
        "invalid_entries": invalid_entries,
    }


def _chunked(items: list[str], size: int) -> list[list[str]]:
    if size <= 0:
        raise ValueError("chunk size must be > 0")
    return [items[idx : idx + size] for idx in range(0, len(items), size)]


def _rows_to_upsert_params(
    *,
    symbol: str,
    timeframe: str,
    rows: list[Any],
    from_open_time_ms: int,
    to_open_time_ms: int,
    shard_count: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    shard_id = stable_shard_of(symbol, shard_count)
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) < 7:
            continue
        try:
            open_time_ms = int(row[0])
            close_time_ms = int(row[6])
            if open_time_ms < from_open_time_ms or open_time_ms > to_open_time_ms:
                continue
            out.append(
                {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "open_time_ms": open_time_ms,
                    "close_time_ms": close_time_ms,
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": float(row[5]),
                    "is_partial": False,
                    "shard_id": shard_id,
                }
            )
        except (TypeError, ValueError):
            continue
    return out


def _job_created_at_ms(job: BackfillJob) -> int:
    created_at = job.created_at
    if created_at is None:
        return 0
    if created_at.tzinfo is None:
        return int(created_at.replace(tzinfo=timezone.utc).timestamp() * 1000)
    return int(created_at.astimezone(timezone.utc).timestamp() * 1000)


async def _backfill_job_from_binance(
    session,
    http_session: aiohttp.ClientSession,
    *,
    base_url: str,
    symbol: str,
    timeframe: str,
    from_open_time_ms: int,
    to_open_time_ms: int,
    shard_count: int,
) -> tuple[int, dict[str, str]]:
    step_ms = timeframe_to_ms(timeframe)
    cursor = from_open_time_ms
    inserted = 0
    response_headers: dict[str, str] = {}

    while cursor <= to_open_time_ms:
        batch_to_open = min(
            to_open_time_ms, cursor + ((MAX_KLINES_PER_REQUEST - 1) * step_ms)
        )
        batch_end_time_ms = batch_to_open + step_ms - 1
        http_result = await _fetch_binance_klines_batch(
            http_session,
            base_url=base_url,
            symbol=symbol,
            timeframe=timeframe,
            start_time_ms=cursor,
            end_time_ms=batch_end_time_ms,
        )
        response_headers = http_result.headers
        upsert_rows = _rows_to_upsert_params(
            symbol=symbol,
            timeframe=timeframe,
            rows=http_result.payload,
            from_open_time_ms=cursor,
            to_open_time_ms=batch_to_open,
            shard_count=shard_count,
        )
        if upsert_rows:
            session.execute(text(UPSERT_CANDLE_SQL), upsert_rows)
            session.commit()
            inserted += len(upsert_rows)

        if not upsert_rows:
            break
        next_cursor = int(upsert_rows[-1]["open_time_ms"]) + step_ms
        if next_cursor <= cursor:
            break
        cursor = next_cursor

    return inserted, response_headers


def normalize_execution_mode(raw_mode: str) -> str:
    mode = raw_mode.strip().lower()
    if mode == "dry_run":
        return "backtesting"
    if mode in {"backtesting", "live"}:
        return mode
    raise ValueError("execution mode must be one of: backtesting, live")


def _get_execution_mode() -> tuple[str, bool]:
    settings = Settings()
    approved = bool(settings.live_trading_approved)
    try:
        mode = normalize_execution_mode(settings.execution_mode)
    except ValueError as exc:
        raise RuntimeError(f"Invalid execution_mode={settings.execution_mode}: {exc}")
    if mode == "live" and not approved:
        raise RuntimeError("live trading requires LIVE_TRADING_APPROVED=true")
    return mode, approved


def _activity_log(level: str, event: str, **fields: Any) -> None:
    logger = activity.logger
    log_method = getattr(logger, level.lower(), logger.info)
    if not fields:
        log_method(event)
        return
    try:
        log_method(event, **fields)
    except TypeError:
        details = " ".join(f"{key}={value!r}" for key, value in sorted(fields.items()))
        log_method("%s %s", event, details)


# =========================
# Helpers (placeholders)
# =========================


def stable_shard_of(symbol: str, shard_count: int) -> int:
    # Use a stable hash (crc32) in production, not Python hash().
    import zlib

    return zlib.crc32(symbol.encode("utf-8")) % shard_count


# =========================
# DB / Event ingestion
# =========================


@activity.defn(name="fetch_candle_close_events")
async def fetch_candle_close_events(
    shard_id: int, shard_count: int, limit: int
) -> list[CandleCloseEvent]:
    """
    Fetch candle_close_event rows for the shard.
    Recommended: watermark cursor + ORDER BY open_time_ms / id.
    """
    # TODO: SELECT ... WHERE shard_id=? AND id > cursor LIMIT ?
    _activity_log(
        "info",
        "fetch_candle_close_events",
        shard_id=shard_id,
        shard_count=shard_count,
        limit=limit,
    )
    return []


@activity.defn(name="mark_candle_close_events_processed")
async def mark_candle_close_events_processed(events: list[CandleCloseEvent]) -> None:
    """Mark consumed events (idempotent)."""
    # TODO: DELETE FROM candle_close_event WHERE (symbol,tf,open_time) IN (...)
    _activity_log("info", "mark_events_processed", count=len(events))


# =========================
# Validation + Features
# =========================


@activity.defn(name="validate_candle_event")
async def validate_candle_event(evt: CandleCloseEvent) -> dict[str, Any]:
    """
    Sanity checks + gap detection.
    Return dict (ok/gap/etc.). If gap -> trigger backfill elsewhere.
    """
    # TODO: verify previous candle, OHLCV, etc.
    return {"ok": True, "gap": False}


@activity.defn(name="compute_indicator_snapshot")
async def compute_indicator_snapshot(
    symbol: str, timeframe: Timeframe, open_time_ms: int
) -> IndicatorSnapshot:
    """
    Compute indicators on historical window and persist (or return) snapshot.
    """
    # TODO: load N candles from DB + compute RSI/EMA/MACD/ATR...
    payload = {"rsi": 50.0, "ema21": 0.0, "macd": 0.0, "atr": 0.0}
    return IndicatorSnapshot(
        symbol=symbol, timeframe=timeframe, open_time_ms=open_time_ms, payload=payload
    )


@activity.defn(name="load_latest_snapshots")
async def load_latest_snapshots(
    symbol: str,
) -> dict[Timeframe, Optional[IndicatorSnapshot]]:
    """
    Fetch latest snapshots for 4h/1h/15m/5m/1m.
    """
    # TODO: SELECT latest per tf
    return {"4h": None, "1h": None, "15m": None, "5m": None, "1m": None}


@activity.defn(name="load_mtf_state")
async def load_mtf_state(symbol: str) -> MtfState:
    # TODO: SELECT mtf_state WHERE symbol=...
    return MtfState(symbol=symbol)


@activity.defn(name="save_mtf_state")
async def save_mtf_state(state: MtfState) -> None:
    # TODO: UPSERT mtf_state
    _activity_log("info", "save_mtf_state", symbol=state.symbol)


# =========================
# Signal -> OrderIntent
# =========================


@activity.defn(name="cascade_validate_mtf")
async def cascade_validate_mtf(
    symbol: str,
    snapshots: dict[Timeframe, Optional[IndicatorSnapshot]],
    state: MtfState,
) -> dict[str, Any]:
    """
    Apply cascade 4h->1h->15m->5m->1m.
    Return {"ok": bool, "failed_tf": "5m"|..., "reason": "..."}.
    """
    # TODO: implement your exact rules
    # Simplified example:
    if snapshots.get("4h") is None or snapshots.get("1h") is None:
        return {"ok": False, "failed_tf": "4h", "reason": "missing_context"}
    return {"ok": True, "failed_tf": None, "reason": "ok"}


@activity.defn(name="create_buy_intent")
async def create_buy_intent(symbol: str, open_time_ms: int) -> OrderIntent:
    """
    Create/UPSERT OrderIntent BUY idempotent via intent_key.
    """
    intent_key = f"buy:{symbol}:{open_time_ms}"
    payload = {"order_type": "LIMIT", "quote_budget": 100.0}
    # TODO: UPSERT order_intent(intent_key UNIQUE)
    _activity_log(
        "info",
        "signal_intent_created",
        intent_key=intent_key,
        side="BUY",
        symbol=symbol,
        ts_ms=int(time.time() * 1000),
    )
    return OrderIntent(
        intent_key=intent_key,
        symbol=symbol,
        side="BUY",
        timeframe="1m",
        open_time_ms=open_time_ms,
        payload=payload,
    )


@activity.defn(name="create_sell_intent")
async def create_sell_intent(
    position_id: str, symbol: str, lot_id: str, qty_pct: float
) -> OrderIntent:
    intent_key = f"sell:{position_id}:{lot_id}"
    payload = {"order_type": "LIMIT", "qty_pct": qty_pct, "lot_id": lot_id}
    # TODO: UPSERT order_intent
    _activity_log(
        "info",
        "signal_intent_created",
        intent_key=intent_key,
        side="SELL",
        symbol=symbol,
        ts_ms=int(time.time() * 1000),
    )
    return OrderIntent(
        intent_key=intent_key,
        symbol=symbol,
        side="SELL",
        timeframe="1m",
        open_time_ms=0,
        payload=payload,
    )


# =========================
# Execution (Binance via REST)
# =========================


@activity.defn(name="place_order")
async def place_order(intent: OrderIntent) -> dict[str, Any]:
    """
    Execute the intent on Binance (I/O).
    """
    mode, approved = _get_execution_mode()
    # TODO: call Binance REST, apply quantization, handle rate limits/retries.
    _activity_log(
        "info",
        "place_order",
        side=intent.side,
        symbol=intent.symbol,
        mode=mode,
        approved=approved,
        ts_ms=int(time.time() * 1000),
    )
    return {
        "ok": True,
        "order_id": "123456",
        "client_order_id": intent.intent_key,
        "mode": mode,
    }


@activity.defn(name="cancel_order")
async def cancel_order(symbol: str, order_id: str) -> dict[str, Any]:
    mode, approved = _get_execution_mode()
    # TODO: Binance cancel
    _activity_log(
        "info",
        "cancel_order",
        symbol=symbol,
        order_id=order_id,
        mode=mode,
        approved=approved,
        ts_ms=int(time.time() * 1000),
    )
    return {"ok": True, "mode": mode}


# =========================
# Positions + Exit Engine
# =========================


@activity.defn(name="fetch_due_positions")
async def fetch_due_positions(shard_id: int, limit: int) -> list[Position]:
    """
    Fetch positions due (next_check_at <= now).
    """
    # TODO: SELECT FROM position WHERE shard_id=? AND status IN (...) AND next_check_at<=now LIMIT ?
    return []


@activity.defn(name="apply_exit_engine")
async def apply_exit_engine(pos: Position) -> dict[str, Any]:
    """
    Compute exit actions (sell% / hold%) based on exit_plan + state.
    Return e.g. {"actions":[{"type":"SELL","lot":"A","pct":0.60}, ...], "next_check_in_ms": 10000}
    """
    # TODO: TP1/TP2/runner trailing/time-stop...
    return {"actions": [], "next_check_in_ms": 10_000}


@activity.defn(name="update_position_after_actions")
async def update_position_after_actions(
    position_id: str, patch: dict[str, Any]
) -> None:
    # TODO: UPDATE position SET ...
    _activity_log("info", "update_position", position_id=position_id, patch=patch)


# =========================
# Reconciliation / Maintenance
# =========================


@activity.defn(name="reconcile_klines")
async def reconcile_klines() -> dict[str, Any]:
    """
    Detect gaps and backfill via REST if needed.
    """
    settings = Settings()
    session_factory = create_session_factory(settings)
    policy = _backfill_policy_from_settings(settings)
    base_url = os.environ.get("BINANCE_REST_URL", BINANCE_REST_URL).strip() or BINANCE_REST_URL

    scheduled_jobs = 0
    processed_jobs = 0
    inserted_candles = 0
    failures = 0
    fetched_requests = 0

    with session_factory() as session:
        repo = BackfillRepoSql(session)
        requests = list(
            session.scalars(
                select(CandleGapRequest)
                .order_by(CandleGapRequest.id.asc())
                .limit(GAP_REQUEST_BATCH_LIMIT)
            )
        )
        fetched_requests = len(requests)
        gaps_by_symbol_tf = _build_gaps_from_requests(requests)
        detect_symbols = _target_symbols_for_detection() | {
            str(item.symbol).upper() for item in requests
        }
        now_ms = _now_ms()
        for (symbol, timeframe), gaps in gaps_by_symbol_tf.items():
            created = repo.schedule_gap_jobs(
                symbol=symbol,
                timeframe=timeframe,
                gaps=gaps,
                priority=100 if timeframe == "1m" else 50,
                now_ms=now_ms,
            )
            scheduled_jobs += len(created)

        for symbol in sorted(detect_symbols):
            for timeframe in DETECT_RECONCILE_TIMEFRAMES:
                bounds = session.execute(
                    text(
                        """
                        SELECT MIN(open_time_ms) AS min_open, MAX(open_time_ms) AS max_open
                        FROM candles
                        WHERE symbol = :symbol AND timeframe = :timeframe
                        """
                    ),
                    {"symbol": symbol, "timeframe": timeframe},
                ).one()
                min_open = bounds.min_open
                max_open = bounds.max_open
                if min_open is None or max_open is None:
                    continue
                detected_gaps = repo.detect_gaps(
                    symbol=symbol,
                    timeframe=timeframe,
                    from_open_time_ms=int(min_open),
                    to_open_time_ms=int(max_open),
                )
                if not detected_gaps:
                    continue
                created = repo.schedule_gap_jobs(
                    symbol=symbol,
                    timeframe=timeframe,
                    gaps=detected_gaps,
                    priority=100 if timeframe == "1m" else 80,
                    now_ms=now_ms,
                )
                scheduled_jobs += len(created)

        if requests:
            request_ids = [int(item.id) for item in requests if item.id is not None]
            if request_ids:
                session.execute(
                    delete(CandleGapRequest).where(CandleGapRequest.id.in_(request_ids))
                )
                session.commit()

        jobs = repo.list_ready_jobs(now_ms=_now_ms(), limit=READY_JOBS_BATCH_LIMIT)
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as http_session:
            for job in jobs:
                job_id = int(job.id)
                repo.mark_in_progress(job_id=job_id)
                try:
                    inserted, headers = await _backfill_job_from_binance(
                        session,
                        http_session,
                        base_url=base_url,
                        symbol=str(job.symbol),
                        timeframe=str(job.timeframe),
                        from_open_time_ms=int(job.from_open_time_ms),
                        to_open_time_ms=int(job.to_open_time_ms),
                        shard_count=settings.shard_count,
                    )
                    inserted_candles += inserted
                    repo.record_http_result(
                        job_id=job_id,
                        http_status=200,
                        now_ms=_now_ms(),
                        policy=policy,
                        headers=headers,
                    )
                except _BinanceHttpError as exc:
                    failures += 1
                    repo.record_http_result(
                        job_id=job_id,
                        http_status=exc.status,
                        now_ms=_now_ms(),
                        policy=policy,
                        headers=exc.headers,
                        error_message=str(exc),
                    )
                except Exception as exc:  # pragma: no cover - defensive guard
                    failures += 1
                    created_at_ms = _job_created_at_ms(job)
                    repo.record_http_result(
                        job_id=job_id,
                        http_status=500,
                        now_ms=max(_now_ms(), created_at_ms),
                        policy=policy,
                        headers={},
                        error_message=str(exc),
                    )
                processed_jobs += 1

    _activity_log(
        "info",
        "reconcile_klines_done",
        scheduled_jobs=scheduled_jobs,
        processed_jobs=processed_jobs,
        inserted_candles=inserted_candles,
        gap_requests=fetched_requests,
        failures=failures,
    )
    return {
        "ok": failures == 0,
        "gap_requests": fetched_requests,
        "jobs_scheduled": scheduled_jobs,
        "jobs_processed": processed_jobs,
        "gaps_filled": inserted_candles,
        "failures": failures,
    }


@activity.defn(name="reconcile_orders")
async def reconcile_orders() -> dict[str, Any]:
    """
    Resync orders/positions vs Binance REST.
    """
    # TODO: fetch open orders, compare DB, patch states
    return {"ok": True, "fixed": 0}


@activity.defn(name="refresh_exchange_info")
async def refresh_exchange_info() -> dict[str, Any]:
    """
    Refresh exchangeInfo (filters LOT_SIZE/PRICE_FILTER/MIN_NOTIONAL...).
    """
    settings = Settings()
    session_factory = create_session_factory(settings)
    base_url = (
        os.environ.get("BINANCE_REST_URL", BINANCE_REST_URL).strip() or BINANCE_REST_URL
    )

    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as http_session:
        http_result = await _fetch_binance_exchange_info(
            http_session,
            base_url=base_url,
        )

    fetched_at_ms = _now_ms()
    rows, stats = _build_exchange_info_rows(http_result.payload, fetched_at_ms)
    if not rows:
        raise RuntimeError("binance /api/v3/exchangeInfo returned no symbols")

    inserted = 0
    updated = 0
    symbols = [str(row["symbol"]) for row in rows]
    existing_by_symbol: dict[str, ExchangeInfoCache] = {}

    with session_factory() as session:
        for chunk in _chunked(symbols, 500):
            for existing_row in session.scalars(
                select(ExchangeInfoCache).where(ExchangeInfoCache.symbol.in_(chunk))
            ):
                existing_by_symbol[str(existing_row.symbol)] = existing_row

        for row in rows:
            symbol = str(row["symbol"])
            existing = existing_by_symbol.get(symbol)
            if existing is None:
                session.add(ExchangeInfoCache(**row))
                inserted += 1
                continue
            existing.status = str(row["status"])
            existing.base_asset = str(row["base_asset"])
            existing.quote_asset = str(row["quote_asset"])
            existing.price_tick_size = row["price_tick_size"]
            existing.price_min = row["price_min"]
            existing.price_max = row["price_max"]
            existing.qty_step_size = row["qty_step_size"]
            existing.qty_min = row["qty_min"]
            existing.qty_max = row["qty_max"]
            existing.min_notional = row["min_notional"]
            existing.max_notional = row["max_notional"]
            existing.order_types_json = row["order_types_json"]
            existing.permissions_json = row["permissions_json"]
            existing.filters_json = row["filters_json"]
            existing.payload_json = row["payload_json"]
            existing.fetched_at_ms = int(row["fetched_at_ms"])
            updated += 1

        session.commit()

    raw_used_weight = str(http_result.headers.get("X-MBX-USED-WEIGHT-1M", "0") or "0")
    try:
        used_weight_1m = int(raw_used_weight)
    except ValueError:
        used_weight_1m = 0
    _activity_log(
        "info",
        "refresh_exchange_info_done",
        base_url=base_url,
        symbols_total=stats["symbols_total"],
        symbols_trading=stats["symbols_trading"],
        symbols_usdc=stats["symbols_usdc"],
        inserted=inserted,
        updated=updated,
        used_weight_1m=used_weight_1m,
    )
    return {
        "ok": True,
        "symbols_total": stats["symbols_total"],
        "symbols_trading": stats["symbols_trading"],
        "symbols_usdc": stats["symbols_usdc"],
        "invalid_entries": stats["invalid_entries"],
        "inserted": inserted,
        "updated": updated,
        "used_weight_1m": used_weight_1m,
        "fetched_at_ms": fetched_at_ms,
    }
