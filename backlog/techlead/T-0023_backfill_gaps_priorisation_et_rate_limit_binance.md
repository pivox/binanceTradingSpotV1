---
id: T-0023
title: "Backend - Backfill des trous avec priorisation et gestion rate-limit Binance"
status: TODO
owner: techlead
links: ["US-0006", "US-0005", "T-0021"]
---

## Contexte
US-0006 exige un rattrapage idempotent des donnees manquantes sans depassement des limites Binance et avec comportement robuste sur 429/418.

## Perimetre
- Detecter trous de candles par pair/timeframe/plage.
- Orchestrer jobs de backfill avec priorisation configurable.
- Exploiter headers `X-MBX-USED-WEIGHT-*` pour debit dynamique.
- Implementer politiques 429 (backoff+jitter) et 418 (stop+cooldown+alerte).

## Hors perimetre
- Calcul indicateurs (ticket dedie moteur).

## Plan d'implementation
1. Ajouter table/jobs `backfill_jobs` + scheduler.
2. Implementer strategie de priorite (top volume, actives UI, timeframe court).
3. Ajouter retry policy bornee (`max_attempts`, `max_backoff`, `max_retry_window`).
4. Exposer metriques/evt critiques observables.

## Tests
- Integration detection trous et idempotence insertion.
- Tests resilience 429/418 (mocks Binance).
- Tests starvation/politique priorite.

## Criteres d'acceptation
1. Aucun retry infini, chaque echec terminal observable.
2. Mode "slow" active proche seuil critique weight.
3. Rattrapage sans doublons, tri strict temporel.
