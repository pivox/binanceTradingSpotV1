---
id: US-0017
title: "CI - Gerer les secrets Binance de maniere securisee"
status: TODO
owner: po
links: ["EPIC-CICD-TRADING-SECURISE", "T-0037"]
---

## User Story
En tant que PO/SecOps
Je veux que les cles API Binance soient gerees via les secrets CI et jamais en dur
Afin de securiser l'execution des workflows et limiter l'exposition accidentelle des secrets.

## Contexte
- Les secrets doivent etre limites aux jobs qui en ont besoin.
- L'absence de secret requis doit echouer rapidement (fail-fast) pour eviter des comportements partiels.

## Criteres d'acceptation
1. Aucune cle n'est stockee en dur dans le repository (code, docs, fichiers).
2. Les workflows CI/CD utilisent les secrets du runner (ex: GitHub Secrets) pour `BINANCE_API_KEY` et `BINANCE_API_SECRET`.
3. Les jobs qui necessitent les secrets echouent explicitement si un secret requis est absent, avec un message exploitable.
4. Les secrets ne sont jamais loggues (pas de echo accidentel, pas de dump d'env).
5. Les secrets requis et leur usage sont documentes pour chaque environnement (dev/staging/production).

## NFR
1. Les secrets de notification (ex: Slack) suivent les memes regles (non loggues, scopes minimaux).

