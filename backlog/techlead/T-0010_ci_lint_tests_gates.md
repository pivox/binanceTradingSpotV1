---
id: T-0010
title: "CI - Lint et tests obligatoires"
status: VALIDATED
owner: dev
links: ["TL-10", "BUG-004"]
---

## Contexte
Rendre obligatoires les gates de qualite (lint + tests) dans la CI et statuer sur mypy.

## Perimetre
- Ajout d'une etape `lint` via `ruff`.
- Tests `pytest` avec sortie standardisee (junit XML).
- Decision explicite sur `mypy` (gate activee ou deferree).

## Plan
1. Ajouter l'etape lint `poetry run ruff check .` dans la CI.
2. Standardiser la sortie des tests avec `--junitxml`.
3. Documenter la decision mypy (deferree tant que BUG-004 non resolu).

## Definition of Done
- CI echoue si lint ou tests echouent.
- Sortie tests standardisee.
- Decision mypy documentee et appliquee.
