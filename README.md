# Tradebot

Bot de trading spot Binance avec exécution live et backtesting. Architecture orientée événements : un daemon WebSocket collecte les klines en temps réel, Temporal.io orchestre le backfill et les activités métier, et une API aiohttp expose les données au frontend chart.

## Quick start

1. Install deps
   - `poetry install`
2. Copy env
   - `cp .env.example .env`
3. Fill in credentials and config
   - If you use `docker-compose` Postgres service, keep `DATABASE_URL` on port `5433`
4. Start full stack
   - `make start`

## Layout

- `config/` runtime config and symbols list
- `src/tradebot/` source code
- `tests/` tests
- `docker/` container scaffolding

## Stack technique

| Couche | Technologie |
|--------|-------------|
| Langage | Python 3.11, poetry |
| ORM / DB | SQLAlchemy 2.0, PostgreSQL 15 (psycopg3) |
| Orchestration | Temporal.io (auto-setup Docker) |
| API web | aiohttp |
| Frontend chart | Canvas JS vanilla |
| Observabilité | structlog, prometheus-client |
| Linting / typage | ruff, mypy |
| Tests | pytest |

## Infrastructure Docker

```
docker-compose.yml
  postgres          → port 5433  (tradebot DB, user/pass)
  temporal-postgres → port 5434  (temporal DB interne)
  temporal          → port 7234  (gRPC Temporal server)
  temporal-ui       → port 8080  (UI Temporal)
```

Démarrage complet : `make start`. Arrêt : `make stop`.

## Processus

| Commande make | Rôle |
|---------------|------|
| `make daemon` | WebSocket Binance → klines 1m → DB, agrège 5m/15m/1h/4h |
| `make worker` | Worker Temporal (activities + workflows) |
| `make api` | API aiohttp sur port 8000 |
| `make user-stream` | WebSocket user stream Binance (ordres, balances) |

## Daemon API

Endpoints :

- `GET /daemon/status`
- `GET /daemon/permissions`
- `POST /daemon/start`
- `POST /daemon/stop`
- `GET /daemon/mode`
- `POST /daemon/mode` (payload `{ "mode": "backtesting" | "live" }`)
- `GET /chart/symbols`
- `GET /chart/timeframes?symbol=BTCUSDC`
- `GET /chart/candles?symbol=BTCUSDC&timeframe=1m&limit=500&from_open_time_ms=0`
- `GET /indicators/latest?symbol=BTCUSDC&timeframe=1h`
- `GET /indicators/history?symbol=BTCUSDC&timeframe=1h`

RBAC (optional) :

- Enable with `RBAC_ENABLED=true`
- Identify user with header `X-User` (override via `RBAC_USER_HEADER`)
- Configure allowlists with `RBAC_ADMIN_USERS` and `RBAC_OPERATOR_USERS`

Logging :

- `LOG_LEVEL` for global default level (`DEBUG|INFO|WARNING|ERROR|CRITICAL`)
- `API_LOG_LEVEL` optional override for daemon API process
- `DAEMON_LOG_LEVEL` optional override for websocket daemon process

UI :

- `http://API_HOST:API_PORT/` — panneau de contrôle (daemon status, switch live/backtesting)
- `http://API_HOST:API_PORT/chart` — chart des klines

## Indicateurs calculés (Phase 1a ✅)

Calculés à chaque bougie fermée via `build_indicator_snapshot()`, persistés dans `indicator_snapshots` :

| Indicateur | Paramètres | Statut |
|------------|-----------|--------|
| RSI | période 14 | ✅ |
| ATR | période 14, Wilder smoothing | ✅ |
| EMA | 20, 50, 200 | ✅ |
| SMA | 9, 21 | ✅ |
| MACD | fast 12 / slow 26 / signal 9 | ✅ |
| Bollinger Bands | période 20, ±2σ | ✅ |
| ADX | période 14 | ✅ |
| VWAP | journalier, reset UTC midnight | ✅ |
| Stochastic RSI | RSI 14, stoch 14, K 3, D 3 | ✅ |
| Pivot Points | PP, R1/R2/R3, S1/S2/S3 (session précédente) | ✅ |

See [ROADMAP.md](ROADMAP.md) for upcoming phases.
