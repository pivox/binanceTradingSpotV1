---
id: US-0020
title: "Execution trading - Mode securise avec simulation par defaut"
status: TODO
owner: po
links: ["EPIC-CICD-TRADING-SECURISE", "T-0037"]
---

## User Story
En tant que trader/PO
Je veux que la strategie demarre en mode simulation par defaut et que le mode reel soit explicitement approuve
Afin de reduire le risque de perte financiere due a une mauvaise configuration ou un bug.

## Contexte
- Le mode d'execution v1 est controle par `execution_mode` avec une valeur par defaut `dry_run`.
- Le passage en mode reel (`live`) doit exiger un flag d'approbation explicite (ex: `LIVE_TRADING_APPROVED=true`).

## Criteres d'acceptation
1. Le mode `dry_run` est actif par defaut et ne soumet jamais d'ordres reels.
2. Le mode `live` n'est possible qu'avec un parametre explicite `execution_mode=live` et une approbation `LIVE_TRADING_APPROVED=true`.
3. Si `execution_mode=live` sans approbation, l'execution echoue explicitement avec un message clair.
4. Les signaux et intentions d'ordres sont journalises avec horodatage et contexte (mode, symbole, decision).
5. Les tests couvrent au minimum: default `dry_run`, blocage `live` sans approval, et `live` autorise avec approval.

## NFR
1. Le guard de securite est centralise (une seule source de verite) et difficile a contourner involontairement.

