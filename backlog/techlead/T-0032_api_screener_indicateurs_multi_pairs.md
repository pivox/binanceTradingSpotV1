---
id: T-0032
title: "API - Endpoint screener indicateurs multi-paires avec filtres et tris"
status: TODO
owner: dev
links: ["US-0008", "US-0007", "T-0029", "T-0024"]
---

## Contexte
US-0008 exige un affichage fluide sur >= 200 paires avec filtres/tris. Les endpoints actuels (`/indicators/latest`, `/indicators/history`) sont centres sur une paire/timeframe et ne suffisent pas pour un screener performant.

## Perimetre
- Ajouter un endpoint dedie screener (proposition: `GET /indicators/screener`).
- Retourner les derniers snapshots multi-symbols pour une timeframe avec:
  - filtres (symbol, indicateur, plage de valeur),
  - tri asc/desc par colonne numerique,
  - pagination curseur opaque et stable.
- Conserver la representation normalisee des indisponibilites (`status/reason`).
- Retourner des metadonnees de fraicheur (`last_updated`, `stale`).
- Documenter le contrat dans OpenAPI et verifier en CI.

## Hors perimetre
- UI du screener (ticket dedie T-0033).
- Persistance serveur des presets utilisateur.

## Proposition contrat v1
- Query params minimum:
  - `timeframe` (required),
  - `limit` (default borne),
  - `cursor` (opaque),
  - `sort_by`, `sort_dir`,
  - filtres simples (`symbol_like`, `rsi_lt`, `rsi_gt`, etc.).
- Reponse:
  - `items[]` avec `symbol`, `timeframe`, `close_time`, `computed_at`, indicateurs normalises,
  - `next_cursor`,
  - `last_updated`,
  - `stale` (bool) + `stale_reason` si applicable.

## Plan d'implementation
1. Definir le contrat OpenAPI du nouvel endpoint.
2. Implementer repository de lecture "latest multi-symbols" avec tri deterministic (tie-break stable).
3. Ajouter validation stricte des params + erreurs normalisees.
4. Ajouter E2E API tests (filtres, tri, pagination, indisponibilite, stale).
5. Instrumenter latence et volumetrie endpoint.

## Tests
- Unitaires:
  - validation params,
  - tri deterministic/reversible,
  - cursor encode/decode.
- Integration:
  - filtres combinables,
  - pagination stable sans doublon/skip,
  - performance nominale sur dataset >= 200 paires.

## Criteres d'acceptation
1. Le screener API sert 200 paires en <= 2s en environnement de test nominal.
2. Les valeurs indisponibles restent explicites (`unavailable + reason`).
3. Tri/pagination sont stables et deterministes.
4. Le schema OpenAPI est versionne et valide en CI.

## Definition of Done
- Code merge avec `ruff check .`, `ruff format .`, `pytest -q` verts.
- Documentation API mise a jour (`docs/openapi-indicators.yaml`, `docs/indicators-api.md`).
