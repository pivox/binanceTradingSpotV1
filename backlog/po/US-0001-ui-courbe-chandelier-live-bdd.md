---
id: US-0001
title: "UI - Afficher la courbe chandelier d'un token en live depuis la BDD"
status: TODO
owner: po
links: ["US-0001"]
---

## User Story
En tant que trader
Je veux afficher la courbe chandelier d'un token dans l'interface
Afin de suivre l'evolution du prix en m'appuyant sur les donnees stockees en base.

## Contexte
- Les chandeliers sont persistes dans la table `candles`.
- La cle metier est `(symbol, timeframe, open_time_ms)`.
- L'interface existante est aujourd'hui centree sur le controle du daemon, sans vue chart.

## Criteres d'acceptation
1. L'utilisateur peut ouvrir un ecran "Chart" depuis l'UI.
2. A l'ouverture, l'UI charge un historique initial de chandeliers depuis la BDD pour une paire et une timeframe.
3. Chaque chandelier affiche au minimum `open`, `high`, `low`, `close`, `open_time_ms`.
4. Les donnees affichees proviennent uniquement de la BDD locale (pas d'appel direct Binance cote UI).
5. En cas d'absence de donnees pour la selection, l'UI affiche un etat vide explicite.
6. En cas d'erreur de lecture des donnees, l'UI affiche un message exploitable (sans crash).

## NFR
1. Le premier affichage du graphique doit etre <= 2 secondes pour un volume standard.
2. Le rendu doit rester lisible sur desktop et mobile.
3. Les erreurs de chargement doivent etre journalisees cote serveur.

