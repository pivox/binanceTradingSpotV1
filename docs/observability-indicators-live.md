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

## Hardening Websocket (T-0035)

Variables d'environnement operationnelles:

1. `USDC_STREAMS_HARD_CAP` (defaut `1000`): nombre maximum de streams websocket autorises au boot.
2. `WS_RECONNECT_BASE_DELAY_S` (defaut `2`): delai initial de reconnexion.
3. `WS_RECONNECT_MAX_DELAY_S` (defaut `30`): plafond de backoff exponentiel.
4. `BOOT_WARN_MS` (defaut `5000`): seuil de lenteur de boot websocket.

Metriques exposees:

1. `tradebot_ws_streams_selected` (gauge): nombre de streams selectionnes au demarrage.
2. `tradebot_ws_reconnect_total` (counter): nombre total de tentatives de reconnexion.
3. `tradebot_ws_boot_slow_total` (counter): nombre de boots websocket au-dela de `BOOT_WARN_MS`.

Logs attendus pour diagnostic:

1. `ws_boot_complete`: boot termine, inclut `streams`, `symbols_ms`, `subscribe_ms`, `boot_ms`.
2. `ws_boot_slow`: boot lent, inclut `boot_ms`, `threshold_ms`, `streams`.
3. `ws_reconnect_scheduled`: reconnexion planifiee, inclut `attempt`, `delay_s`, `previous_error`, `streams`.
