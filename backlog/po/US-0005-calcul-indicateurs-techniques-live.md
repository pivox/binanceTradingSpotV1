---
id: US-0005
title: "Moteur indicateurs - Calcul en continu des indicateurs techniques"
status: TODO
owner: po
links: ["EPIC-INDICATEURS-LIVE", "US-0001", "US-0004", "US-0007"]
---

## User Story
En tant que trader
Je veux que les indicateurs techniques soient calcules en continu pour chaque pair et timeframe
Afin de prendre des decisions de trading avec des signaux fiables, reproductibles et comparables entre environnements.

## Contexte
- Le systeme produit un snapshot a chaque cloture de bougie (jamais sur bougie en cours).
- Les formules et conventions ci-dessous sont normatives pour eviter toute implementation "a interpretation".
- Les calculs sont bases sur `close`, sauf mention contraire (ATR/ADX utilisent OHLC, VWAP utilise HLC3*volume).

## Specification normative des indicateurs
1. **RSI(14)**
   - Methode Wilder (RMA) sur gains/pertes de `close`.
   - Echelle de sortie: **0 a 100**.
2. **EMA(20/50/200)**
   - Formule EMA standard avec `alpha = 2/(n+1)`.
3. **SMA(9/21)**
   - Moyenne arithmetique simple des `close`.
4. **MACD(12,26,9)**
   - `macd = ema12 - ema26`.
   - `signal = ema(macd, 9)`.
   - `hist = macd - signal`.
5. **Bollinger(20, 2.0)**
   - `middle = sma20(close)`.
   - `upper = middle + 2.0 * stddev(close,20)`.
   - `lower = middle - 2.0 * stddev(close,20)`.
6. **ATR(14)**
   - True Range standard, lissage Wilder (RMA 14).
7. **VWAP(session)**
   - Prix typique `tp = (high + low + close)/3`.
   - `vwap = sum(tp * volume) / sum(volume)` depuis le debut de session.
8. **ADX(14)**
   - +DM/-DM, TR et DI selon Wilder, puis ADX en RMA 14.
   - Echelle de sortie: **0 a 100**.
9. **Stochastic RSI(14,14,3,3)**
   - RSI source = RSI(14) Wilder.
   - `stoch_rsi_raw = (rsi - lowest(rsi,14)) / (highest(rsi,14)-lowest(rsi,14))`.
   - Si denominateur = 0, valeur brute = 0.
   - `%K = SMA(stoch_rsi_raw,3)` et `%D = SMA(%K,3)`.
   - Echelle de sortie: **0 a 1** (pas 0 a 100).
10. **Pivots standards (session precedente)**
   - Calcul sur OHLC de la **session precedente**.
   - `pp=(high+low+close)/3`, `r1=2*pp-low`, `s1=2*pp-high`, `r2=pp+(high-low)`, `s2=pp-(high-low)`, `r3=high+2*(pp-low)`, `s3=low-2*(high-pp)`.
   - Extensions futures possibles `r4..r6` / `s4..s6`.

## Definition de session (obligatoire)
- Pour VWAP et pivots, la session de reference est **UTC 00:00:00 -> 23:59:59**.
- Pas de session locale/exchange configurable en v1 (pour eviter les divergences).
- Pour timeframe >= 1D, la session reste le jour UTC.

## Warmup / disponibilite minimale
- RSI14: 14 bougies.
- EMA20/50/200: 20/50/200 bougies.
- SMA9/21: 9/21 bougies.
- MACD12/26/9: 26 + 9 = 35 bougies minimales.
- Bollinger20: 20 bougies.
- ATR14: 14 bougies.
- ADX14: 28 bougies minimales.
- StochRSI14/14/3/3: 14 (RSI) + 14 (stoch) + 3 (K) + 3 (D) - 3 = 31 bougies minimales.
- VWAP: disponible des la 1ere bougie de session.
- Pivots: disponibles apres cloture de la session precedente.

## Regles de calcul temporelles
1. Calcul uniquement sur bougies **cloturees** (`is_final=true`).
2. En cas de correction tardive ou donnee out-of-order, le moteur recalcule depuis la premiere bougie impactee jusqu'au present.
3. Le recalcul conserve la determinisme: historique identique => valeurs identiques.

## Criteres d'acceptation
1. Le moteur applique strictement les definitions/formules ci-dessus, sans option implicite par librairie.
2. Le snapshot contient pair, timeframe, close_time, timestamp de calcul et valeurs d'indicateurs.
3. Les valeurs indisponibles en warmup suivent le contrat d'indisponibilite defini en US-0007.
4. Les tests de non-regression comparent les valeurs a un jeu de reference fixe multi-environnements.

## NFR
1. Calcul incremental O(1) ou amorti pour les indicateurs compatibles.
2. Pipeline non bloquant pour l'ingestion des bougies.
3. Ecart numerique inter-environnements <= 1e-8 sur les valeurs normalisees.
