---
id: US-0032
title: "Backtesting - Comparer les runs et calibrations"
status: TODO
owner: po
links: ["US-0024", "US-0026", "US-0028"]
---

## User Story
En tant que trader/PO
Je veux comparer plusieurs runs de backtest
Afin de choisir une calibration robuste plutot qu'un resultat isole ou sur-optimise.

## Contexte
- La Roadmap prevoit plusieurs iterations sur conditions YAML, seuils RSI/ADX, score minimum, `k_atr` et `r_multiple`.
- Une calibration acceptable doit etre robuste sur plusieurs periodes, pas seulement optimale sur un echantillon unique.

## Criteres d'acceptation
1. L'utilisateur peut selectionner plusieurs runs termines pour comparaison.
2. L'UI affiche les differences de configuration entre runs.
3. L'UI compare winrate, profit factor, drawdown, expectancy, nombre de trades, MFE, MAE et verdict Phase 2.
4. L'UI signale les runs peu robustes: faible nombre de trades, outlier dominant, drawdown eleve ou profit factor instable.
5. L'utilisateur peut comparer une periode in-sample et une periode out-of-sample si disponibles.
6. L'UI met en evidence la calibration recommandee selon les criteres PO: passage du gate, drawdown controle et echantillon suffisant.
7. L'utilisateur peut ouvrir le detail d'un run depuis la comparaison.

## NFR
1. La comparaison doit etre lisible avec au moins 5 runs.
2. Les deltas doivent etre affiches avec unite et sens clair.
3. Aucune recommandation ne doit masquer les limites statistiques du run.
