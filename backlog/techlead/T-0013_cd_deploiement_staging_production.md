---
id: T-0013
title: "CD - Deploiement controle vers staging puis production"
status: NEEDS_QA
owner: dev
links: ["TL-13", "B-0006"]
---

## Contexte
Mettre en place un deploiement manuel vers staging puis production avec validations.

## Perimetre
- Workflow `deploy.yml` via `workflow_dispatch`.
- Environnements GitHub `staging` et `production` avec approbations.
- Build/push image Docker vers GHCR.
- Procedure de rollback documentee.

## Plan
1. Ajouter un workflow de deploiement manuel.
2. Publier une image Docker dans GHCR.
3. Configurer les environnements (gating) et documenter le rollback.

## Definition of Done
- Deploiement staging possible apres CI verte.
- Deploiement production avec approbation.
- Rollback documente.

## Livrables
- Gate CI sur le workflow de deploiement dans `/.github/workflows/deploy.yml`.
- Documentation du gate CI et secrets par environnement dans `/docs/deploy.md`.
