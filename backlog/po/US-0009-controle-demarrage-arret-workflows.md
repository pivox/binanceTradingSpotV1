---
id: US-0009
title: "UI/API - Demarrer et stopper les workflows Temporal"
status: TODO
owner: po
links: ["US-0009", "US-0002", "US-0004", "TL-01", "TL-15"]
---

## User Story
En tant que PO/operateur
Je veux pouvoir demarrer et stopper les workflows critiques depuis l'interface de controle
Afin de maitriser l'execution de la plateforme sans intervention manuelle sur l'infrastructure.

## Contexte
- L'application expose deja un controle `daemon` (status/start/stop) pour la collecte des candles.
- Les workflows Temporal tournent cote worker et portent des traitements critiques (consommation, execution, reconciliation).
- L'exploitation a besoin d'une action rapide en cas d'incident (degradation exchange, erreur de strategie, maintenance).

## Portee fonctionnelle
- Exposer l'etat de chaque workflow critique: `running`, `paused`, `stopped`, `error`.
- Permettre le demarrage et l'arret controle workflow par workflow.
- Permettre une action globale `Stop all` et `Start all` avec confirmation explicite.
- Afficher un retour utilisateur immediat puis un etat consolide apres relecture backend.

## Hors portee
- Edition de la logique metier des workflows.
- Rejeu historique automatique des traitements arretes.
- Gestion fine RBAC multi-profils (couverte par un chantier securite dedie).

## Parcours utilisateur
1. L'utilisateur ouvre l'ecran "Controle workflows" et voit la liste des workflows avec leur etat temps reel.
2. Il clique sur `Stopper` pour un workflow donne.
3. L'UI demande confirmation (`impact`, `workflow`, `environnement`) puis envoie la commande.
4. L'UI affiche un etat intermediaire `stopping...` avec trace horodatee.
5. L'UI rafraichit l'etat backend et confirme `stopped` ou affiche une erreur exploitable.
6. Le meme comportement existe pour `Demarrer` avec etat intermediaire `starting...`.

## Criteres d'acceptation
1. L'ecran liste au minimum: nom workflow, statut courant, date de dernier changement, operateur source.
2. Le bouton `Demarrer` est desactive si le workflow est deja `running`.
3. Le bouton `Stopper` est desactive si le workflow est deja `stopped`.
4. Toute action `Demarrer/Stopper` requiert une confirmation explicite cote UI.
5. En cas de succes, l'UI affiche un message de confirmation et l'etat se met a jour en moins de 2 secondes.
6. En cas d'echec, l'UI affiche un code erreur metier (ex: `already_running`, `already_stopped`, `permission_denied`, `timeout`).
7. Les actions sont idempotentes: rejouer `Demarrer` sur un workflow deja actif ne casse pas le service.
8. L'action globale `Stop all` execute une strategie ordonnee (priorite aux workflows d'execution avant ingestion).
9. L'action globale `Start all` respecte les dependances minimales (ingestion avant workflows consommateurs).
10. Un journal d'audit enregistre chaque commande avec horodatage, acteur, cible, resultat, correlation id.

## API cible (contract first)
- `GET /workflows/status` -> liste des workflows controles et leur etat.
- `POST /workflows/{name}/start` -> demarrage d'un workflow.
- `POST /workflows/{name}/stop` -> arret d'un workflow.
- `POST /workflows/start-all` -> demarrage global ordonne.
- `POST /workflows/stop-all` -> arret global ordonne.

## NFR
1. Disponibilite de l'API de controle >= 99.9% sur plage ouvrable.
2. Temps de reponse P95 des commandes de controle <= 500 ms (hors latence de convergence etat).
3. Propagation de l'etat final en UI <= 2 secondes apres ack backend.
4. Tracabilite complete via logs structures + metriques (`workflow_control_requests_total`, `workflow_control_failures_total`).
5. Les operations de controle sont protegees par authentification forte et autorisation explicite.

## Definition of Done
- Contrat API versionne et documente.
- Tests unitaires des cas nominaux + erreurs + idempotence.
- Tests d'integration sur environnement de staging avec workflows factices.
- Runbook d'exploitation mis a jour (demarrage, arret, rollback, incidents frequents).
- Demonstration PO avec scenario nominal et scenario incident.

## Assumptions
- Le runtime Temporal expose des primitives fiables pour suspendre/reprendre ou terminer/redeclencher les workflows cibles.
- La liste des workflows critiques est stable sur le sprint et maintenue en configuration.
- Un identifiant utilisateur est disponible dans le contexte API pour l'audit.

## Open questions
1. Le "stop" attendu est-il un `pause` reversible ou un `terminate` irreversible + redeploiement ?
2. Faut-il une validation a double confirmation pour les workflows d'execution d'ordres reels ?
3. Quel niveau de granularite doit etre visible en UI: workflow logique, schedule Temporal, ou run instance ?
4. Souhaite-t-on un mode "drain" (laisser finir les runs en cours) avant arret complet ?
5. Quel canal d'alerte est obligatoire en cas d'echec d'une commande de controle (Slack, email, pager) ?
