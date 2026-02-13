# TL-10 CI - Lint et tests obligatoires

## Objectif
Rendre obligatoires les gates de qualite (lint + tests) dans la CI.

## Scope
- Etapes `lint` et `test` dans le workflow CI.
- Lint base sur `ruff`.
- Tests unitaires via `pytest`.
- Decision sur l'usage de `mypy` comme gate (voir BUG-004).

## Taches
- Definir les commandes de qualite (ex: `poetry run ruff check .`, `poetry run pytest -q`).
- Ajouter l'etape `lint` obligatoire dans le workflow.
- Ajouter l'etape `test` obligatoire dans le workflow.
- Statuer sur `mypy` comme gate et corriger/configurer si necessaire (BUG-004).
- Standardiser la sortie des tests (ex: `--junitxml=artifacts/pytest.xml`).

## Criteres d'acceptation
- Le workflow echoue si `lint` echoue.
- Le workflow echoue si `test` echoue.
- La decision `mypy gate` est prise et appliquee (passant ou ignoree de facon explicite).

## Dependances
- TL-09.
- BUG-004 (ruff/mypy en echec).
