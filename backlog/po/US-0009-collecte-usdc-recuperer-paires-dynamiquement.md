---
id: US-0009
title: "Collecte USDC - Recuperer dynamiquement les paires Spot USDC"
status: TODO
owner: po
links: ["EPIC-COLLECTE-USDC", "T-0035"]
---

## User Story
En tant que systeme de collecte market data
Je veux recuperer automatiquement la liste des paires Spot se terminant par `USDC` depuis Binance au demarrage
Afin de ne plus dependre d'une liste statique de symboles et de rester aligne sur l'exchange.

## Contexte
- La collecte websocket doit s'abonner a des streams de klines pour une liste de symboles.
- Une liste statique est fragile (nouveaux listings, delistings, symboles suspendus) et couteuse a maintenir.
- Le critere v1 de selection est simple: `symbol.endswith("USDC")`.

## Criteres d'acceptation
1. Au demarrage, le service appelle l'API Binance permettant de recuperer la liste des tickers 24h.
2. Seules les paires dont le symbole se termine par `USDC` sont conservees.
3. En cas de reponse invalide (format inattendu) ou d'erreur HTTP, le daemon echoue explicitement (pas d'ecoute partielle silencieuse).
4. Le service loggue au minimum: le nombre total recu, le nombre retenu, et un echantillon (top N) pour audit.
5. Si aucune paire `*USDC` n'est retournee, le daemon echoue avec un message explicite.

## NFR
1. Le temps de selection au demarrage (hors latence reseau) reste <= 5s.
2. Les logs d'erreur contiennent endpoint, code HTTP et une cause exploitable.

