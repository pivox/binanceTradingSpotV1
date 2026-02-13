---
id: TL-06
title: "Collecte USDC - Abonnement websocket dynamique"
status: DONE
owner: techlead
links: ["TL-06"]
---

# TL-06 Collecte USDC - Abonnement websocket dynamique

## Objectif
Abonner le daemon aux klines 1m pour la liste dynamique calculee et resynchroniser au reconnect.

## Scope
- Construction des streams websocket a partir de la liste dynamique.
- Nombre de streams conforme a la limite retenue.
- Reconnexion: rejouer selection + resubscribe.

## Taches
- Construire les streams websocket depuis la liste dynamique.
- Verifier la correspondance exacte avec la limite appliquee.
- Integrer la re-selection dynamique avant resubscribe.
- Tester la reconnexion (cas reseau instable).

## Criteres d'acceptation
- Le nombre de streams abonnes correspond a la limite.
- En cas de reconnexion, la liste est recalculee avant resubscribe.

## Dependances
- TL-04 (liste des paires USDC).
- TL-05 (tri + limite).
