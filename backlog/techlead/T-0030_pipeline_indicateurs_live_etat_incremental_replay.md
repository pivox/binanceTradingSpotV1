---
id: T-0030
title: "Backend - Pipeline indicateurs live avec etat incremental et replay"
status: TODO
owner: dev
links: ["US-0005", "US-0007", "T-0029", "T-0022", "T-0024"]
---

## Contexte
Les fonctions de calcul indicateurs existent (`src/tradebot/services/indicators/`) et l'API lit `indicator_snapshots`, mais il manque la chaine runtime qui calcule/persiste automatiquement les snapshots a partir des bougies closes.

## Perimetre
- Ajouter l'etat incremental persistant par `(symbol, timeframe)` (table + repository `indicator_state`).
- Consommer les `candle_close_event` pour declencher les calculs sur bougies closes.
- Construire puis persister les snapshots via `build_indicator_snapshot` + `IndicatorRepository.upsert_snapshot`.
- Gerer corrections tardives/out-of-order: replay depuis la premiere bougie impactee.
- Garantir idempotence et ordre de traitement par `(symbol,timeframe)`.
- Ajouter logs/metriques operationnelles (latence calcul, replay_count, erreurs).

## Hors perimetre
- Evolution UX/UI screener.
- Ajout de nouveaux indicateurs hors spec US-0005.

## Plan d'implementation
1. Ajouter modele/repository `indicator_state` (dernier close traite, etat warmup, metadonnees replay).
2. Implementer un service `indicator_pipeline` qui:
   - lit les bougies closes necessaires,
   - applique le moteur de calcul,
   - persiste snapshot + etat.
3. Brancher le service sur le flux de production (worker/activite) en s'appuyant sur `candle_close_event`.
4. Ajouter la logique replay quand une bougie historique est corrigee.
5. Instrumenter metriques + logs structures.

## Tests
- Unitaires:
  - warmup indisponibilite (`status/reason`) sans `null` ambigu,
  - determinisme replay (meme historique => memes snapshots),
  - idempotence sur re-traitement du meme event.
- Integration:
  - insertion de candles + events puis verification snapshots persistes,
  - correction tardive d'une bougie et recalcul jusqu'au present.

## Criteres d'acceptation
1. Tout `candle_close_event` valide produit (ou met a jour) un snapshot pour `(symbol,timeframe)` cible.
2. En cas de correction historique, le replay reconstruit des valeurs coherentes et deterministes.
3. Les champs indisponibles suivent strictement `status=unavailable` avec `reason` attendu.
4. Les snapshots sont disponibles pour l'API sans intervention manuelle.

## Definition of Done
- Code merge avec `ruff check .`, `ruff format .`, `pytest -q` verts.
- Documentation technique courte du pipeline ajoutee dans `docs/`.
