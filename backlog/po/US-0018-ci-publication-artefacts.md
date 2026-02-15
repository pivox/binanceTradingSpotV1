---
id: US-0018
title: "CI - Publier des artefacts (build + logs) a chaque run reussi"
status: TODO
owner: po
links: ["EPIC-CICD-TRADING-SECURISE", "T-0037"]
---

## User Story
En tant que developpeur
Je veux publier les artefacts de build et les logs de CI
Afin de faciliter le diagnostic des executions et de tracer la qualite livree.

## Contexte
- Les artefacts (build + logs) facilitent l'analyse post-mortem (tests flaky, erreurs de build, etc.).
- Une retention explicite evite l'accumulation inutile.

## Criteres d'acceptation
1. Un artefact est publie a chaque run CI reussi.
2. L'artefact contient au minimum: le build (ex: `dist/`) et les logs/tests (ex: fichiers `artifacts/`).
3. La retention des artefacts est configuree (ex: 7 jours) et documentee.
4. Le nom de l'artefact est stable et facilement retrouvable depuis l'UI GitHub Actions.

## NFR
1. Les artefacts n'incluent jamais de secrets (scan manuel ou garde de base).

