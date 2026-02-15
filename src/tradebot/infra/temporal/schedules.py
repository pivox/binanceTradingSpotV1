from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import re
from typing import Protocol

from temporalio.client import (
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleAlreadyRunningError,
    ScheduleIntervalSpec,
    ScheduleSpec,
    ScheduleUpdate,
)
from temporalio.service import RPCError, RPCStatusCode

from tradebot.config.types import AppConfig

RECONCILE_KLINES_SCHEDULE_ID = "tradebot-reconcile-klines"
RECONCILE_ORDERS_SCHEDULE_ID = "tradebot-reconcile-orders"
REFRESH_EXCHANGEINFO_SCHEDULE_ID = "tradebot-refresh-exchangeinfo"
_DAILY_HHMM_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


class _ScheduleHandle(Protocol):
    async def update(self, updater): ...


class _ScheduleClient(Protocol):
    async def create_schedule(self, id: str, schedule: Schedule): ...

    def get_schedule_handle(self, id: str) -> _ScheduleHandle: ...


@dataclass(frozen=True)
class ScheduleDefinition:
    schedule_id: str
    schedule: Schedule


def _daily_hhmm_to_cron(value: str) -> str:
    if not _DAILY_HHMM_RE.fullmatch(value):
        raise ValueError("exchangeinfo_daily must match HH:MM (24h)")
    hour, minute = value.split(":", maxsplit=1)
    return f"{int(minute)} {int(hour)} * * *"


def _build_schedule_definitions(
    app_config: AppConfig, *, task_queue: str
) -> list[ScheduleDefinition]:
    if app_config.schedules.reconcile_klines_min <= 0:
        raise ValueError("reconcile_klines_min must be > 0")
    if app_config.schedules.reconcile_orders_min <= 0:
        raise ValueError("reconcile_orders_min must be > 0")

    return [
        ScheduleDefinition(
            schedule_id=RECONCILE_KLINES_SCHEDULE_ID,
            schedule=Schedule(
                action=ScheduleActionStartWorkflow(
                    "ReconcileKlinesWorkflow",
                    id=f"{RECONCILE_KLINES_SCHEDULE_ID}-workflow",
                    task_queue=task_queue,
                ),
                spec=ScheduleSpec(
                    intervals=[
                        ScheduleIntervalSpec(
                            every=timedelta(
                                minutes=app_config.schedules.reconcile_klines_min
                            )
                        )
                    ]
                ),
            ),
        ),
        ScheduleDefinition(
            schedule_id=RECONCILE_ORDERS_SCHEDULE_ID,
            schedule=Schedule(
                action=ScheduleActionStartWorkflow(
                    "ReconcileOrdersWorkflow",
                    id=f"{RECONCILE_ORDERS_SCHEDULE_ID}-workflow",
                    task_queue=task_queue,
                ),
                spec=ScheduleSpec(
                    intervals=[
                        ScheduleIntervalSpec(
                            every=timedelta(
                                minutes=app_config.schedules.reconcile_orders_min
                            )
                        )
                    ]
                ),
            ),
        ),
        ScheduleDefinition(
            schedule_id=REFRESH_EXCHANGEINFO_SCHEDULE_ID,
            schedule=Schedule(
                action=ScheduleActionStartWorkflow(
                    "RefreshExchangeInfoWorkflow",
                    id=f"{REFRESH_EXCHANGEINFO_SCHEDULE_ID}-workflow",
                    task_queue=task_queue,
                ),
                spec=ScheduleSpec(
                    cron_expressions=[
                        _daily_hhmm_to_cron(app_config.schedules.exchangeinfo_daily)
                    ]
                ),
            ),
        ),
    ]


class ScheduleBootstrap:
    def __init__(self, client: _ScheduleClient, *, task_queue: str) -> None:
        self._client = client
        self._task_queue = task_queue

    async def bootstrap(self, app_config: AppConfig) -> dict[str, int]:
        created = 0
        updated = 0

        for definition in _build_schedule_definitions(
            app_config, task_queue=self._task_queue
        ):
            op = await self._upsert_schedule(definition)
            if op == "created":
                created += 1
            else:
                updated += 1

        return {
            "created": created,
            "updated": updated,
            "total": created + updated,
        }

    async def _upsert_schedule(self, definition: ScheduleDefinition) -> str:
        try:
            await self._client.create_schedule(
                id=definition.schedule_id,
                schedule=definition.schedule,
            )
            return "created"
        except ScheduleAlreadyRunningError:
            pass
        except RPCError as exc:
            if exc.status != RPCStatusCode.ALREADY_EXISTS:
                raise

        handle = self._client.get_schedule_handle(definition.schedule_id)
        await handle.update(lambda _input: ScheduleUpdate(schedule=definition.schedule))
        return "updated"
