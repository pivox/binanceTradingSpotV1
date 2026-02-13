---
id: T-0016
title: "API - Exposer les donnees chandeliers/symbols/timeframes pour l'UI chart"
status: NEEDS_QA
owner: techlead
links: ["US-0001", "US-0002", "US-0003", "US-0004", "B-0008"]
---

## Contexte
Les US UI chart requièrent un accès en lecture aux chandeliers stockés en BDD `candles`, ainsi qu'aux symboles et timeframes disponibles. L'API actuelle ne sert que le contrôle du daemon et ne se connecte pas à la base.

## Perimetre
- Ajouter des endpoints REST read-only pour l'UI chart (aiohttp) :
  - `GET /chart/symbols` : liste des `symbol` présents en BDD, triés alpha.
  - `GET /chart/timeframes?symbol=` : timeframes distinctes pour un symbol (sinon toutes).
  - `GET /chart/candles?symbol=BTCUSDC&timeframe=1m&limit=500&from_open_time_ms=` : chandeliers ordonnés par `open_time_ms` asc, limite configurable.
- Intégrer une session SQLAlchemy (engine existant) avec gestion de durée de vie par requête et logs structurés des erreurs.
- Validation d'entrée (symbol, timeframe, limites) avec codes d'erreur explicites (400) et messages exploitables.
- Respect des NFR de latence (<2s pour charges standard) et empty-state clair (200 + liste vide).

## Hors perimetre
- Agrégations ou indicateurs (RSI, EMA...).
- Pagination infinie côté API (seule une fenêtre limitée est fournie).
- AuthN/RBAC spécifique aux endpoints chart (réutiliser global si activé).

## Solution
- Introduire un module `tradebot.api.chart_repository` utilisant SQLAlchemy `Session` pour :
  - `list_symbols()`, `list_timeframes(symbol|None)`, `fetch_candles(symbol, timeframe, limit, from_open_time_ms|None)`.
- Étendre `create_app` pour initialiser une `SessionLocal` via `create_session_factory(settings)` et l'injecter dans les handlers chart (context manager).
- Ajouter routes aiohttp `/chart/symbols`, `/chart/timeframes`, `/chart/candles` avec schéma de réponse homogène (`{"ok": true, "data": ...}` / `ok:false`), codes HTTP cohérents.
- Tracer les erreurs DB (time-out, invalid request) avec `structlog`, sans divulguer de secrets.
- Paramètres : `limit` borné (ex: max 1000, défaut 500), `from_open_time_ms` filtre strict `>` pour le rafraîchissement live.

## Plan d'implementation
1. Créer le repository chart (requêtes SQLAlchemy optimisées sur `candles`).
2. Étendre les settings si besoin pour `chart_max_limit` (valeur par défaut fixée si non exposée).
3. Brancher la session factory dans `create_app` + middleware helper pour fournir la session aux handlers.
4. Implémenter les 3 handlers chart avec validation et réponses JSON standardisées.
5. Journaliser erreurs/latences et ajouter tests d'intégration API (fixtures DB).

## Tests
- Tests unitaires sur le repository (filtre `from_open_time_ms`, limit, tri ascendant).
- Tests d'intégration aiohttp pour chaque endpoint (200 empty, 400 sur params manquants/invalides, 404 si symbol absent?).
- Mesure de temps de réponse sur dataset de test (~500 lignes) pour vérifier <2s.

## Criteres d'acceptation
- Les 3 endpoints répondent en <2s avec 500 chandeliers sur environnement local de test.
- `GET /chart/candles` ne retourne que les champs nécessaires (`open, high, low, close, open_time_ms, close_time_ms, volume, is_partial`).
- Pas d'appel Binance côté API; seules les données BDD sont utilisées.
- Erreurs et empty-states renvoient des messages explicites sans crash serveur.

## Definition of Done
- Code merge avec tests verts (`pytest -q`) et lint (`ruff check .`).
- Documentation minimale des endpoints (README ou `/docs/chart-api.md`) et paramètres supportés.
- Logs visibles pour erreurs DB et latences anormales.
