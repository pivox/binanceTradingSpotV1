---
id: T-0029
title: "Solution - Lot 2 pour US non implementees (US-0005, US-0006, US-0008)"
status: TODO
owner: techlead
links: ["US-0005", "US-0006", "US-0007", "US-0008", "T-0030", "T-0031", "T-0032", "T-0033"]
---

## Contexte
Les US versionnees existent, mais l'implementation est inegale:
- US-0001 a US-0004: socle chart API/UI deja present.
- US-0005 et US-0006: briques techniques presentes (calculs indicateurs, repo backfill), mais pas encore completement branchees en execution runtime.
- US-0008: ecran screener non livre en production (API agregation + UI).

## Ecarts constates
1. Le moteur d'indicateurs calcule des snapshots, mais le pipeline runtime ne persiste pas encore automatiquement les snapshots depuis les evenements de cloture de bougie.
2. Le backfill gere la detection/politique en repository, mais l'orchestration continue (scheduler + worker + client Binance) n'est pas finalisee.
3. Le contrat API pour le screener multi-paires (filtres/tris/volumetrie) n'est pas expose.
4. L'UI screener (table virtualisee, debounce, presets, stale state, accessibilite) n'est pas livree.

## Solution cible
1. Brancher un pipeline backend event-driven:
   - lecture des `candle_close_event`,
   - construction snapshot indicateurs,
   - persistence `indicator_snapshots`,
   - replay deterministic en cas de correction/out-of-order.
2. Completer la chaine backfill runtime:
   - planification des gaps,
   - execution bornee avec politiques 429/418,
   - monitoring rate-limit et mode slow.
3. Exposer une API screener dediee:
   - liste des snapshots "latest" multi-symbols/timeframe,
   - filtres/tris server-side stables,
   - pagination curseur opaque et metadata de fraicheur.
4. Livrer l'UI screener:
   - table virtualisee,
   - filtres/tris debounce,
   - presets rechargeables,
   - etat stale et a11y clavier/focus.

## Decoupage tickets dev
1. `T-0030` - Pipeline indicateurs live + etat incremental + replay.
2. `T-0031` - Orchestrateur backfill runtime + rate-limit Binance.
3. `T-0032` - API screener multi-paires versionnee et performante.
4. `T-0033` - UI screener virtualisee avec filtres/tris/presets.

## Ordre de livraison recommande
1. T-0030
2. T-0031
3. T-0032
4. T-0033

## Risques et garde-fous
- Risque latence sur screener > 200 paires: imposer index SQL + pagination + payload borne.
- Risque incoherence replay indicateurs: introduire tests golden files et invariants de determinisme.
- Risque surcharge Binance: activer mode slow et cooldown stricts, metriques obligatoires.

## Criteres d'acceptation
1. Chaque US ciblee (0005/0006/0008) a au moins un ticket dev executable, trace et testable.
2. Les dependances inter-tickets sont explicites et sans ambiguite de sequence.
3. Les tests attendus et criteres NFR sont definis avant implementation.
