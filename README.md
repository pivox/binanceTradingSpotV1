# Tradebot

Scaffold for a Binance spot trading bot with multi-timeframe cascade validation.

This repo is a starting point only. Implementations are placeholders.

## Quick start

1. Install deps
   - `poetry install`
2. Copy env
   - `cp .env.example .env`
3. Fill in credentials and config
   - If you use `docker-compose` Postgres service, keep `DATABASE_URL` on port `5433`

## Layout

- `config/` runtime config and symbols list
- `src/tradebot/` source code
- `tests/` tests
- `docker/` container scaffolding

## Daemon API

Run the control API:

```bash
poetry run python -m tradebot.apps.daemon_api_main
```

Endpoints:

- `GET /daemon/status`
- `POST /daemon/start`
- `POST /daemon/stop`
- `GET /chart/symbols`
- `GET /chart/timeframes?symbol=BTCUSDC`
- `GET /chart/candles?symbol=BTCUSDC&timeframe=1m&limit=500&from_open_time_ms=0`

RBAC (optional):

- Enable with `RBAC_ENABLED=true`
- Identify user with header `X-User` (override via `RBAC_USER_HEADER`)
- Configure allowlists with `RBAC_ADMIN_USERS` and `RBAC_OPERATOR_USERS`

UI:

- Open `http://API_HOST:API_PORT/` for the control panel
- Open `http://API_HOST:API_PORT/chart` for the candles chart page

Chart API docs:

- `docs/chart-api.md`

USDC collection:

- Uses Binance 24h ticker field `quoteVolume` to sort pairs
- Limit with `USDC_PAIRS_LIMIT`

Documents a voir:

- `https://testnet.binance.vision/`
