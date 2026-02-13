---
id: T-0009
title: "CI de base via GitHub Actions"
status: VALIDATED
owner: dev
links: ["TL-09"]
---

## Contexte
Mettre en place une CI standard declenchee sur push/PR sur `main` avec un status check fiable.

## Perimetre
- Workflow `.github/workflows/ci.yml`.
- Triggers `push` et `pull_request` sur `main`.
- Setup Python 3.11 + Poetry + deps.
- Concurrency pour annuler les runs obsoletes.
- Permissions minimales.
- Documentation des regles de branche pour bloquer le merge si echec.

## Plan
1. Creer le workflow CI GitHub Actions.
2. Ajouter cache + installation Poetry/deps.
3. Executer une verification de base (tests).
4. Documenter le status check a activer.

## Definition of Done
- Workflow present et fonctionnel.
- Documentation de la regle de branche.
