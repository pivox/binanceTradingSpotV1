---
id: TL-11
title: "CI - Gestion securisee des secrets Binance"
status: DONE
owner: techlead
links: ["TL-11"]
---

# TL-11 CI - Gestion securisee des secrets Binance

## Objectif
Garantir que les cles Binance sont gerees via les secrets CI et jamais en dur.

## Scope
- Secrets GitHub (ou runner) pour `BINANCE_API_KEY` et `BINANCE_API_SECRET`.
- Validation explicite de presence des secrets pour les jobs qui en ont besoin.
- Aucun secret loggue.

## Taches
- Definir la liste des secrets requis et leurs noms exacts.
- Ajouter une etape de validation des secrets (fail fast si absent).
- Injecter les secrets via `env:` uniquement dans les jobs qui les utilisent.
- Documenter l'usage des secrets pour les environnements `staging`/`production`.

## Criteres d'acceptation
- Aucune cle n'est stockee en dur dans le repo.
- Les jobs utilisent uniquement les secrets du runner.
- Le workflow echoue si un secret requis est absent.

## Dependances
- TL-09.
- TL-13 (deploiement).
