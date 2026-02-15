---
id: B-0008
title: "Demarrage daemon depuis UI: crash au bootstrap DB et etat trompeur, chart indisponible"
status: VALIDATED
owner: qa
links: ["B-0008", "TL-01", "T-0016", "T-0017", "T-0020"]
---

# BUG-008 - Demarrage daemon et chargement chart KO

## Contexte
Depuis l'interface, le bouton `Demarrer` lancait le daemon websocket via l'API de controle.

## Description
Deux problemes ont ete observes:
- Le daemon plante au demarrage avec `RuntimeError: DATABASE_URL env is empty` quand les variables ne sont pas transmises au sous-processus.
- Le status daemon peut rester `running` alors que le process a deja quitte (processus zombie), ce qui masque l'echec reel.

Effet secondaire cote chart:
- Les endpoints `/chart/*` ne se chargent pas quand la stack DB est indisponible/mal configuree, et l'UI affiche une erreur generique de chargement des chandeliers.

## Impact
- Bouton `Demarrer` non fiable: faux positif "running".
- Pas d'alimentation des chandeliers en base.
- Ecran chart inutilisable (erreur chargement).

## Correctif implemente
- Injection explicite des variables d'environnement critiques dans le sous-processus daemon.
- Alignement de l'interpreteur du daemon sur celui de l'API (`sys.executable`).
- Verification de sante au demarrage: si le process sort immediatement, retour `start_failed` et pas d'ecriture PID.
- Detection des processus zombies pour eviter un status `running` errone.
- Chargement `.env` au bootstrap API/daemon.
- Normalisation des DSN `postgresql+...://` vers un format accepte par `asyncpg`.

## Resultat attendu
- `POST /daemon/start` echoue explicitement si le daemon ne tient pas le demarrage.
- `GET /daemon/status` ne retourne pas `running` pour un processus zombie.
- Le chart recharge des donnees si la connexion DB est valide.

## Critere de cloture
- Reproduction KO avant fix / OK apres fix.
- Tests verts (`pytest -q`) et lint vert (`ruff check .`).
- Validation QA sur demarrage/stop daemon + page chart.
