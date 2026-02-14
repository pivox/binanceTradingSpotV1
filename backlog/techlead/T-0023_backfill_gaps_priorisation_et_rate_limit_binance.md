---
id: T-0023
title: "Backend - Backfill des trous avec priorisation et gestion rate-limit Binance"
status: NEEDS_QA
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

## Journal Dev (2026-02-14)
### Livre
- Ajout du modele DB `backfill_jobs` pour persister les jobs de rattrapage:
  - fenetre cible (`from_open_time_ms`, `to_open_time_ms`), priorite, statut, tentatives, retry/cooldown, dernier statut HTTP.
- Implementation repository `BackfillRepoSql`:
  - detection de trous temporels dans `candles` par `(symbol,timeframe)` avec bornes optionnelles.
  - scheduling idempotent des jobs (contrainte unique par fenetre cible).
  - selection des jobs prets ordonnee par priorite puis retry time.
  - politique 429/418 avec retries bornes, backoff exponentiel + jitter deterministe, cooldown explicite, statut terminal.
  - interpretation des headers `X-MBX-USED-WEIGHT-*` et passage en `rate_mode=slow` proche seuil.
- Ajout des tests unitaires dans `tests/unit/test_backfill_repo.py`:
  - detection des gaps, idempotence de scheduling, policies 429/418, terminal failure.
- Documentation technique ajoutee: `docs/backfill-rate-limit.md`.
