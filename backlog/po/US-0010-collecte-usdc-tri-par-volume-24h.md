---
id: US-0010
title: "Collecte USDC - Trier les paires par volume de trade 24h"
status: TODO
owner: po
links: ["EPIC-COLLECTE-USDC", "T-0035"]
---

## User Story
En tant que trader/ops
Je veux que les paires `*USDC` soient triees par volume de trade 24h decroissant
Afin de prioriser les marches les plus liquides et optimiser l'allocation des ressources.

## Contexte
- Les tickers 24h Binance exposent un champ `quoteVolume` (volume dans la devise de cotation).
- Un tri deterministe facilite l'audit et reduit les differences d'execution entre environnements.

## Criteres d'acceptation
1. Le tri est effectue sur le champ `quoteVolume` du ticker 24h, interprete comme un nombre.
2. L'ordre final des paires est strictement decroissant par volume.
3. En cas d'egalite de volume, un tie-break deterministe est applique (ex: `symbol` ascendant) afin de garantir un ordre stable.
4. Si une valeur de volume est manquante ou invalide, elle est traitee comme `0` et un log signale l'anomalie.
5. Le service loggue les N premieres paires (symbole + volume) pour audit.

## NFR
1. Le tri est reproductible: meme input => meme output.
2. Le tri ne doit pas degrader de maniere notable le demarrage sur une volumetrie standard.

