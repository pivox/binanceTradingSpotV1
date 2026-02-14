# Observability - Indicateurs Live

Ticket: `T-0025`

## Dashboard unique

Dashboard unique recommande: **"tradebot-indicators-live"**

Panels minimum:

1. API indicateurs latence p50/p95 (`tradebot_indicator_api_latency_ms`)
2. Cache conditionnel hit/miss (`tradebot_indicator_cache_requests_total`)
3. Fraicheur snapshot (`tradebot_indicator_snapshot_freshness_ms`)
4. Backfill events (`tradebot_backfill_events_total`)
5. Derniere valeur weight Binance (`tradebot_backfill_weight_used`)

## SLO initiaux

1. `SLO-API-LATEST-LATENCY`: p95 `/indicators/latest` <= 300ms sur 30 min.
2. `SLO-BACKFILL-SUCCESS`: taux de `backfill_success` >= 99% sur 1h.
3. `SLO-SNAPSHOT-FRESHNESS`: fraicheur p95 <= 120s pour les paires actives UI.

## Correlation ID

`X-Correlation-ID` est gere par middleware API:

- Reprise si header entrant present.
- Generation automatique sinon.
- Reponse HTTP echoe ce header.
- Logs critiques API incluent `correlation_id`.

## Alerting + runbook

- Rules: `docs/alerts-indicators-live.yml`
- Runbook: `docs/runbook-indicators-live.md`
