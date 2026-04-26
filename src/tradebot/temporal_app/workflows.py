from __future__ import annotations

from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy, WorkflowIDReusePolicy

from .types import CandleCloseEvent, Position

DEFAULT_RETRY = RetryPolicy(maximum_attempts=3)
AIO_TIMEOUT = timedelta(seconds=30)


@workflow.defn
class ConsumeCandleEventsWorkflow:
    """
    Batch consumer per shard:
    - read candle_close_event
    - validate + compute snapshot
    - update mtf_state
    """

    @workflow.run
    async def run(
        self, shard_id: int, shard_count: int, batch_limit: int = 500
    ) -> dict:
        events: list[CandleCloseEvent] = await workflow.execute_activity(
            "fetch_candle_close_events",
            args=[shard_id, shard_count, batch_limit],
            start_to_close_timeout=AIO_TIMEOUT,
            retry_policy=DEFAULT_RETRY,
        )

        processed = 0
        for evt in events:
            v = await workflow.execute_activity(
                "validate_candle_event",
                arg=evt,
                start_to_close_timeout=AIO_TIMEOUT,
                retry_policy=DEFAULT_RETRY,
            )
            if not v.get("ok", False):
                continue

            await workflow.execute_activity(
                "compute_indicator_snapshot",
                args=[evt.symbol, evt.timeframe, evt.open_time_ms],
                start_to_close_timeout=AIO_TIMEOUT,
                retry_policy=DEFAULT_RETRY,
            )
            processed += 1

            # F-001: 1m close triggers cascade evaluation
            if evt.timeframe == "1m":
                has_active: bool = await workflow.execute_activity(
                    "check_active_position",
                    arg=evt.symbol,
                    start_to_close_timeout=AIO_TIMEOUT,
                    retry_policy=DEFAULT_RETRY,
                )
                if not has_active:
                    await workflow.execute_child_workflow(
                        CascadeValidateAndEnterWorkflow.run,
                        args=[evt.symbol, evt.open_time_ms],
                        id=f"cascade-{evt.symbol}-{evt.open_time_ms}",
                        id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
                        parent_close_policy=workflow.ParentClosePolicy.ABANDON,
                    )

        if events:
            await workflow.execute_activity(
                "mark_candle_close_events_processed",
                arg=events,
                start_to_close_timeout=AIO_TIMEOUT,
                retry_policy=DEFAULT_RETRY,
            )

        return {"shard": shard_id, "events": len(events), "processed": processed}


@workflow.defn
class CascadeValidateAndEnterWorkflow:
    """
    Cascade 4h->1h->15m->5m->1m for a symbol and a 1m close,
    then create + execute a BUY intent.
    """

    @workflow.run
    async def run(self, symbol: str, open_time_ms_1m: int) -> dict:
        snapshots = await workflow.execute_activity(
            "load_latest_snapshots",
            arg=symbol,
            start_to_close_timeout=AIO_TIMEOUT,
            retry_policy=DEFAULT_RETRY,
        )

        state = await workflow.execute_activity(
            "load_mtf_state",
            arg=symbol,
            start_to_close_timeout=AIO_TIMEOUT,
            retry_policy=DEFAULT_RETRY,
        )

        decision = await workflow.execute_activity(
            "cascade_validate_mtf",
            args=[symbol, snapshots, state],
            start_to_close_timeout=AIO_TIMEOUT,
            retry_policy=DEFAULT_RETRY,
        )

        if not decision.get("ok", False):
            return {
                "ok": False,
                "symbol": symbol,
                "failed_tf": decision.get("failed_tf"),
                "reason": decision.get("reason"),
            }

        intent = await workflow.execute_activity(
            "create_buy_intent",
            args=[symbol, open_time_ms_1m],
            start_to_close_timeout=AIO_TIMEOUT,
            retry_policy=DEFAULT_RETRY,
        )

        placed = await workflow.execute_activity(
            "place_order",
            arg=intent,
            start_to_close_timeout=timedelta(seconds=20),
            retry_policy=RetryPolicy(maximum_attempts=5),
        )

        return {
            "ok": True,
            "symbol": symbol,
            "intent_key": intent.intent_key,
            "placed": placed,
        }


@workflow.defn
class PostFillSetupWorkflow:
    """
    Triggered by ws_user after a BUY fill.
    Places SL + TP_A + TP_B protection orders on Binance.
    """

    @workflow.run
    async def run(self, position_id: str) -> dict:
        result = await workflow.execute_activity(
            "place_protection_orders",
            arg=position_id,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=5),
        )
        return {"ok": True, "position_id": position_id, "orders": result}


@workflow.defn
class ProcessClosedCandlesWorkflow:
    """
    Wrapper workflow triggered by a Schedule:
    - consume events (batch shard)
    - (optional) trigger cascade on 1m events
    """

    @workflow.run
    async def run(self, shard_id: int, shard_count: int) -> dict:
        summary = await workflow.execute_child_workflow(
            ConsumeCandleEventsWorkflow.run,
            args=[shard_id, shard_count, 500],
        )
        return {"ok": True, "summary": summary}


@workflow.defn
class ManageOpenPositionsWorkflow:
    """
    Tick batch per shard:
    - load due positions
    - apply ExitEngine -> SELL intents -> place orders
    """

    @workflow.run
    async def run(self, shard_id: int, max_positions: int = 200) -> dict:
        positions: list[Position] = await workflow.execute_activity(
            "fetch_due_positions",
            args=[shard_id, max_positions],
            start_to_close_timeout=AIO_TIMEOUT,
            retry_policy=DEFAULT_RETRY,
        )

        acted = 0
        for pos in positions:
            out = await workflow.execute_activity(
                "apply_exit_engine",
                arg=pos,
                start_to_close_timeout=AIO_TIMEOUT,
                retry_policy=DEFAULT_RETRY,
            )
            actions = out.get("actions", [])
            for a in actions:
                if a.get("type") == "SELL":
                    intent = await workflow.execute_activity(
                        "create_sell_intent",
                        args=[
                            pos.position_id,
                            pos.symbol,
                            a.get("lot", "A"),
                            float(a.get("pct", 0.0)),
                        ],
                        start_to_close_timeout=AIO_TIMEOUT,
                        retry_policy=DEFAULT_RETRY,
                    )
                    await workflow.execute_activity(
                        "place_order",
                        arg=intent,
                        start_to_close_timeout=timedelta(seconds=20),
                        retry_policy=RetryPolicy(maximum_attempts=5),
                    )
                    acted += 1

                elif a.get("type") == "UPDATE_SL":
                    # F-004: propagate stop-loss update to Binance
                    new_sl = a.get("new_stop_loss") or a.get("new_trailing")
                    if new_sl:
                        await workflow.execute_activity(
                            "update_stop_loss",
                            args=[pos.position_id, str(new_sl), pos.symbol],
                            start_to_close_timeout=timedelta(seconds=20),
                            retry_policy=RetryPolicy(maximum_attempts=3),
                        )
                        acted += 1

            next_in = int(out.get("next_check_in_ms", 10_000))
            # F-003: pass candle high so activity can advance high_since_entry
            patch = {"next_check_in_ms": next_in, "new_high": out.get("new_high")}
            await workflow.execute_activity(
                "update_position_after_actions",
                args=[pos.position_id, patch],
                start_to_close_timeout=AIO_TIMEOUT,
                retry_policy=DEFAULT_RETRY,
            )

        return {
            "ok": True,
            "shard": shard_id,
            "positions": len(positions),
            "actions": acted,
        }


@workflow.defn
class ReconcileKlinesWorkflow:
    @workflow.run
    async def run(self) -> dict:
        return await workflow.execute_activity(
            "reconcile_klines",
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )


@workflow.defn
class CheckKlineFreshnessWorkflow:
    """
    Runs every minute.  Detects stale leading edges for every active
    symbol/timeframe and, when gaps are found, immediately triggers
    ReconcileKlinesWorkflow to backfill them without waiting for the
    30-minute maintenance window.
    """

    @workflow.run
    async def run(self) -> dict:
        result = await workflow.execute_activity(
            "detect_kline_leading_gaps",
            start_to_close_timeout=AIO_TIMEOUT,
            retry_policy=DEFAULT_RETRY,
        )

        if result.get("gaps_found", 0) > 0:
            await workflow.execute_child_workflow(
                ReconcileKlinesWorkflow.run,
                id=f"reconcile-klines-triggered-{workflow.info().workflow_id}",
                id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
                parent_close_policy=workflow.ParentClosePolicy.ABANDON,
            )

        return result


@workflow.defn
class ReconcileOrdersWorkflow:
    @workflow.run
    async def run(self) -> dict:
        return await workflow.execute_activity(
            "reconcile_orders",
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )


@workflow.defn
class RefreshExchangeInfoWorkflow:
    @workflow.run
    async def run(self) -> dict:
        return await workflow.execute_activity(
            "refresh_exchange_info",
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )


@workflow.defn
class InitialBackfillWorkflow:
    """
    Launched once per calendar day at worker startup.
    Ensures every active symbol has at least `min_candles` historical klines on
    all configured timeframes so technical indicators can produce valid values.
    Sequential per symbol to respect Binance rate limits.
    """

    @workflow.run
    async def run(self, min_candles: int = 200) -> dict:
        symbols: list[str] = await workflow.execute_activity(
            "list_warmup_symbols",
            start_to_close_timeout=AIO_TIMEOUT,
            retry_policy=DEFAULT_RETRY,
        )

        timeframes = ["4h", "1h", "15m", "5m", "1m"]  # longest first to warm up indicators
        total_inserted = 0
        skipped = 0

        for symbol in symbols:
            for tf in timeframes:
                result = await workflow.execute_activity(
                    "ensure_indicator_warmup",
                    args=[symbol, tf, min_candles],
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=RetryPolicy(maximum_attempts=3),
                )
                if result.get("already_sufficient") or result.get("skipped"):
                    skipped += 1
                else:
                    total_inserted += result.get("inserted", 0)

        return {
            "ok": True,
            "symbols": len(symbols),
            "timeframes": len(timeframes),
            "inserted": total_inserted,
            "skipped": skipped,
        }


@workflow.defn
class BacktestDataFetchWorkflow:
    """
    On-demand workflow: fetches all klines for a symbol in [from_ms, to_ms]
    across the requested timeframes.  Triggered manually via Temporal UI / CLI
    or a future API endpoint to prepare historical data for backtesting.
    """

    @workflow.run
    async def run(
        self,
        symbol: str,
        from_ms: int,
        to_ms: int,
        timeframes: list[str] | None = None,
    ) -> dict:
        tfs = timeframes or ["4h", "1h", "15m", "5m", "1m"]
        total_inserted = 0

        for tf in tfs:
            result = await workflow.execute_activity(
                "fetch_historical_klines",
                args=[symbol, tf, from_ms, to_ms],
                # Long timeout: large date ranges can need many paginated requests.
                start_to_close_timeout=timedelta(minutes=30),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
            total_inserted += result.get("inserted", 0)

        return {
            "ok": True,
            "symbol": symbol,
            "from_ms": from_ms,
            "to_ms": to_ms,
            "timeframes": tfs,
            "inserted": total_inserted,
        }


@workflow.defn
class IntentDispatcherWorkflow:
    """
    Optional: isolate execution of an intent (BUY/SELL) + error handling.
    """

    @workflow.run
    async def run(self, intent_key: str) -> dict:
        # TODO: load intent from DB, then place/cancel with stronger retry semantics
        return {"ok": True, "intent_key": intent_key}


@workflow.defn
class PositionWorkflow:
    """
    Optional: 1 workflow per position (instead of ManageOpenPositions batch).
    """

    @workflow.run
    async def run(self, position_id: str) -> dict:
        # TODO: loop with timers, continue-as-new if needed
        return {"ok": True, "position_id": position_id}
