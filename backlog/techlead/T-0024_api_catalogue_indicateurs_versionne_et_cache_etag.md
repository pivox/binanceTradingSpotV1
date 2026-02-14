---
id: T-0024
title: "API - Catalogue indicateurs versionne, historique curseur et cache ETag"
status: TODO
owner: techlead
links: ["US-0007", "US-0005", "US-0006", "T-0021"]
---

## Contexte
US-0007 impose un contrat API stable/versionne avec representation explicite des indisponibilites, historique pagine et cache conditionnel.

## Perimetre
- Publier OpenAPI design-first du catalogue indicateurs.
- Implementer endpoint dernier snapshot (`ETag`/`If-None-Match`/`304`).
- Implementer endpoint historique tri `close_time desc` + curseur opaque.
- Normaliser erreurs API (`code`, `message`, `categorie`, `action conseillee`).

## Hors perimetre
- UX du screener frontend.

## Plan d'implementation
1. Spec OpenAPI + validation CI breaking changes.
2. Mapping payload snapshot vers format `status/reason`.
3. ETag stable derive du snapshot versionne.
4. Pagination curseur opaque bornee (taille max).

## Tests
- Contract tests OpenAPI.
- Tests conditionnels HTTP 200/304.
- Tests pagination deterministe et retrocompatibilite champs optionnels pivots.

## Criteres d'acceptation
1. `schema_version` present sur chaque reponse.
2. Aucun `null` ambigu pour indisponibilite.
3. p95 endpoint "dernier snapshot" <= 300ms en nominal.
