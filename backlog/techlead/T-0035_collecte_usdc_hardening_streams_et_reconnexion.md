---
id: T-0035
title: "Collecte USDC - Hardening streams, reconnexion et observabilite"
status: NEEDS_QA
owner: dev
links: ["US-0012", "US-0014", "T-0034"]
---

## Contexte
La collecte dynamique USDC est fonctionnelle (`load_symbols`, `subscribe_in_chunks`, `ws_loop`), mais les NFR demandent des gardes explicites et des signaux d'exploitation plus actionnables.

## Perimetre
- Ajouter un **hard cap** configurable du nombre de streams websocket (ex: `USDC_STREAMS_HARD_CAP`).
- Echouer explicitement au boot si la selection depasse le cap.
- Journaliser chaque tentative de reconnexion avec:
  - numero de tentative,
  - delai applique,
  - cause d'echec precedente,
  - taille de souscription.
- Exposer des compteurs/metriques minimum:
  - `ws_reconnect_total`,
  - `ws_boot_slow_total`,
  - `ws_streams_selected`.
- Ajouter des tests de non-regression sur:
  - depassement hard cap,
  - format des logs de reconnexion,
  - comportement first boot fail-fast conserve.

## Hors perimetre
- Refonte du client websocket Binance.
- Changement du mecanisme de chunking existant.

## Plan d'implementation
1. Introduire lecture/validation `USDC_STREAMS_HARD_CAP` (valeur par defaut documentee).
2. Ajouter garde avant `subscribe_in_chunks`.
3. Structurer le bloc retry/reconnect de `ws_loop` avec compteur de tentative et backoff observable.
4. Instrumenter les metriques necessaires.
5. Completer la suite tests unitaires sur ces cas.

## Tests
- `pytest -q`:
  - test cap depasse -> `RuntimeError` explicite,
  - test reconnect logs/metriques increments,
  - test first boot indisponible -> echec immediat (non regression).

## Criteres d'acceptation
1. Le daemon refuse explicitement une souscription au-dela du cap configure.
2. Les reconnexions sont tracables (tentative, delai, cause, taille).
3. Les metriques de base permettent de diagnostiquer saturation et instabilite.

## Definition of Done
- Code merge avec `ruff check .`, `ruff format .`, `pytest -q` verts.
- Documentation maj dans `docs/` (variables env et interpretation metriques/logs).
