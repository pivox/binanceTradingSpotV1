---
id: T-0031
title: "Backend - Orchestrateur backfill runtime avec priorisation et rate-limit"
status: TODO
owner: dev
links: ["US-0006", "US-0005", "US-0007", "T-0029", "T-0023"]
---

## Contexte
Le repository backfill est en place (`BackfillRepoSql`), mais l'orchestration runtime complete (scheduler + executeur + integration API Binance) n'est pas finalisee.

## Perimetre
- Implementer un scheduler periodique qui detecte les gaps et alimente `backfill_jobs`.
- Implementer un worker qui consomme les jobs prets et appelle Binance REST klines.
- Persister les candles recuperees de facon idempotente (sans doublon, tri temporel strict).
- Appliquer les politiques 429/418 existantes:
  - 429 -> backoff exponentiel + jitter borne,
  - 418 -> cooldown dur + reprise controlee.
- Prendre en compte les headers `X-MBX-USED-WEIGHT-*` pour piloter le mode normal/slow.
- Definir et appliquer une priorisation configurable (top volume, paires actives, timeframe court).
- Emettre evenements/metriques critiques pour observabilite/alerting.

## Hors perimetre
- Refactor complet du client Binance.
- Evolution des formules indicateurs.

## Plan d'implementation
1. Ajouter un service `backfill_scheduler` (scan gaps -> creation jobs) et un service `backfill_worker` (execution jobs).
2. Brancher la politique de priorisation dans la creation/ordonnancement.
3. Integrer le client Binance REST avec handling explicite 2xx/429/418/5xx.
4. Ajouter persistence idempotente des candles manquantes + emission de `candle_close_event` si necessaire.
5. Exposer metriques et logs structures pour retries, cooldown, terminal failure, rate mode.

## Tests
- Unitaires:
  - priorisation des jobs,
  - transitions de statut (`PENDING`, `RETRY_WAIT`, `COOLDOWN`, `DONE`, `FAILED_TERMINAL`).
- Integration:
  - scenario gap -> backfill -> candles inserees sans doublon,
  - scenario 429 puis succes,
  - scenario 418 puis cooldown puis reprise.

## Criteres d'acceptation
1. Les gaps detectes sont rattrapes sans insertion dupliquee et avec ordre temporel strict.
2. Aucun retry infini: toutes sequences de retry sont bornees et observables.
3. Le service degrade proprement en mode `slow` proche du seuil de weight.
4. Les incidents 429/418 sont traces et exploitables en operation.

## Definition of Done
- Code merge avec `ruff check .`, `ruff format .`, `pytest -q` verts.
- Documentation d'exploitation mise a jour (`docs/backfill-rate-limit.md` ou equivalent).
