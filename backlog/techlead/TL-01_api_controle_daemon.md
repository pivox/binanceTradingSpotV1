# TL-01 API controle du daemon (Start/Stop/Status)

## Objectif
Exposer une API backend pour demarrer, stopper et interroger l'etat du daemon.

## Scope
- `GET /daemon/status`
- `POST /daemon/start`
- `POST /daemon/stop`
- Contrat JSON standardise
- Logs d'actions

## Taches
- Definir le contrat API (requests, responses, codes d'erreur).
- Implementer service de controle du process (PID, process absent, permission).
- Ajouter logs structures (timestamp, user, action, resultat).
- Ajouter tests unitaires et tests API.

## Criteres d'acceptation
- Les 3 endpoints repondent en <2s.
- Les erreurs renvoient des codes explicites (`permission_denied`, `process_not_found`, `already_running`, `already_stopped`).
- Un log est ecrit pour chaque commande.

## Dependances
- Mecanisme actuel de lancement/arret du daemon.
