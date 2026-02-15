from __future__ import annotations

import time
from temporalio import activity
from typing import Any, Optional

from .types import (
    CandleCloseEvent,
    IndicatorSnapshot,
    MtfState,
    OrderIntent,
    Position,
    Timeframe,
)
from tradebot.config.settings import Settings


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
    log_method = getattr(logger, level)
    try:
        if fields:
            log_method(event, **fields)
        else:
            log_method(event)
    except TypeError:
        if fields:
            log_method("%s %s", event, fields)
            return
        log_method(event)


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
    activity.logger.info("fetch_candle_close_events shard=%s limit=%s", shard_id, limit)
    return []


@activity.defn(name="mark_candle_close_events_processed")
async def mark_candle_close_events_processed(events: list[CandleCloseEvent]) -> None:
    """Mark consumed events (idempotent)."""
    # TODO: DELETE FROM candle_close_event WHERE (symbol,tf,open_time) IN (...)
    activity.logger.info("mark events processed count=%s", len(events))


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
    activity.logger.info("save_mtf_state symbol=%s", state.symbol)


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
    activity.logger.info("update_position %s patch=%s", position_id, patch)


# =========================
# Reconciliation / Maintenance
# =========================


@activity.defn(name="reconcile_klines")
async def reconcile_klines() -> dict[str, Any]:
    """
    Detect gaps and backfill via REST if needed.
    """
    # TODO: scan per symbol/tf, backfill /api/v3/klines
    return {"ok": True, "gaps_filled": 0}


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
    # TODO: call exchangeInfo, store cache
    return {"ok": True}
