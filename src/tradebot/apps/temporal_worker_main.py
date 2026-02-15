import asyncio
import logging

from temporalio.client import Client
from temporalio.worker import Worker

from tradebot.config.loader import load_app_config
from tradebot.config.settings import Settings
from tradebot.config.utils import get_app_config_path
from tradebot.infra.temporal.schedules import ScheduleBootstrap
from tradebot.temporal_app import activities as act
from tradebot.temporal_app import workflows as wf

TASK_QUEUE = "tradebot"


def build_worker(client: Client) -> Worker:
    return Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[
            wf.ConsumeCandleEventsWorkflow,
            wf.CascadeValidateAndEnterWorkflow,
            wf.ProcessClosedCandlesWorkflow,
            wf.ManageOpenPositionsWorkflow,
            wf.ReconcileKlinesWorkflow,
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
            act.create_buy_intent,
            act.create_sell_intent,
            act.place_order,
            act.cancel_order,
            act.fetch_due_positions,
            act.apply_exit_engine,
            act.update_position_after_actions,
            act.reconcile_klines,
            act.reconcile_orders,
            act.refresh_exchange_info,
        ],
    )


async def run_worker() -> None:
    settings = Settings()
    client = await Client.connect(settings.temporal_address)
    app_config = load_app_config(get_app_config_path())
    schedule_bootstrap = ScheduleBootstrap(client, task_queue=TASK_QUEUE)
    bootstrap_result = await schedule_bootstrap.bootstrap(app_config)
    worker = build_worker(client)
    logging.getLogger(__name__).info(
        "Temporal worker started",
        extra={
            "address": settings.temporal_address,
            "task_queue": TASK_QUEUE,
            **bootstrap_result,
        },
    )
    await worker.run()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
