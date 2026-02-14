---
id: T-0025
title: "Ops - Observabilite, SLO et alerting du pipeline indicateurs"
status: TODO
owner: techlead
links: ["US-0005", "US-0006", "US-0007", "US-0008", "T-0021"]
---

## Contexte
Le pipeline doit etre operable en production avec visibilite sur latence, retries, saturation rate-limit et fraicheur donnees UI/API.

## Perimetre
- Definir metriques, dashboards et alertes du flux ingestion/backfill/engine/api.
- Definir SLO initiaux (latence API, fraicheur snapshot, succes backfill).
- Integrer traces/evenements critiques (429/418, cooldown, reprise, stale).

## Hors perimetre
- Refonte complete plateforme observabilite.

## Criteres d'acceptation
1. Dashboard unique pour incidents indicateurs live.
2. Alertes actionnables avec seuils et runbook.
3. Correlation id presente sur logs critiques.
