---
id: US-0012
title: "Collecte USDC - S'abonner en websocket sur la liste dynamique retenue"
status: TODO
owner: po
links: ["EPIC-COLLECTE-USDC", "T-0035"]
---

## User Story
En tant que systeme de streaming
Je veux que le daemon s'abonne aux klines `1m` de la liste dynamique calculee
Afin de collecter en continu les donnees des paires selectionnees automatiquement.

## Contexte
- La liste de symboles retenue provient du filtrage/tri/limite (US-0009/US-0010/US-0011).
- Une reconnexion websocket doit re-synchroniser proprement la souscription.

## Criteres d'acceptation
1. Le daemon construit les streams websocket a partir de la liste retenue (un stream par symbole) pour les klines `1m`.
2. Le nombre de streams abonnes correspond exactement au nombre de paires retenues (pas d'abonnement en trop ou manquant).
3. En cas de reconnexion, la selection (filtrage + tri + limite + override) est rejouee avant resubscribe.
4. Un resubscribe ne cree pas de doublons logiques (pas de double ingestion pour un meme symbole/timeframe).
5. Le service loggue les evenements de (re)connexion avec la taille de la souscription et une cause exploitable.

## NFR
1. La reconnexion ne doit pas bloquer indefiniment: une strategie de retry/backoff est definie et observable.

