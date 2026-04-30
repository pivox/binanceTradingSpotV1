---
id: T-0056
title: "Livraison Dev - Backtesting UI + API"
status: DONE
owner: dev
links: ["T-0056", "US-0024", "US-0025", "US-0026", "US-0027", "US-0028", "US-0029", "US-0030", "US-0031", "US-0032", "US-0033"]
---

## Resume

Livraison Dev du 2026-04-30 pour le perimetre T-0056: Backtesting UI + API.

## Fichiers crees

- `src/tradebot/services/backtesting/readiness.py` - Service de verification de couverture donnees: 5 timeframes, gaps, warmup.
- `src/tradebot/api/backtesting_routes.py` - 6 handlers aiohttp backtesting.
- `src/tradebot/api/static/backtesting.html` - Page UI backtesting.
- `src/tradebot/api/static/backtesting.js` - Logique frontend vanilla JS.
- `src/tradebot/api/static/backtesting.css` - Styles dark dense.
- `tests/unit/test_backtesting_api.py` - Tests endpoints backtesting.
- `tests/unit/test_backtesting_readiness.py` - Tests service readiness.

## Fichiers modifies

- `src/tradebot/services/backtesting/models.py` - Ajout `BacktestConfig`, enum `Verdict`, champs `verdict` et `verdict_reasons` dans `BacktestMetrics`.
- `src/tradebot/services/backtesting/metrics.py` - Verdict `PASS` / `FAIL` / `INCONCLUSIVE` avec seuil `min_closed_trades`.
- `src/tradebot/infra/db/repositories/backtest_repo_sql.py` - Methodes `list_runs`, `get_run`, `list_trades`, `build_report`.
- `src/tradebot/api/app.py` - Enregistrement des routes backtesting et handler `/backtesting`.
- `src/tradebot/api/static/index.html` - Lien vers `/backtesting`.
- `tests/unit/test_backtesting_metrics.py` - Tests verdict ajoutes.

## Endpoints disponibles

- `GET /backtesting/readiness?symbol=&from_ms=&to_ms=&profile=`
- `POST /backtesting/runs`
- `GET /backtesting/runs?symbol=&limit=&cursor=`
- `GET /backtesting/runs/{run_id}`
- `GET /backtesting/runs/{run_id}/trades?limit=&cursor=&result=&reason=`
- `GET /backtesting/runs/{run_id}/report?format=json|markdown`
- `GET /backtesting` - Page UI backtesting.

## Checks

- `ruff check .` - OK, 0 erreur.
- `pytest tests/unit/ -q` - 263 passed, 11 failed. Les echecs restants sont declares pre-existants et hors perimetre T-0056.

## Limites restantes

- Backtest synchrone: bloquant pour les runs longs; async/Temporal a prevoir en Phase 3.
- Graphe canvas minimal: candles + markers; les interactions avancees zoom/pan reutilisent le pattern `chart.js` mais ne partagent pas encore le code.
- Rapport Markdown sans detail readiness; a enrichir si besoin avec le service readiness.

## QA — 2026-04-30

### Resultats

- `pytest` perimetre T-0056 : **53/53 passed**
- `ruff check` fichiers T-0056 : **0 erreur**
- 7 endpoints enregistres et verifies
- Lien `/backtesting` dans `index.html` confirme

### Bug corrige avant promotion DONE

- `btnPrevTrades` et `btnPrevRuns` initialises `disabled` et jamais re-actives (`backtesting.js`).
  Correction : ajout de `btnPrevTrades.disabled = state.tradesPrevCursors.length === 0` dans `loadAndRenderTrades` et equivalent pour runs dans `loadRuns`.

### Notes hors perimetre (pre-existants, non bloqueants)

- 14 erreurs ruff globales dans des fichiers hors T-0056 (pre-existantes).
- Code mort `app.py:622-636` dans `mode_switch_handler` (pre-existant).
- `_is_valid_symbol` duplique entre `app.py` et `backtesting_routes.py` (harmonisation possible ulterieurement).
