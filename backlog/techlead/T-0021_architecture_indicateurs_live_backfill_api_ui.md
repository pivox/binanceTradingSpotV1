---
id: T-0021
title: "Architecture - Blueprint indicateurs live + backfill + API + UI"
status: TODO
owner: techlead
links: ["US-0005", "US-0006", "US-0007", "US-0008"]
---

## Contexte
Les US 0005 a 0008 introduisent un flux bout-en-bout (ingestion -> calcul -> API -> UI) avec contraintes fortes de determinisme, rate-limit Binance et performance UI.

## Perimetre
- Definir architecture logique et flux de donnees cibles.
- Definir modeles de donnees (candles, snapshots, etats incremental, jobs backfill).
- Definir contrats d'evenements internes et standards observabilite.
- Produire ADR des choix clefs (recalcul, curseur API, ETag, priorisation backfill).

## Hors perimetre
- Implementation detaillee des composants.
- Ecriture des tests metier de chaque US.

## Livrables
- Document architecture consolide dans `docs/architecture-indicateurs-live.md`.
- Schema de sequence et matrice responsabilites (Ingestion/Backfill/Engine/API/UI).
- Plan de livraison par increments.

## Criteres d'acceptation
1. Architecture validee en revue tech (backend + frontend + ops).
2. Chaque US 0005..0008 mappee a un ou plusieurs composants.
3. NFR principaux couverts par des garde-fous explicites.

## Definition of Done
- Doc mergee et referencee depuis backlog techlead.
- Risques + hypotheses + questions ouvertes documentes.
