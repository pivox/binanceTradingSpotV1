---
id: US-0033
title: "Backtesting - Generer un rapport go/no-go"
status: TODO
owner: po
links: ["US-0024", "US-0028", "US-0030", "US-0032", "ROADMAP.md"]
---

## User Story
En tant que PO/trader
Je veux generer un rapport de decision a partir d'un backtest
Afin de documenter objectivement le passage, le blocage ou la recalibration avant les phases Signal Engine, Paper Trading et Execution.

## Contexte
- La Roadmap interdit de passer a l'execution reelle sans validation historique puis paper trading.
- Le rapport doit servir de trace produit et trading, pas seulement de capture d'ecran.

## Criteres d'acceptation
1. Le rapport resume configuration, periode, donnees disponibles, profil de strategie et metriques principales.
2. Le rapport affiche le verdict PASS, FAIL ou INCONCLUSIVE avec les raisons.
3. Le rapport liste les criteres Phase 2 et leur statut individuel.
4. Le rapport inclut les risques identifies: gaps, warmup incomplet, faible echantillon, frais non modelises, slippage, divergence entre backtest et moteur runtime.
5. Le rapport propose une recommandation PO: passer a calibration suivante, passer a Phase 3, rester bloque, ou preparer paper trading.
6. Le rapport rappelle explicitement qu'un PASS Phase 2 ne suffit pas a autoriser le live: Phase 5 paper trading reste obligatoire.
7. L'utilisateur peut exporter le rapport en Markdown ou JSON.
8. Le rapport exporte contient l'identifiant du run et les parametres permettant sa reproduction.

## NFR
1. L'export ne doit pas contenir de secret ni de donnees sensibles Binance.
2. Le rapport doit etre stable et lisible dans une PR, un ticket ou une revue de decision.
3. Les recommandations doivent rester factuelles et fondees sur les criteres affiches.
