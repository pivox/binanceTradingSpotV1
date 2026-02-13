# TL-09 CI de base via GitHub Actions

## Objectif
Mettre en place une CI standard qui se declenche sur push/PR sur main et fournit un status check fiable.

## Scope
- Workflow `.github/workflows/ci.yml`.
- Triggers `push` et `pull_request` sur `main`.
- Installation Python 3.11 + Poetry + deps.
- Concurrency pour annuler les runs obsoletes sur la meme branche.
- Permissions minimales dans le workflow.

## Taches
- Creer le workflow CI avec les triggers attendus.
- Ajouter setup Python + cache (pip/poetry) pour accelerer.
- Installer les deps via `poetry install`.
- Documenter le status check a activer dans les regles de branche (merge bloque si echec).

## Criteres d'acceptation
- Le workflow se declenche sur `push` et `pull_request` sur `main`.
- Le status est visible dans la PR.
- Le merge est bloque si la CI echoue (via regles de branche documentees).

## Dependances
- Acces a la configuration GitHub (branch protection).
