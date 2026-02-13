# TL-02 Securite et roles (RBAC)

## Objectif
Restreindre l'acces aux actions Start/Stop aux utilisateurs autorises.

## Scope
- Controle d'acces sur `POST /daemon/start` et `POST /daemon/stop`
- Lecture du status selon regles

## Taches
- Definir roles/permissions (ex: `admin`, `operator`).
- Ajouter middleware/guard d'autorisation.
- Tracer les refus d'acces (log).
- Tests d'integration securite.

## Criteres d'acceptation
- Start/Stop refuses pour utilisateur non autorise (HTTP 403).
- Logs d'acces refuse presents (user + endpoint).

## Dependances
- Systeme d'authentification existant.
