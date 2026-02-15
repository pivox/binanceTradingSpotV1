---
id: US-0013
title: "Collecte USDC - Forcer une liste statique de symboles via SYMBOLS (override)"
status: TODO
owner: po
links: ["EPIC-COLLECTE-USDC", "T-0035"]
---

## User Story
En tant qu'operateur
Je veux pouvoir forcer une liste statique de symboles via `SYMBOLS`
Afin de faire du debug ou de l'exploitation ciblee, independamment de la selection dynamique.

## Contexte
- Le mode override doit etre explicite et prioritaire sur la selection dynamique.
- Le format v1 attendu est une liste separee par virgules (ex: `BTCUSDC,ETHUSDC`), avec normalisation en majuscules.

## Criteres d'acceptation
1. Si `SYMBOLS` est renseignee, elle est prioritaire sur la selection dynamique (pas d'appel Binance requis pour la selection).
2. La liste est parsee comme une liste de symboles separes par virgules; les espaces sont ignores et les symboles sont normalises en majuscules.
3. Si `SYMBOLS` est vide ou ne contient aucun symbole apres parsing, le daemon echoue avec un message clair.
4. Le log indique explicitement que le mode override est actif, avec le nombre de symboles et un echantillon (top N).
5. Le comportement de collecte est identique pour ces symboles (abonnement klines 1m, ingestion, persistence).

## NFR
1. Le mode override doit etre facilement activable/desactivable sans changement de code (env only).

