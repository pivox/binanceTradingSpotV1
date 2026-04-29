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

## Indicateurs calculés

Calculés à chaque bougie fermée via `build_indicator_snapshot()`, persistés dans `indicator_snapshots` :

| Indicateur | Paramètres |
|------------|-----------|
| RSI | période 14 |
| ATR | période 14, Wilder smoothing |
| EMA | 20, 50, 200 |
| SMA | 9, 21 |
| MACD | fast 12 / slow 26 / signal 9 |
| Bollinger Bands | période 20, ±2σ |
| ADX | période 14 |
| VWAP | journalier, reset UTC midnight |
| Stochastic RSI | RSI 14, stoch 14, K 3, D 3 |
| Pivot Points | PP, R1/R2/R3, S1/S2/S3 (session précédente) |

---

## Roadmap

### État actuel (déjà implémenté)

| Couche | Statut |
|--------|--------|
| WebSocket Binance → klines 1m | ✅ |
| Agrégation multi-timeframe (1m → 5m/15m/1h/4h) | ✅ |
| Stockage PostgreSQL | ✅ |
| Reconciliation / backfill via Temporal | ✅ |
| Calcul indicateurs (RSI, ATR, EMA, MACD, Bollinger, ADX, VWAP) | ✅ |
| API aiohttp (candles, indicateurs) | ✅ |
| Frontend chart canvas (zoom, pan, scroll historique, gaps) | ✅ |

### Clarifications de périmètre

- **Marché cible : Binance Spot uniquement.** Pas de short-selling — signaux `LONG` et `NO_TRADE` uniquement.
- **Temporal n'est pas adapté au temps réel strict.** Il reste l'orchestrateur pour le backfill, les calculs batch et la réconciliation. Le Trade Manager tournera dans une boucle async dédiée, hors workflow Temporal.
- **Aucun ordre réel avant validation sur données historiques.** Le pipeline backtesting + paper trading est obligatoire avant l'Execution Engine live.

### Phase 1b — MTF Validator

**Objectif** : transformer les snapshots d'indicateurs multi-timeframes en un signal structuré et scoré.

**Architecture** : fonction pure `validate(snapshots: dict[Timeframe, IndicatorSnapshot]) -> MTFSignal`. Pas d'accès DB direct — testable unitairement sans infrastructure.

**Profil de base : `regular`** :

```
Contexte : 4h → 1h → 15m
Déclencheur : 5m (condition binaire)
```

Conditions par timeframe (déclarées en YAML) :

```yaml
'4h':
    long:
        all_of:
            - ema20_above_ema50
            - ema50_above_ema200
            - rsi_between_45_70
            - macd_hist_positive

'1h':
    long:
        all_of:
            - price_above_ema20
            - adx_gt_25
            - macd_hist_positive_or_rising

'15m':
    long:
        all_of:
            - rsi_between_40_60
            - price_near_ema20
            - atr_contracting

'5m':                                # déclencheur binaire (ne participe pas au score)
    long:
        any_of:
            - macd_hist_turning_positive
            - close_above_recent_high_n
```

Filtres bloquants : RSI 4h > 75, prix 4h > EMA20 + 2×ATR, ADX 1h < 20, MACD 1h histogram négatif ET en baisse.

Scoring : `score_4h` (max 40) + `score_1h` (max 30) + `score_15m` (max 30) = 100 pts. Signal valide si `score >= seuil AND trigger_5m AND aucun filtre bloquant`.

**Sortie** : `MTFSignal { trend_4h, trend_1h, structure_15m, trigger_5m, score, valid, context_json }`

### Phase 2 — Backtesting pipeline

Rejouer le MTF Validator sur l'historique des snapshots en base. Simuler les entrées au close de la bougie 5m de déclenchement + slippage 0.05%. Stop-loss : niveau pivot VWAP + 0.3% buffer, max 2% ; fallback ATR × k (k entre 2 et 4). Take-profit : TP = entry + (distance_SL × r_multiple), départ 1.5.

**Critères de passage à la Phase 3** : winrate > 50%, profit factor > 1.3, max drawdown < 15%.

### Phase 3 — Signal Engine

Si `mtf.valid && mtf.score > seuil_validé_phase2` → signal `LONG`, sinon `NO_TRADE`. Persisté en base + exposé via `GET /signal/latest?symbol=X`.

### Phase 4 — Risk Engine

```
distance_sl  = max(pivot_distance + 0.3%, atr × k)
qty          = (capital × risk_pct) / distance_sl_abs
```

Daily loss cap, entry zone (center = VWAP ou EMA20, TTL 180s). **Sortie** : `OrderPlan { symbol, side, qty, entry_zone, entry_price, stop_loss, take_profit }`.

### Phase 5 — Paper trading

Signaux en temps réel, fill simulé (close bougie 5m suivante + slippage 0.05%), P&L tracé trade par trade. Durée minimale 2–4 semaines. Mêmes critères de passage que Phase 2.

### Phase 6 — Execution Engine

LIMIT maker dans l'entry zone, fallback MARKET après TTL (180s), OCO stop-loss + take-profit. Capital limité à 10% du capital total au démarrage.

### Phase 7 — Trade Manager

Boucle async dédiée (hors Temporal). Trailing stop ATR / Chandelier Exit, TP partiel à 2R (60%), time-stop, invalidation dynamique sur retournement MACD/RSI 15m.

### Phase 8 — Analytics + feedback loop

Vue PostgreSQL `position_trade_analysis`, métriques (winrate, profit factor, max drawdown, expectancy, MFE/MAE), `GET /analytics/summary`, tableau de bord frontend.

### Séquençage

```
Phase 1b – MTF Validator
    ↓
Phase 2  – Backtesting pipeline        ← go/no-go obligatoire
    ↓ (si métriques OK)
Phase 3  – Signal Engine
Phase 4  – Risk Engine                 ← en parallèle de Phase 3
    ↓
Phase 5  – Paper trading               ← go/no-go obligatoire avant live
    ↓ (si métriques OK)
Phase 6  – Execution Engine
    ↓
Phase 7  – Trade Manager
    ↓
Phase 8  – Analytics + feedback loop
```

### Contraintes techniques

- Toute activité batch ou réconciliation passe par **Temporal** ; le Trade Manager est une boucle async hors Temporal
- Pas d'ordre réel sans `LIVE_TRADING_APPROVED=true` en `.env`
- Pas de mock DB dans les tests — intégration sur vraie base uniquement
- Chaque signal, order plan, ordre et trade est persisté en base pour audit complet
- Les conditions YAML sont la source de vérité de la stratégie — pas de logique hardcodée dans le code
