---
id: T-0040
title: "Resolution conflits PR-13 + traitement retours MR"
status: NEEDS_QA
owner: dev
links: ["T-0035", "T-0036", "T-0037", "US-0022"]
---

## Objectif
Resoudre les conflits de merge de la PR #13 avec `main`, puis traiter les commentaires de review code associes.

## Conflits resolus
1. `src/tradebot/api/static/index.html`
- Fusion complete des fonctionnalites RBAC daemon + switch de mode.
- Suppression des artefacts de conflit et doublons de code JS.

2. `tests/unit/test_daemon_api.py`
- Fusion des tests permissions RBAC et endpoints mode daemon.
- Conservation des cas payload invalide et refus RBAC sur changement de mode.

## Commentaires de review traites
1. Polling UI asynchrone
- Remplacement du `setInterval(async ...)` par une boucle recursive `setTimeout` pour eviter les recouvrements de requetes.
- Rafraichissement periodique limite au statut/mode daemon; les permissions sont rechargees au chargement et lors du changement d'utilisateur.

2. Coherence terminologique action stop
- UI harmonisee vers "Arreter" / "Daemon arrete" (sans rupture API, endpoint conserve: `POST /daemon/stop`).

3. CI summary fiable
- `.github/workflows/ci.yml`: `overall_status` passe a `failure` si un des outcomes `lint/tests/build` est different de `success` (inclut les cas `skipped` lors d'echec amont).

4. Remarque migrations DB
- Point pris en compte: `Base.metadata.create_all` reste un filet de securite sur DB fraiche.
- Action de suivi recommandee: introduire des migrations versionnees (Alembic) via ticket dedie.

## Validation locale
Commandes a executer:
- `ruff check .`
- `ruff format .`
- `pytest -q`
