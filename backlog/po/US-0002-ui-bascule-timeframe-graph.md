---
id: US-0002
title: "UI - Basculer entre les timeframes du graphique chandelier"
status: TODO
owner: po
links: ["US-0002", "US-0001"]
---

## User Story
En tant que trader
Je veux changer rapidement de timeframe sur le graphique
Afin d'analyser le marche a differentes echelles de temps.

## Contexte
- Les timeframes actuellement produites par la collecte sont `1m`, `5m`, `15m`, `1h`, `4h`.
- La table `candles` stocke les donnees par `symbol` et `timeframe`.

## Criteres d'acceptation
1. L'UI propose un selecteur de timeframe visible sur la vue chart.
2. Les options minimales disponibles sont `1m`, `5m`, `15m`, `1h`, `4h`.
3. Au clic sur une timeframe, le graphique se recharge avec les chandeliers de cette timeframe.
4. La timeframe active est visuellement identifiable.
5. La selection de timeframe est conservee lors des rafraichissements live.
6. Si une timeframe n'a pas de donnees pour la paire choisie, l'UI affiche un etat vide explicite.

## NFR
1. Le changement de timeframe doit mettre a jour la vue en <= 2 secondes.
2. Le composant de selection ne doit pas bloquer l'interface pendant le chargement.

