---
id: US-0019
title: "CD - Deployer manuellement vers staging puis production avec validations"
status: TODO
owner: po
links: ["EPIC-CICD-TRADING-SECURISE", "T-0037"]
---

## User Story
En tant que PO
Je veux un deploiement manuel vers `staging` puis `production` avec validations
Afin de maitriser la mise en production et de limiter le risque de deploiements non controles.

## Contexte
- Le deploiement doit etre bloque si la CI n'est pas verte pour le commit cible.
- La production doit exiger une approbation explicite (gating via environnements).

## Criteres d'acceptation
1. Un workflow de deploiement est declenchable manuellement (`workflow_dispatch`) avec un choix d'environnement `staging|production`.
2. Le deploiement est autorise uniquement si la CI est verte pour le commit cible (gate explicite).
3. Le deploiement `production` necessite une validation manuelle/approbation (gating GitHub environment).
4. Le deploiement publie un artefact deployable (ex: image Docker) avec un tag permettant d'identifier la version et l'environnement.
5. Une procedure de rollback est documentee et testable (etapes, prerequis, verification).

## NFR
1. Les actions de deploiement sont auditees (qui, quoi, quand, environnement, version).

