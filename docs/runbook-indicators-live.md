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
