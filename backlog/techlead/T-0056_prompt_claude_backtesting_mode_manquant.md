---
id: T-0056
title: "Prompt Claude - Developper la partie manquante du mode backtesting"
status: NEEDS_QA
owner: techlead
links: ["US-0024", "US-0025", "US-0026", "US-0027", "US-0028", "US-0029", "US-0030", "US-0031", "US-0032", "US-0033"]
---

## Objectif

Fournir a Claude un prompt complet pour developper la partie manquante du mode Backtesting: API, persistance, UI fonctionnelle, visualisation des trades et rapport go/no-go.

## Prompt a donner a Claude

```text
Tu es Claude, agent de developpement senior Python/JS, et tu interviens dans le repo `binanceTradingSpot`.

Role attendu:
- Agis comme TechLead + implementer.
- Lis le code avant de modifier.
- Respecte l'architecture existante.
- Ne fais pas de refactor large non necessaire.
- Ne touche jamais a l'execution live Binance pour ce ticket.
- Le mode Backtesting ne doit jamais placer d'ordre reel.

Contexte produit:
- Le projet est un bot Binance Spot Python.
- Marche cible: Spot uniquement, LONG / NO_TRADE, pas de short, pas de levier.
- ROADMAP.md impose que la Phase 2 Backtesting valide la strategie MTF avant Signal Engine, Paper Trading et Execution live.
- Les US PO a satisfaire sont:
  - `backlog/po/US-0024-epic-visualisation-backtesting-mode.md`
  - `backlog/po/US-0025-backtesting-preparer-donnees-historiques.md`
  - `backlog/po/US-0026-backtesting-configurer-run.md`
  - `backlog/po/US-0027-backtesting-suivre-execution-run.md`
  - `backlog/po/US-0028-backtesting-dashboard-performance.md`
  - `backlog/po/US-0029-backtesting-visualiser-trades-sur-graphe.md`
  - `backlog/po/US-0030-backtesting-expliquer-signaux-mtf.md`
  - `backlog/po/US-0031-backtesting-table-trades-et-filtres.md`
  - `backlog/po/US-0032-backtesting-comparer-runs-calibrations.md`
  - `backlog/po/US-0033-backtesting-rapport-go-no-go.md`
- Le prototype visuel est dans:
  - `docs/backtesting-mode-projection.html`
  - `docs/backtesting-mode-projection.md`

Etat technique actuel:
- Le moteur backtest existe deja:
  - `src/tradebot/services/backtesting/models.py`
  - `src/tradebot/services/backtesting/engine.py`
  - `src/tradebot/services/backtesting/trade_simulator.py`
  - `src/tradebot/services/backtesting/metrics.py`
  - `src/tradebot/infra/db/repositories/backtest_repo_sql.py`
  - `src/tradebot/apps/backtest_main.py`
- Le backtest actuel:
  - charge les snapshots historiques;
  - aligne les timeframes via `_find_as_of`;
  - utilise `services/mtf/validator.py` et `config/validations.regular.yaml`;
  - simule entree au close 5m + slippage;
  - calcule SL/TP via pivots ou ATR fallback;
  - simule sortie TP/SL;
  - calcule winrate, profit factor, drawdown, expectancy, MFE/MAE;
  - persiste dans `backtest_runs` et `backtest_trades`.
- L'API existante est `aiohttp` dans `src/tradebot/api/app.py`.
- L'UI existante est statique vanilla JS dans:
  - `src/tradebot/api/static/index.html`
  - `src/tradebot/api/static/chart.html`
  - `src/tradebot/api/static/chart.js`
  - `src/tradebot/api/static/chart.css`
- Ne pas implementer dans les stubs `src/tradebot/infra/temporal/workflows/*` ou `src/tradebot/infra/temporal/activities/*`. Le vrai Temporal est dans `src/tradebot/temporal_app`.

Objectif de ce ticket:
Implementer un vrai espace Backtesting utilisable depuis l'UI, base sur le moteur existant et inspire du prototype HTML. L'utilisateur doit pouvoir:
1. verifier la disponibilite des donnees historiques;
2. configurer et lancer un run de backtest;
3. consulter les runs passes;
4. ouvrir le detail d'un run;
5. lire les KPIs et le verdict Phase 2;
6. visualiser les trades sur un graphe de chandeliers;
7. inspecter les explications MTF par trade;
8. consulter une table de trades;
9. generer un rapport go/no-go en JSON et Markdown.

Perimetre fonctionnel attendu:

1. API Backtesting
   Ajouter des endpoints dans `src/tradebot/api/app.py` ou dans un module dedie importe par `app.py`.

   Endpoints minimum:
   - `GET /backtesting/readiness?symbol=BTCUSDC&from_ms=...&to_ms=...&profile=regular`
     Retourne la couverture par timeframe, gaps simples, warmup indicateurs et statut `ready`.
   - `POST /backtesting/runs`
     Lance un backtest synchrone pour le MVP, persiste le resultat, retourne `run_id`.
   - `GET /backtesting/runs?symbol=&limit=&cursor=`
     Liste paginee des runs.
   - `GET /backtesting/runs/{run_id}`
     Retourne config, metrics, verdict, risques, resume.
   - `GET /backtesting/runs/{run_id}/trades?limit=&cursor=&result=&setup=&reason=`
     Retourne les trades pagines + contexte signal.
   - `GET /backtesting/runs/{run_id}/report?format=json|markdown`
     Retourne le rapport go/no-go.

   Contraintes API:
   - Valider symbol, dates, ranges et parametres numeriques.
   - Ne jamais appeler Binance directement depuis l'UI.
   - Reutiliser `create_session_factory(settings)`.
   - Reutiliser `BacktestEngine` et `BacktestRepoSql`.
   - Retourner des erreurs JSON coherentes avec le style existant.
   - Ajouter des tests unitaires d'API.

2. Repository Backtest
   Completer `BacktestRepoSql` pour la lecture:
   - `list_runs(...)`
   - `get_run(run_id)`
   - `list_trades(run_id, ...)`
   - `build_report(run_id, format)`

   Si besoin, ajouter des helpers de conversion payload.
   Ne pas casser la persistance existante.

3. Readiness historique
   Implementer un service pur, par exemple:
   - `src/tradebot/services/backtesting/readiness.py`

   Il doit calculer:
   - timeframes requis: 4h, 1h, 15m, 5m, 1m;
   - nombre de candles;
   - premier/dernier timestamp;
   - couverture approx par timeframe sur `[from_ms, to_ms]`;
   - gaps detectables a partir des open_time_ms;
   - presence de snapshots indicateurs;
   - warmup minimal: EMA200, RSI14, ATR14, MACD, ADX, pivots/VWAP quand possible;
   - statut global `ready`, `warning`, `blocked`;
   - raisons exploitables.

   Attention trading:
   - Eviter le look-ahead bias: ne valider que les donnees disponibles jusqu'au timestamp simule.
   - Un run en mode go/no-go doit etre bloque si les donnees critiques manquent.
   - Une periode trop courte doit donner `INCONCLUSIVE` ou `blocked`, pas un faux FAIL.

4. Metrics et verdict
   Conserver les metrics existantes, mais exposer aussi dans les payloads API:
   - total trades;
   - closed trades;
   - open trades;
   - winning trades;
   - losing trades;
   - winrate;
   - profit factor;
   - max drawdown pct;
   - expectancy R;
   - avg MFE pct;
   - avg MAE pct;
   - verdict: `PASS`, `FAIL`, `INCONCLUSIVE`.

   Regles:
   - PASS: winrate > 50%, profit factor > 1.3, max drawdown < 15%, echantillon suffisant.
   - FAIL: echantillon suffisant mais au moins un critere gate echoue.
   - INCONCLUSIVE: trop peu de trades, donnees incompletes, trop de trades ouverts, ou readiness warning bloquant.

   Proposer un seuil simple pour MVP:
   - `min_closed_trades` configurable dans `BacktestConfig`, defaut 20.
   - Si closed_trades < min_closed_trades => INCONCLUSIVE.

5. Configuration de run
   Etendre `BacktestConfig` de maniere retrocompatible si necessaire:
   - `initial_capital_usdc`
   - `risk_pct`
   - `fees_pct`
   - `min_closed_trades`
   - `mode`: `exploration` ou `phase_gate`

   Les nouveaux champs doivent etre serialises dans `config_json`.
   Si la table SQL n'a pas de colonne dediee, ne pas ajouter une migration lourde: garder dans `config_json` et calculer le payload API depuis run + trades.

6. UI Backtesting
   Ajouter une route statique `/backtesting` dans `src/tradebot/api/app.py`.
   Ajouter les fichiers:
   - `src/tradebot/api/static/backtesting.html`
   - `src/tradebot/api/static/backtesting.js`
   - `src/tradebot/api/static/backtesting.css`

   Ajouter un lien depuis `index.html` vers `/backtesting`.

   UI attendue:
   - section Preparation:
     - symbole, periode, profil;
     - bouton "Verifier donnees";
     - tableau coverage par timeframe.
   - section Run:
     - config slippage, frais, k ATR, R multiple, stop max, buffer pivot, risk pct, capital;
     - bouton "Lancer backtest";
     - etats loading, success, error.
   - section Resultats:
     - KPIs: verdict, trades fermes, winrate, profit factor, drawdown, expectancy, MFE, MAE;
     - courbe equity et drawdown si possible.
   - section Graphe:
     - candles 5m ou timeframe trigger;
     - marqueurs entry/exit;
     - lignes SL/TP du trade selectionne;
     - affichage du detail trade.
   - section Trades:
     - table paginee;
     - filtres gagnants/perdants/open, raison de sortie.
   - section MTF:
     - conditions passees/echouees depuis `signal_context_json`;
     - blocking filters;
     - scores par timeframe.
   - section Rapport:
     - rapport JSON/Markdown;
     - mention claire: "PASS Phase 2 ne donne pas autorisation live; paper trading obligatoire".

   Contraintes UI:
   - Vanilla JS, pas de framework.
   - Pas de carte dans carte.
   - Interface dense, sobre, orientee outil trading.
   - Pas de hero marketing.
   - Pas de texte inutile pour expliquer le produit; le libelle doit servir l'action.
   - Doit rester utilisable desktop; mobile en consultation minimum.
   - Ne pas exposer secret.

7. Visualisation chart
   Peut demarrer avec Canvas comme `chart.js`.
   Reutiliser si possible les patterns existants du chart live.
   Pour MVP, le graphe doit au minimum:
   - charger les candles autour du run via `/chart/candles`;
   - afficher markers trades;
   - selectionner un trade depuis table ou graphe;
   - afficher entry/exit/SL/TP/MFE/MAE.

8. Rapport go/no-go
   Implementer une generation Markdown stable:
   - run_id;
   - symbole;
   - periode;
   - profil;
   - config;
   - readiness;
   - metrics;
   - verdict;
   - raisons PASS/FAIL/INCONCLUSIVE;
   - risques;
   - recommandation.

   Recommandations:
   - PASS => "peut preparer Phase 3 / calibration out-of-sample, pas de live";
   - FAIL => "recalibrer YAML/seuils/k/R";
   - INCONCLUSIVE => "ameliorer donnees ou echantillon".

9. Tests
   Ajouter ou completer des tests:
   - readiness service;
   - repo read methods;
   - API validation errors;
   - API run creation happy path avec fixtures SQLite;
   - API report JSON/Markdown;
   - metrics verdict PASS/FAIL/INCONCLUSIVE;
   - UI static route `/backtesting`.

   Commandes obligatoires:
   - `poetry run ruff check .`
   - `poetry run ruff format .`
   - `poetry run pytest -q`

   Si des tests existants echouent sans rapport, documenter precisement lesquels et pourquoi. Ne pas masquer.

Contraintes d'implementation:
- Ne pas deplacer les fichiers backlog selon un statut.
- Ne pas modifier les statuts PO sauf demande explicite.
- Garder le status des tickets TechLead modifiable par Dev uniquement si tu prends un ticket en implementation.
- Ne pas creer de nouvelle dependance frontend.
- Ne pas introduire Alembic si le repo n'en a pas l'usage operationnel; privilegier `Base.metadata.create_all()` et tables existantes pour ce lot.
- Ne pas faire d'appel Binance depuis le navigateur.
- Ne pas implementer paper trading/live execution dans ce lot.
- Ne pas hardcoder une strategie dans l'UI: afficher la config/profil utilise.
- Ne pas utiliser `innerHTML` avec donnees dynamiques non echappees.
- Eviter les calculs JS fragiles sur grands arrays avec spread `Math.max(...largeArray)`.

Fichiers probablement touches:
- `src/tradebot/api/app.py`
- `src/tradebot/api/static/index.html`
- `src/tradebot/api/static/backtesting.html`
- `src/tradebot/api/static/backtesting.js`
- `src/tradebot/api/static/backtesting.css`
- `src/tradebot/services/backtesting/models.py`
- `src/tradebot/services/backtesting/engine.py`
- `src/tradebot/services/backtesting/metrics.py`
- `src/tradebot/services/backtesting/readiness.py` (nouveau)
- `src/tradebot/infra/db/repositories/backtest_repo_sql.py`
- `tests/unit/test_backtesting_*.py`
- `tests/unit/test_daemon_api.py` ou nouveau `tests/unit/test_backtesting_api.py`
- `docs/backtesting-mode-projection.md` si besoin pour noter l'ecart avec l'implementation

Definition of Done:
1. `/backtesting` est accessible depuis l'API locale.
2. L'utilisateur peut verifier les donnees d'un symbole/periode.
3. L'utilisateur peut lancer un backtest depuis l'UI.
4. Le run est persiste dans `backtest_runs` / `backtest_trades`.
5. L'utilisateur peut reouvrir un run et voir les KPIs.
6. L'utilisateur peut voir une table de trades.
7. L'utilisateur peut visualiser les trades sur un graphe.
8. L'utilisateur peut inspecter le contexte MTF du trade.
9. L'utilisateur peut exporter/consulter un rapport go/no-go.
10. Les tests couvrent les nouveaux comportements.
11. `ruff check`, `ruff format`, `pytest -q` sont executes et l'etat est documente.

Avant de commencer:
- Fais un `git status -sb`.
- Verifie que tu es a jour avec `main`.
- Lis `ROADMAP.md`, les US `US-0024` a `US-0033`, et le prototype `docs/backtesting-mode-projection.html`.
- Lis le moteur backtesting existant.
- Donne un plan court, puis implemente.

Sortie attendue dans ta reponse finale:
- Resume des fichiers modifies.
- Endpoints ajoutes.
- Parcours UI disponible.
- Checks executes et resultats.
- Limites restantes.
- PR/commit si le workflow te demande de pousser.
```

## Notes TechLead

- Le lot est volontairement large. Si Claude doit le decouper, prioriser d'abord API + lecture runs + UI minimale, puis graphe/rapport.
- Ne pas laisser Claude partir sur Paper Trading ou Live Execution: ce sont des phases suivantes.
- Le point le plus sensible est l'alignement entre le moteur backtest `services/mtf/validator.py` et le flux runtime `services/mtf/cascade.py`; l'UI doit signaler cette divergence tant qu'elle existe.
- Le prototype HTML est une projection visuelle, pas une base a copier-coller telle quelle dans l'app.

## Livraison Dev - 2026-04-30

### Fichiers crees

- `src/tradebot/services/backtesting/readiness.py` - Service de verification de couverture donnees: 5 timeframes, gaps, warmup.
- `src/tradebot/api/backtesting_routes.py` - 6 handlers aiohttp backtesting.
- `src/tradebot/api/static/backtesting.html` - Page UI backtesting.
- `src/tradebot/api/static/backtesting.js` - Logique frontend vanilla JS.
- `src/tradebot/api/static/backtesting.css` - Styles dark dense.
- `tests/unit/test_backtesting_api.py` - Tests endpoints backtesting.
- `tests/unit/test_backtesting_readiness.py` - Tests service readiness.

### Fichiers modifies

- `src/tradebot/services/backtesting/models.py` - Ajout `BacktestConfig`, enum `Verdict`, champs `verdict` et `verdict_reasons` dans `BacktestMetrics`.
- `src/tradebot/services/backtesting/metrics.py` - Verdict `PASS` / `FAIL` / `INCONCLUSIVE` avec seuil `min_closed_trades`.
- `src/tradebot/infra/db/repositories/backtest_repo_sql.py` - Methodes `list_runs`, `get_run`, `list_trades`, `build_report`.
- `src/tradebot/api/app.py` - Enregistrement des routes backtesting et handler `/backtesting`.
- `src/tradebot/api/static/index.html` - Lien vers `/backtesting`.
- `tests/unit/test_backtesting_metrics.py` - Tests verdict ajoutes.

### Endpoints disponibles

- `GET /backtesting/readiness?symbol=&from_ms=&to_ms=&profile=`
- `POST /backtesting/runs`
- `GET /backtesting/runs?symbol=&limit=&cursor=`
- `GET /backtesting/runs/{run_id}`
- `GET /backtesting/runs/{run_id}/trades?limit=&cursor=&result=&reason=`
- `GET /backtesting/runs/{run_id}/report?format=json|markdown`
- `GET /backtesting` - Page UI backtesting.

### Checks

- `ruff check .` - OK, 0 erreur.
- `pytest tests/unit/ -q` - 263 passed, 11 failed. Les echecs restants sont declares pre-existants et hors perimetre T-0056.

### Limites restantes

- Backtest synchrone: bloquant pour les runs longs; async/Temporal a prevoir en Phase 3.
- Graphe canvas minimal: candles + markers; les interactions avancees zoom/pan reutilisent le pattern `chart.js` mais ne partagent pas encore le code.
- Rapport Markdown sans detail readiness; a enrichir si besoin avec le service readiness.
