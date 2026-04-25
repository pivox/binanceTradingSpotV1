---
id: T-0047
title: "Service - MarketRegimeDetector : classification du régime de marché par symbole"
status: TODO
owner: techlead
phase: 2
priority: P0
links: ["T-0044", "T-0048"]
---

## Contexte

Avant d'évaluer la cascade MTF, le système doit classifier le régime de marché
pour chaque symbole. Ce régime détermine quels setups sont autorisés et si le
trading est possible du tout. C'est la première couche de filtrage.

## Périmètre

Créer `src/tradebot/services/mtf/regime.py`.

### Enum `MarketRegime`

```python
class MarketRegime(str, Enum):
    TRENDING_UP   = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    RANGING       = "RANGING"
    RECOVERY      = "RECOVERY"    # golden cross récent (< 3 bougies 1h)
    VOLATILE      = "VOLATILE"    # ATR ratio > 4 %
```

### Règles de classification (basées sur le snapshot 1h)

Évaluer dans cet ordre (premier match gagne) :

```
1. VOLATILE
   ATR(14) / close_price > 0.04
   → Arrêt immédiat, aucun trade possible

2. TRENDING_DOWN
   EMA20 < EMA50 < EMA200
   ET ADX > 25
   → Aucun trade possible en spot

3. RECOVERY
   EMA20 vient de croiser EMA50 vers le haut
   Détection : snapshot 1h[n-1].ema20 < snapshot 1h[n-1].ema50
              ET snapshot 1h[n].ema20 > snapshot 1h[n].ema50
   Ou : croisement dans les 3 dernières bougies 1h fermées
   → Setups autorisés : Pullback EMA uniquement, taille × 0.5

4. TRENDING_UP
   EMA20 > EMA50 > EMA200
   ET ADX > 25
   ET close_price > EMA50
   → Tous setups autorisés

5. RANGING
   ADX < 20
   ET close entre BB_lower et BB_upper (±5 % de tolérance)
   → Setups autorisés : mean-reversion Bollinger, Bounce support

6. Fallback → RANGING (si aucune condition stricte n'est remplie)
```

### Interface publique

```python
@dataclass(frozen=True)
class RegimeResult:
    regime: MarketRegime
    adx: float
    atr_ratio: float            # ATR / prix
    ema_aligned: bool           # EMA20 > EMA50 > EMA200
    golden_cross_detected: bool
    bb_squeeze: bool            # bandwidth < 0.03
    tradeable: bool             # False si VOLATILE ou TRENDING_DOWN


def detect_regime(
    snapshot_1h: dict,          # retour de build_indicator_snapshot pour 1h
    prev_snapshot_1h: dict | None = None,  # snapshot précédent pour détecter le croisement
) -> RegimeResult:
    """
    Fonction pure. Pas d'I/O.
    `snapshot_1h` doit avoir status="available" pour ADX, EMA, ATR, Bollinger.
    Si un indicateur est unavailable → fallback conservateur (RANGING si doute).
    """
```

### Gestion des indicateurs unavailable

```python
# Si ADX unavailable → supposer ADX = 0 (range)
# Si EMA unavailable → supposer non-aligné
# Si ATR unavailable → supposer non-volatile (pas de blocage)
# Loguer un warning structuré avec le champ manquant
```

## Hors périmètre

- Snapshot 4h (utilisé directement dans `evaluate_cascade`, pas ici)
- Persistance du régime (stocké dans MtfState via T-0046)
- Filtres de setup (dans SignalEngine)

## Tests

- `tests/unit/test_market_regime_detector.py`

Cas à couvrir :

| Cas | ADX | EMA | ATR ratio | Résultat attendu |
|-----|-----|-----|-----------|-----------------|
| Tendance forte | 30 | 20>50>200 | 0.02 | TRENDING_UP |
| Death cross | 28 | 20<50<200 | 0.02 | TRENDING_DOWN |
| Range calme | 15 | désaligné | 0.01 | RANGING |
| Volatilité | 20 | aligné | 0.05 | VOLATILE |
| Golden cross | 26 | vient croiser | 0.02 | RECOVERY |
| ADX unavailable | n/a | aligné | 0.02 | RANGING (fallback) |

## Critères d'acceptation

1. Fonction pure, déterministe, testable sans DB ni réseau
2. VOLATILE et TRENDING_DOWN retournent `tradeable=False`
3. RECOVERY détecté uniquement si croisement EMA20/EMA50 dans les 3 dernières bougies 1h
4. Tous les indicateurs unavailable → pas de crash, fallback RANGING
5. `atr_ratio` et `bb_squeeze` retournés dans `RegimeResult` pour observabilité
