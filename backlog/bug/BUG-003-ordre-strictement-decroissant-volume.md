---
id: B-0003
title: "Ambiguite / non-respect potentiel: strictement decroissant sur quoteVolume"
status: VALIDATED
owner: qa
links: ["B-0003", "TL-05"]
---

# BUG-003 - Ambiguite / non-respect potentiel: "strictement decroissant" sur `quoteVolume`

## Contexte
US-02 / TL-05 demandent: "L'ordre final des paires est strictement decroissant" sur le volume 24h (ex: `quoteVolume`).

## Description
L'implementation dans `src/tradebot/apps/ws_candle_daemon.py` trie avec `reverse=True` sur `quoteVolume`, ce qui produit un ordre decroissant (non-croissant), mais pas "strictement decroissant" si plusieurs paires ont un volume identique.

## Impact
- La CA "strictement" est mathematiquement non garantie avec des volumes reels (egalites possibles).
- Les audits et tests peuvent etre flakys si l'ordre attendu n'est pas precise en cas d'egalite.

## Proposition
- Clarifier la CA: remplacer "strictement" par "decroissant" (non-croissant).
- Et/ou definir un tie-break deterministe (ex: `(-quoteVolume, symbol)`), puis documenter le comportement.

## Critere de cloture
- CA clarifiee + comportement deterministe documente (et idealement teste).
