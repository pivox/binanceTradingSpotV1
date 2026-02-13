---
id: T-0011
title: "CI - Gestion securisee des secrets Binance"
status: NEEDS_QA
owner: dev
links: ["TL-11", "B-0005"]
---

## Contexte
Garantir que les cles Binance sont gerees via les secrets CI et jamais en dur.

## Perimetre
- Definition des secrets requis.
- Validation explicite de presence (fail fast) pour les jobs qui en ont besoin.
- Documentation des secrets pour staging/production.

## Plan
1. Ajouter une verification des secrets dans la CI.
2. Documenter les noms exacts des secrets.
3. S'assurer qu'aucun secret n'est loggue.

## Definition of Done
- Workflow echoue si secret requis manquant.
- Documentation a jour.

## Livrables
- Ajout d'un message d'erreur explicite et d'une alerte Slack sur echec du check secrets dans `/.github/workflows/ci.yml`.
- Documentation des secrets par environnement dans `/docs/ci.md` et `/docs/deploy.md`.
