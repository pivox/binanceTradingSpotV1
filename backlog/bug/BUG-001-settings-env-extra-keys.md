---
id: B-0001
title: "Settings() echoue si .env contient des cles non supportees"
status: VALIDATED
owner: qa
links: ["B-0001", "TL-01", "TL-02", "TL-03"]
---

# BUG-001 - Settings() echoue si .env contient des cles non supportees

## Contexte
Les taches TL-01/TL-02/TL-03 s'appuient sur `Settings()` (Pydantic Settings) pour demarrer l'API de controle du daemon et pour les tests.

## Description
`tradebot.config.settings.Settings()` echoue avec une `ValidationError` quand le fichier `.env` contient des variables qui ne correspondent pas a des champs du modele (ex: `BINANCE_REST_URL`, `USDC_PAIRS_LIMIT`, `BINANCE_DEMO_API_KEY`, `BINANCE_DEMO_API_SECRET`).

Impact direct:
- L'API `python -m tradebot.apps.daemon_api_main` ne demarre pas si on suit le README (`cp .env.example .env`).
- Les tests `tests/unit/test_daemon_api.py` echouent.

## Etapes pour reproduire
1. `cp .env.example .env` (ou conserver le `.env` actuel)
2. `poetry run python -c "from tradebot.config.settings import Settings; Settings()"`
3. (Optionnel) `poetry run pytest -q`

## Resultat actuel
- Crash avec `pydantic_core._pydantic_core.ValidationError: Extra inputs are not permitted` sur:
  - `binance_demo_api_key`
  - `binance_demo_api_secret`
  - `binance_rest_url`
  - `usdc_pairs_limit`

## Resultat attendu
- `Settings()` doit charger correctement la configuration meme si `.env` contient des variables additionnelles non utilisees par `Settings`.
- L'API de controle doit pouvoir demarrer avec un `.env` derive de `.env.example`.
- `pytest` ne doit pas dependre du contenu du `.env` local.

## Notes / Analyse
- `src/tradebot/config/settings.py` ne declare pas `binance_rest_url` ni `usdc_pairs_limit` (pourtant presentes dans `.env.example`).
- TL-04/TL-05 utilisent ces variables directement via `os.environ`, mais TL-01/TL-03 instancient `Settings()` (qui lit `.env`).

## Proposition de correction
- Option A: configurer `SettingsConfigDict(..., extra="ignore")` pour ignorer les cles inconnues.
- Option B: ajouter les champs manquants dans `Settings` (`binance_rest_url`, `usdc_pairs_limit`, et/ou un namespace `binance_demo_*`) si on souhaite les supporter officiellement.
- Option C: isoler la configuration daemon/API dans un fichier env dedie (moins pratique a l'usage).

## Critere de cloture
- `poetry run python -c "from tradebot.config.settings import Settings; Settings()"` retourne 0 avec `.env.example`.
- `poetry run pytest -q` passe localement.
