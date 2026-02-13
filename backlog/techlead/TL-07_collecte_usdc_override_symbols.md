---
id: TL-07
title: "Collecte USDC - Override manuel via SYMBOLS"
status: DONE
owner: techlead
links: ["TL-07"]
---

# TL-07 Collecte USDC - Override manuel via SYMBOLS

## Objectif
Permettre un override manuel de la liste dynamique via `SYMBOLS`.

## Scope
- `SYMBOLS` prioritaire sur la selection dynamique.
- Log explicite du mode override.
- Le comportement de collecte reste identique pour ces symboles.

## Taches
- Implementer le parsing de `SYMBOLS` (liste de symboles).
- Prioriser `SYMBOLS` sur la liste dynamique.
- Ajouter un log explicite (mode override actif).
- Tests sur listes valides et invalides.

## Criteres d'acceptation
- Si `SYMBOLS` est renseignee, elle est prioritaire.
- Le log indique clairement que l'override est actif.
- Le comportement de collecte reste identique.

## Dependances
- TL-06 (abonnement websocket).
