---
id: T-0022
title: "Backend - Moteur indicateurs normatif et etat incremental"
status: IN_PROGRESS
owner: techlead
links: ["US-0005", "T-0021"]
---

## Contexte
US-0005 impose des formules normatives et un comportement strict sur bougies closes, warmup et recalcul suite aux corrections tardives.

## Perimetre
- Implementer moteur indicateurs incremental par `(symbol,timeframe)`.
- Implementer RSI, EMA, SMA, MACD, Bollinger, ATR, VWAP, ADX, Stoch RSI, Pivots selon spec.
- Gerer warmup et indisponibilite standardisable (`available/unavailable`).
- Supporter recalcul segmentaire depuis premiere bougie impactee.

## Hors perimetre
- Contrat HTTP final (traite par ticket API).

## Plan d'implementation
1. Structurer module `indicator_engine` + registries indicateurs.
2. Ajouter etat incremental persistant (`indicator_state`).
3. Implementer detecteur de correction/out-of-order + replay cible.
4. Exporter snapshot normalise pret pour API.

## Tests
- Unitaires par indicateur (jeu de reference fixe).
- Integration replay correction tardive.
- Non-regression numerique inter-env (tolerance <= 1e-8).

## Criteres d'acceptation
1. Toutes formules US-0005 respectees sans options implicites.
2. Recalcul deterministic valide par tests.
3. Warmup correctement mappe vers indisponibilite.

## Journal Dev (2026-02-14)
### Livre
- Implementation du socle indicateurs dans `src/tradebot/services/indicators/`:
  - `EMA`, `RSI`, `MACD`, `ATR` (Wilder/alpha standard).
  - Snapshot normalise via `build_indicator_snapshot` avec:
    - `schema_version`, `symbol`, `timeframe`, `close_time`, `computed_at`.
    - format `available/unavailable` + `reason` (`warmup`, `missing_history`).
    - indicateurs: `rsi`, `ema20/50/200`, `sma9/21`, `macd`, `bollinger`, `atr`, `vwap`, `adx`, `stoch_rsi`, `pivots`.
- Ajout des tests unitaires dans `tests/unit/test_indicators.py` (formules et contrat snapshot).

### Reste a faire
- Etat incremental persistant par `(symbol,timeframe)` (`indicator_state` en DB).
- Recalcul segmentaire automatique depuis la premiere bougie impactee lors des corrections/out-of-order.
- Branchement du moteur sur le pipeline d'activites/workflows + persistence snapshot en base.
