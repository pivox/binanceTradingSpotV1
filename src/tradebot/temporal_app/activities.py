from __future__ import annotations

import hashlib
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from temporalio import activity
from typing import Any, Optional

import json
import aiohttp
from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .types import (
    CandleCloseEvent,
    IndicatorSnapshot,
    MtfState,
    OrderIntent,
    Position,
    Timeframe,
)
from tradebot.config.loader import load_app_config
from tradebot.config.settings import Settings
from tradebot.config.utils import get_app_config_path
from tradebot.domain.models.candle import Candle as DomainCandle
from tradebot.domain.models.cascade_result import CascadeResult as DomainCascadeResult, MarketRegime
from tradebot.domain.models.exit_plan import ExitPlan, Lot, LotRule
from tradebot.domain.models.mtf_state import MtfState as DomainMtfState
from tradebot.domain.models.order_intent import (
    OrderIntent as DomainOrderIntent,
    OrderIntentStatus,
    OrderType as DomainOrderType,
    Side as DomainSide,
)
from tradebot.domain.models.position import Position as DomainPosition, PositionStatus
from tradebot.domain.models.signal import SignalQuality, SetupType
from tradebot.domain.models.symbol_filters import SymbolFilters
from tradebot.infra.binance.filters import BinanceFilters
from tradebot.infra.binance.rest import BinanceRestClient
from tradebot.infra.db.engine import create_session_factory
from tradebot.infra.db.models import (
    BackfillJob,
    Candle,
    CandleCloseEvent as CandleCloseEventModel,
    CandleCloseEventProcessed,
    CandleGapRequest,
    ExchangeInfoCache,
    IndicatorSnapshot as IndicatorSnapshotModel,
)
from tradebot.infra.db.repositories.mtf_state_repo_sql import MtfStateRepoSql
from tradebot.infra.db.repositories.order_intent_repo_sql import OrderIntentRepoSql
from tradebot.infra.db.repositories.position_repo_sql import PositionRepoSql
from tradebot.services.indicators.factory import build_indicator_snapshot, CandleSample
from tradebot.services.mtf.cascade import evaluate_cascade
from tradebot.services.strategy.exit_engine import compute_exit_intents
from tradebot.services.strategy.signal_engine import compute_signal
from tradebot.infra.db.repositories.backfill_repo_sql import (
    BackfillRepoSql,
    BackfillRetryPolicy,
    timeframe_to_ms,
)

BINANCE_REST_URL = "https://api.binance.com"
MAX_KLINES_PER_REQUEST = 1_000
GAP_REQUEST_BATCH_LIMIT = 500
READY_JOBS_BATCH_LIMIT = 100
DETECT_RECONCILE_TIMEFRAMES = ("1m", "5m", "15m", "1h", "4h")
SUPPORTED_GAP_REQUEST_TIMEFRAMES = DETECT_RECONCILE_TIMEFRAMES
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


def _today_start_ms() -> int:
    """Milliseconds timestamp for UTC midnight of the current calendar day."""
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(today.timestamp() * 1000)


def _normalize_gap_request_window(
    *,
    from_open_time_ms: int,
    to_open_time_ms: int,
    timeframe: Timeframe,
) -> tuple[int, int] | None:
    # candle_gap_request stores [from, to) — convert to inclusive using the TF step.
    end_inclusive = to_open_time_ms - timeframe_to_ms(timeframe)
    if end_inclusive < from_open_time_ms:
        return None
    return from_open_time_ms, end_inclusive


def _build_gaps_from_requests(
    requests: list[CandleGapRequest],
) -> dict[tuple[str, str], list[tuple[int, int]]]:
    by_symbol_tf: dict[tuple[str, str], list[tuple[int, int]]] = {}
    for req in requests:
        symbol = str(req.symbol).upper()
        from_ms = int(req.from_open_time_ms)
        to_ms = int(req.to_open_time_ms)
        for timeframe in SUPPORTED_GAP_REQUEST_TIMEFRAMES:
            normalized = _normalize_gap_request_window(
                from_open_time_ms=from_ms,
                to_open_time_ms=to_ms,
                timeframe=timeframe,
            )
            if normalized is None:
                continue
            by_symbol_tf.setdefault((symbol, timeframe), []).append(normalized)
    return by_symbol_tf


def _target_symbols_for_detection(session) -> set[str]:
    raw = os.environ.get("RECONCILE_SYMBOLS", "").strip()
    if raw:
        symbols = {item.strip().upper() for item in raw.split(",") if item.strip()}
        return {item for item in symbols if item}
    symbols = {
        str(value).upper()
        for value in session.scalars(select(Candle.symbol).distinct())
        if value is not None and str(value).strip()
    }
    if symbols:
        return symbols
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
    settings = Settings()
    session_factory = create_session_factory(settings)
    with session_factory() as session:
        rows = session.execute(
            select(CandleCloseEventModel)
            .outerjoin(
                CandleCloseEventProcessed,
                CandleCloseEventModel.id == CandleCloseEventProcessed.id,
            )
            .where(
                CandleCloseEventModel.shard_id == shard_id,
                CandleCloseEventProcessed.id.is_(None),
            )
            .order_by(CandleCloseEventModel.id.asc())
            .limit(limit)
        ).scalars().all()
    _activity_log("info", "fetch_candle_close_events", shard_id=shard_id, count=len(rows))
    return [
        CandleCloseEvent(
            symbol=str(row.symbol),
            timeframe=str(row.timeframe),
            open_time_ms=int(row.open_time_ms),
        )
        for row in rows
    ]


@activity.defn(name="mark_candle_close_events_processed")
async def mark_candle_close_events_processed(events: list[CandleCloseEvent]) -> None:
    if not events:
        return
    settings = Settings()
    session_factory = create_session_factory(settings)
    now_ms = _now_ms()
    with session_factory() as session:
        for evt in events:
            row = session.execute(
                select(CandleCloseEventModel).where(
                    CandleCloseEventModel.symbol == evt.symbol,
                    CandleCloseEventModel.timeframe == evt.timeframe,
                    CandleCloseEventModel.open_time_ms == evt.open_time_ms,
                )
            ).scalar_one_or_none()
            if row is None:
                continue
            session.execute(
                pg_insert(CandleCloseEventProcessed)
                .values(id=int(row.id), processed_at_ms=now_ms)
                .on_conflict_do_nothing(index_elements=["id"])
            )
        session.commit()
    _activity_log("info", "mark_events_processed", count=len(events))


# =========================
# Validation + Features
# =========================


@activity.defn(name="validate_candle_event")
async def validate_candle_event(evt: CandleCloseEvent) -> dict[str, Any]:
    settings = Settings()
    session_factory = create_session_factory(settings)
    with session_factory() as session:
        count = session.execute(
            select(func.count()).select_from(Candle).where(
                Candle.symbol == evt.symbol,
                Candle.timeframe == evt.timeframe,
                Candle.open_time_ms == evt.open_time_ms,
            )
        ).scalar() or 0
    return {"ok": count > 0, "gap": False}


@activity.defn(name="compute_indicator_snapshot")
async def compute_indicator_snapshot(
    symbol: str, timeframe: Timeframe, open_time_ms: int
) -> IndicatorSnapshot:
    _WINDOW = 1500  # EMA200 warmup (200) + full 1m day for VWAP (1440 candles/day)
    settings = Settings()
    session_factory = create_session_factory(settings)

    with session_factory() as session:
        rows = session.execute(
            select(Candle)
            .where(
                Candle.symbol == symbol,
                Candle.timeframe == timeframe,
                Candle.open_time_ms <= open_time_ms,
                Candle.is_partial.is_(False),
            )
            .order_by(Candle.open_time_ms.desc())
            .limit(_WINDOW)
        ).scalars().all()

    if not rows:
        raise RuntimeError(f"no candles for {symbol}/{timeframe}@{open_time_ms}")

    candles = sorted(
        [
            CandleSample(
                open_time_ms=int(row.open_time_ms),
                close_time_ms=int(row.close_time_ms),
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                volume=float(row.volume),
            )
            for row in rows
        ],
        key=lambda c: c.open_time_ms,
    )

    computed_at = _now_ms()
    try:
        payload = build_indicator_snapshot(
            symbol=symbol,
            timeframe=timeframe,
            candles=candles,
            computed_at=computed_at,
        )
    except ValueError as exc:
        _activity_log("warning", "compute_indicator_snapshot_skipped",
                      symbol=symbol, timeframe=timeframe, reason=str(exc))
        return IndicatorSnapshot(symbol=symbol, timeframe=timeframe,
                                 open_time_ms=open_time_ms, payload={})
    # close_price is needed by condition helpers
    payload["close_price"] = candles[-1].close

    close_time_ms = candles[-1].close_time_ms
    etag = hashlib.md5(
        f"{symbol}:{timeframe}:{close_time_ms}:{computed_at}".encode()
    ).hexdigest()[:16]

    with session_factory() as session:
        session.execute(
            pg_insert(IndicatorSnapshotModel)
            .values(
                symbol=symbol,
                timeframe=timeframe,
                close_time_ms=close_time_ms,
                computed_at_ms=computed_at,
                schema_version=settings.indicator_default_schema_version,
                payload_json=payload,
                etag=etag,
            )
            .on_conflict_do_update(
                constraint="uq_indicator_snapshots_symbol_tf_close_time",
                set_={"computed_at_ms": computed_at, "payload_json": payload, "etag": etag},
            )
        )
        session.commit()

    _activity_log("info", "indicator_snapshot_computed", symbol=symbol, timeframe=timeframe)
    return IndicatorSnapshot(
        symbol=symbol, timeframe=timeframe, open_time_ms=open_time_ms, payload=payload
    )


@activity.defn(name="load_latest_snapshots")
async def load_latest_snapshots(
    symbol: str,
) -> dict[Timeframe, Optional[IndicatorSnapshot]]:
    settings = Settings()
    session_factory = create_session_factory(settings)
    result: dict[str, Optional[IndicatorSnapshot]] = {}
    with session_factory() as session:
        for tf in ("4h", "1h", "15m", "5m", "1m"):
            row = session.execute(
                select(IndicatorSnapshotModel)
                .where(
                    IndicatorSnapshotModel.symbol == symbol,
                    IndicatorSnapshotModel.timeframe == tf,
                )
                .order_by(IndicatorSnapshotModel.close_time_ms.desc())
                .limit(1)
            ).scalar_one_or_none()
            if row is None:
                result[tf] = None
            else:
                payload = dict(row.payload_json) if row.payload_json else {}
                result[tf] = IndicatorSnapshot(
                    symbol=symbol,
                    timeframe=tf,
                    open_time_ms=int(row.close_time_ms),
                    payload=payload,
                )
    return result


@activity.defn(name="load_mtf_state")
async def load_mtf_state(symbol: str) -> MtfState:
    settings = Settings()
    session_factory = create_session_factory(settings)
    with session_factory() as session:
        repo = MtfStateRepoSql(session)
        domain_state = repo.get(symbol)
    if domain_state is None:
        return MtfState(symbol=symbol)
    return MtfState(
        symbol=symbol,
        context_ok_4h=domain_state.cascade_passed,
        context_ok_1h=domain_state.cascade_passed,
        ok_15m=domain_state.cascade_passed,
        ok_5m=domain_state.cascade_passed,
        last_eval_1m_open_time_ms=domain_state.signal_open_time_ms or 0,
        next_allowed_eval_at_ms=domain_state.evaluated_at_ms,
    )


@activity.defn(name="save_mtf_state")
async def save_mtf_state(state: MtfState) -> None:
    # The rich domain MtfState is persisted inside cascade_validate_mtf;
    # this activity is a no-op kept for workflow API compatibility.
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
    # Convert temporal snapshots to raw payload dicts for evaluate_cascade
    snap_dict: dict[str, dict] = {}
    for tf, snap in snapshots.items():
        if snap is not None:
            snap_dict[tf] = snap.payload

    settings = Settings()
    session_factory = create_session_factory(settings)

    # Load the previous 1h snapshot for golden-cross detection
    prev_1h_payload: Optional[dict] = None
    with session_factory() as session:
        prev_row = session.execute(
            select(IndicatorSnapshotModel)
            .where(
                IndicatorSnapshotModel.symbol == symbol,
                IndicatorSnapshotModel.timeframe == "1h",
            )
            .order_by(IndicatorSnapshotModel.close_time_ms.desc())
            .offset(1)
            .limit(1)
        ).scalar_one_or_none()
        if prev_row is not None:
            prev_1h_payload = dict(prev_row.payload_json)

    cascade_result = evaluate_cascade(symbol, snap_dict, prev_1h_payload)

    # Persist result so downstream activities can use it
    with session_factory() as session:
        repo = MtfStateRepoSql(session)
        domain_state = DomainMtfState(
            symbol=symbol,
            regime=cascade_result.regime.value,
            cascade_passed=cascade_result.cascade_passed,
            score=cascade_result.score,
            quality=cascade_result.quality.value,
            active_setup=cascade_result.active_setup.value if cascade_result.active_setup else None,
            scores_by_tf=cascade_result.scores_by_tf,
            rejection_reason=cascade_result.rejection_reason,
            evaluated_at_ms=cascade_result.evaluated_at_ms,
        )
        repo.upsert(domain_state)
        session.commit()

    if not cascade_result.cascade_passed:
        return {
            "ok": False,
            "failed_tf": cascade_result.rejection_reason or "cascade",
            "reason": cascade_result.rejection_reason or "score_below_threshold",
        }
    return {"ok": True, "failed_tf": None, "reason": "ok"}


@activity.defn(name="create_buy_intent")
async def create_buy_intent(symbol: str, open_time_ms: int) -> OrderIntent:
    intent_key = f"buy:{symbol}:{open_time_ms}"
    settings = Settings()
    session_factory = create_session_factory(settings)
    now_ms = _now_ms()

    # Idempotency guard
    with session_factory() as session:
        existing = OrderIntentRepoSql(session).get_by_intent_key(intent_key)
    if existing is not None:
        return OrderIntent(
            intent_key=existing.intent_key,
            symbol=existing.symbol,
            side=existing.side.value,
            timeframe="1m",
            open_time_ms=open_time_ms,
            payload={"order_id": existing.id, "position_id": existing.position_id},
            status=existing.status.value,
        )

    # Load cascade result + exchange filters + candles in a single session
    with session_factory() as session:
        mtf_repo = MtfStateRepoSql(session)
        domain_mtf = mtf_repo.get(symbol)
        if domain_mtf is None or not domain_mtf.cascade_passed:
            raise RuntimeError(f"cascade not passed for {symbol}")

        cache_row = session.get(ExchangeInfoCache, symbol)
        if cache_row is None:
            raise RuntimeError(f"no exchange info for {symbol}")
        filters = SymbolFilters(
            step_size=Decimal(str(cache_row.qty_step_size or "0.01")),
            min_qty=Decimal(str(cache_row.qty_min or "0.001")),
            max_qty=Decimal(str(cache_row.qty_max or "999999")),
            tick_size=Decimal(str(cache_row.price_tick_size or "0.01")),
            min_price=Decimal(str(cache_row.price_min or "0")),
            max_price=Decimal(str(cache_row.price_max or "999999")),
            min_notional=Decimal(str(cache_row.min_notional or "10")),
        )

        candle_rows = session.execute(
            select(Candle)
            .where(
                Candle.symbol == symbol,
                Candle.timeframe == "1m",
                Candle.open_time_ms <= open_time_ms,
            )
            .order_by(Candle.open_time_ms.desc())
            .limit(2)
        ).scalars().all()
        if not candle_rows:
            raise RuntimeError(f"no 1m candle for {symbol}@{open_time_ms}")

        def _to_domain_candle(r: Any) -> DomainCandle:
            return DomainCandle(
                symbol=symbol,
                timeframe="1m",
                open_time_ms=int(r.open_time_ms),
                close_time_ms=int(r.close_time_ms),
                open=Decimal(str(r.open)),
                high=Decimal(str(r.high)),
                low=Decimal(str(r.low)),
                close=Decimal(str(r.close)),
                volume=Decimal(str(r.volume)),
            )

        candle_1m = _to_domain_candle(candle_rows[0])
        prev_candle_1m = _to_domain_candle(candle_rows[1]) if len(candle_rows) >= 2 else None

        snap_1m_row = session.execute(
            select(IndicatorSnapshotModel)
            .where(
                IndicatorSnapshotModel.symbol == symbol,
                IndicatorSnapshotModel.timeframe == "1m",
                IndicatorSnapshotModel.close_time_ms <= int(candle_rows[0].close_time_ms),
            )
            .order_by(IndicatorSnapshotModel.close_time_ms.desc())
            .limit(1)
        ).scalar_one_or_none()
        snap_5m_row = session.execute(
            select(IndicatorSnapshotModel)
            .where(
                IndicatorSnapshotModel.symbol == symbol,
                IndicatorSnapshotModel.timeframe == "5m",
            )
            .order_by(IndicatorSnapshotModel.close_time_ms.desc())
            .limit(1)
        ).scalar_one_or_none()
        snapshot_1m: dict = dict(snap_1m_row.payload_json) if snap_1m_row else {}
        snapshot_5m: dict = dict(snap_5m_row.payload_json) if snap_5m_row else {}

        open_count = PositionRepoSql(session).count_open()
        daily_pnl_raw = session.scalar(
            text("SELECT COALESCE(SUM(realized_pnl), 0) FROM pnl_trades WHERE closed_at_ms >= :ts"),
            {"ts": _today_start_ms()},
        )

    app_config = load_app_config(get_app_config_path())
    strategy = app_config.strategy
    if open_count >= strategy.max_open_positions:
        raise RuntimeError(f"max_open_positions={strategy.max_open_positions} reached")

    if strategy.daily_loss_limit_usdc < 0 and float(daily_pnl_raw or 0) <= strategy.daily_loss_limit_usdc:
        raise RuntimeError(
            f"daily_loss_limit reached: pnl={float(daily_pnl_raw or 0):.2f} USDC "
            f"(limit={strategy.daily_loss_limit_usdc})"
        )

    cascade_obj = DomainCascadeResult(
        symbol=symbol,
        regime=MarketRegime(domain_mtf.regime),
        cascade_passed=domain_mtf.cascade_passed,
        score=domain_mtf.score,
        quality=SignalQuality(domain_mtf.quality),
        active_setup=SetupType(domain_mtf.active_setup) if domain_mtf.active_setup else None,
        scores_by_tf=domain_mtf.scores_by_tf,
        rejection_reason=domain_mtf.rejection_reason,
        evaluated_at_ms=domain_mtf.evaluated_at_ms,
    )

    signal = compute_signal(
        cascade_obj,
        candle_1m,
        snapshot_1m,
        snapshot_5m,
        filters,
        prev_candle_1m=prev_candle_1m,
        config=strategy,
    )
    if signal is None:
        raise RuntimeError(f"signal not generated for {symbol}@{open_time_ms}")

    # Size lots
    lot_cfgs = strategy.exit_plan.lots  # [A, B, C]
    quote_budget = Decimal(str(strategy.per_trade_quote_budget))
    qty_total = BinanceFilters.round_quantity(quote_budget / signal.entry_price, filters)
    qty_a = BinanceFilters.round_quantity(qty_total * Decimal(str(lot_cfgs[0].pct)), filters)
    qty_b = BinanceFilters.round_quantity(qty_total * Decimal(str(lot_cfgs[1].pct)), filters)
    qty_c = BinanceFilters.round_quantity(qty_total - qty_a - qty_b, filters)

    exit_plan = ExitPlan(
        lot_a=Lot(
            id="A", pct=lot_cfgs[0].pct,
            rule=LotRule(type=lot_cfgs[0].rule.type, r_multiple=lot_cfgs[0].rule.params.get("r", 2.0)),
            quantity=qty_a,
        ),
        lot_b=Lot(
            id="B", pct=lot_cfgs[1].pct,
            rule=LotRule(type=lot_cfgs[1].rule.type, r_multiple=lot_cfgs[1].rule.params.get("r", 3.0)),
            quantity=qty_b,
        ),
        lot_c=Lot(
            id="C", pct=lot_cfgs[2].pct,
            rule=LotRule(
                type=lot_cfgs[2].rule.type,
                atr_tf=lot_cfgs[2].rule.params.get("atr_tf", "5m"),
                atr_multiplier=lot_cfgs[2].rule.params.get("k", 2.0),
            ),
            quantity=qty_c,
        ),
        r_distance=signal.r_distance,
    )

    position_id = str(uuid.uuid4())
    intent_id = str(uuid.uuid4())
    shard_id = stable_shard_of(symbol, settings.shard_count)

    domain_position = DomainPosition(
        id=position_id,
        symbol=symbol,
        side="BUY",
        status=PositionStatus.PENDING_ENTRY,
        entry_price=signal.entry_price,
        quantity_total=qty_total,
        stop_loss=signal.stop_loss,
        atr_at_entry=signal.atr_1m,
        signal_score=float(signal.score),
        setup_type=domain_mtf.active_setup or "A",
        shard_id=shard_id,
        opened_at_ms=now_ms,
        exit_plan=exit_plan,
        high_since_entry=signal.entry_price,
    )
    domain_intent = DomainOrderIntent(
        id=intent_id,
        intent_key=intent_key,
        symbol=symbol,
        side=DomainSide.BUY,
        order_type=DomainOrderType.LIMIT,
        quantity=qty_total,
        price=signal.entry_price,
        position_id=position_id,
        created_at_ms=now_ms,
        updated_at_ms=now_ms,
    )

    with session_factory() as session:
        pos_repo = PositionRepoSql(session)
        intent_repo = OrderIntentRepoSql(session)
        pos_repo.create(domain_position)
        intent_repo.create(domain_intent)
        session.commit()

    _activity_log("info", "buy_intent_created", intent_key=intent_key, symbol=symbol)
    return OrderIntent(
        intent_key=intent_key,
        symbol=symbol,
        side="BUY",
        timeframe="1m",
        open_time_ms=open_time_ms,
        payload={
            "order_id": intent_id,
            "position_id": position_id,
            "entry_price": str(signal.entry_price),
            "stop_loss": str(signal.stop_loss),
            "qty": str(qty_total),
        },
    )


@activity.defn(name="create_sell_intent")
async def create_sell_intent(
    position_id: str, symbol: str, lot_id: str, qty_pct: float
) -> OrderIntent:
    intent_key = f"sell:{position_id}:{lot_id}"
    settings = Settings()
    session_factory = create_session_factory(settings)
    now_ms = _now_ms()

    # Idempotency guard
    with session_factory() as session:
        existing = OrderIntentRepoSql(session).get_by_intent_key(intent_key)
    if existing is not None:
        return OrderIntent(
            intent_key=existing.intent_key,
            symbol=existing.symbol,
            side=existing.side.value,
            timeframe="1m",
            open_time_ms=0,
            payload={"order_id": existing.id, "lot_id": lot_id},
            status=existing.status.value,
        )

    with session_factory() as session:
        domain_pos = PositionRepoSql(session).get_by_id(position_id)
    if domain_pos is None:
        raise RuntimeError(f"position not found: {position_id}")

    # Determine the exact lot quantity
    lot_map = {lot.id: lot for lot in domain_pos.exit_plan.lots}
    lot = lot_map.get(lot_id)
    qty = lot.quantity if lot is not None else Decimal(str(qty_pct)) * domain_pos.quantity_total

    intent_id = str(uuid.uuid4())
    domain_intent = DomainOrderIntent(
        id=intent_id,
        intent_key=intent_key,
        symbol=symbol,
        side=DomainSide.SELL,
        order_type=DomainOrderType.MARKET,
        quantity=qty,
        lot_id=lot_id,
        position_id=position_id,
        created_at_ms=now_ms,
        updated_at_ms=now_ms,
    )

    with session_factory() as session:
        OrderIntentRepoSql(session).create(domain_intent)
        # F-006: transition position to CLOSING on first SELL intent
        session.execute(
            text("UPDATE positions SET status='CLOSING' WHERE id=:id AND status='ACTIVE'"),
            {"id": position_id},
        )
        session.commit()

    _activity_log("info", "sell_intent_created", intent_key=intent_key, symbol=symbol, lot=lot_id)
    return OrderIntent(
        intent_key=intent_key,
        symbol=symbol,
        side="SELL",
        timeframe="1m",
        open_time_ms=0,
        payload={"order_id": intent_id, "lot_id": lot_id, "qty": str(qty)},
    )


# F-001: duplicate-position guard used by ConsumeCandleEventsWorkflow
@activity.defn(name="check_active_position")
async def check_active_position(symbol: str) -> bool:
    settings = Settings()
    session_factory = create_session_factory(settings)
    with session_factory() as session:
        pos = PositionRepoSql(session).get_open_by_symbol(symbol)
    return pos is not None


# =========================
# Execution (Binance via REST)
# =========================


@activity.defn(name="place_order")
async def place_order(intent: OrderIntent) -> dict[str, Any]:
    mode, approved = _get_execution_mode()
    settings = Settings()
    session_factory = create_session_factory(settings)
    now_ms = _now_ms()

    # Load the canonical domain intent from DB
    with session_factory() as session:
        domain_intent = OrderIntentRepoSql(session).get_by_intent_key(intent.intent_key)

    if domain_intent is None:
        raise RuntimeError(f"intent not found: {intent.intent_key}")

    if domain_intent.status not in (OrderIntentStatus.PENDING, OrderIntentStatus.SENT):
        return {"ok": True, "mode": mode, "status": domain_intent.status.value, "skipped": True}

    if mode != "live":
        # Backtesting / dry-run: simulate fill immediately
        with session_factory() as session:
            OrderIntentRepoSql(session).update_status(
                domain_intent.id,
                OrderIntentStatus.FILLED,
                filled_qty=domain_intent.quantity,
                avg_price=domain_intent.price or Decimal("0"),
            )
            session.commit()
        _activity_log("info", "place_order_simulated", intent_key=intent.intent_key, mode=mode)
        return {"ok": True, "mode": mode, "simulated": True, "client_order_id": intent.intent_key}

    # Live: call Binance REST
    client = BinanceRestClient(
        settings,
    )
    try:
        resp = await client.place_order(
            symbol=domain_intent.symbol,
            side=domain_intent.side.value,
            order_type=domain_intent.order_type.value,
            quantity=domain_intent.quantity,
            price=domain_intent.price,
            stop_price=domain_intent.stop_price,
            client_order_id=intent.intent_key,
        )
        data = resp.data if isinstance(resp.data, dict) else {}
        binance_order_id = int(data.get("orderId", 0)) or None
        with session_factory() as session:
            OrderIntentRepoSql(session).update_status(
                domain_intent.id,
                OrderIntentStatus.SENT,
                binance_order_id=binance_order_id,
            )
            # F-006: mark position as sent to exchange
            if domain_intent.side == DomainSide.BUY and domain_intent.position_id:
                session.execute(
                    text("UPDATE positions SET status='OPEN_ENTRY_SENT' WHERE id=:id AND status='PENDING_ENTRY'"),
                    {"id": domain_intent.position_id},
                )
            session.commit()
        _activity_log("info", "place_order_sent", intent_key=intent.intent_key, binance_id=binance_order_id)
        return {"ok": True, "mode": mode, "binance_order_id": binance_order_id, "client_order_id": intent.intent_key}
    finally:
        await client.close()


@activity.defn(name="cancel_order")
async def cancel_order(symbol: str, order_id: str) -> dict[str, Any]:
    mode, approved = _get_execution_mode()
    if mode != "live":
        _activity_log("info", "cancel_order_skipped", symbol=symbol, order_id=order_id, mode=mode)
        return {"ok": True, "mode": mode, "skipped": True}

    settings = Settings()
    client = BinanceRestClient(
        settings,
    )
    try:
        binance_id = int(order_id) if order_id.isdigit() else None
        client_oid = order_id if not order_id.isdigit() else None
        await client.cancel_order(symbol=symbol, order_id=binance_id, client_order_id=client_oid)
        _activity_log("info", "cancel_order_sent", symbol=symbol, order_id=order_id)
        return {"ok": True, "mode": mode}
    except Exception as exc:
        # -2011 = unknown order (already cancelled/filled) — treat as ok
        if "-2011" in str(exc):
            return {"ok": True, "mode": mode, "already_done": True}
        raise
    finally:
        await client.close()


# F-002: place SL + TP-A + TP-B on Binance immediately after BUY fill
@activity.defn(name="place_protection_orders")
async def place_protection_orders(position_id: str) -> dict[str, Any]:
    settings = Settings()
    mode, _ = _get_execution_mode()
    session_factory = create_session_factory(settings)

    with session_factory() as session:
        domain_pos = PositionRepoSql(session).get_by_id(position_id)
    if domain_pos is None:
        raise RuntimeError(f"position not found: {position_id}")

    exit_plan = domain_pos.exit_plan
    entry = domain_pos.entry_price
    r = exit_plan.r_distance
    tp_a = entry + Decimal(str(exit_plan.lot_a.rule.r_multiple)) * r
    tp_b = entry + Decimal(str(exit_plan.lot_b.rule.r_multiple)) * r
    sl_qty = sum(lot.quantity for lot in exit_plan.lots)

    if mode != "live":
        _activity_log("info", "place_protection_orders_simulated", position_id=position_id, mode=mode)
        return {"ok": True, "mode": mode, "simulated": True}

    client = BinanceRestClient(
        settings,
    )
    try:
        sl_resp = await client.place_order(
            symbol=domain_pos.symbol, side="SELL", order_type="STOP_LOSS",
            quantity=sl_qty, stop_price=domain_pos.stop_loss,
            client_order_id=f"sl:{position_id}",
        )
        sl_order_id = int((sl_resp.data or {}).get("orderId", 0)) or None

        tp_a_resp = await client.place_order(
            symbol=domain_pos.symbol, side="SELL", order_type="LIMIT",
            quantity=exit_plan.lot_a.quantity, price=tp_a,
            client_order_id=f"tp_a:{position_id}",
        )
        tp_a_order_id = int((tp_a_resp.data or {}).get("orderId", 0)) or None

        tp_b_resp = await client.place_order(
            symbol=domain_pos.symbol, side="SELL", order_type="LIMIT",
            quantity=exit_plan.lot_b.quantity, price=tp_b,
            client_order_id=f"tp_b:{position_id}",
        )
        tp_b_order_id = int((tp_b_resp.data or {}).get("orderId", 0)) or None
    finally:
        await client.close()

    # Persist binance order IDs into exit_plan_json
    from tradebot.infra.db.repositories._serializers import exit_plan_to_json
    exit_plan.lot_a.binance_order_id = tp_a_order_id
    exit_plan.lot_b.binance_order_id = tp_b_order_id
    plan_dict = json.loads(exit_plan_to_json(exit_plan))
    plan_dict["sl_order_id"] = sl_order_id
    with session_factory() as session:
        session.execute(
            text("UPDATE positions SET exit_plan_json=:p WHERE id=:id"),
            {"p": json.dumps(plan_dict), "id": position_id},
        )
        session.commit()

    _activity_log("info", "place_protection_orders_done", position_id=position_id,
                  sl=sl_order_id, tp_a=tp_a_order_id, tp_b=tp_b_order_id)
    return {"ok": True, "mode": "live", "sl_order_id": sl_order_id,
            "tp_a_order_id": tp_a_order_id, "tp_b_order_id": tp_b_order_id}


# F-004: cancel old SL order and place a new one at updated level
@activity.defn(name="update_stop_loss")
async def update_stop_loss(position_id: str, new_sl: str, symbol: str) -> dict[str, Any]:
    settings = Settings()
    mode, _ = _get_execution_mode()
    session_factory = create_session_factory(settings)
    new_sl_dec = Decimal(new_sl)

    with session_factory() as session:
        row = session.execute(
            text("SELECT exit_plan_json, quantity_total FROM positions WHERE id=:id"),
            {"id": position_id},
        ).fetchone()
    if row is None:
        raise RuntimeError(f"position not found: {position_id}")

    plan_dict: dict = json.loads(row[0]) if row[0] else {}
    qty = Decimal(str(row[1]))

    if mode != "live":
        with session_factory() as session:
            session.execute(
                text("UPDATE positions SET stop_loss=:sl WHERE id=:id"),
                {"sl": str(new_sl_dec), "id": position_id},
            )
            session.commit()
        return {"ok": True, "mode": mode, "simulated": True}

    old_sl_order_id = plan_dict.get("sl_order_id")
    client = BinanceRestClient(
        settings,
    )
    try:
        if old_sl_order_id:
            try:
                await client.cancel_order(symbol=symbol, order_id=int(old_sl_order_id))
            except Exception as exc:
                _activity_log("warning", "update_sl_cancel_failed", error=str(exc))
        new_resp = await client.place_order(
            symbol=symbol, side="SELL", order_type="STOP_LOSS",
            quantity=qty, stop_price=new_sl_dec,
            client_order_id=f"sl_upd:{position_id}:{int(time.time())}",
        )
        new_sl_order_id = int((new_resp.data or {}).get("orderId", 0)) or None
    finally:
        await client.close()

    plan_dict["sl_order_id"] = new_sl_order_id
    with session_factory() as session:
        session.execute(
            text("UPDATE positions SET stop_loss=:sl, exit_plan_json=:p WHERE id=:id"),
            {"sl": str(new_sl_dec), "p": json.dumps(plan_dict), "id": position_id},
        )
        session.commit()

    _activity_log("info", "update_stop_loss_done", position_id=position_id, new_sl=new_sl)
    return {"ok": True, "mode": "live", "new_sl_order_id": new_sl_order_id}


# =========================
# Positions + Exit Engine
# =========================


@activity.defn(name="fetch_due_positions")
async def fetch_due_positions(shard_id: int, limit: int) -> list[Position]:
    _CHECK_INTERVAL_MS = 10_000  # positions older than 10s are due
    settings = Settings()
    session_factory = create_session_factory(settings)
    due_before_ms = _now_ms() - _CHECK_INTERVAL_MS
    with session_factory() as session:
        domain_positions = PositionRepoSql(session).list_open_by_shard(shard_id, due_before_ms)
    # Convert domain Position → temporal Position (limit applied in Python to keep it simple)
    result: list[Position] = []
    for p in domain_positions[:limit]:
        from tradebot.infra.db.repositories._serializers import exit_plan_to_json
        import json
        result.append(
            Position(
                position_id=p.id,
                symbol=p.symbol,
                shard_id=p.shard_id,
                status=p.status.value,
                qty_base=float(p.quantity_total),
                avg_entry_price=float(p.entry_price),
                exit_plan=json.loads(exit_plan_to_json(p.exit_plan)),
                next_check_at_ms=p.last_checked_ms or 0,
            )
        )
    return result


@activity.defn(name="apply_exit_engine")
async def apply_exit_engine(pos: Position) -> dict[str, Any]:
    settings = Settings()
    session_factory = create_session_factory(settings)

    with session_factory() as session:
        domain_pos = PositionRepoSql(session).get_by_id(pos.position_id)
        if domain_pos is None:
            return {"actions": [], "next_check_in_ms": 10_000}

        snap_1h_row = session.execute(
            select(IndicatorSnapshotModel)
            .where(
                IndicatorSnapshotModel.symbol == pos.symbol,
                IndicatorSnapshotModel.timeframe == "1h",
            )
            .order_by(IndicatorSnapshotModel.close_time_ms.desc())
            .limit(1)
        ).scalar_one_or_none()
        snap_5m_row = session.execute(
            select(IndicatorSnapshotModel)
            .where(
                IndicatorSnapshotModel.symbol == pos.symbol,
                IndicatorSnapshotModel.timeframe == "5m",
            )
            .order_by(IndicatorSnapshotModel.close_time_ms.desc())
            .limit(1)
        ).scalar_one_or_none()

        candle_row = session.execute(
            select(Candle)
            .where(Candle.symbol == pos.symbol, Candle.timeframe == "5m")
            .order_by(Candle.open_time_ms.desc())
            .limit(1)
        ).scalar_one_or_none()

    if candle_row is None:
        return {"actions": [], "next_check_in_ms": 10_000}

    snapshot_1h: dict = dict(snap_1h_row.payload_json) if snap_1h_row else {}
    snapshot_5m: dict = dict(snap_5m_row.payload_json) if snap_5m_row else {}
    candle_5m = DomainCandle(
        symbol=pos.symbol,
        timeframe="5m",
        open_time_ms=int(candle_row.open_time_ms),
        close_time_ms=int(candle_row.close_time_ms),
        open=Decimal(str(candle_row.open)),
        high=Decimal(str(candle_row.high)),
        low=Decimal(str(candle_row.low)),
        close=Decimal(str(candle_row.close)),
        volume=Decimal(str(candle_row.volume)),
    )

    intents = compute_exit_intents(domain_pos, snapshot_1h, snapshot_5m, candle_5m)

    actions: list[dict[str, Any]] = []
    for intent in intents:
        if intent.quantity > Decimal("0"):
            actions.append({
                "type": "SELL",
                "lot": intent.lot_id,
                "qty": str(intent.quantity),
                "reason": intent.reason.value,
                "order_type": intent.order_type,
            })
        elif intent.new_stop_loss is not None or intent.new_trailing_level is not None:
            actions.append({
                "type": "UPDATE_SL",
                "lot": intent.lot_id,
                "new_stop_loss": str(intent.new_stop_loss) if intent.new_stop_loss else None,
                "new_trailing": str(intent.new_trailing_level) if intent.new_trailing_level else None,
                "reason": intent.reason.value,
            })

    # F-003: expose current candle high so the workflow can update high_since_entry
    return {"actions": actions, "next_check_in_ms": 10_000, "new_high": float(candle_5m.high)}


@activity.defn(name="update_position_after_actions")
async def update_position_after_actions(
    position_id: str, patch: dict[str, Any]
) -> None:
    settings = Settings()
    session_factory = create_session_factory(settings)
    now_ms = _now_ms()
    with session_factory() as session:
        repo = PositionRepoSql(session)
        domain_pos = repo.get_by_id(position_id)
        if domain_pos is None:
            _activity_log("warning", "update_position_not_found", position_id=position_id)
            return
        from dataclasses import replace as dc_replace
        new_high_val = patch.get("new_high")
        new_high = (
            Decimal(str(new_high_val))
            if new_high_val is not None and Decimal(str(new_high_val)) > domain_pos.high_since_entry
            else domain_pos.high_since_entry
        )
        updated = dc_replace(domain_pos, last_checked_ms=now_ms, high_since_entry=new_high)
        repo.update(updated)
        session.commit()
    _activity_log("info", "update_position", position_id=position_id)


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
    base_url = (
        os.environ.get("BINANCE_REST_URL", BINANCE_REST_URL).strip() or BINANCE_REST_URL
    )

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
        detect_symbols = _target_symbols_for_detection(session) | {
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
                    if inserted <= 0:
                        session.rollback()
                        failures += 1
                        repo.record_http_result(
                            job_id=job_id,
                            http_status=424,
                            now_ms=_now_ms(),
                            policy=policy,
                            headers=headers,
                            error_message="binance returned no candles for requested gap window",
                        )
                    else:
                        session.commit()
                        inserted_candles += inserted
                        repo.record_http_result(
                            job_id=job_id,
                            http_status=200,
                            now_ms=_now_ms(),
                            policy=policy,
                            headers=headers,
                        )
                except _BinanceHttpError as exc:
                    session.rollback()
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
                    session.rollback()
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
    mode, _ = _get_execution_mode()
    settings = Settings()
    session_factory = create_session_factory(settings)
    fixed = 0
    errors = 0

    with session_factory() as session:
        active_intents = OrderIntentRepoSql(session).list_active()

    if not active_intents or mode != "live":
        return {"ok": True, "fixed": fixed, "mode": mode}

    client = BinanceRestClient(
        settings,
    )
    try:
        for intent in active_intents:
            if intent.binance_order_id is None:
                continue
            try:
                resp = await client.get_order(
                    symbol=intent.symbol, order_id=intent.binance_order_id
                )
                data = resp.data if isinstance(resp.data, dict) else {}
                binance_status = str(data.get("status", "")).upper()
                if binance_status in ("FILLED", "CANCELED", "EXPIRED", "REJECTED"):
                    new_status = (
                        OrderIntentStatus.FILLED
                        if binance_status == "FILLED"
                        else OrderIntentStatus.CANCELLED
                    )
                    filled_qty_raw = data.get("executedQty")
                    avg_price_raw = data.get("avgPrice") or data.get("price")
                    with session_factory() as session:
                        OrderIntentRepoSql(session).update_status(
                            intent.id,
                            new_status,
                            filled_qty=Decimal(str(filled_qty_raw)) if filled_qty_raw else None,
                            avg_price=Decimal(str(avg_price_raw)) if avg_price_raw else None,
                        )
                        session.commit()
                    fixed += 1
            except Exception as exc:
                _activity_log("warning", "reconcile_orders_error", intent_id=intent.id, error=str(exc))
                errors += 1
    finally:
        await client.close()

    _activity_log("info", "reconcile_orders_done", fixed=fixed, errors=errors)
    return {"ok": errors == 0, "fixed": fixed, "errors": errors, "mode": mode}


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
            for key, value in row.items():
                setattr(existing, key, value)
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


# Lag tolerance before a timeframe's leading edge is considered stale.
# 2 steps absorbs WS processing + Temporal scheduling jitter.
_FRESHNESS_LAG_STEPS: dict[str, int] = {
    "1m": 2, "5m": 2, "15m": 2, "1h": 2, "4h": 2,
}


@activity.defn(name="detect_kline_leading_gaps")
async def detect_kline_leading_gaps() -> dict[str, Any]:
    """
    For every active symbol and configured timeframe, check whether the most
    recent candle in the DB is fresh enough.  If the leading edge is stale,
    insert a candle_gap_request so ReconcileKlinesWorkflow can backfill it.
    """
    settings = Settings()
    session_factory = create_session_factory(settings)
    now_ms = _now_ms()
    gaps_found = 0
    symbols_checked = 0

    with session_factory() as session:
        symbols: list[str] = list(
            session.scalars(
                select(ExchangeInfoCache.symbol).where(ExchangeInfoCache.status == "TRADING")
            )
        )
        if not symbols:
            symbols = list(_target_symbols_for_detection(session))

        for symbol in symbols:
            symbols_checked += 1
            for tf in DETECT_RECONCILE_TIMEFRAMES:
                step_ms = timeframe_to_ms(tf)
                lag_steps = _FRESHNESS_LAG_STEPS.get(tf, 2)
                # Latest candle we should already have (with tolerance)
                expected_latest_ms = (now_ms // step_ms - lag_steps) * step_ms

                max_open = session.scalar(
                    select(func.max(Candle.open_time_ms)).where(
                        Candle.symbol == symbol,
                        Candle.timeframe == tf,
                    )
                )

                if max_open is None or int(max_open) < expected_latest_ms:
                    gap_from = int(max_open) + step_ms if max_open is not None else expected_latest_ms
                    # exclusive upper bound so _normalize_gap_request_window includes expected_latest_ms
                    gap_to = expected_latest_ms + step_ms
                    if gap_from >= gap_to:
                        continue

                    # Avoid duplicate requests created in the last 5 minutes
                    recent_exists = session.scalar(
                        select(func.count()).select_from(CandleGapRequest).where(
                            CandleGapRequest.symbol == symbol,
                            CandleGapRequest.from_open_time_ms == gap_from,
                            CandleGapRequest.to_open_time_ms == gap_to,
                            CandleGapRequest.detected_at >= func.now() - text("interval '5 minutes'"),
                        )
                    )
                    if recent_exists:
                        continue

                    session.add(CandleGapRequest(
                        symbol=symbol,
                        from_open_time_ms=gap_from,
                        to_open_time_ms=gap_to,  # exclusive: normalize subtracts step_ms
                    ))
                    gaps_found += 1

        session.commit()

    _activity_log(
        "info", "detect_kline_leading_gaps_done",
        symbols_checked=symbols_checked,
        gaps_found=gaps_found,
    )
    return {"gaps_found": gaps_found, "symbols_checked": symbols_checked}


# =========================
# Historical Data / Warmup
# =========================

# Minimum candles needed to produce a valid EMA200 (the longest warmup indicator).
MIN_WARMUP_CANDLES = 200


@activity.defn(name="list_warmup_symbols")
async def list_warmup_symbols() -> list[str]:
    """
    Returns the list of symbols that need indicator warmup.
    Priority: WARMUP_SYMBOLS env var > exchange_info_cache TRADING symbols > default.
    """
    raw = os.environ.get("WARMUP_SYMBOLS", "").strip()
    if raw:
        return [s.strip().upper() for s in raw.split(",") if s.strip()]

    settings = Settings()
    session_factory = create_session_factory(settings)
    with session_factory() as session:
        symbols = list(
            session.scalars(
                select(ExchangeInfoCache.symbol).where(ExchangeInfoCache.status == "TRADING")
            )
        )
    return symbols if symbols else list(DEFAULT_RECONCILE_SYMBOLS)


@activity.defn(name="ensure_indicator_warmup")
async def ensure_indicator_warmup(
    symbol: str, timeframe: str, min_candles: int = MIN_WARMUP_CANDLES
) -> dict[str, Any]:
    """
    Ensures at least `min_candles` exist for (symbol, timeframe).
    Backfills backwards from the earliest existing candle (or from now) if needed.
    """
    settings = Settings()
    session_factory = create_session_factory(settings)
    base_url = os.environ.get("BINANCE_REST_URL", BINANCE_REST_URL).strip() or BINANCE_REST_URL
    step_ms = timeframe_to_ms(timeframe)
    now_ms = _now_ms()

    with session_factory() as session:
        count: int = session.scalar(
            select(func.count()).select_from(Candle).where(
                Candle.symbol == symbol, Candle.timeframe == timeframe,
            )
        ) or 0
        min_open: int | None = session.scalar(
            select(func.min(Candle.open_time_ms)).where(
                Candle.symbol == symbol, Candle.timeframe == timeframe,
            )
        )

    if count >= min_candles:
        return {"symbol": symbol, "timeframe": timeframe,
                "already_sufficient": True, "count": count, "inserted": 0}

    needed = min_candles - count
    if min_open is not None:
        # Extend the window backwards from the earliest stored candle.
        to_ms = int(min_open) - step_ms
        from_ms = to_ms - (needed - 1) * step_ms
    else:
        # No candles at all — take the last min_candles up to the latest completed candle.
        latest_complete_ms = (now_ms // step_ms - 1) * step_ms
        from_ms = latest_complete_ms - (min_candles - 1) * step_ms
        to_ms = latest_complete_ms

    from_ms = max(from_ms, 0)
    if from_ms > to_ms:
        return {"symbol": symbol, "timeframe": timeframe,
                "already_sufficient": False, "inserted": 0, "skipped": True}

    inserted = 0
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as http_session:
        with session_factory() as session:
            inserted, _ = await _backfill_job_from_binance(
                session, http_session,
                base_url=base_url, symbol=symbol, timeframe=timeframe,
                from_open_time_ms=from_ms, to_open_time_ms=to_ms,
                shard_count=settings.shard_count,
            )
            session.commit()

    _activity_log("info", "ensure_indicator_warmup_done",
                  symbol=symbol, timeframe=timeframe, inserted=inserted, was_count=count)
    return {"symbol": symbol, "timeframe": timeframe,
            "already_sufficient": False, "inserted": inserted}


@activity.defn(name="get_daily_realized_pnl")
async def get_daily_realized_pnl() -> dict[str, Any]:
    """
    Returns today's realized PnL in USDC and a per-symbol breakdown.
    Used for observability and the daily loss circuit breaker.
    """
    settings = Settings()
    session_factory = create_session_factory(settings)
    today_ms = _today_start_ms()

    with session_factory() as session:
        total = session.scalar(
            text("SELECT COALESCE(SUM(realized_pnl), 0) FROM pnl_trades WHERE closed_at_ms >= :ts"),
            {"ts": today_ms},
        )
        rows = session.execute(
            text(
                "SELECT symbol, SUM(realized_pnl) AS pnl "
                "FROM pnl_trades WHERE closed_at_ms >= :ts "
                "GROUP BY symbol ORDER BY symbol"
            ),
            {"ts": today_ms},
        ).fetchall()

    by_symbol = {str(r[0]): float(r[1]) for r in rows}
    return {
        "today_start_ms": today_ms,
        "total_pnl_usdc": float(total or 0),
        "by_symbol": by_symbol,
        "trades": len(rows),
    }


@activity.defn(name="fetch_historical_klines")
async def fetch_historical_klines(
    symbol: str, timeframe: str, from_ms: int, to_ms: int
) -> dict[str, Any]:
    """
    Fetches and upserts ALL klines in [from_ms, to_ms] from Binance REST API.
    Used by BacktestDataFetchWorkflow for arbitrary date-range backfills.
    """
    settings = Settings()
    session_factory = create_session_factory(settings)
    base_url = os.environ.get("BINANCE_REST_URL", BINANCE_REST_URL).strip() or BINANCE_REST_URL

    inserted = 0
    timeout = aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession(timeout=timeout) as http_session:
        with session_factory() as session:
            inserted, _ = await _backfill_job_from_binance(
                session, http_session,
                base_url=base_url, symbol=symbol, timeframe=timeframe,
                from_open_time_ms=from_ms, to_open_time_ms=to_ms,
                shard_count=settings.shard_count,
            )
            session.commit()

    _activity_log("info", "fetch_historical_klines_done",
                  symbol=symbol, timeframe=timeframe, from_ms=from_ms, to_ms=to_ms, inserted=inserted)
    return {"symbol": symbol, "timeframe": timeframe,
            "from_ms": from_ms, "to_ms": to_ms, "inserted": inserted}
