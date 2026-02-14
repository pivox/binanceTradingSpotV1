---
id: T-0022
title: "Backend - Moteur indicateurs normatif et etat incremental"
status: TODO
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
