---
id: B-0004
title: "Gates qualite en echec (ruff / mypy)"
status: VALIDATED
owner: qa
links: ["B-0004", "TL-10", "T-0010"]
---

# BUG-004 - Gates qualite en echec (ruff / mypy)

## Description
Les checks qualite echouent actuellement:
- `poetry run ruff check .` retourne des erreurs (imports inutilises, nom de variable ambigu, etc.).
- `poetry run mypy src/tradebot` retourne plusieurs erreurs (stubs manquants, typage SQLAlchemy, signature aiohttp, Temporal overloads).

## Impact
- Difficulte a mettre en place une CI stricte.
- Signal bruit/erreurs qui masque les regressions reelles.

## Exemples (ruff)
- `src/tradebot/apps/ws_candle_daemon.py`: E741 variable `l`
- `src/tradebot/services/validator.py`: F401 import unused
- `src/tradebot/temporal_app/types.py`: F401 import unused
- `tests/unit/test_daemon_control.py`: F401 import unused

## Exemples (mypy)
- `src/tradebot/config/loader.py`: stubs PyYAML manquants
- `src/tradebot/infra/db/models.py`: Base SQLAlchemy non typable
- `src/tradebot/api/app.py`: handler sync `FileResponse` non awaitable
- `src/tradebot/temporal_app/workflows.py`: signatures `execute_activity` non conformes

## Critere de cloture
- Decider si `ruff`/`mypy` sont des gates obligatoires.
- Si oui: corriger les erreurs ou ajuster la config (ignore ciblages, dependances de stubs, patterns SQLAlchemy/Temporal).
