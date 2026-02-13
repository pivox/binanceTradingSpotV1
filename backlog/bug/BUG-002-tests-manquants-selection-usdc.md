---
id: B-0002
title: "Tests manquants pour la selection dynamique USDC (TL-04/05/06/08)"
status: VALIDATED
owner: qa
links: ["B-0002", "TL-04", "TL-05", "TL-06", "TL-08"]
---

# BUG-002 - Tests manquants pour la selection dynamique USDC (TL-04/05/06/08)

## Contexte
Les tickets TL-04 a TL-08 demandent explicitement des tests (non-regression, reconnect, erreurs API, validation env).

## Description
Il n'y a pas de coverage de tests sur le chemin "selection dynamique" de `load_symbols()` (sans `SYMBOLS`):
- Filtrage `*USDC` depuis la reponse `/api/v3/ticker/24hr`
- Tri par `quoteVolume` (decroissant)
- Application de `USDC_PAIRS_LIMIT` (valeur par defaut + validation)
- Echec explicite si l'API Binance est indisponible au premier boot
- Log "top" des premieres paires retenues (audit)

Actuellement, seuls les cas suivants sont testes:
- Override `SYMBOLS` (tests/unit/test_symbols_override.py)
- Chunking `SUBSCRIBE` (tests/unit/test_symbols_override.py)

## Impact
- Risque de regression sur un chemin critique (startup/reconnect).
- Les criteres d'acceptation des tickets TL-04/05/06/08 ne sont pas verifies automatiquement.

## Proposition de tests
- Ajouter des tests unitaires qui patchent `fetch_24h_tickers()` pour retourner des tickers synthetiques:
  - Verifier filtrage `USDC` uniquement
  - Verifier ordre decroissant par `quoteVolume`
  - Verifier limite `USDC_PAIRS_LIMIT` + erreurs (0, negatif, non numerique)
- Ajouter un test "first boot API down" au niveau de `ws_loop()` (ou d'une fonction extraite) pour valider le comportement "fail fast".

## Critere de cloture
- Tests couvrant TL-04/05/06/08 (chemin sans override) passent et echouent de facon deterministe.
