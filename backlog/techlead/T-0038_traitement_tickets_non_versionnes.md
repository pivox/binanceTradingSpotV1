---
id: T-0038
title: "Traitement - Tickets non versionnes (normalisation et triage dev)"
status: DONE
owner: dev
links: ["T-0029", "T-0030", "T-0031", "T-0032", "T-0033", "T-0034", "T-0035", "T-0036", "T-0037", "US-0009", "US-0010", "US-0011", "US-0012", "US-0013", "US-0014", "US-0015", "US-0016", "US-0017", "US-0018", "US-0019", "US-0020", "US-0021", "US-0022"]
---

## Objectif
Traiter l'ensemble des tickets non versionnes detectes dans le backlog en les rendant exploitables par l'equipe (liens standardises, coherents et triage dev explicite).

## Actions realisees
1. Verification des tickets non versionnes detectes dans Git.
2. Controle de conformite front-matter sur les fichiers `US-0009..US-0022` et `T-0029..T-0037`.
3. Normalisation des liens `links` des US vers des IDs tickets `T-XXXX` actifs:
   - US-0009..US-0014 -> `T-0035`
   - US-0015..US-0021 -> `T-0037`
   - US-0022 -> `T-0036`
4. Normalisation du ticket `T-0036` pour retirer les references legacy `TL-*` dans `links`.
5. Validation qualite locale:
   - `poetry run ruff check .`
   - `poetry run ruff format --check .`
   - `poetry run pytest -q`

## Triage dev (etat courant)
- `T-0030`: TODO (workflows/activities encore partiellement en placeholders TODO).
- `T-0031`: TODO (orchestration runtime backfill non finalisee de bout en bout).
- `T-0032`: TODO (endpoint screener multi-paires non expose).
- `T-0033`: TODO (UI screener dediee non livree).
- `T-0035`: NEEDS_QA (hard cap streams + observabilite reconnexion implementes avec tests unitaires).
- `T-0036`: NEEDS_QA (endpoint `/daemon/permissions` + UX RBAC explicite livres, tests API ajoutes).
- `T-0037`: NEEDS_QA (duree CI exportee, checks secrets deploy, rollback smoke executable, alerting homogenise).

## Resultat
Les tickets non versionnes identifies sont maintenant relies a des tickets dev versionnes et exploitables, avec une base de triage explicite pour la suite d'implementation.
