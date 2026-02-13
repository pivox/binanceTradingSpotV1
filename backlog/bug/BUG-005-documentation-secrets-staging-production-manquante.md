---
id: B-0005
title: "Documentation incomplete des secrets Binance pour staging/production"
status: VALIDATED
owner: qa
links: ["B-0005", "T-0011", "TL-11"]
---

# BUG-005 - Documentation incomplete des secrets Binance pour staging/production

## Contexte
Le ticket `T-0011` demande de documenter les secrets Binance pour les environnements `staging` et `production`.

## Description
La documentation actuelle ne decrit pas explicitement la configuration des secrets Binance par environnement GitHub (`staging`/`production`), ni la strategie de nommage/portee.

Fichiers controles:
- `docs/ci.md`
- `docs/deploy.md`

## Impact
- Ambiguite operationnelle lors de la configuration GitHub Environments.
- Risque d'erreur de deploiement ou de job CI/CD incomplet selon l'environnement.

## Resultat actuel
- Les secrets `BINANCE_API_KEY` et `BINANCE_API_SECRET` sont cites globalement.
- Aucune section explicite ne decrit leur configuration environment-scoped pour `staging` et `production`.

## Resultat attendu
- Documentation explicite, pas-a-pas, de la configuration des secrets Binance pour `staging` et `production`.
- Clarification de la portee (repository secrets vs environment secrets) et des noms exacts.

## Critere de cloture
- `docs/ci.md` et/ou `docs/deploy.md` decrivent clairement la configuration des secrets Binance par environnement cible.
- Un lecteur peut configurer les secrets sans hypothese implicite.
