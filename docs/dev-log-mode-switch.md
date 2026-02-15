# Dev log - switch live/backtesting

## Commands run

### 1) Unit tests (targeted)

```bash
poetry run pytest tests/unit/test_execution_mode.py tests/unit/test_daemon_api.py -q
```

Output:

```text
ERROR tests/unit/test_execution_mode.py - ModuleNotFoundError: No module named 'tradebot'
ERROR tests/unit/test_daemon_api.py - ModuleNotFoundError: No module named 'async_timeout'
```

### 2) Syntax checks on changed Python files

```bash
python -m py_compile src/tradebot/api/app.py src/tradebot/config/settings.py src/tradebot/temporal_app/activities.py tests/unit/test_execution_mode.py tests/unit/test_daemon_api.py
```

Output:

```text
(no output; exit code 0)
```

### 3) Regression check for `/daemon/mode` payload validation

```bash
PYTHONPATH=src pytest tests/unit/test_daemon_api.py -q
```

Output:

```text
ERROR tests/unit/test_daemon_api.py - ModuleNotFoundError: No module named 'async_timeout'
```

### 4) Syntax check after `/daemon/mode` handler hardening

```bash
python -m py_compile src/tradebot/api/app.py tests/unit/test_daemon_api.py
```

Output:

```text
(no output; exit code 0)
```
