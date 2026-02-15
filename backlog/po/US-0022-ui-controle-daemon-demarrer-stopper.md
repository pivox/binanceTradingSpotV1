---
id: US-0022
title: "UI - Controler le daemon (etat, demarrer, stopper) avec feedback"
status: TODO
owner: po
links: ["EPIC-CONTROLE-DAEMON", "T-0036"]
---

## User Story
En tant que utilisateur de l'application
Je veux une interface UI pour afficher l'etat du daemon et le demarrer/stopper
Afin de controler l'execution du service sans passer par la ligne de commande.

## Contexte
- Le backend expose des endpoints de controle (`/daemon/status`, `/daemon/start`, `/daemon/stop`).
- Les actions Start/Stop doivent etre restreintes aux utilisateurs autorises (RBAC).

## Criteres d'acceptation
1. L'UI affiche l'etat courant du daemon (`running` ou `stopped`) et le rafraichit regulierement.
2. L'utilisateur peut demarrer le daemon via un bouton `Demarrer`.
3. L'utilisateur peut stopper le daemon via un bouton `Stopper`.
4. Les actions `Demarrer` et `Stopper` retournent un feedback visuel explicite (succes/erreur) avec un message exploitable.
5. Si le daemon est deja demarre, le bouton `Demarrer` est desactive; si le daemon est deja stoppe, le bouton `Stopper` est desactive.
6. En cas d'echec (ex: permission, process introuvable), un message d'erreur exploitable est affiche (sans crash UI).
7. Si RBAC est active, Start/Stop sont inaccessibles aux utilisateurs non autorises (etat des boutons + message) et les erreurs 403 sont gerees proprement.

## NFR
1. La mise a jour de l'etat dans l'UI apres action doit etre <= 2 secondes.
2. Les commandes de controle du daemon sont journalisees (horodatage, utilisateur, action, resultat).
