---
id: US-0024
title: "Epic - Visualisation complete du mode backtesting"
status: TODO
owner: po
links: ["US-0024", "ROADMAP.md"]
---

## User Story
En tant que trader/PO
Je veux disposer d'un espace Backtesting complet, visuel et exploitable
Afin de valider ou invalider la strategie MTF sur donnees historiques avant toute decision de passage vers signal live, paper trading ou execution reelle.

## Contexte
- La Roadmap impose un go/no-go Phase 2 avant Phase 3.
- Le backtesting doit rejouer le MTF Validator sur les snapshots historiques et simuler entree, stop-loss, take-profit, slippage et sorties.
- Les phases Signal Engine, Risk Engine, Paper Trading et Execution Engine ne sont pas toutes finalisees; l'UI doit afficher clairement ce qui est simule, calibre ou non encore pret pour le live.
- Le trader ne doit pas seulement lire des chiffres; il doit pouvoir comprendre visuellement pourquoi une strategie passe ou echoue.

## Perimetre fonctionnel
1. Creer une vue Backtesting dediee, accessible depuis l'UI principale.
2. Permettre la preparation et verification des donnees historiques necessaires.
3. Permettre la configuration d'un run de backtest sans modifier le code.
4. Afficher les resultats sous forme de dashboard trading, graphe, tableau de trades et rapport de decision.
5. Permettre la comparaison de plusieurs runs et calibrations.
6. Encadrer explicitement les limites: frais, slippage, liquidite, look-ahead bias, warmup indicateurs, taille d'echantillon et readiness des phases suivantes.

## Criteres d'acceptation
1. L'utilisateur peut ouvrir un espace `Backtesting` depuis l'interface.
2. L'espace distingue clairement `Preparation`, `Run`, `Resultats`, `Trades`, `Comparaison` et `Rapport`.
3. Les resultats affichent au minimum winrate, profit factor, max drawdown, expectancy, MFE, MAE et statut du gate Phase 2.
4. Le graphe permet de visualiser les entrees, sorties, stop-loss, take-profit et zones de risque par trade.
5. L'utilisateur peut comprendre pourquoi un signal a ete pris ou rejete via le contexte MTF.
6. L'UI indique explicitement qu'aucun ordre reel n'est place depuis le mode backtesting.
7. Les parametres critiques utilises pour le run sont visibles et historises avec le resultat.
8. Les limites connues et points non finalises de la Roadmap sont affiches comme contraintes produit, pas caches dans les logs.

## NFR
1. L'affichage initial des resultats d'un run standard doit etre inferieur a 2 secondes une fois le run termine.
2. Les visualisations doivent rester lisibles sur desktop; mobile doit au minimum permettre consultation et partage.
3. Les chiffres financiers doivent etre arrondis de facon coherente mais les valeurs sources restent accessibles dans le detail.
4. Aucune cle API, secret ou information Binance sensible ne doit etre exposee cote UI.
