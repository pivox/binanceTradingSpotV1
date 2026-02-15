---
id: US-0015
title: "CI - Declencher automatiquement la CI sur push et pull_request"
status: TODO
owner: po
links: ["EPIC-CICD-TRADING-SECURISE", "T-0037"]
---

## User Story
En tant que developpeur
Je veux que la CI se lance automatiquement sur `push` et `pull_request` vers `main`
Afin de valider rapidement le code et de reduire le risque de regressions au merge.

## Contexte
- La CI est la source de verite pour la qualite: lint, tests, build.
- Les runs obsoletes doivent etre limites (annulation/concurrency) pour reduire le bruit et le cout.

## Criteres d'acceptation
1. Un workflow CI se declenche sur `push` et `pull_request` sur la branche `main`.
2. Le status de la CI est visible et associe a la pull request.
3. Les regles de branche (branch protection) sont documentees pour rendre le status check obligatoire avant merge.
4. Les runs obsoletes d'une meme branche sont annules (concurrency) afin d'eviter l'encombrement.
5. Les permissions du workflow sont minimales (principe du moindre privilege).

## NFR
1. La CI reste suffisamment rapide pour feedback: un objectif p95 est defini et suivi (ex: < 10 minutes).

