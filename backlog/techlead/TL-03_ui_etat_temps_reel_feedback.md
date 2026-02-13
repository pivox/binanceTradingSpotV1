# TL-03 UI etat temps reel + feedback

## Objectif
Afficher l'etat courant et fournir un feedback explicite apres action.

## Scope
- Affichage `running/stopped`
- Boutons `Demarrer/Stopper`
- Feedback visuel succes/erreur
- Refresh <2s

## Taches
- Integrer `GET /daemon/status`.
- Declencher `POST /daemon/start` et `POST /daemon/stop`.
- Mettre en place polling 1-2s ou mecanisme push.
- Gerer erreurs cote UI avec messages exploitables.

## Criteres d'acceptation
- Etat UI mis a jour en <2s apres action.
- Boutons desactives selon l'etat.
- Message d'erreur clair en cas d'echec.

## Dependances
- Ticket TL-01 (API controle).
