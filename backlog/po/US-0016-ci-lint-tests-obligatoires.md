---
id: US-0016
title: "CI - Rendre obligatoires le lint et les tests unitaires"
status: TODO
owner: po
links: ["EPIC-CICD-TRADING-SECURISE", "T-0037"]
---

## User Story
En tant que membre de l'equipe
Je veux executer automatiquement le lint et les tests unitaires dans la CI
Afin d'eviter les regressions et d'imposer des gates de qualite avant merge/deploiement.

## Contexte
- Le lint v1 est base sur `ruff`.
- Les tests unitaires v1 sont executes via `pytest`.
- La position sur un gate `mypy` doit etre explicite (actif et vert, ou desactive et documente).

## Criteres d'acceptation
1. Une etape `lint` execute `ruff check .` et echoue si des erreurs sont detectees.
2. Une etape `test` execute `pytest -q` et echoue si un test echoue.
3. La decision sur `mypy` est explicite (gate actif et vert, ou gate desactive) et documentee.
4. Les sorties de lint/tests sont exportees dans des logs consultables (au minimum via les logs GitHub Actions).
5. En cas d'echec, le workflow echoue et le status check bloque le merge (selon regles de branche).

## NFR
1. Les commandes de qualite sont standardisees et reproductibles localement (meme commandes que la CI).

