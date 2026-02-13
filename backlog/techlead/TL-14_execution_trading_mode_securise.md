---
id: TL-14
title: "Execution trading en mode securise"
status: DONE
owner: techlead
links: ["TL-14"]
---

# TL-14 Execution trading en mode securise

## Objectif
Garantir un mode simulation par defaut et un passage en mode reel uniquement avec validation explicite.

## Scope
- `execution_mode` par defaut a `dry_run`.
- Passage en mode reel uniquement si flag explicite + approval.
- Journalisation horodatee des signaux et ordres.

## Taches
- Definir les flags d'activation (ex: `EXECUTION_MODE=live` + `LIVE_TRADING_APPROVED=true`).
- Ajouter un guard runtime qui bloque le mode reel sans approval explicite.
- Introduire un routeur d'execution (paper vs real) dans la couche d'execution.
- Logguer l'etat du mode et toutes les actions (signals/ordres) avec timestamp.
- Ajouter des tests (default dry_run, live bloque sans approval, live ok avec approval).

## Criteres d'acceptation
- Le mode `paper/simulation` est actif par defaut.
- Le mode reel n'est possible qu'avec un flag explicite et une approbation.
- Les signaux et ordres sont journalises avec horodatage.

## Dependances
- Definition du point d'execution des ordres (couche infra/binance).
