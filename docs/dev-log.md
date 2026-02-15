# Dev log

## 2026-02-15 — PR follow-up fixes for symbol overlay metrics

### Commands run

1) `node --check src/tradebot/api/static/chart.js`

Output:

```text
(no output; exit code 0)
```

2) `pytest tests/unit/test_chart_api.py`

Output:

```text
ERROR tests/unit/test_chart_api.py
ModuleNotFoundError: No module named 'async_timeout'
```

3) `python - <<'PY' ... requests.get('https://developer.mozilla.org/en-US/docs/Web/API/AbortController') ... PY`

Output:

```text
requests.exceptions.ProxyError: HTTPSConnectionPool(host='developer.mozilla.org', port=443): Max retries exceeded ... Tunnel connection failed: 403 Forbidden
```

4) `poetry run python -m tradebot.apps.daemon_api_main > /tmp/tradebot_api.log 2>&1 &`

Output:

```text
Process became defunct immediately; no server log output produced.
```
