---
id: B-0013
title: "T-0035: documentation env/metriques de hardening websocket manquante"
status: VALIDATED
owner: qa
links: ["B-0013", "T-0035", "US-0012", "US-0014"]
---

# B-0013 - DoD documentaire non satisfaite pour T-0035

## Contexte
La DoD de `T-0035` exige une mise a jour `docs/` pour:
- les variables env (`USDC_STREAMS_HARD_CAP`, backoff reconnect),
- l'interpretation des metriques/logs de reconnexion.

## Reproduction
1. Executer:
```bash
rg -n "USDC_STREAMS_HARD_CAP|WS_RECONNECT_BASE_DELAY_S|tradebot_ws_reconnect_total|tradebot_ws_boot_slow_total|tradebot_ws_streams_selected" docs -g '*.md'
```
2. Observer: aucune occurrence.

## Resultat observe
- Le code et les tests existent, mais la documentation d'exploitation n'a pas ete ajoutee dans `docs/`.

## Resultat attendu
- Documentation explicite dans `docs/` des nouvelles variables, metriques et logs introduits par `T-0035`.

## Impact
- Exploitation et diagnostic incomplets en production.
- Ticket `T-0035` non conforme a sa Definition of Done.

## References
- `backlog/techlead/T-0035_collecte_usdc_hardening_streams_et_reconnexion.md:54`
- `docs/observability-indicators-live.md`
- `docs/runbook-indicators-live.md`
