import asyncio
import logging
from datetime import date, timedelta

from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.worker import Worker

from tradebot.config.loader import load_app_config
from tradebot.config.settings import Settings
from tradebot.config.utils import get_app_config_path
from tradebot.infra.temporal.schedules import ScheduleBootstrap
from tradebot.temporal_app import activities as act
from tradebot.temporal_app import workflows as wf

TASK_QUEUE = "tradebot"

log = logging.getLogger(__name__)


def build_worker(client: Client) -> Worker:
    return Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[
            wf.ConsumeCandleEventsWorkflow,
            wf.CascadeValidateAndEnterWorkflow,
            wf.PostFillSetupWorkflow,
            wf.ProcessClosedCandlesWorkflow,
            wf.ManageOpenPositionsWorkflow,
            wf.ReconcileKlinesWorkflow,
            wf.CheckKlineFreshnessWorkflow,
            wf.InitialBackfillWorkflow,
            wf.BacktestDataFetchWorkflow,
            wf.ReconcileOrdersWorkflow,
            wf.RefreshExchangeInfoWorkflow,
            wf.IntentDispatcherWorkflow,
            wf.PositionWorkflow,
        ],
        activities=[
            act.fetch_candle_close_events,
            act.mark_candle_close_events_processed,
            act.validate_candle_event,
            act.compute_indicator_snapshot,
            act.load_latest_snapshots,
            act.load_mtf_state,
            act.save_mtf_state,
            act.cascade_validate_mtf,
            act.check_active_position,
            act.create_buy_intent,
            act.create_sell_intent,
            act.place_order,
            act.cancel_order,
            act.place_protection_orders,
            act.update_stop_loss,
            act.fetch_due_positions,
            act.apply_exit_engine,
            act.update_position_after_actions,
            act.reconcile_klines,
            act.detect_kline_leading_gaps,
            act.list_warmup_symbols,
            act.ensure_indicator_warmup,
            act.fetch_historical_klines,
            act.reconcile_orders,
            act.refresh_exchange_info,
        ],
    )


async def _trigger_initial_backfill(client: Client) -> None:
    """
    Start InitialBackfillWorkflow once per calendar day.
    Uses a date-scoped ID so it is a no-op if already running or completed today.
    """
    workflow_id = f"initial-backfill-{date.today().isoformat()}"
    try:
        await client.start_workflow(
            "InitialBackfillWorkflow",
            args=[200],
            id=workflow_id,
            task_queue=TASK_QUEUE,
            execution_timeout=timedelta(hours=4),
            id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
        )
        log.info("Initial backfill workflow started", extra={"workflow_id": workflow_id})
    except Exception as exc:
        # Already completed or running for today — not an error.
        log.info("Initial backfill skipped (already run today or running)",
                 extra={"workflow_id": workflow_id, "reason": str(exc)})


async def run_worker() -> None:
    settings = Settings()
    client = await Client.connect(settings.temporal_address)
    app_config = load_app_config(get_app_config_path())
    schedule_bootstrap = ScheduleBootstrap(client, task_queue=TASK_QUEUE)
    bootstrap_result = await schedule_bootstrap.bootstrap(app_config)
    worker = build_worker(client)
    log.info(
        "Temporal worker started",
        extra={
            "address": settings.temporal_address,
            "task_queue": TASK_QUEUE,
            **bootstrap_result,
        },
    )
    # Fire-and-forget: the workflow runs on this same worker once it's processing.
    await _trigger_initial_backfill(client)
    await worker.run()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
