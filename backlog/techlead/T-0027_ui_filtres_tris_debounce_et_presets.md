---
id: T-0027
title: "UI - Filtres/tris debounce et presets rechargeables"
status: TODO
owner: techlead
links: ["US-0008", "US-0007", "T-0026"]
---

## Contexte
Le screener doit permettre de trouver rapidement des opportunites via filtres/tris sans surcharge API ni lag UI.

## Perimetre
- Filtres par pair/timeframe/indicateur/plage de valeur.
- Tri asc/desc sur colonnes numeriques.
- Debounce des actions filtre/tri.
- Sauvegarde/rechargement presets (stockage local v1 minimum).

## Hors perimetre
- Moteur de regles avancees multi-conditions complexes.

## Tests
- Unitaires sur serialisation presets.
- E2E filtres + tri + restore preset.
- Validation UX latence percue <=200ms hors reseau.

## Criteres d'acceptation
1. Debounce effectif et configurable.
2. Presets persistants et rechargeables sans erreur.
3. Tri numerique exact, stable et reversible.
