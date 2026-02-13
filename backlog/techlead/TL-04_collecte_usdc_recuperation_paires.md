---
id: TL-04
title: "Collecte USDC - Recuperation dynamique des paires"
status: DONE
owner: techlead
links: ["TL-04"]
---

# TL-04 Collecte USDC - Recuperation dynamique des paires

## Objectif
Recuperer automatiquement la liste des paires Spot se terminant par `USDC` depuis l'API Binance au demarrage du daemon.

## Scope
- Appel API tickers 24h au demarrage.
- Filtrage des symboles finissant par `USDC`.
- Echec explicite si l'API Binance est indisponible.

## Taches
- Identifier l'endpoint Binance utilise (ex: 24h tickers) et son champ de volume.
- Implementer l'appel et le filtrage `symbol.endswith('USDC')`.
- Gerer l'indisponibilite API (erreur, pas d'ecoute partielle silencieuse).
- Ajouter logs structures pour succes/erreur.

## Criteres d'acceptation
- L'appel API est fait au demarrage.
- Seules les paires `*USDC` sont conservees.
- En cas d'echec API, le daemon echoue avec message clair.

## Dependances
- Client Binance existant et gestion d'erreurs reseau.
