from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from temporalio.client import Client

from tradebot.apps.temporal_worker_main import TASK_QUEUE
from tradebot.config.loader import load_app_config
from tradebot.config.settings import Settings
from tradebot.infra.temporal.schedules import ScheduleBootstrap


def _config_path() -> Path:
    return Path(os.getenv("APP_CONFIG_PATH", "config/app.yaml"))


async def run_bootstrap() -> None:
    settings = Settings()
    app_config = load_app_config(_config_path())
    client = await Client.connect(settings.temporal_address)
    result = await ScheduleBootstrap(client, task_queue=TASK_QUEUE).bootstrap(app_config)
    logging.getLogger(__name__).info(
        "Temporal schedules bootstrapped",
        extra={
            "address": settings.temporal_address,
            "task_queue": TASK_QUEUE,
            **result,
        },
    )


def main() -> None:
    asyncio.run(run_bootstrap())


if __name__ == "__main__":
    main()
