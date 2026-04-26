---
id: T-0049
title: "Service - SignalEngine : compute_signal() du trigger 1m vers l'OrderIntent BUY"
status: TODO
owner: techlead
phase: 2
priority: P0
links: ["T-0048", "T-0052"]
---

## Contexte

`src/tradebot/services/strategy/signal_engine.py` contient `compute_signal()` → `NotImplementedError`.
Quand la cascade MTF valide un setup (T-0048), le signal engine est appelé
à chaque bougie 1m fermée pour décider si le trigger d'exécution est atteint.
Il calcule aussi les niveaux concrets (entry, SL, TP) de la position à ouvrir.

## Périmètre

Implémenter `compute_signal()` dans `src/tradebot/services/strategy/signal_engine.py`.

### Signature

```python
def compute_signal(
    cascade: CascadeResult,
    candle_1m: Candle,
    snapshot_1m: dict,
    snapshot_5m: dict,
    filters: SymbolFilters,       # pour arrondi des prix
    config: StrategyConfig | None = None,
) -> Signal | None:
    """
    Retourne un Signal si le trigger 1m est déclenché, None sinon.
    Appelé à chaque bougie 1m fermée tant que le signal n'a pas expiré.
    """
```

### Dataclass `Signal` (compléter `domain/models/signal.py`)

```python
@dataclass
class Signal:
    symbol: str
    setup: SetupType
    quality: SignalQuality
    score: float

    # Niveaux d'exécution
    entry_price: Decimal           # prix LIMIT suggéré
    stop_loss: Decimal             # SL initial
    tp_lot_a: Decimal              # TP Lot A (entry + 2R)
    tp_lot_b: Decimal              # TP Lot B (entry + 3R)
    r_distance: Decimal            # entry - stop_loss (1R)
    atr_1m: Decimal               # ATR(14) sur 1m au moment du signal

    # Métadonnées
    risk_pct: float                # risque ajusté selon qualité et setup
    cascade_score: float
    created_at_ms: int
    expires_at_ms: int             # created_at + 15 bougies 1m = + 15 minutes
    trigger_candle_open_ms: int    # open_time_ms de la bougie 1m qui a triggeré
```

### Algorithme

#### 1. Vérification expiry

```python
expires_at_ms = cascade.evaluated_at_ms + (15 * 60 * 1000)  # 15 min
if candle_1m.close_time_ms > expires_at_ms:
    return None  # signal expiré, la cascade doit être réévaluée
```

#### 2. Vérification trigger 1m

```python
def _trigger_1m(candle_1m: Candle, snapshot_1m: dict, snapshot_5m: dict) -> bool:
    conditions = [
        # Micro-breakout : close > high bougie précédente
        # (nécessite d'avoir le high de la bougie précédente dans le snapshot ou en paramètre)
        _close_above_prev_high(candle_1m),

        # Volume 1m > 1.5× la moyenne
        _volume_spike(snapshot_1m, multiplier=1.5),

        # StochRSI 5m K > D et en zone non-surachetée
        _stochrsi_bullish(snapshot_5m, max_k=0.75),
    ]
    # Au moins 2/3 conditions pour trigger
    return sum(conditions) >= 2
```

Si trigger non atteint → retourner `None`.

#### 3. Calcul des niveaux

```python
# ATR sur 1m pour le SL (plus précis que 5m pour le trigger)
atr_1m = _get_value(snapshot_1m, "atr")
atr_15m = _get_value(snapshot_15m, "atr")  # si disponible, sinon ATR 1m × 3

# SL : sous le plus bas récent OU ATR-based (le plus conservateur)
recent_low = candle_1m.low                         # low de la bougie trigger
atr_sl = candle_1m.close - (atr_1m * config.sl_atr_multiplier)  # 1.5× ATR
stop_loss = min(recent_low * Decimal("0.999"), atr_sl)  # plus bas des deux

# Entry : close de la bougie trigger + 0.05 % (léger slippage)
entry_price = candle_1m.close * Decimal("1.0005")

# R distance
r = entry_price - stop_loss

# TP
tp_lot_a = entry_price + (r * Decimal("2"))   # 2R
tp_lot_b = entry_price + (r * Decimal("3"))   # 3R

# Arrondi Binance
entry_price = BinanceFilters.round_price(entry_price, filters)
stop_loss   = BinanceFilters.round_price(stop_loss, filters)
tp_lot_a    = BinanceFilters.round_price(tp_lot_a, filters)
tp_lot_b    = BinanceFilters.round_price(tp_lot_b, filters)
```

#### 4. Calcul du risque ajusté

```python
risk_pct = config.risk_per_trade_pct  # 0.01 base

if cascade.quality == SignalQuality.MEDIUM:
    risk_pct *= 0.6
if cascade.active_setup == SetupType.C:
    risk_pct *= 0.7
if cascade.active_setup == SetupType.D:
    risk_pct *= 0.5
# La réduction pour corrélation est faite dans l'activité place_order
```

#### 5. Validation minimale avant retour

```python
if r <= 0:
    log.warning("signal_invalid_r", symbol=symbol, r=str(r))
    return None
if entry_price <= stop_loss:
    return None
```

### Cas particuliers par setup

**Setup A — Pullback EMA :**
- Entry : close 1m (marché récupère)
- SL : sous EMA50 15m - 0.5×ATR(15m)
- Si le signal est déclenché alors que le prix est déjà > EMA20 15m + 0.5 % → signal trop tardif, None

**Setup B — Breakout :**
- Entry : close 1m (momentum)
- SL : sous le bas du range (niveau de support cassé)
- Si retest en cours : entry = niveau du retest + tick_size

**Setup C — Pivot :**
- Entry : close 1m au-dessus du pivot support
- SL : S2 - 0.5×ATR ou S3 selon entry

**Setup D — Golden Cross :**
- Entry : close 1m
- SL : sous EMA50 1h au moment de l'entrée
- TP_lot_a → 1.5R (plus conservateur, tendance non établie)

## Hors périmètre

- Calcul de la quantité (dans `risk.py` existant)
- Placement de l'ordre (dans l'activité T-0052)
- Gestion des lots (dans ExitPlan / position)

## Tests

- `tests/unit/test_signal_engine.py`

```python
def test_trigger_1m_all_conditions():
    # Toutes les conditions 1m vraies → Signal retourné

def test_trigger_1m_insufficient():
    # Moins de 2/3 conditions → None

def test_signal_expired():
    # candle_1m.close_time_ms > expires_at → None

def test_sl_calculation_setup_a():
    # Vérifier SL = min(recent_low × 0.999, entry - 1.5×ATR)

def test_r_negative_returns_none():
    # SL > entry → None

def test_risk_pct_medium_quality():
    # quality=MEDIUM → risk_pct = 0.006

def test_setup_d_tp_at_1_5r():
    # Setup D → tp_lot_a = entry + 1.5R (pas 2R)
```

## Critères d'acceptation

1. Fonction pure, déterministe
2. Retourne `None` si trigger non atteint ou signal expiré
3. `r > 0` obligatoire (sinon None)
4. Niveaux arrondis selon les filtres Binance
5. `risk_pct` ajusté selon qualité et setup
6. `expires_at_ms = evaluated_at_ms + 15 minutes`
