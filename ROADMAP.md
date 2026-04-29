# ROADMAP — Système de Trading MTF Binance Spot

## État actuel (déjà implémenté)

| Couche | Statut |
|--------|--------|
| WebSocket Binance → klines 1m | ✅ |
| Agrégation multi-timeframe (1m → 5m/15m/1h/4h) | ✅ |
| Stockage PostgreSQL | ✅ |
| Reconciliation / backfill via Temporal | ✅ |
| Calcul indicateurs (RSI, ATR, EMA, MACD, Bollinger, ADX, VWAP) | ✅ |
| API aiohttp (candles, indicateurs) | ✅ |
| Frontend chart canvas (zoom, pan, scroll historique, gaps) | ✅ |

---

## Clarifications de périmètre

- **Marché cible : Binance Spot uniquement.** Pas de short-selling — signaux `LONG` et `NO_TRADE` uniquement. Extension Futures/Margin hors scope.
- **Temporal n'est pas adapté au temps réel strict.** Il reste l'orchestrateur pour le backfill, les calculs batch et la réconciliation. Le Trade Manager (réaction en secondes) tournera dans une boucle async dédiée, hors workflow Temporal.
- **Aucun ordre réel avant validation sur données historiques.** Le pipeline backtesting + paper trading est obligatoire avant l'Execution Engine live.
- **Inspiration : tradingV3/trading-app** (Symfony/PHP, Bitmart Futures). L'architecture conditions-en-YAML, les profils de stratégie, les formules de risk et d'entry zone sont validées en production sur ce projet — on les adapte pour Binance Spot Python, sans levier ni shorts.

---

## Phases

### Phase 1b — MTF Validator

**Objectif** : transformer les snapshots d'indicateurs multi-timeframes en un signal structuré et scoré.

**Architecture** : fonction pure `validate(snapshots: dict[Timeframe, IndicatorSnapshot]) -> MTFSignal`. Pas d'accès DB direct — testable unitairement sans infrastructure.

**Profil de base : `regular`** (inspiré de tradingV3, adapté Spot) :

```
Contexte : 4h → 1h → 15m
Déclencheur : 5m (condition binaire)
```

Conditions par timeframe (déclarées en YAML, évaluées par des classes isolées) :

```yaml
# validations.regular.yaml
'4h':
    long:
        all_of:
            - ema20_above_ema50
            - ema50_above_ema200
            - rsi_between_45_70
            - macd_hist_positive

'1h':
    long:
        all_of:
            - price_above_ema20
            - adx_gt_25              # filtre régime : pas de trade en range
            - macd_hist_positive_or_rising

'15m':
    long:
        all_of:
            - rsi_between_40_60      # retracement sain sans casser la structure
            - price_near_ema20       # retour sur support dynamique
            - atr_contracting        # consolidation (volatilité en baisse)

'5m':                                # déclencheur binaire (ne participe pas au score)
    long:
        any_of:
            - macd_hist_turning_positive
            - close_above_recent_high_n
```

Filtres bloquants (invalident peu importe le score) :
- RSI 4h > 75 — surachat extrême
- Prix 4h > EMA20 + 2×ATR — extension excessive
- ADX 1h < 20 — marché en range, système trend-following inopérant
- MACD 1h histogram négatif ET en baisse — momentum baissier dominant

Scoring :
```
score_4h       = évaluation pondérée conditions 4h   → max 40 pts
score_1h       = évaluation pondérée conditions 1h   → max 30 pts
score_15m      = évaluation pondérée conditions 15m  → max 30 pts
score_total    = score_4h + score_1h + score_15m     → max 100 pts

valid = score_total >= seuil            # seuil calibré en Phase 2
        AND trigger_5m == True
        AND aucun filtre bloquant
```

**Sortie** : `MTFSignal { trend_4h, trend_1h, structure_15m, trigger_5m, score, valid, context_json }`

Persister chaque signal évalué en base (y compris `valid=False`) pour audit backtesting.

---

### Phase 2 — Backtesting pipeline

**Objectif** : valider que la stratégie MTF est profitable sur données historiques *avant* de construire quoi que ce soit d'exécution.

- Rejouer le MTF Validator sur l'historique des snapshots indicateurs déjà en base
- Simuler les entrées au close de la bougie 5m de déclenchement + slippage estimé 0.05%
- Stop-loss : niveau pivot (S1/S2 VWAP) le plus proche + 0.3% buffer, max 2% de distance ; fallback ATR × k (k entre 2 et 4)
- Take-profit : TP = entry + (distance_SL × r_multiple), r_multiple à calibrer (départ : 1.5)
- Calculer les métriques : winrate, profit factor, max drawdown, expectancy, MFE/MAE
- **Critères de passage à la Phase 3** : winrate > 50%, profit factor > 1.3, max drawdown < 15%
- Si non atteints : ajuster les conditions YAML, les seuils RSI/ADX, le score minimum, k et r_multiple — puis relancer

> Cette phase peut nécessiter plusieurs itérations. Ne pas passer à la Phase 3 sans résultats satisfaisants.

---

### Phase 3 — Signal Engine

**Objectif** : transformer le `MTFSignal` en décision de trading actionnable en temps réel.

- Si `mtf.valid && mtf.score > seuil_validé_phase2` → signal `LONG`
- Sinon → `NO_TRADE`
- Persister le signal en base avec timestamp, score, contexte JSON
- Exposer via API : `GET /signal/latest?symbol=X`

---

### Phase 4 — Risk Engine

**Objectif** : calculer la taille de position et valider l'exposition avant tout ordre.

Formules validées depuis tradingV3 (adaptées sans levier) :

```
distance_sl  = max(pivot_distance + 0.3%, atr × k)   # k calibré Phase 2
qty          = (capital × risk_pct) / distance_sl_abs
risk_usdt    = capital × risk_pct                     # défaut : 1–2%
```

- Daily loss cap : bloquer tout nouveau signal si le drawdown journalier dépasse le seuil configuré
- Entry zone : `center = VWAP ou EMA20`, `width = clamp(k_atr × ATR, center × w_min, center × w_max)`, TTL 180s
- **Sortie** : `OrderPlan { symbol, side, qty, entry_zone, entry_price, stop_loss, take_profit }`

---

### Phase 5 — Paper trading

**Objectif** : valider le comportement du système complet (signal + risk) sans risque capital.

- Signaux générés en temps réel (Phases 3 + 4 actives)
- Fill simulé : close de la bougie 5m suivante + slippage 0.05%
- P&L tracé en base trade par trade
- Durée minimale : 2–4 semaines
- **Critères de passage à la Phase 6** : mêmes métriques que Phase 2 confirmées sur données live
- Si non atteints : retour Phase 2 ou ajustement des filtres

---

### Phase 6 — Execution Engine

**Objectif** : placer les ordres sur Binance de manière fiable. Uniquement après validation Phase 5.

Stratégie d'ordre (inspirée tradingV3, adaptée Spot) :
- LIMIT maker dans l'entry zone, prix = best_bid + tick
- Fallback MARKET si non rempli après TTL (défaut 180s)
- OCO : stop-loss + take-profit simultanés
- Gérer les rejets Binance (min notional, lot size, filtres de prix)
- Persister chaque ordre en base (`orders` table) avec client_order_id idempotent (UUID)
- Démarrer avec capital limité (10% du capital total)

Pipeline : `Signal → Risk check → OrderPlan → Execution → Confirmation`

---

### Phase 7 — Trade Management Engine

**Objectif** : gérer les positions ouvertes jusqu'à leur clôture.

- **Boucle async dédiée** — pas un workflow Temporal (latence incompatible avec la réaction en secondes)
- Trailing stop ATR / Chandelier Exit : déplacer le SL au fil du mouvement favorable
- TP partiel : clôturer 60% de la position à 2R, laisser courir le reste avec trailing
- Time-stop : clôture forcée si durée > seuil configuré sans atteindre 1R
- Invalidation dynamique : clôture si RSI ou MACD retourne contre la position sur 15m
- Monitoring continu via WebSocket user stream (déjà partiellement en place)

---

### Phase 8 — Analytics + feedback loop

**Objectif** : mesurer la performance réelle et ajuster les paramètres du système.

- Vue PostgreSQL `position_trade_analysis` : historique complet des trades fermés
- Métriques : winrate, profit factor, max drawdown, expectancy, MFE/MAE, slippage réel
- Exposer via API : `GET /analytics/summary?symbol=X&period=30d`
- Tableau de bord dans le frontend (onglet stats)
- **Feedback loop** : comparer les seuils utilisés en production avec les résultats réels pour ajuster les conditions YAML, le score minimum et les paramètres k/r_multiple

---

## Séquençage

```
Phase 1b – MTF Validator (conditions YAML + scoring)
    ↓
Phase 2  – Backtesting pipeline        ← go/no-go obligatoire
    ↓ (si métriques OK)
Phase 3  – Signal Engine
Phase 4  – Risk Engine                 ← en parallèle de Phase 3
    ↓
Phase 5  – Paper trading               ← go/no-go obligatoire avant live
    ↓ (si métriques OK)
Phase 6  – Execution Engine
    ↓
Phase 7  – Trade Manager
    ↓
Phase 8  – Analytics + feedback loop
```

---

## Ce qu'on n'adapte PAS de tradingV3

| Fonctionnalité tradingV3 | Raison d'exclusion |
|--------------------------|-------------------|
| Order Flow Imbalance (OFI) | Nécessite carnet d'ordres temps réel, complexité élevée, hors scope Phase 1 |
| Levier dynamique | Pas de levier sur Spot |
| Signaux SHORT | Spot uniquement |
| MakerTakerSwitch / LimitFillWatch | Logique spécifique Futures Bitmart |
| Stochastic | Non prioritaire, MACD + RSI suffisants pour commencer |

---

## Contraintes techniques à respecter

- Toute activité batch ou réconciliation passe par **Temporal** ; le Trade Manager est une boucle async hors Temporal
- Pas d'ordre réel sans `LIVE_TRADING_APPROVED=true` en `.env`
- Le mode `backtesting` reste fonctionnel à chaque phase
- Pas de mock DB dans les tests — intégration sur vraie base uniquement
- Chaque signal, order plan, ordre et trade est persisté en base pour audit complet
- Capital live limité à une fraction du capital total jusqu'à validation des performances réelles
- Les conditions YAML sont la source de vérité de la stratégie — pas de logique hardcodée dans le code
