---
id: US-0011
title: "Collecte USDC - Limiter le nombre de paires ecoutees via une variable d'environnement"
status: TODO
owner: po
links: ["EPIC-COLLECTE-USDC", "T-0035"]
---

## User Story
En tant qu'operateur
Je veux limiter le nombre de paires a ecouter via une variable d'environnement
Afin de controler la charge du daemon sans changement de code.

## Contexte
- La limitation intervient apres filtrage et tri, pour conserver les paires les plus pertinentes.
- Le parametre v1 est `USDC_PAIRS_LIMIT` avec une valeur par defaut de `200`.

## Criteres d'acceptation
1. `USDC_PAIRS_LIMIT` determine le nombre maximum de paires retenues.
2. Si `USDC_PAIRS_LIMIT` est absente ou vide, la valeur par defaut `200` est appliquee.
3. Si la valeur est invalide (non numerique ou `<= 0`), le daemon echoue avec un message clair incluant le nom de la variable.
4. La limite est appliquee apres tri par volume (US-0010) et avant tout abonnement websocket.
5. Le service loggue: limite appliquee, nombre de paires retenues, et un echantillon (top N) pour audit.

## NFR
1. La modification de `USDC_PAIRS_LIMIT` prend effet au prochain demarrage (comportement explicite).

