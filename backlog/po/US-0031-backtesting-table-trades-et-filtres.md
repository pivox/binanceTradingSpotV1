---
id: US-0031
title: "Backtesting - Explorer la table des trades simules"
status: TODO
owner: po
links: ["US-0024", "US-0028", "US-0029", "US-0030"]
---

## User Story
En tant que trader
Je veux explorer tous les trades simules dans une table detaillee
Afin d'identifier les patterns de gains, pertes, drawdown et erreurs de calibration.

## Contexte
- Une visualisation complete doit permettre de passer du dashboard global au trade unitaire.
- Les trades doivent etre triables et filtrables par resultat, duree, setup, score, timeframe et raison de sortie.

## Criteres d'acceptation
1. La table affiche au minimum symbole, date entree, date sortie, setup, score, entry, SL, TP, exit, pnl R, pnl net, MFE, MAE, duree et raison de sortie.
2. L'utilisateur peut filtrer gagnants, perdants, ouverts, SL, TP et signaux par setup.
3. L'utilisateur peut trier par pnl R, drawdown intra-trade, duree, score et date.
4. Un clic sur une ligne synchronise le graphe sur le trade choisi.
5. La table affiche un resume des filtres actifs et le nombre de trades concernes.
6. L'utilisateur peut isoler les pires trades, les meilleurs trades et les trades avec MAE elevee.
7. Les trades ouverts en fin de periode sont identifies et exclus ou inclus selon la metrique affichee.

## NFR
1. La table doit rester utilisable avec plusieurs milliers de lignes via pagination ou virtualisation.
2. Les exports ne doivent pas bloquer l'interface.
3. Les colonnes critiques doivent rester visibles sur desktop.
