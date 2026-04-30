---
id: US-0029
title: "Backtesting - Visualiser les trades sur le graphe des chandeliers"
status: TODO
owner: po
links: ["US-0024", "US-0001", "US-0002", "US-0028"]
---

## User Story
En tant que trader
Je veux voir les trades simules directement sur le graphe de prix
Afin de comprendre la qualite des entrees, des stops, des take-profits et des conditions de marche.

## Contexte
- Une performance agregee peut cacher de mauvaises entrees ou une exposition mal geree.
- Le backtest simule une entree au close 5m, un stop pivot/ATR et un take-profit en multiple de R.

## Criteres d'acceptation
1. Le graphe affiche les chandeliers de la periode du backtest.
2. Chaque trade simule affiche un marqueur d'entree, un marqueur de sortie et une ligne reliant le trade.
3. Le stop-loss, le take-profit et la distance R sont visibles pour le trade selectionne.
4. Les trades gagnants, perdants et ouverts sont distinguables sans masquer le prix.
5. L'utilisateur peut cliquer un trade depuis le graphe pour ouvrir son detail.
6. Le detail affiche entry price, exit price, SL, TP, pnl R, MFE, MAE, duree et raison de sortie.
7. L'utilisateur peut afficher ou masquer les indicateurs utilises par la strategie: EMA20/50/200, VWAP, RSI, MACD, ADX, ATR, pivots.
8. Le graphe permet de naviguer vers le trade precedent ou suivant.
9. Quand un trade touche SL et TP dans la meme bougie, l'UI indique la regle pessimiste utilisee.

## NFR
1. Les overlays ne doivent pas rendre les chandeliers illisibles.
2. La navigation doit rester fluide sur une periode longue.
3. Les prix doivent respecter la precision du symbole quand elle est disponible.
