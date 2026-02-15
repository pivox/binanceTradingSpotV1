from __future__ import annotations

import os
from pathlib import Path

APP_CONFIG_PATH_ENV = "APP_CONFIG_PATH"
DEFAULT_APP_CONFIG_PATH = "config/app.yaml"


def get_app_config_path() -> Path:
    return Path(os.getenv(APP_CONFIG_PATH_ENV, DEFAULT_APP_CONFIG_PATH))
