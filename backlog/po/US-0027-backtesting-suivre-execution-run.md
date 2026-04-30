---
id: US-0027
title: "Backtesting - Suivre l'execution et l'historique des runs"
status: TODO
owner: po
links: ["US-0024", "US-0026"]
---

## User Story
En tant que trader
Je veux suivre l'avancement et retrouver l'historique de mes runs de backtest
Afin de ne pas perdre le contexte d'une calibration et de pouvoir reprendre une analyse plus tard.

## Contexte
- Les runs peuvent etre courts ou longs selon la periode, les timeframes et le nombre de symboles.
- Les resultats doivent rester auditables et comparables apres execution.

## Criteres d'acceptation
1. Apres lancement, l'utilisateur voit un etat du run: pending, running, completed, failed ou cancelled.
2. L'UI affiche progression, symbole, periode, profil, nombre de snapshots analyses et temps ecoule.
3. En cas d'erreur, l'UI affiche une cause exploitable: donnees manquantes, config invalide, erreur DB ou timeout.
4. L'utilisateur peut consulter la liste des runs precedents avec filtres par symbole, periode, profil et statut.
5. Chaque run affiche son identifiant, sa configuration, ses resultats synthetiques et un lien vers le detail.
6. L'utilisateur peut relancer un run avec la meme configuration.
7. L'utilisateur peut annuler un run non termine si l'infrastructure le supporte.

## NFR
1. La liste des runs doit etre paginee.
2. Les erreurs doivent etre journalisees avec correlation id.
3. Le suivi d'avancement ne doit pas bloquer l'API chart existante.
