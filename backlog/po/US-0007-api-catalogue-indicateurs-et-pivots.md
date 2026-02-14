---
id: US-0007
title: "API - Exposer un catalogue unifie des indicateurs par pair/timeframe"
status: TODO
owner: po
links: ["EPIC-INDICATEURS-LIVE", "US-0005", "US-0006", "US-0008"]
---

## User Story
En tant que consommateur API (UI ou service externe)
Je veux consulter les indicateurs calcules via un contrat stable et versionne
Afin d'afficher et d'exploiter les signaux sans logique de recalcul cote client.

## Contexte
- L'API doit etre design-first (OpenAPI) pour limiter les regressions de contrat.
- Les sorties multi-valeurs doivent etre namespacees pour eviter collisions futures.

## Contrat de payload (normatif)
- Champs de contexte: `schema_version`, `symbol`, `timeframe`, `close_time`, `computed_at`.
- Champs mono-valeur: `rsi`, `ema20`, `ema50`, `ema200`, `sma9`, `sma21`, `atr`, `vwap`, `adx`.
- Champs multi-valeurs namespaces:
  - `macd: { macd, signal, hist }`
  - `bollinger: { upper, middle, lower }`
  - `stoch_rsi: { k, d }`
  - `pivots: { pp, r1, r2, r3, s1, s2, s3, r4?, r5?, r6?, s4?, s5?, s6? }`
- Representation standard d'indisponibilite par champ:
  - `{ "status": "available", "value": <number> }`
  - `{ "status": "unavailable", "reason": "warmup|missing_history|not_supported" }`

## Criteres d'acceptation
1. Route "dernier snapshot" et route "historique" disponibles pour pair/timeframe.
2. `schema_version` est obligatoire dans chaque reponse et incremente selon regles de versionning documentees.
3. Le schema OpenAPI est publie en design-first et valide en CI (breaking changes detectees).
4. Le "dernier snapshot" supporte cache HTTP conditionnel via `ETag` + `If-None-Match` + reponse `304`.
5. L'historique pagine possede un contrat stable: tri deterministic (`close_time desc`), pagination par curseur opaque, taille max explicite.
6. Les champs indisponibles utilisent la representation standard `status/reason`, jamais un `null` ambigu.
7. Les ajouts de pivots `r4..r6/s4..s6` sont retrocompatibles (ajout de champs optionnels, sans rupture).

## NFR
1. p95 <= 300 ms sur "dernier snapshot" en charge nominale avec cache conditionnel actif.
2. Endpoints observables (latence p50/p95, erreurs, hit ratio cache, volume).
3. Erreurs API normalisees (code, message, categorie, action conseillee).
