---
id: US-0003
title: "UI - Selectionner une pair via une liste des pairs disponibles"
status: TODO
owner: po
links: ["US-0003", "US-0001", "US-0002"]
---

## User Story
En tant que trader
Je veux cliquer sur le nom du pair affiche pour ouvrir la liste des pairs disponibles
Afin de changer rapidement de marche a analyser.

## Contexte
- La collecte daemon alimente des symboles Spot (notamment suffixes `USDC`) dans `candles`.
- L'interface doit afficher le graphique du pair choisi apres selection.

## Criteres d'acceptation
1. Le pair courant est visible en haut de la vue chart.
2. Un clic sur ce pair ouvre une liste des pairs disponibles.
3. La liste contient uniquement les pairs presentes dans les donnees BDD.
4. Un clic sur un pair de la liste ferme la liste et recharge le graphique sur ce pair.
5. Le pair selectionne est mis en evidence dans la liste.
6. En cas de liste vide, l'UI affiche un message explicite et aucun crash.

## NFR
1. L'ouverture de la liste doit etre instantanee (< 300 ms cote UI).
2. Le chargement du graphique apres selection de pair doit etre <= 2 secondes.
3. Le composant liste doit rester utilisable au clavier (navigation + validation).

