---
id: T-0012
title: "CI - Publication d'artefacts"
status: VALIDATED
owner: dev
links: ["TL-12"]
---

## Contexte
Publier des artefacts de build et des logs pour faciliter le diagnostic.

## Perimetre
- Build `poetry build` -> `dist/`.
- Logs/tests dans `artifacts/`.
- Upload artefacts avec retention.

## Plan
1. Ajouter step `poetry build`.
2. S'assurer que `artifacts/` existe (junit).
3. Uploader `dist/` + `artifacts/`.

## Definition of Done
- Artefacts publies a chaque run reussi.
- Retention configuree.
