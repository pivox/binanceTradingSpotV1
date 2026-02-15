# Runbook - Indicateurs Live

## Latence API elevee

Symptome:
- alerte `IndicatorsLatestHighLatencyP95`

Checks:
1. verifier `tradebot_indicator_api_latency_ms` par endpoint/resultat
2. verifier erreurs DB dans logs (`db_error`) avec `correlation_id`
3. verifier saturation DB/IO (connexions, locks, CPU)

Actions:
1. reduire le `limit` API si pic de charge
2. activer cache amont (gateway/CDN interne) pour `If-None-Match`
3. escalader DB si contention persistante > 15 min

## Cooldown backfill (418)

Symptome:
- alerte `IndicatorsBackfillCooldownSpike`

Checks:
1. count des events `backfill_cooldown`
2. `tradebot_backfill_weight_used` proche limite
3. verifier headers Binance `X-MBX-USED-WEIGHT-*`

Actions:
1. reduire la cadence/jobs concurrents
2. augmenter marge `backfill_slow_mode_threshold_ratio`
3. reprendre progressivement apres cooldown

## Snapshots stale

Symptome:
- alerte `IndicatorsSnapshotStale`

Checks:
1. `tradebot_indicator_snapshot_freshness_ms` par symbol/timeframe
2. etat du pipeline ingestion/backfill
3. erreurs de calcul snapshot en logs

Actions:
1. relancer le worker de calcul indicateurs
2. verifier l'etat des jobs backfill bloquants
3. si incident durable, basculer UI en mode degrade explicite

## Demarrage websocket refuse (hard cap)

Symptome:
- Le daemon echoue au boot avec `selected streams exceed USDC_STREAMS_HARD_CAP`.

Checks:
1. verifier la valeur `USDC_STREAMS_HARD_CAP` en runtime
2. verifier `tradebot_ws_streams_selected` au dernier boot reussi
3. verifier la cardinalite des paires USDC retournees par Binance

Actions:
1. augmenter `USDC_STREAMS_HARD_CAP` si la capacite cible le permet
2. reduire `USDC_PAIRS_LIMIT` pour limiter la selection
3. redemarrer le daemon et confirmer un log `ws_boot_complete`

## Reconnexions websocket frequentes

Symptome:
- Hausse rapide de `tradebot_ws_reconnect_total`.
- Logs repetes `ws_reconnect_scheduled`.

Checks:
1. lire `attempt`, `delay_s`, `previous_error`, `streams` dans `ws_reconnect_scheduled`
2. verifier la config `WS_RECONNECT_BASE_DELAY_S` et `WS_RECONNECT_MAX_DELAY_S`
3. verifier la sante reseau vers `wss://stream.binance.com:9443/ws`

Actions:
1. augmenter progressivement `WS_RECONNECT_BASE_DELAY_S` pour lisser la pression
2. ajuster `WS_RECONNECT_MAX_DELAY_S` si des incidents longs sont observes
3. corriger la cause racine (`previous_error`) avant nouveau redemarrage force

## Boot websocket lent

Symptome:
- Increments de `tradebot_ws_boot_slow_total` ou logs `ws_boot_slow`.

Checks:
1. comparer `boot_ms` vs `threshold_ms` (`BOOT_WARN_MS`)
2. verifier la phase dominante via `symbols_ms` et `subscribe_ms` (`ws_boot_complete`)
3. verifier le volume de streams et la latence Binance REST/websocket

Actions:
1. relever `BOOT_WARN_MS` seulement si la lenteur est attendue et stable
2. reduire temporairement le nombre de streams (cap/limit) en mitigation
3. ouvrir incident plateforme si degradation reseau persistante
