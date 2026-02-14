---
id: T-0024
title: "API - Catalogue indicateurs versionne, historique curseur et cache ETag"
status: NEEDS_QA
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

## Journal Dev (2026-02-14)
### Livre
- Ajout du modele DB `indicator_snapshots`:
  - contexte versionne (`schema_version`, `symbol`, `timeframe`, `close_time_ms`, `computed_at_ms`).
  - payload JSON indicateurs et `etag` stable.
- Implementation repository `IndicatorRepository`:
  - upsert snapshot versionne.
  - lecture "latest snapshot" + ETag.
  - historique tri `close_time desc` avec pagination par curseur opaque stable.
- API exposee dans `src/tradebot/api/app.py`:
  - `GET /indicators/latest` (support `If-None-Match` -> `304`).
  - `GET /indicators/history` (limit borne + curseur opaque).
  - erreurs normalisees: `code`, `message`, `categorie`, `action_conseillee`.
  - `schema_version` present dans les reponses historiques et dans chaque snapshot.
- Design-first/OpenAPI:
  - ajout de `docs/openapi-indicators.yaml`.
  - documentation d'usage `docs/indicators-api.md`.
- Tests ajoutes `tests/unit/test_indicator_api.py`:
  - validation 200/304 sur latest avec ETag.
  - pagination curseur deterministe.
  - erreur `invalid_cursor` normalisee.
- Test contrat OpenAPI ajoute: `tests/unit/test_openapi_indicators.py`.

## Journal Dev (2026-02-14) - Correctifs QA/MR
### Corrige
- B-0010: ETag `latest` maintenant sensible au payload (hash inclut representation JSON canonique du payload).
- MR: `_parse_limit` clamp le `default_limit` avec `max_limit` quand `limit` est absent.
- MR: `_decode_cursor` capture uniquement les erreurs attendues (`binascii/json/key/type/value`), plus de `except Exception` large.
- MR: simplification `_request_logger` (correlation_id prise depuis le middleware).

### Validation
- Ajout test non-regression `test_upsert_snapshot_recomputes_etag_when_payload_changes`.
- Ajout test non-regression `test_indicators_history_default_limit_is_clamped_by_configured_max`.

## Journal Dev (2026-02-14) - Retours MR supplementaires
### Corrige
- Protection RBAC ajoutee sur:
  - `GET /indicators/latest`
  - `GET /indicators/history`
  - `GET /metrics`
- Hardening RBAC: le header utilisateur n'est pris en compte que si `request.remote` appartient a la allowlist `rbac_trusted_proxy_ips`.
- `updated_at` des modeles DB critiques passe en auto-update (`onupdate=func.now()`).
- Hardening auth proxy: ajout d'un secret partage (`rbac_proxy_shared_secret`) exige via header `X-RBAC-Proxy-Token` quand RBAC est active.
- Simplification `_request_logger` alignee sur le middleware (correlation id attendu dans le contexte requete).

### Validation
- Ajout test `test_indicators_and_metrics_are_rbac_protected` (controle acces + proxy non fiable refuse).
