---
id: T-0036
title: "UI Daemon - Aligner UX avec RBAC et permissions explicites"
status: NEEDS_QA
owner: dev
links: ["US-0022", "T-0034"]
---

## Contexte
Le backend applique RBAC sur `/daemon/status`, `/daemon/start`, `/daemon/stop`, mais l'UI ne presente pas explicitement les permissions de l'utilisateur et ne gere pas finement l'etat des boutons en mode RBAC.

## Perimetre
- Ajouter un endpoint de permissions (proposition: `GET /daemon/permissions`) retournant:
  - utilisateur resolu,
  - roles,
  - `can_read_status`,
  - `can_start`,
  - `can_stop`.
- Mettre a jour l'UI (`index.html`) pour:
  - desactiver `Demarrer`/`Stopper` selon permissions,
  - afficher un etat "lecture seule" ou "non autorise" explicite,
  - conserver un message d'erreur exploitable en cas de 403.
- Ajouter tests API + UI logique JS (au minimum unitaires JS ou tests d'integration API).

## Hors perimetre
- Changement de modele RBAC (roles/regles).
- SSO/IdP complet.

## Plan d'implementation
1. Exposer `GET /daemon/permissions` en reutilisant la logique RBAC existante.
2. Adapter le script UI pour charger permissions au demarrage et apres changement utilisateur.
3. Synchroniser l'etat des boutons avec `permissions + status`.
4. Gerer proprement les cas denies (403) sans etat trompeur.
5. Ajouter tests de non-regression.

## Tests
- API:
  - permissions refusees/autorisees selon roles.
- UI:
  - boutons desactives si `can_start/can_stop=false`,
  - message explicite quand actions refusees.

## Criteres d'acceptation
1. En RBAC active, l'UI reflete clairement ce qui est autorise ou non.
2. Les boutons Start/Stop ne proposent pas une action interdite sans indication.
3. Les erreurs 403 restent non bloquantes et comprehensibles.

## Definition of Done
- Code merge avec `ruff check .`, `ruff format .`, `pytest -q` verts.
- Documentation UI/API mise a jour (`docs/ui.md` ou equivalent).
