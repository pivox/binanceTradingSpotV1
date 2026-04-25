---
id: T-0053
title: "Temporal - Activities gestion positions : fetch_due, apply_exit_engine, create_sell_intent, update_position"
status: TODO
owner: techlead
phase: 3
priority: P0
links: ["T-0045", "T-0046", "T-0050", "T-0052"]
---

## Contexte

Ces activités constituent le pipeline de gestion des positions ouvertes.
Elles sont appelées par `ManageOpenPositionsWorkflow` toutes les 5s.
Pour chaque position active, le pipeline vérifie si une sortie est nécessaire
(TP, trailing, sortie forcée) et place les ordres SELL correspondants.

## Périmètre

### Activity 1 — `fetch_due_positions`

```python
@activity.defn
async def fetch_due_positions(input: FetchDuePositionsInput) -> FetchDuePositionsOutput:
```

**Input :**
```python
@dataclass
class FetchDuePositionsInput:
    shard_id: int
    check_interval_ms: int = 5000  # re-checker une position max toutes les 5s
```

**Logique :**
```python
# Calculer due_before_ms = now_ms - check_interval_ms
due_before_ms = int(time.time() * 1000) - input.check_interval_ms

positions = await position_repo.list_open_by_shard(
    shard_id=input.shard_id,
    due_before_ms=due_before_ms,
)

# Pour chaque position, charger aussi les snapshots 1h et 5m les plus récents
# (pour ne pas multiplier les aller-retours dans l'activité exit_engine)
enriched = []
for pos in positions:
    snap_1h = await indicator_repo.get_latest_snapshot(pos.symbol, "1h")
    snap_5m = await indicator_repo.get_latest_snapshot(pos.symbol, "5m")
    candle_5m = await candle_repo.fetch_latest(pos.symbol, "5m", limit=1)
    enriched.append(PositionWithContext(
        position=pos,
        snapshot_1h=snap_1h,
        snapshot_5m=snap_5m,
        latest_candle_5m=candle_5m[0] if candle_5m else None,
    ))

return FetchDuePositionsOutput(positions=enriched)
```

---

### Activity 2 — `apply_exit_engine`

```python
@activity.defn
async def apply_exit_engine(input: ApplyExitEngineInput) -> ApplyExitEngineOutput:
```

**Input :**
```python
@dataclass
class ApplyExitEngineInput:
    position: PositionData
    snapshot_1h: dict | None
    snapshot_5m: dict | None
    candle_5m: CandleData | None
```

**Logique :**
```python
# Sécurité : si snapshots manquants, ne rien faire (pas de sortie aveugle)
if not input.snapshot_1h or not input.snapshot_5m or not input.candle_5m:
    log.warning("apply_exit_engine_missing_data", symbol=input.position.symbol)
    return ApplyExitEngineOutput(intents=[], reason="missing_data")

config = load_app_config(...).strategy
position = _from_data(input.position)
candle_5m = _from_data(input.candle_5m)

# Appeler le service pur (T-0050)
intents = compute_exit_intents(
    position=position,
    snapshot_1h=input.snapshot_1h,
    snapshot_5m=input.snapshot_5m,
    candle_5m=candle_5m,
    config=config,
)

# Mettre à jour high_since_entry si nécessaire
new_high = max(position.high_since_entry, candle_5m.high)
if new_high > position.high_since_entry:
    # Sera sauvegardé dans update_position_after_actions

return ApplyExitEngineOutput(
    intents=[_to_data(i) for i in intents],
    new_high_since_entry=str(new_high),
    reason=None,
)
```

---

### Activity 3 — `create_sell_intent`

```python
@activity.defn
async def create_sell_intent(input: CreateSellIntentInput) -> CreateSellIntentOutput:
```

**Logique :**
```python
for exit_intent in input.exit_intents:
    # Skip les ExitIntent sans vente (quantity == 0 → juste MAJ de niveau)
    if exit_intent.quantity == 0:
        continue

    intent_key = make_intent_key(
        symbol=input.symbol,
        side="SELL",
        open_time_ms=input.position_opened_at_ms,
        lot_id=exit_intent.lot_id,
    )

    # Idempotence : si cet intent existe déjà → ne pas dupliquer
    existing = await order_intent_repo.get_by_intent_key(intent_key)
    if existing:
        continue

    intent = OrderIntent(
        id=str(uuid4()),
        intent_key=intent_key,
        position_id=input.position_id,
        symbol=input.symbol,
        side="SELL",
        order_type=exit_intent.order_type,
        quantity=exit_intent.quantity,
        price=exit_intent.price,                  # None si MARKET
        stop_price=exit_intent.new_trailing_level, # pour STOP_MARKET trailing
        lot_id=exit_intent.lot_id,
        status=OrderIntentStatus.PENDING,
    )
    await order_intent_repo.create(intent)

# Les ordres SELL sont ensuite placés via `place_order` (même activité que BUY)
```

---

### Activity 4 — `update_position_after_actions`

```python
@activity.defn
async def update_position_after_actions(input: UpdatePositionInput) -> None:
```

**Input :**
```python
@dataclass
class UpdatePositionInput:
    position_id: str
    new_stop_loss: str | None        # Decimal sérialisé
    new_trailing_level: str | None   # Decimal sérialisé
    new_high_since_entry: str | None
    last_checked_ms: int
    lots_filled: list[str]           # ["A", "B"] → marquer comme filled dans exit_plan
    new_status: str | None           # ex: "CLOSED" si tous les lots sortis
```

**Logique :**
```python
position = await position_repo.get_by_id(input.position_id)
if not position:
    log.error("update_position_not_found", position_id=input.position_id)
    return

# Appliquer les modifications
if input.new_stop_loss:
    position = replace(position, stop_loss=Decimal(input.new_stop_loss))
if input.new_high_since_entry:
    position = replace(position, high_since_entry=Decimal(input.new_high_since_entry))
if input.new_trailing_level:
    # MAJ du niveau trailing dans exit_plan.lot_c
    position = _update_lot_c_trailing(position, Decimal(input.new_trailing_level))
for lot_id in input.lots_filled:
    position = _mark_lot_filled(position, lot_id)

position = replace(position, last_checked_ms=input.last_checked_ms)

if input.new_status:
    position = replace(position, status=PositionStatus(input.new_status))
    if input.new_status == "CLOSED":
        position = replace(position, closed_at_ms=input.last_checked_ms)

await position_repo.update(position)
```

## Contraintes communes

- `apply_exit_engine` : si snapshot manquant → retourner `intents=[]`, **ne jamais sortir à l'aveugle**
- `create_sell_intent` : idempotent sur `intent_key` (même lot_id, même position)
- `update_position_after_actions` : si position CLOSED mais ordre SELL pas encore FILLED → status = CLOSING, pas CLOSED
  - CLOSED uniquement confirmé par `reconcile_orders` (T-0054)
- `fetch_due_positions` : charger snapshots et candles dans la même activité pour limiter les aller-retours

## Tests

- `tests/unit/test_position_management_activities.py`
  - `fetch_due_positions` : filtre last_checked_ms correct
  - `apply_exit_engine` : snapshots manquants → intents=[]
  - `apply_exit_engine` : death cross → ExitIntent ALL MARKET
  - `create_sell_intent` : idempotent sur intent_key
  - `update_position_after_actions` : position inconnue → warning, pas crash
  - `update_position_after_actions` : lot marqué filled → exit_plan mis à jour

## Critères d'acceptation

1. `apply_exit_engine` ne crée jamais d'intent si snapshot manquant
2. `create_sell_intent` idempotent : doublon intent_key → skip silencieux
3. Position status = CLOSING (pas CLOSED) tant que les ordres SELL ne sont pas confirmés filled
4. `high_since_entry` mis à jour à chaque tick même sans sortie
5. `last_checked_ms` toujours mis à jour après chaque check
