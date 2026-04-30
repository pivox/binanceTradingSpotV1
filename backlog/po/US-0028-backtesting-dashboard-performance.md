---
id: US-0028
title: "Backtesting - Afficher un dashboard de performance trading"
status: TODO
owner: po
links: ["US-0024", "US-0026", "US-0027"]
---

## User Story
En tant que trader
Je veux lire un tableau de bord de performance clair apres un backtest
Afin de decider si la strategie merite calibration, rejet ou passage vers la phase suivante.

## Contexte
- Les metriques de la Roadmap sont winrate, profit factor, max drawdown, expectancy, MFE et MAE.
- Pour un trader, la distribution des gains/pertes et la qualite de l'echantillon comptent autant que la moyenne.

## Criteres d'acceptation
1. Le dashboard affiche total trades, trades fermes, trades ouverts, winrate, profit factor, expectancy en R et en devise, max drawdown, avg MFE et avg MAE.
2. Le dashboard affiche le verdict Phase 2: PASS, FAIL ou INCONCLUSIVE.
3. Le verdict INCONCLUSIVE est utilise quand l'echantillon est trop faible, les donnees sont incompletes ou trop de trades restent ouverts.
4. Les criteres de gate sont visibles a cote des valeurs mesurees.
5. L'UI affiche une courbe d'equity, une courbe de drawdown et une repartition des PnL en R.
6. L'utilisateur voit les frais et slippage integres au calcul.
7. Les metriques distinguent performance brute et performance nette quand les frais sont configures.
8. Les valeurs extremes sont signalees: drawdown anormal, serie de pertes, profit factor infini du a trop peu de pertes, ou outlier dominant.

## NFR
1. Les graphiques doivent rester lisibles avec au moins 1 000 trades.
2. Les couleurs ne doivent pas etre le seul moyen de comprendre PASS/FAIL.
3. Les calculs affiches doivent correspondre aux resultats persistes pour le run.
