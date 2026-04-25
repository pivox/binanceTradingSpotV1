---
id: T-0052
title: "Temporal - Activities exécution : cascade_validate, create_buy_intent, place_order, cancel_order"
status: TODO
owner: techlead
phase: 3
priority: P0
links: ["T-0042", "T-0043", "T-0045", "T-0046", "T-0048", "T-0049"]
---

## Contexte

Ces quatre activités constituent le pipeline d'entrée en position.
Elles sont appelées par `CascadeValidateAndEnterWorkflow`.

Le pipeline est : évaluer la cascade → si signal → créer l'intent → placer l'ordre Binance.
La double garde `EXECUTION_MODE` est appliquée dans `place_order`.

## Périmètre

### Activity 1 — `load_latest_snapshots`

```python
@activity.defn
async def load_latest_snapshots(input: LoadSnapshotsInput) -> LoadSnapshotsOutput:
```

**Input :**
```python
@dataclass
class LoadSnapshotsInput:
    symbol: str
    timeframes: list[str]   # ["4h", "1h", "15m", "5m", "1m"]
```

**Logique :**
```python
# Pour chaque timeframe, lire le snapshot le plus récent depuis indicator_snapshots
# Si un snapshot n'existe pas ou est trop vieux (> 2× la durée du timeframe) → None
# Retourner dict[timeframe, snapshot_dict | None]

MAX_AGE = {
    "1m": 2 * 60 * 1000,
    "5m": 10 * 60 * 1000,
    "15m": 30 * 60 * 1000,
    "1h": 2 * 3600 * 1000,
    "4h": 8 * 3600 * 1000,
}
```

**Output :**
```python
@dataclass
class LoadSnapshotsOutput:
    snapshots: dict[str, dict | None]
    missing_timeframes: list[str]   # timeframes sans snapshot valide
```

---

### Activity 2 — `load_mtf_state` + `save_mtf_state`

```python
@activity.defn
async def load_mtf_state(input: LoadMtfStateInput) -> MtfStateData | None:
    # Lire MtfStateRepoSql.get(symbol)
    # Retourner None si inexistant

@activity.defn
async def save_mtf_state(input: SaveMtfStateInput) -> None:
    # Appeler MtfStateRepoSql.upsert(state)
```

---

### Activity 3 — `cascade_validate_mtf`

```python
@activity.defn
async def cascade_validate_mtf(input: CascadeValidateInput) -> CascadeResultData:
```

**Input :**
```python
@dataclass
class CascadeValidateInput:
    symbol: str
    snapshots: dict[str, dict | None]
    prev_snapshot_1h: dict | None
    candle_1m: CandleData
    snapshot_1m: dict
    snapshot_5m: dict
```

**Logique :**
```python
# 1. Charger StrategyConfig depuis app.yaml
config = load_app_config(get_app_config_path()).strategy

# 2. Appeler evaluate_cascade() (service pur, T-0048)
cascade = evaluate_cascade(
    symbol=input.symbol,
    snapshots={tf: s for tf, s in input.snapshots.items() if s is not None},
    prev_snapshot_1h=input.prev_snapshot_1h,
    config=config,
)

# 3. Si cascade.cascade_passed → appeler compute_signal() (T-0049)
signal = None
if cascade.cascade_passed:
    filters = await _load_symbol_filters(input.symbol)  # depuis exchange_info_cache
    signal = compute_signal(
        cascade=cascade,
        candle_1m=_to_candle(input.candle_1m),
        snapshot_1m=input.snapshot_1m,
        snapshot_5m=input.snapshot_5m,
        filters=filters,
        config=config,
    )

# 4. Retourner le résultat
return CascadeResultData(
    cascade=cascade,
    signal=signal,
)
```

**Heartbeat :** non nécessaire (opération rapide).

---

### Activity 4 — `create_buy_intent`

```python
@activity.defn
async def create_buy_intent(input: CreateBuyIntentInput) -> CreateBuyIntentOutput:
```

**Logique :**
```python
# 1. Vérifier qu'aucune position n'est déjà ouverte sur ce symbole
existing = await position_repo.get_open_by_symbol(input.symbol)
if existing:
    return CreateBuyIntentOutput(skipped=True, reason="position_already_open")

# 2. Vérifier la limite de positions ouvertes
open_count = await position_repo.count_open()
if open_count >= config.max_open_positions:
    return CreateBuyIntentOutput(skipped=True, reason="max_positions_reached")

# 3. Vérifier l'exposition totale (max 40 % du capital)
# balances = await binance_rest.get_account_balances()
# total_capital = balances.get("USDC", Decimal("0"))
# ... calcul exposition

# 4. Calculer la quantité via risk.py (déjà implémenté)
balance = await _get_usdc_balance()
quantity = size_order(
    quote_budget=min(balance * Decimal(str(input.signal.risk_pct)), Decimal(str(config.per_trade_quote_budget))),
    price=input.signal.entry_price,
)
quantity = BinanceFilters.round_quantity(quantity, input.filters)

# 5. Vérifier MIN_NOTIONAL
BinanceFilters.validate_order(quantity, input.signal.entry_price, input.filters)

# 6. Construire l'ExitPlan (lots A, B, C)
exit_plan = _build_exit_plan(input.signal, quantity, config)

# 7. Créer la Position (état PENDING_ENTRY)
position = Position(
    id=str(uuid4()),
    symbol=input.symbol,
    entry_price=input.signal.entry_price,
    stop_loss=input.signal.stop_loss,
    quantity_total=quantity,
    exit_plan=exit_plan,
    ...
)

# 8. Créer l'OrderIntent BUY
intent_key = make_intent_key(input.symbol, "BUY", input.signal.trigger_candle_open_ms, "entry")
existing_intent = await order_intent_repo.get_by_intent_key(intent_key)
if existing_intent:
    return CreateBuyIntentOutput(intent=existing_intent, position=position, skipped=False)

intent = OrderIntent(
    id=str(uuid4()),
    intent_key=intent_key,
    symbol=input.symbol,
    side="BUY",
    order_type="LIMIT",
    quantity=quantity,
    price=input.signal.entry_price,
    position_id=position.id,
    status=OrderIntentStatus.PENDING,
)

# 9. Persister (position + intent) dans une transaction
async with session_factory() as session:
    async with session.begin():
        await position_repo.create(position, session=session)
        await order_intent_repo.create(intent, session=session)

return CreateBuyIntentOutput(intent=intent, position=position, skipped=False)
```

---

### Activity 5 — `place_order`

```python
@activity.defn
async def place_order(input: PlaceOrderInput) -> PlaceOrderOutput:
```

**Double garde live trading :**
```python
settings = Settings()
if settings.execution_mode != "live" or not settings.live_trading_approved:
    log.info("place_order_skipped_not_live", mode=settings.execution_mode)
    return PlaceOrderOutput(
        order_id=None,
        simulated=True,
        status="SIMULATED",
    )
```

**Logique (mode live) :**
```python
# 1. Vérifier que l'intent n'est pas déjà FILLED ou CANCELLED (idempotence)
intent = await order_intent_repo.get_by_id(input.intent_id)
if intent.status in (OrderIntentStatus.FILLED, OrderIntentStatus.CANCELLED):
    return PlaceOrderOutput(order_id=intent.binance_order_id, simulated=False, ...)

# 2. Placer l'ordre via BinanceRestClient
try:
    response = await binance_rest.place_order(
        symbol=input.symbol,
        side=intent.side,
        order_type=intent.order_type,
        quantity=intent.quantity,
        price=intent.price,
        client_order_id=intent.id,  # UUID = client_order_id pour idempotence Binance
    )
except BinanceRateLimitError:
    raise  # Temporal va retry
except BinanceInvalidQtyError as e:
    await order_intent_repo.update_status(intent.id, OrderIntentStatus.FAILED, error_msg=str(e))
    raise ApplicationError(f"invalid_qty: {e}", non_retryable=True)

# 3. Mettre à jour l'intent
await order_intent_repo.update_status(
    intent.id,
    OrderIntentStatus.SENT,
    binance_order_id=response.data["orderId"],
)

# 4. Mettre à jour la position (OPEN_ENTRY_SENT)
await position_repo.update(position.with_status(PositionStatus.OPEN_ENTRY_SENT))

return PlaceOrderOutput(order_id=response.data["orderId"], simulated=False, status="SENT")
```

---

### Activity 6 — `cancel_order`

```python
@activity.defn
async def cancel_order(input: CancelOrderInput) -> None:
```

**Logique :**
```python
# Annuler l'ordre sur Binance si encore SENT (pas encore FILLED)
# Si erreur -2011 (order not found) → considérer comme déjà annulé
# Mettre à jour intent.status = CANCELLED
```

## Contraintes communes

- `place_order` : `ApplicationError(non_retryable=True)` sur `-1013`, `-2010` (qty invalide, doublon résolu)
- `create_buy_intent` : transaction atomique position + intent (pas de position sans intent)
- Tous les Decimal sérialisés en str dans les dataclasses Temporal (JSON-serializable)

## Tests

- `tests/unit/test_execution_activities.py`
  - `place_order` en mode backtesting → retourne simulated=True sans appel REST
  - `create_buy_intent` : skip si position déjà ouverte
  - `create_buy_intent` : skip si max_positions atteint
  - `place_order` : idempotent si intent déjà FILLED
  - `cancel_order` : -2011 → CANCELLED silencieux

## Critères d'acceptation

1. `place_order` ne passe jamais d'ordre si `execution_mode != live`
2. `create_buy_intent` idempotent via `intent_key`
3. Position et OrderIntent créés dans la même transaction DB
4. `place_order` idempotent : intent FILLED → retourne sans appel Binance
5. `cancel_order` : erreur -2011 (already cancelled) → pas d'exception
