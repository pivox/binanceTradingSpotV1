---
id: TL-12
title: "CI - Publication d'artefacts"
status: DONE
owner: techlead
links: ["TL-12"]
---

# TL-12 CI - Publication d'artefacts

## Objectif
Publier des artefacts de build et des logs pour faciliter le diagnostic.

## Scope
- Artefacts `dist/` (ex: `poetry build`).
- Logs/tests (ex: `artifacts/pytest.xml`, logs CI).
- Retention configuree (ex: 7 jours).

## Taches
- Ajouter une etape `poetry build` pour generer `dist/`.
- Normaliser un dossier `artifacts/` pour les logs/tests.
- Ajouter `actions/upload-artifact` pour build + logs.
- Configurer la retention des artefacts.

## Criteres d'acceptation
- Un artefact est publie a chaque run reussi.
- L'artefact contient le build et les logs.
- La retention est configuree (ex: 7 jours).

## Dependances
- TL-09.
- TL-10.
