# CLAUDE.md — binanceTradingSpot

## Présentation du projet

Bot de trading spot Binance avec exécution live et backtesting. Architecture orientée événements : un daemon WebSocket collecte les klines en temps réel, Temporal.io orchestre le backfill et les activités métier, et une API aiohttp expose les données au frontend chart.

---

## Stack technique

| Couche | Technologie |
|--------|-------------|
| Langage | Python 3.11, poetry |
| ORM / DB | SQLAlchemy 2.0, PostgreSQL 15 (psycopg3) |
| Orchestration | Temporal.io (auto-setup Docker) |
| API web | aiohttp |
| Frontend chart | Canvas JS vanilla (chart.js custom) |
| Observabilité | structlog, prometheus-client |
| Linting / typage | ruff, mypy |
| Tests | pytest |

---

## Infrastructure Docker

```
docker-compose.yml
  postgres          → port 5433  (tradebot DB, user/pass)
  temporal-postgres → port 5434  (temporal DB interne)
  temporal          → port 7234  (gRPC Temporal server)
  temporal-ui       → port 8080  (UI Temporal)
```

Démarrage complet : `make start` (lance `scripts/start.sh`).
Arrêt : `make stop`.

---

## Processus / entrypoints

| Commande make | Module Python | Rôle |
|---------------|---------------|------|
| `make daemon` | `ws_candle_daemon.py` | WebSocket Binance → klines 1m → DB, agrège 5m/15m/1h/4h via `MultiTfAggregator` |
| `make worker` | `tradebot.apps.temporal_worker_main` | Worker Temporal (activities + workflows) |
| `make api` | `tradebot.apps.daemon_api_main` | API aiohttp sur port 8000 |
| `make user-stream` | `tradebot.apps.user_stream_main` | WebSocket user stream Binance (ordres, balances) |

---

## Structure des sources

```
src/tradebot/
├── api/
│   ├── app.py                  # Tous les handlers aiohttp + routing
│   ├── chart_repository.py     # Requêtes DB pour le chart (candles)
│   ├── indicator_repository.py # Requêtes DB pour les indicateurs
│   └── static/                 # Frontend : chart.html, chart.js, chart.css
├── apps/                       # Entrypoints des processus
├── config/settings.py          # Settings pydantic-settings (.env)
├── daemon/control.py           # DaemonController (start/stop ws_candle_daemon)
├── domain/models/              # Dataclasses métier (Candle, Order, …)
├── infra/
│   ├── binance/                # REST client, WS market, WS user
│   └── db/
│       ├── models.py           # SQLAlchemy ORM (Candle, CandleGapRequest, IndicatorSnapshot, …)
│       ├── engine.py           # create_session_factory
│       └── repositories/       # BackfillRepoSql, …
├── observability/              # Logging structlog + métriques Prometheus
├── ports/                      # Interfaces abstraites
├── services/
│   ├── indicators/             # Calcul RSI, ATR, EMA, Bollinger, MACD, …
│   ├── mtf/                    # MultiTfAggregator (1m → 5m/15m/1h/4h)
│   └── strategy/               # Logique de stratégie
└── temporal_app/
    ├── activities.py           # Toutes les activities Temporal (reconcile_klines, backfill, indicators, …)
    ├── workflows.py            # Workflows Temporal
    └── types.py                # Types partagés Temporal
```

---

## Base de données — tables clés

| Table | Clé primaire | Description |
|-------|-------------|-------------|
| `candles` | `(symbol, timeframe, open_time_ms)` | Klines OHLCV, `is_partial` pour la bougie courante |
| `candle_gap_request` | `id` (autoincrement) | Demandes de backfill détectées par le frontend ou le worker |
| `indicator_snapshots` | `(symbol, timeframe, close_time_ms)` | Snapshots JSON des indicateurs calculés |

`CandleGapRequest` n'a **pas** de champ `timeframe` : le worker backfille tous les TF (`1m`, `5m`, `15m`, `1h`, `4h`) directement depuis Binance REST pour chaque gap request. `SUPPORTED_GAP_REQUEST_TIMEFRAMES` est un alias de `DETECT_RECONCILE_TIMEFRAMES`.

---

## API chart — endpoints

Toutes les réponses : `{"ok": true, "data": ...}` ou `{"ok": false, "error": {...}}`.

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/chart/symbols` | Liste des symboles distincts en DB |
| GET | `/chart/timeframes?symbol=X` | Liste des timeframes disponibles |
| GET | `/chart/candles` | Klines (voir params ci-dessous) |
| POST | `/chart/gap-request` | Signaler un trou → Temporal backfille |
| GET | `/indicators/latest?symbol=X&timeframe=Y` | Dernier snapshot d'indicateurs |
| GET | `/indicators/history` | Historique des snapshots |

### `GET /chart/candles` — paramètres

| Param | Obligatoire | Description |
|-------|-------------|-------------|
| `symbol` | oui | `^[A-Z0-9]{2,20}$` |
| `timeframe` | oui | `^[1-9][0-9]*[mhdwM]$` |
| `limit` | non | défaut 500, max 1000 |
| `from_open_time_ms` | non | Incrémental live : retourne les klines `> valeur` |
| `before_open_time_ms` | non | Scroll historique : retourne les klines `< valeur` |

`from_open_time_ms` et `before_open_time_ms` sont mutuellement exclusifs (`from` a priorité si les deux sont fournis).

### `POST /chart/gap-request` — body JSON

```json
{ "symbol": "BTCUSDC", "from_open_time_ms": 1700000000000, "to_open_time_ms": 1700003600000 }
```

---

## Frontend chart (`chart.js`)

### Architecture

- **`CandleCanvasChart`** : rendu canvas custom (pas de lib externe). Gère viewport (`viewStart`, `viewCount`), zoom molette, pan souris.
- **`state`** : objet central qui contient `candles` (fenêtre récente, max 500), `olderCandles` (historique chargé via scroll), `symbol`, `timeframe`, indicateurs, etc.
- **`getChartData()`** : retourne `[...state.olderCandles, ...state.candles]` — toujours utiliser cette fonction pour passer des données au chart, jamais `state.candles` directement.

### Flux de données

1. **Chargement initial** : `fetchCandles()` → dernières 500 bougies.
2. **Live polling** : `runLiveTick()` toutes les N ms (adaptatif au timeframe) avec `from_open_time_ms` pour ne récupérer que les nouvelles bougies. Merge via `mergeCandles()`.
3. **Scroll historique** : `loadOlderCandles()` déclenché quand `chart.viewStart === 0` (callback `chart.onLeftEdge`). Charge avec `before_open_time_ms`, prépend dans `state.olderCandles`, ajuste `chart.viewStart += older.length` pour éviter le saut visuel.
4. **Détection de gaps** : `detectGaps()` analyse les intervalles entre bougies consécutives (seuil : > 1.5× l'intervalle du timeframe). `reportGapsIfNeeded()` envoie un `POST /chart/gap-request` pour chaque trou. Déclenché au chargement initial, changement de pair/timeframe et chargement historique.

### Reset état historique

`resetHistoricalState()` doit être appelé à chaque changement de symbol/timeframe (fait dans `loadAndRenderCandles`) et lors d'un full reload live (`fullReloadCurrentSelectionWithoutOverlay`).

---

## Temporal — activités clés

| Activité | Description |
|----------|-------------|
| `reconcile_klines` | Détecte les gaps en DB + consomme `CandleGapRequest` → backfille via REST Binance |
| `detect_kline_leading_gaps` | Détecte les données manquantes au "leading edge" (bord droit) |
| `ensure_indicator_warmup` | Garantit 200+ bougies pour les indicateurs (EMA200) |
| `fetch_historical_klines` | Backfill arbitraire par plage de dates (backtesting) |
| `compute_indicator_snapshot` | Calcule et persiste le snapshot JSON des indicateurs |

---

## Configuration (`.env`)

Variables clés :

```env
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5433/tradebot
TEMPORAL_ADDRESS=localhost:7233
BINANCE_API_KEY=...
BINANCE_API_SECRET=...
EXECUTION_MODE=backtesting          # ou live
LIVE_TRADING_APPROVED=false
SHARD_COUNT=8
API_HOST=0.0.0.0
API_PORT=8000
```

---

## Commandes de développement

```bash
make start          # Lance toute la stack (infra + processus)
make stop           # Arrête tout
make infra-up       # Docker uniquement (postgres + temporal)
make api            # Lance seulement l'API
make worker         # Lance seulement le worker Temporal
make daemon         # Lance seulement le daemon WebSocket
make logs           # tail -f logs/daemon.log worker.log api.log

poetry run pytest tests/unit/          # Tests unitaires
poetry run pytest tests/integration/   # Tests d'intégration (nécessite DB)
poetry run ruff check src/             # Linting
poetry run mypy src/                   # Typage statique
```

---

## Conventions de code

- **Pas de commentaires sauf si le WHY est non-évident.**
- Toutes les réponses API suivent `{"ok": true/false, "data"/"error": ...}`.
- Les klines sont **immutables par PK** `(symbol, timeframe, open_time_ms)` — upsert via `ON CONFLICT DO UPDATE`.
- `is_partial=True` sur la bougie courante ouverte — exclue des calculs d'indicateurs.
- Le sharding des symboles se fait par CRC32 (`stable_shard_of(symbol, shard_count)`).
- Les modes d'exécution sont `"live"` et `"backtesting"` (alias `"dry_run"` accepté en entrée).
- Les tests d'intégration touchent une vraie DB (pas de mock DB — risque de divergence prod).

---

## Modes d'exécution

| Mode | Comportement |
|------|-------------|
| `backtesting` | Ordres simulés (fill immédiat), pas de WebSocket live |
| `live` | Ordres réels via Binance REST, WebSocket actif, `LIVE_TRADING_APPROVED=true` requis |

Le frontend chart est **identique** dans les deux modes (polling sur les mêmes endpoints).
