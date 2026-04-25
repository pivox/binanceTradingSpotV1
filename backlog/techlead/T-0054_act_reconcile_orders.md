---
id: T-0054
title: "Temporal - Activity reconcile_orders : synchronisation état local ↔ Binance"
status: TODO
owner: techlead
phase: 3
priority: P1
links: ["T-0042", "T-0045", "T-0046", "T-0053"]
---

## Contexte

`reconcile_orders` retourne actuellement `{"ok": True, "fixed": 0}` sans rien faire.
C'est l'activité critique de sécurité : elle détecte les divergences entre l'état
local (DB) et l'état réel sur Binance, et les corrige.

Sans cette réconciliation, des positions peuvent rester "ouvertes" en DB alors
que les ordres SELL ont été exécutés sur Binance, ou inversement.

Cadence : toutes les 10 minutes (schedule Temporal existant).

## Périmètre

### Signature

```python
@activity.defn
async def reconcile_orders(input: ReconcileOrdersInput) -> ReconcileOrdersOutput:
```

```python
@dataclass
class ReconcileOrdersInput:
    dry_run: bool = False    # True = détecter sans corriger (utile pour debug)

@dataclass
class ReconcileOrdersOutput:
    checked: int
    fixed: int
    errors: int
    details: list[ReconcileAction]

@dataclass
class ReconcileAction:
    symbol: str
    position_id: str
    intent_id: str
    action: str          # "mark_filled" | "mark_cancelled" | "cancel_stale" | "reopen"
    binance_order_id: int | None
    reason: str
```

### Algorithme

#### Phase 1 — Récupérer tous les intents en cours

```python
# Lire tous les OrderIntent avec status IN (PENDING, SENT, PARTIALLY_FILLED)
pending_intents = await order_intent_repo.list_active()
```

#### Phase 2 — Pour chaque intent, interroger Binance

```python
for intent in pending_intents:
    try:
        binance_order = await binance_rest.get_order(
            symbol=intent.symbol,
            order_id=intent.binance_order_id,
        )
    except BinanceApiError as e:
        if e.code == -2013:   # order does not exist
            # L'ordre n'existe pas sur Binance → considérer CANCELLED
            await _handle_order_not_found(intent)
        else:
            log.error("reconcile_get_order_failed", intent_id=intent.id, error=str(e))
            errors += 1
        continue

    await _sync_intent_with_binance(intent, binance_order)
```

#### Phase 3 — Synchronisation intent ↔ Binance

```python
async def _sync_intent_with_binance(intent: OrderIntent, binance: dict):
    binance_status = binance["status"]
    # Statuts Binance : NEW | PARTIALLY_FILLED | FILLED | CANCELED | EXPIRED | REJECTED

    if binance_status == "FILLED" and intent.status != OrderIntentStatus.FILLED:
        await _mark_intent_filled(
            intent=intent,
            filled_qty=Decimal(binance["executedQty"]),
            avg_price=Decimal(binance["price"]),
            binance_order_id=binance["orderId"],
        )

    elif binance_status in ("CANCELED", "EXPIRED", "REJECTED") and intent.status not in (
        OrderIntentStatus.CANCELLED, OrderIntentStatus.FAILED
    ):
        await _mark_intent_cancelled(intent, reason=binance_status.lower())

    elif binance_status == "PARTIALLY_FILLED":
        await order_intent_repo.update_status(
            intent.id,
            OrderIntentStatus.PARTIALLY_FILLED,
            filled_qty=Decimal(binance["executedQty"]),
        )
```

#### Phase 4 — Propagation sur la position

```python
async def _mark_intent_filled(intent: OrderIntent, filled_qty: Decimal, avg_price: Decimal, ...):
    # Mettre à jour l'intent
    await order_intent_repo.update_status(
        intent.id, OrderIntentStatus.FILLED,
        filled_qty=filled_qty, avg_price=avg_price,
    )

    if not intent.position_id:
        return  # ordre orphelin, rien à faire

    position = await position_repo.get_by_id(intent.position_id)
    if not position:
        return

    if intent.side == "BUY":
        # Position passe en ACTIVE, enregistrer l'entry price réel
        position = replace(
            position,
            status=PositionStatus.ACTIVE,
            entry_price=avg_price,   # prix moyen réel, pas le prix limite demandé
        )

    elif intent.side == "SELL":
        lot_id = intent.lot_id
        position = _mark_lot_filled_on_position(position, lot_id, filled_qty, avg_price)

        # Si tous les lots sont filled → CLOSED
        if _all_lots_filled(position):
            position = replace(
                position,
                status=PositionStatus.CLOSED,
                closed_at_ms=int(time.time() * 1000),
            )

    await position_repo.update(position)
```

#### Phase 5 — Détecter les ordres SENT trop vieux

```python
STALE_THRESHOLD_MS = 3 * 60 * 1000  # 3 minutes pour un ordre LIMIT

for intent in pending_intents:
    age_ms = now_ms - intent.created_at_ms
    if intent.status == OrderIntentStatus.SENT and age_ms > STALE_THRESHOLD_MS:
        # Tenter d'annuler l'ordre sur Binance
        try:
            await binance_rest.cancel_order(intent.symbol, intent.binance_order_id)
        except BinanceApiError as e:
            if e.code != -2011:  # order already cancelled
                log.error("reconcile_cancel_failed", ...)
                continue

        await order_intent_repo.update_status(intent.id, OrderIntentStatus.CANCELLED, reason="stale")
        # Mettre la position en statut PENDING_ENTRY (réessayer l'entrée)
        await _reset_position_to_pending(intent.position_id)
```

#### Phase 6 — Vérifier les positions ACTIVE sans ordres SELL placés

```python
# Pour chaque position ACTIVE :
# - Vérifier que les ordres TP Lot A et TP Lot B existent bien sur Binance
# - Vérifier que le SL global (STOP_MARKET) existe bien
# Si un ordre manque → le recréer via create_sell_intent + place_order
# (protection contre perte d'ordre suite à disconnect WebSocket user stream)
```

## Contraintes techniques

- **Rate limiting** : `get_order` coûte 4 de poids Binance. Avec 10 positions × 3 lots = 30 appels max.
  Respecter la limite de 1200 poids/min → espacer les appels de 150ms minimum.
- **Heartbeat Temporal** : envoyer un heartbeat toutes les 10 itérations (opération longue possible).
- **dry_run** : si True, détecter mais ne rien écrire en DB, juste retourner les `ReconcileAction`.
- **Idempotence** : appelé toutes les 10 min, doit être sûr à rejouer.

## Tests

- `tests/unit/test_reconcile_orders.py`
  - Intent SENT + Binance FILLED → position ACTIVE, intent FILLED
  - Intent SENT + Binance -2013 (not found) → intent CANCELLED
  - Intent SENT stale (> 3 min) → cancel Binance + PENDING_ENTRY
  - Lot A SELL FILLED → lot_a.is_filled = True sur la position
  - Tous lots FILLED → position CLOSED
  - dry_run → aucune écriture DB

## Critères d'acceptation

1. Intent FILLED sur Binance → propagation sur la position (status + prix réel)
2. Intent -2013 Binance (disparu) → CANCELLED sans exception
3. Ordres LIMIT stale > 3 min → annulés et position reset
4. `dry_run=True` → zéro modification DB
5. Rate limiting respecté (pause entre appels REST)
6. Heartbeat Temporal envoyé sur les longues réconciliations
