---
id: US-0026
title: "Backtesting - Configurer un run sans modifier le code"
status: TODO
owner: po
links: ["US-0024", "US-0025", "ROADMAP.md"]
---

## User Story
En tant que trader
Je veux configurer un run de backtest depuis l'UI
Afin de tester plusieurs hypotheses de strategie, risque et execution simulee sans intervention technique.

## Contexte
- La Roadmap Phase 2 prevoit de calibrer `k_atr`, `r_multiple`, les seuils RSI/ADX et le score minimum.
- Les entrees sont simulees au close de la bougie 5m de declenchement avec slippage estime.
- Les stops utilisent pivots S1/S2 ou fallback ATR, avec distance max.

## Criteres d'acceptation
1. L'utilisateur peut saisir symbole, plage de dates, profil YAML, capital de reference, risque par trade et devise de reference.
2. L'utilisateur peut configurer slippage, frais, `k_atr`, `r_multiple`, distance stop max et buffer pivot.
3. L'utilisateur voit les valeurs par defaut recommandees par la Roadmap avant de les modifier.
4. L'UI indique si un parametre sort d'une zone raisonnable pour du Spot Binance.
5. L'utilisateur peut choisir un mode `exploration` ou `gate Phase 2`.
6. En mode `gate Phase 2`, les criteres winrate > 50%, profit factor > 1.3 et max drawdown < 15% sont appliques.
7. Le lancement cree un run identifiable avec configuration immuable, horodatage et auteur si disponible.
8. L'utilisateur voit immediatement que le run est une simulation et ne peut pas declencher d'ordre reel.

## NFR
1. Les champs numeriques doivent avoir validation front et back.
2. Les unites doivent etre explicites: pourcentage, USDC, R multiple, millisecondes ou nombre de bougies.
3. Une configuration de run doit etre serialisable pour repetition exacte.
