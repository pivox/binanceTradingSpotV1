from __future__ import annotations

from pathlib import Path

import yaml


def test_openapi_indicators_contract_file_is_valid_yaml() -> None:
    path = Path("docs/openapi-indicators.yaml")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))

    assert payload["openapi"] == "3.1.0"
    assert "/indicators/latest" in payload["paths"]
    assert "/indicators/history" in payload["paths"]
