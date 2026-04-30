---
id: US-0025
title: "Backtesting - Verifier la disponibilite des donnees historiques"
status: TODO
owner: po
links: ["US-0024", "US-0006", "US-0007"]
---

## User Story
En tant que trader
Je veux verifier que les donnees historiques sont suffisantes avant de lancer un backtest
Afin d'eviter des resultats trompeurs lies aux gaps, au warmup incomplet ou a une periode trop courte.

## Contexte
- La strategie MTF depend des timeframes 4h, 1h, 15m, 5m et 1m.
- Les indicateurs comme EMA200, VWAP, ADX, RSI, MACD et pivots ont des besoins de warmup differents.
- Un backtest qui ignore des gaps ou des snapshots incomplets peut surestimer la performance.

## Criteres d'acceptation
1. L'utilisateur choisit un symbole, une periode et un profil de strategie.
2. L'UI affiche pour chaque timeframe le nombre de bougies disponibles, le premier timestamp, le dernier timestamp et le taux de couverture.
3. L'UI indique les gaps detectes et leur impact estime sur le backtest.
4. L'UI affiche l'etat de warmup des indicateurs requis avant validation du run.
5. Si les donnees sont insuffisantes, l'utilisateur voit une raison claire: periode trop courte, timeframe manquante, gaps bloquants ou snapshots absents.
6. L'utilisateur peut demander un backfill preparatoire quand une plage manque, sans quitter la vue.
7. Le backtest ne peut pas etre lance en mode "decision go/no-go" si les donnees critiques ne sont pas pretes.

## NFR
1. Le diagnostic de disponibilite doit etre calculable sans appel direct Binance cote navigateur.
2. Les seuils de suffisance doivent etre explicites et auditables.
3. Les controles doivent prevenir le look-ahead bias: seules les donnees disponibles a l'instant simule sont prises en compte.
