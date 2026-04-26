from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from temporalio.client import ScheduleAlreadyRunningError, ScheduleUpdate
from temporalio.service import RPCError, RPCStatusCode

from tradebot.config.loader import load_app_config
from tradebot.infra.temporal.schedules import (
    MANAGE_POSITIONS_SCHEDULE_PREFIX,
    PROCESS_CANDLES_SCHEDULE_PREFIX,
    RECONCILE_KLINES_SCHEDULE_ID,
    RECONCILE_ORDERS_SCHEDULE_ID,
    REFRESH_EXCHANGEINFO_SCHEDULE_ID,
    ScheduleBootstrap,
    _build_schedule_definitions,
)


class _FakeScheduleHandle:
    def __init__(self) -> None:
        self.updates: list[ScheduleUpdate] = []

    async def update(self, updater):
        update = updater(object())
        self.updates.append(update)


class _FakeScheduleClient:
    def __init__(
        self,
        *,
        existing_schedule_ids: set[str] | None = None,
        already_running_schedule_ids: set[str] | None = None,
    ) -> None:
        self._existing_schedule_ids = set(existing_schedule_ids or set())
        self._already_running_schedule_ids = set(already_running_schedule_ids or set())
        self.created_ids: list[str] = []
        self.handles: dict[str, _FakeScheduleHandle] = {}

    async def create_schedule(self, id: str, schedule) -> None:
        del schedule
        self.created_ids.append(id)
        if id in self._already_running_schedule_ids:
            raise ScheduleAlreadyRunningError()
        if id in self._existing_schedule_ids:
            raise RPCError("already exists", RPCStatusCode.ALREADY_EXISTS, b"")

    def get_schedule_handle(self, id: str) -> _FakeScheduleHandle:
        return self.handles.setdefault(id, _FakeScheduleHandle())


def _app_config():
    return load_app_config(Path("config/app.yaml"))


def test_build_schedule_definitions_uses_expected_intervals_and_cron():
    cfg = _app_config()
    defs = _build_schedule_definitions(cfg, task_queue="tradebot")
    by_id = {item.schedule_id: item for item in defs}

    shard_count = cfg.sharding.shard_count  # 8
    expected_ids = {
        RECONCILE_KLINES_SCHEDULE_ID,
        RECONCILE_ORDERS_SCHEDULE_ID,
        REFRESH_EXCHANGEINFO_SCHEDULE_ID,
        *[f"{PROCESS_CANDLES_SCHEDULE_PREFIX}-{i}" for i in range(shard_count)],
        *[f"{MANAGE_POSITIONS_SCHEDULE_PREFIX}-{i}" for i in range(shard_count)],
    }
    assert set(by_id) == expected_ids

    # Maintenance schedules
    assert by_id[RECONCILE_KLINES_SCHEDULE_ID].schedule.spec.intervals[0].every == timedelta(minutes=30)
    assert by_id[RECONCILE_ORDERS_SCHEDULE_ID].schedule.spec.intervals[0].every == timedelta(minutes=10)
    assert by_id[REFRESH_EXCHANGEINFO_SCHEDULE_ID].schedule.spec.cron_expressions == ["10 3 * * *"]

    # Per-shard schedules — verify tick intervals match config
    candles_tick = timedelta(seconds=cfg.schedules.candles_tick_sec)
    positions_tick = timedelta(seconds=cfg.schedules.positions_tick_sec)
    for i in range(shard_count):
        assert by_id[f"{PROCESS_CANDLES_SCHEDULE_PREFIX}-{i}"].schedule.spec.intervals[0].every == candles_tick
        assert by_id[f"{MANAGE_POSITIONS_SCHEDULE_PREFIX}-{i}"].schedule.spec.intervals[0].every == positions_tick


def test_build_schedule_definitions_rejects_invalid_daily_format():
    config = _app_config()
    bad_config = replace(
        config,
        schedules=replace(config.schedules, exchangeinfo_daily="3:10"),
    )

    with pytest.raises(ValueError, match="exchangeinfo_daily"):
        _build_schedule_definitions(bad_config, task_queue="tradebot")


def test_schedule_bootstrap_is_idempotent_with_existing_schedules():
    cfg = _app_config()
    total = 3 + cfg.sharding.shard_count * 2  # 3 maintenance + 2 per shard
    client = _FakeScheduleClient(existing_schedule_ids={RECONCILE_ORDERS_SCHEDULE_ID})

    async def _case():
        bootstrap = ScheduleBootstrap(client, task_queue="tradebot")
        result = await bootstrap.bootstrap(cfg)
        assert result == {"created": total - 1, "updated": 1, "total": total}
        assert len(client.created_ids) == total
        assert RECONCILE_ORDERS_SCHEDULE_ID in client.handles
        assert len(client.handles[RECONCILE_ORDERS_SCHEDULE_ID].updates) == 1
        assert isinstance(
            client.handles[RECONCILE_ORDERS_SCHEDULE_ID].updates[0], ScheduleUpdate
        )

    asyncio.run(_case())


def test_schedule_bootstrap_handles_schedule_already_running_error():
    cfg = _app_config()
    total = 3 + cfg.sharding.shard_count * 2
    client = _FakeScheduleClient(
        already_running_schedule_ids={RECONCILE_KLINES_SCHEDULE_ID}
    )

    async def _case():
        bootstrap = ScheduleBootstrap(client, task_queue="tradebot")
        result = await bootstrap.bootstrap(cfg)
        assert result == {"created": total - 1, "updated": 1, "total": total}
        assert RECONCILE_KLINES_SCHEDULE_ID in client.handles
        assert len(client.handles[RECONCILE_KLINES_SCHEDULE_ID].updates) == 1

    asyncio.run(_case())
