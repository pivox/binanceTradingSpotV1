---
id: US-0004
title: "UI - Mettre a jour le graphique en live a partir des nouvelles bougies BDD"
status: TODO
owner: po
links: ["US-0004", "US-0001", "US-0002", "US-0003"]
---

## User Story
En tant que trader
Je veux que le graphique se mette a jour en live pour la pair/timeframe selectionnee
Afin de suivre le marche sans recharger manuellement la page.

## Contexte
- Le daemon persiste en continu les chandeliers dans la table `candles`.
- L'UI de controle actuelle utilise deja un rafraichissement periodique pour l'etat daemon.

## Criteres d'acceptation
1. L'UI rafraichit periodiquement les donnees du graphique pour la pair/timeframe active.
2. Les nouvelles bougies sont integrees sans perdre la selection courante (pair + timeframe).
3. Le dernier horodatage de mise a jour est visible dans l'UI.
4. Si la source ne renvoie aucune nouveaute, l'UI conserve l'etat affiche sans clignotement.
5. En cas d'erreur temporaire, l'UI garde les donnees deja affichees et indique une erreur non bloquante.
6. Le retour a la normale apres erreur se fait automatiquement au cycle suivant.

## NFR
1. La latence entre disponibilite d'une nouvelle bougie en BDD et affichage UI cible <= 2 secondes.
2. Le mecanisme live ne doit pas provoquer de surcharge notable sur l'API/BDD.
3. Les rafraichissements doivent etre suspendus quand la page n'est plus active si possible.

