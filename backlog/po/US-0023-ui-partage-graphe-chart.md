---
id: US-0023
title: "UI - Partager un graphe via un lien partageable"
status: TODO
owner: po
links: ["US-0023", "US-0001", "US-0002", "US-0003", "US-0004"]
---

## User Story
En tant que trader
Je veux partager un graphe deja configure avec un tiers
Afin qu'il puisse ouvrir exactement la meme vue d'analyse.

## Contexte
- La page `/chart` permet deja de consulter un graphe pour une pair et une timeframe.
- La valeur de partage repose sur la capacite a retrouver le meme contexte visuel sans reconfiguration manuelle.
- Le partage doit au minimum conserver la pair et la timeframe actives, et si disponible les options d'affichage actives du graphe.

## Criteres d'acceptation
1. L'UI propose une action visible `Partager` depuis la vue graphe.
2. Un clic sur `Partager` genere un lien copiable ouvrant la meme vue graphe.
3. Le lien partage restaure au minimum la pair et la timeframe actives.
4. Si des options d'affichage du graphe sont actives au moment du partage, elles sont restaurees quand cela est supporte.
5. L'utilisateur obtient un retour explicite quand le lien est copie ou pret a etre partage.
6. L'ouverture du lien partage affiche directement le graphe sans reconfiguration manuelle supplementaire.
7. En cas d'impossibilite de generer le lien, l'UI affiche une erreur exploitable sans perdre la vue courante.

## NFR
1. La generation du lien de partage doit etre quasi immediate (< 500 ms cote UI).
2. Le mecanisme de partage ne doit pas exposer de secret, de token, ni d'information sensible dans l'URL.
3. Le lien doit rester compatible avec un usage desktop et mobile.
