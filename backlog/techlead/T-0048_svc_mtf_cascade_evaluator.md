---
id: T-0048
title: "Service - MTF Cascade Evaluator : evaluate_cascade() multi-timeframe"
status: TODO
owner: techlead
phase: 2
priority: P0
links: ["T-0044", "T-0047", "T-0049", "T-0051"]
---

## Contexte

`src/tradebot/services/mtf/cascade.py` contient `evaluate_cascade()` qui lève `NotImplementedError`.
C'est le cœur du système de décision de trading.
Cette fonction reçoit les snapshots d'indicateurs de tous les timeframes
et retourne un verdict structuré qui sera utilisé par le SignalEngine.

## Périmètre

Implémenter `evaluate_cascade()` dans `src/tradebot/services/mtf/cascade.py`.

### Signature

```python
def evaluate_cascade(
    symbol: str,
    snapshots: dict[str, dict],  # timeframe → snapshot dict (output de build_indicator_snapshot)
    prev_snapshot_1h: dict | None = None,  # pour détection golden cross dans RegimeDetector
    config: StrategyConfig | None = None,  # depuis app.yaml, ou valeurs par défaut
) -> CascadeResult:
```

### Dataclass `CascadeResult` (créer dans `domain/models/`)

```python
@dataclass
class CascadeResult:
    symbol: str
    regime: MarketRegime
    cascade_passed: bool
    score: float                   # 0.0 → 1.0 normalisé
    quality: SignalQuality         # HIGH | MEDIUM | LOW | REJECTED
    active_setup: SetupType | None # A | B | C | D | None
    scores_by_tf: dict[str, float] # {"4h": 0.8, "1h": 0.6, "15m": 0.6, "5m": 0.75}
    rejection_reason: str | None   # ex: "regime_not_tradeable", "4h_score_too_low"
    evaluated_at_ms: int
```

### Enums à créer dans `domain/models/`

```python
class SignalQuality(str, Enum):
    HIGH     = "HIGH"      # score >= 0.75
    MEDIUM   = "MEDIUM"    # score >= 0.60
    LOW      = "LOW"       # score >= 0.50
    REJECTED = "REJECTED"  # score < 0.50 ou condition bloquante

class SetupType(str, Enum):
    A = "A"  # Pullback EMA en tendance
    B = "B"  # Breakout de range
    C = "C"  # Rebond sur pivot + VWAP
    D = "D"  # Golden Cross initiation
```

### Algorithme d'évaluation

#### Étape 1 — Détection du régime

```python
regime_result = detect_regime(snapshots["1h"], prev_snapshot_1h)
if not regime_result.tradeable:
    return CascadeResult(
        regime=regime_result.regime,
        cascade_passed=False,
        score=0.0,
        quality=SignalQuality.REJECTED,
        rejection_reason="regime_not_tradeable",
        ...
    )
```

#### Étape 2 — Score 4h (condition bloquante si < 3/5)

```python
def score_4h(snap: dict) -> float:
    conditions = [
        _ema_aligned(snap, "ema20", "ema50"),       # EMA20 > EMA50
        _price_above_ema(snap, "ema50"),             # prix > EMA50
        _adx_above(snap, threshold=20),
        _macd_positive_or_crossing(snap),            # MACD > 0 OU croisement haussier
        _rsi_above(snap, threshold=45),
    ]
    score = sum(conditions) / len(conditions)
    return score
```

Si score_4h < 3/5 (0.60) → `rejection_reason = "4h_score_too_low"`.

#### Étape 3 — Score 1h

```python
def score_1h(snap: dict) -> float:
    conditions = [
        _ema_aligned(snap, "ema20", "ema50"),
        _price_above_vwap(snap),
        _adx_trending(snap),                         # ADX > 20 ET +DI > -DI
        _rsi_in_range(snap, low=50, high=70),        # momentum sans surachat
        _macd_histogram_positive(snap),
    ]
    return sum(conditions) / len(conditions)
```

Si score_1h < 3/5 (0.60) → `rejection_reason = "1h_score_too_low"`.

#### Étape 4 — Sélection du setup selon régime

```python
def select_setup(regime: MarketRegime, snap_15m: dict, snap_1h: dict) -> SetupType | None:
    if regime == MarketRegime.TRENDING_UP:
        if _price_in_pullback_zone(snap_15m):    # prix entre EMA20 et EMA50 15m
            return SetupType.A
        if _bollinger_squeeze(snap_1h) and _price_above_upper_bb(snap_15m):
            return SetupType.B
        if _price_near_pivot(snap_15m):
            return SetupType.C
        return SetupType.A   # fallback tendance
    if regime == MarketRegime.RANGING:
        if _price_near_pivot(snap_15m):
            return SetupType.C
        return SetupType.B
    if regime == MarketRegime.RECOVERY:
        return SetupType.D
    return None
```

#### Étape 5 — Score 15m

```python
def score_15m(snap: dict, setup: SetupType) -> float:
    if setup == SetupType.A:
        conditions = [
            _price_in_pullback_zone(snap),
            _rsi_in_range(snap, low=40, high=60),
            _pullback_volume_weak(snap),            # volume < 70 % moyenne 20
            _higher_highs_higher_lows(snap),        # structure préservée
            _reversal_candle(snap),                 # hammer/engulfing/etc.
        ]
    elif setup == SetupType.B:
        conditions = [
            _bollinger_squeeze_resolved(snap),      # prix > upper band
            _breakout_volume_strong(snap),          # volume > 2× moyenne
            _rsi_not_overbought(snap),              # RSI < 65
            _price_above_ema20(snap),
            _macd_positive(snap),
        ]
    # ... setup C, D
    return sum(conditions) / len(conditions)
```

#### Étape 6 — Score 5m

```python
def score_5m(snap: dict) -> float:
    conditions = [
        _stochrsi_crossing_up(snap),               # K croise D vers le haut < 0.30
        _macd_crossing_or_histogram_green(snap),   # croisement OU 2 barres vertes
        _price_above_ema9(snap),
        _volume_above_average(snap),               # volume > moyenne 10 bougies
    ]
    return sum(conditions) / len(conditions)
```

#### Étape 7 — Score global et qualité

```python
WEIGHTS = {"4h": 2.0, "1h": 1.5, "15m": 1.0, "5m": 0.8}
TOTAL_WEIGHT = sum(WEIGHTS.values())  # 5.3

score = (
    score_4h  * WEIGHTS["4h"]  +
    score_1h  * WEIGHTS["1h"]  +
    score_15m * WEIGHTS["15m"] +
    score_5m  * WEIGHTS["5m"]
) / TOTAL_WEIGHT

quality = (
    SignalQuality.HIGH     if score >= 0.75 else
    SignalQuality.MEDIUM   if score >= 0.60 else
    SignalQuality.REJECTED
)

cascade_passed = quality in (SignalQuality.HIGH, SignalQuality.MEDIUM)
```

### Helpers `_xxx()` — règles atomiques

Chaque helper prend un snapshot dict et retourne un bool.
Les regrouper dans `src/tradebot/services/mtf/_conditions.py`.

```python
def _ema_aligned(snap, fast_key: str, slow_key: str) -> bool:
    fast = _get_value(snap, fast_key)
    slow = _get_value(snap, slow_key)
    if fast is None or slow is None:
        return False
    return fast > slow

def _get_value(snap: dict, key: str) -> float | None:
    """Retourne la valeur si status='available', None sinon."""
    field = snap.get(key, {})
    if field.get("status") == "available":
        return field.get("value")
    return None
```

## Contraintes techniques

- Fonction pure, aucun I/O, aucun appel DB
- Paramètres numériques (seuils ADX, RSI, etc.) issus de `StrategyConfig` (app.yaml)
  → avec valeurs par défaut si config non fournie
- Si un snapshot timeframe est manquant → `cascade_passed=False`, `rejection_reason="missing_snapshot_{tf}"`
- Tous les helpers → `False` si indicateur `unavailable` (jamais de crash sur données manquantes)

## Tests

- `tests/unit/test_mtf_cascade.py`

Scénarios :

```python
# Scénario 1 : signal parfait
snapshots = build_perfect_snapshots()   # toutes conditions vraies
result = evaluate_cascade("BTCUSDC", snapshots)
assert result.cascade_passed == True
assert result.quality == SignalQuality.HIGH
assert result.score >= 0.75

# Scénario 2 : régime VOLATILE
snapshots["1h"]["atr"]["value"] = price * 0.06
result = evaluate_cascade("BTCUSDC", snapshots)
assert result.cascade_passed == False
assert result.rejection_reason == "regime_not_tradeable"

# Scénario 3 : snapshot 4h manquant
snapshots_no_4h = {k: v for k, v in snapshots.items() if k != "4h"}
result = evaluate_cascade("BTCUSDC", snapshots_no_4h)
assert result.rejection_reason == "missing_snapshot_4h"

# Scénario 4 : score 4h trop bas (2/5 conditions)
# Scénario 5 : trending up, setup A détecté
# Scénario 6 : ranging, setup B détecté
# Scénario 7 : recovery, setup D, taille réduite signalée
```

## Critères d'acceptation

1. Fonction pure, déterministe (mêmes inputs → mêmes outputs)
2. `CascadeResult.cascade_passed = False` si régime non tradeable
3. `scores_by_tf` peuplé même en cas de rejet (pour debug)
4. Aucun crash si indicateur unavailable ou snapshot manquant
5. `active_setup` cohérent avec le régime détecté
6. Tous les seuils configurables via `StrategyConfig`
