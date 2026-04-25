---
id: T-0050
title: "Service - ExitEngine : compute_exit_intents() gestion des sorties de position"
status: TODO
owner: techlead
phase: 2
priority: P0
links: ["T-0045", "T-0049", "T-0053"]
---

## Contexte

`src/tradebot/services/strategy/exit_engine.py` contient `compute_exit_intents()` → `NotImplementedError`.
Pour chaque position ouverte, cet engine est appelé à chaque bougie 5m fermée.
Il analyse l'état de la position et retourne la liste des actions de sortie à effectuer.
Il est responsable de la gestion du trailing stop et des sorties forcées.

## Périmètre

Implémenter `compute_exit_intents()` dans `src/tradebot/services/strategy/exit_engine.py`.

### Signature

```python
def compute_exit_intents(
    position: Position,
    snapshot_1h: dict,
    snapshot_5m: dict,
    candle_5m: Candle,             # dernière bougie 5m fermée
    config: StrategyConfig | None = None,
) -> list[ExitIntent]:
    """
    Retourne une liste d'ExitIntent (peut être vide si rien à faire).
    Chaque ExitIntent correspond à la sortie d'un lot précis (A, B ou C).
    """
```

### Dataclass `ExitIntent` (compléter `domain/models/exit_plan.py`)

```python
class ExitReason(str, Enum):
    TP_LOT_A         = "TP_LOT_A"
    TP_LOT_B         = "TP_LOT_B"
    TRAILING_STOP_C  = "TRAILING_STOP_C"
    FORCED_DEATH_CROSS = "FORCED_DEATH_CROSS"
    FORCED_RSI_EXTREME = "FORCED_RSI_EXTREME"
    FORCED_EMA200    = "FORCED_EMA200"
    FORCED_TIMEOUT   = "FORCED_TIMEOUT"
    FORCED_DRY_VOLUME = "FORCED_DRY_VOLUME"
    SL_GLOBAL        = "SL_GLOBAL"         # géré par l'ordre STOP_MARKET en place

@dataclass
class ExitIntent:
    position_id: str
    lot_id: str                    # "A" | "B" | "C" | "ALL"
    reason: ExitReason
    quantity: Decimal              # quantité à vendre
    price: Decimal | None          # None = MARKET order
    order_type: str                # "LIMIT" | "MARKET" | "STOP_MARKET"
    new_stop_loss: Decimal | None  # si mise à jour du SL nécessaire (ex: break-even)
    new_trailing_level: Decimal | None  # nouveau niveau du trailing stop Lot C
```

### Algorithme — ordre d'évaluation

**Important** : les sorties forcées ont la priorité absolue.

#### 1. Sorties forcées (priorité maximale, `lot_id = "ALL"`)

```python
def _check_forced_exits(position, snapshot_1h, candle_5m, config) -> ExitIntent | None:

    # Death cross 1h : EMA20 croise EMA50 vers le bas
    ema20_1h = _get_value(snapshot_1h, "ema20")
    ema50_1h = _get_value(snapshot_1h, "ema50")
    if ema20_1h and ema50_1h and ema20_1h < ema50_1h:
        # Vérifier que ce n'était pas déjà le cas (croissement récent)
        return ExitIntent(lot_id="ALL", reason=ExitReason.FORCED_DEATH_CROSS,
                          quantity=position.quantity_remaining, price=None,
                          order_type="MARKET", ...)

    # Prix sous EMA200 1h : structure macro cassée
    ema200_1h = _get_value(snapshot_1h, "ema200")
    if ema200_1h and candle_5m.close < Decimal(str(ema200_1h)):
        return ExitIntent(lot_id="ALL", reason=ExitReason.FORCED_EMA200, ...)

    # RSI 1h > 78 : surachat extrême (si lots B et C encore ouverts)
    rsi_1h = _get_value(snapshot_1h, "rsi")
    if rsi_1h and rsi_1h > 78 and not position.exit_plan.lot_b.is_filled:
        # Vendre B + C au marché immédiatement
        return ExitIntent(lot_id="BC", reason=ExitReason.FORCED_RSI_EXTREME, ...)

    # Timeout : position ouverte > 48h sans avoir atteint TP1
    age_ms = candle_5m.close_time_ms - position.opened_at_ms
    if age_ms > 48 * 3600 * 1000 and not position.exit_plan.lot_a.is_filled:
        return ExitIntent(lot_id="ALL", reason=ExitReason.FORCED_TIMEOUT, ...)

    # Volume sec : moyenne volume 4 dernières bougies 1h < 30 % de la normale
    # (nécessite snapshot_1h avec volume_ratio)
    # Si disponible :
    if _dry_volume(snapshot_1h):
        return ExitIntent(lot_id="BC", reason=ExitReason.FORCED_DRY_VOLUME, ...)

    return None
```

#### 2. Trailing stop Lot C (si Lot A rempli)

```python
def _update_trailing_c(position, candle_5m, snapshot_5m, config) -> ExitIntent | None:
    if not position.exit_plan.lot_a.is_filled:
        return None   # trailing actif seulement après TP A
    if position.exit_plan.lot_c.is_filled:
        return None   # déjà sorti

    # Mettre à jour high_since_entry
    new_high = max(position.high_since_entry, candle_5m.high)

    # ATR sur 5m
    atr_5m = _get_value(snapshot_5m, "atr")
    if atr_5m is None:
        return None

    trailing_level = new_high - Decimal(str(atr_5m)) * Decimal(str(config.trailing_atr_multiplier))
    # trailing_atr_multiplier = 2.0

    intents = []

    # Si le prix actuel touche le trailing → sortir Lot C
    if candle_5m.close <= trailing_level:
        intents.append(ExitIntent(
            lot_id="C",
            reason=ExitReason.TRAILING_STOP_C,
            quantity=position.exit_plan.lot_c.quantity,
            price=None,
            order_type="MARKET",
            new_trailing_level=trailing_level,
            new_stop_loss=None,
        ))
    else:
        # Mise à jour du niveau trailing (pour MAJ de l'ordre STOP_MARKET sur Binance)
        if trailing_level > (position.exit_plan.lot_c.current_trailing or Decimal("0")):
            intents.append(ExitIntent(
                lot_id="C",
                reason=ExitReason.TRAILING_STOP_C,
                quantity=Decimal("0"),   # quantité 0 = pas de vente, juste MAJ niveau
                price=None,
                order_type="STOP_MARKET",
                new_trailing_level=trailing_level,
                new_stop_loss=None,
            ))

    return intents
```

#### 3. Gestion du breakeven

```python
def _check_breakeven(position, candle_5m, config) -> ExitIntent | None:
    """
    Quand prix >= entry + 1R → SL passe à entry + 0.2R
    Quand prix >= entry + 1.5R → SL passe à entry + 0.5R
    """
    if position.exit_plan.lot_a.is_filled:
        return None  # Lot A rempli → breakeven déjà géré lors du fill

    current_price = candle_5m.close
    r = position.exit_plan.r_distance

    target_1r = position.entry_price + r
    target_1_5r = position.entry_price + (r * Decimal("1.5"))

    new_sl = None
    if current_price >= target_1_5r:
        new_sl = position.entry_price + (r * Decimal("0.5"))
    elif current_price >= target_1r:
        new_sl = position.entry_price + (r * Decimal("0.2"))

    if new_sl and new_sl > position.stop_loss:
        return ExitIntent(
            lot_id="NONE",    # pas de vente, juste MAJ du SL
            reason=ExitReason.SL_GLOBAL,
            quantity=Decimal("0"),
            new_stop_loss=new_sl,
            ...
        )
    return None
```

### `quantity_remaining` helper

```python
@property
def quantity_remaining(self) -> Decimal:
    filled = sum(
        lot.quantity for lot in [self.exit_plan.lot_a, self.exit_plan.lot_b, self.exit_plan.lot_c]
        if lot.is_filled
    )
    return self.quantity_total - filled
```

## Contraintes techniques

- Fonction pure, aucun I/O
- Une position ne peut pas avoir deux exits du même lot_id dans la même liste retournée
- Si `quantity == 0` dans un `ExitIntent` → c'est une MAJ de niveau (SL ou trailing), pas une vente
- Les lots déjà remplis (`is_filled=True`) ne génèrent aucune action
- Ordre d'évaluation strict : forcé > trailing > breakeven (les forcés annulent le reste)

## Tests

- `tests/unit/test_exit_engine.py`

```python
def test_forced_death_cross_exits_all():
    position = build_open_position()
    snapshot_1h = build_snapshot(ema20=45000, ema50=46000)  # EMA20 < EMA50
    intents = compute_exit_intents(position, snapshot_1h, ...)
    assert len(intents) == 1
    assert intents[0].lot_id == "ALL"
    assert intents[0].reason == ExitReason.FORCED_DEATH_CROSS
    assert intents[0].order_type == "MARKET"

def test_trailing_update_no_trigger():
    # Trailing calculé mais prix au-dessus → ExitIntent avec quantity=0

def test_trailing_triggered():
    # Prix <= trailing_level → ExitIntent quantité Lot C

def test_breakeven_at_1r():
    # Prix = entry + 1R → new_stop_loss = entry + 0.2R

def test_nothing_when_position_flat():
    # Tous les lots remplis → liste vide

def test_forced_takes_priority_over_trailing():
    # Death cross + trailing actif → seul le death cross retourné

def test_timeout_48h_without_tp_a():
    # Position ouverte depuis > 48h sans Lot A → FORCED_TIMEOUT
```

## Critères d'acceptation

1. Les sorties forcées ont la priorité absolue et retournent lot_id="ALL"
2. Trailing C actif uniquement après fill de Lot A
3. `quantity=0` pour les MAJ de niveaux (pas de vente)
4. Position avec tous lots remplis → liste vide
5. Ordre d'évaluation strict : forcé > trailing > breakeven
6. Fonction pure, déterministe
