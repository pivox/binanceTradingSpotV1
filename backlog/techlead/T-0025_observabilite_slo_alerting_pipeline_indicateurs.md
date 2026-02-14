---
id: T-0025
title: "Ops - Observabilite, SLO et alerting du pipeline indicateurs"
status: NEEDS_QA
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

## Journal Dev (2026-02-14)
### Livre
- Instrumentation metriques:
  - latence endpoints indicateurs (`tradebot_indicator_api_latency_ms`),
  - hit/miss cache conditionnel (`tradebot_indicator_cache_requests_total`),
  - fraicheur snapshots (`tradebot_indicator_snapshot_freshness_ms`),
  - evenements backfill (`tradebot_backfill_events_total`) + dernier weight (`tradebot_backfill_weight_used`).
- Middleware API correlation id:
  - support `X-Correlation-ID` entrant + generation auto,
  - propagation dans les reponses,
  - logs critiques API enrichis avec `correlation_id`.
- Endpoint scrape Prometheus expose: `GET /metrics`.
- Livrables Ops:
  - dashboard/SLO: `docs/observability-indicators-live.md`,
  - alert rules: `docs/alerts-indicators-live.yml`,
  - runbook: `docs/runbook-indicators-live.md`.
- Tests:
  - verification `X-Correlation-ID` et `/metrics` dans `tests/unit/test_indicator_api.py`.
