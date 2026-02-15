---
id: T-0034
title: "Solution - Lot 3 pour US non versionnees (collecte USDC, UI daemon, CI/CD)"
status: TODO
owner: techlead
links: ["US-0009", "US-0010", "US-0011", "US-0012", "US-0013", "US-0014", "US-0015", "US-0016", "US-0017", "US-0018", "US-0019", "US-0020", "US-0021", "US-0022", "T-0035", "T-0036", "T-0037"]
---

## Contexte
Les US non versionnees du PO (`us_collecte_dynamique_klines_spot_usdc.md`, `us_workflows_ci_deploiement_trading.md`, `us_ui_demarrer_stopper_daemon.md`) sont maintenant declinees en US versionnees `US-0009` a `US-0022`.

Le socle est deja en place:
- collecte dynamique USDC et websocket operationnels,
- API/UI de controle daemon en place,
- workflows CI/CD + mode execution securise deja livres.

## Ecarts restants
1. **Collecte USDC (US-0012/US-0014)**: il manque un garde explicite contre une explosion de streams et une observabilite plus actionnable des cycles de reconnexion/backoff.
2. **UI daemon + RBAC (US-0022)**: le backend RBAC existe, mais l'UI ne derive pas explicitement les permissions pour desactiver/afficher clairement les actions autorisees.
3. **CI/CD operations (US-0015..US-0021)**: les workflows existent, mais la preuve operationnelle (SLO CI, rollback teste, checks environnement deploy) reste partielle.

## Strategie
1. Ajouter une couche de hardening runtime sur la collecte USDC.
2. Aligner l'UX UI daemon avec les permissions RBAC exposees par l'API.
3. Completer l'operabilite CI/CD avec des gardes et evidences automatisees.

## Tickets dev proposes
1. `T-0035` - Hardening collecte USDC (caps streams + logs reconnect + tests).
2. `T-0036` - UI daemon RBAC-aware (permissions explicites + boutons etats coherents).
3. `T-0037` - CI/CD finalisation operationnelle (SLO, rollback, checks deploy).

## Ordre recommande
1. T-0035
2. T-0036
3. T-0037

## Criteres d'acceptation
1. Les ecarts restants des US-0009..US-0022 sont couverts par des tickets dev actionnables.
2. Chaque ticket contient perimetre, tests et DoD clairs.
3. Les liens US/tickets sont explicites et exploitables par dev/QA.
