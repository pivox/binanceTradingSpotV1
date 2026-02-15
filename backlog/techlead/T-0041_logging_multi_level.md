---
id: T-0041
title: "Logging multi-level configurable (global + API + daemon)"
status: NEEDS_QA
owner: dev
links: ["T-0025", "T-0035"]
---

## Objectif
Permettre un controle fin du niveau de logs par composant sans changer le code:
- niveau global
- override API
- override daemon websocket

## Implementations
1. `src/tradebot/config/settings.py`
- Ajout des variables:
  - `log_level` (defaut `INFO`)
  - `api_log_level` (override optionnel)
  - `daemon_log_level` (override optionnel)

2. `src/tradebot/observability/logging.py`
- Ajout de `resolve_log_level` avec validation stricte des niveaux supportes.
- `configure_logging(level=...)` configure le root logger stdlib + structlog JSON avec filtrage par niveau.
- Niveaux supportes: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.

3. `src/tradebot/api/app.py`
- Bootstrap logging API sur `API_LOG_LEVEL` sinon fallback `LOG_LEVEL`.

4. `src/tradebot/apps/ws_candle_daemon.py`
- Bootstrap logging daemon sur `DAEMON_LOG_LEVEL` sinon fallback `LOG_LEVEL`.

5. Documentation
- `.env.example` complete avec `LOG_LEVEL`, `API_LOG_LEVEL`, `DAEMON_LOG_LEVEL`.
- `README.md` mis a jour (section logging multi-level).

## Validation
- Ajout tests: `tests/unit/test_logging_config.py`
  - validation niveaux acceptes/rejetes
  - rejet niveau invalide au bootstrap API

Commandes:
- `poetry run ruff check .`
- `poetry run ruff format .`
- `poetry run pytest -q`

## Journal Dev (2026-02-15) - Retours MR PR #14
- `src/tradebot/observability/logging.py`
  - Format stdlib enrichi dans `logging.basicConfig` pour conserver timestamp/niveau/logger sur les logs non-structlog.
- `src/tradebot/temporal_app/activities.py`
  - `_activity_log` rendu plus robuste (lookup niveau insensible a la casse + fallback propre).
  - Uniformisation des logs des activities placeholders via `_activity_log`.
- `src/tradebot/apps/ws_candle_daemon.py`
  - Suppression de `Settings()` au bootstrap `main()` pour eviter la validation globale de config avant lancement daemon.
  - Resolution du niveau de log daemon uniquement via variables d'environnement (`DAEMON_LOG_LEVEL` puis `LOG_LEVEL`).
- `tests/unit/test_logging_config.py`
  - Ajout de tests pour verifier la precedence `DAEMON_LOG_LEVEL`.
  - Ajout d'un test de non-regression: `main()` daemon demarre meme si une variable de config non liee (ex: `API_PORT`) est invalide.
