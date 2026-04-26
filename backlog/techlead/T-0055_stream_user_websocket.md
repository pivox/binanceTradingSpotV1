---
id: T-0055
title: "Stream - User Stream WebSocket Binance : fills et mises à jour d'ordres en temps réel"
status: TODO
owner: techlead
phase: 4
priority: P1
links: ["T-0042", "T-0054"]
---

## Contexte

`src/tradebot/apps/user_stream_main.py` lève `NotImplementedError`.
`src/tradebot/infra/binance/ws_user.py` est une classe vide.

Le User Stream Binance est le canal temps réel pour recevoir les événements de fills
d'ordres (exécution partielle/totale), les mises à jour de statut d'ordres,
et les changements de balance. Il complète `reconcile_orders` (T-0054) qui tourne
toutes les 10 min : le user stream fournit la même information en quasi-temps réel
(< 1 seconde de latence).

**Relation avec reconcile_orders :** le user stream accélère la propagation des fills.
`reconcile_orders` reste la source de vérité et le filet de sécurité.

## Périmètre

### Architecture

```
Binance User Stream WebSocket
  wss://stream.binance.com:9443/ws/<listenKey>
      ↓ executionReport events
BinanceWsUser (infra)
      ↓ callbacks
UserStreamHandler (apps)
      ↓
OrderIntentRepoSql + PositionRepoSql (DB updates)
```

### BinanceWsUser — `src/tradebot/infra/binance/ws_user.py`

```python
class BinanceWsUser:
    def __init__(
        self,
        settings: Settings,
        on_execution_report: Callable[[dict], Awaitable[None]],
        on_balance_update: Callable[[dict], Awaitable[None]],
    ) -> None: ...

    async def start(self) -> None:
        """
        1. Créer un listenKey via POST /api/v3/userDataStream
        2. Ouvrir le WebSocket sur wss://stream.binance.com:9443/ws/{listenKey}
        3. Écouter les messages et router vers les callbacks
        4. Renouveler le listenKey toutes les 30 min (keepalive via PUT)
        5. Reconnexion automatique avec backoff exponentiel
        """

    async def stop(self) -> None:
        """Fermer proprement : DELETE /api/v3/userDataStream + close WebSocket."""
```

### Gestion du listenKey

```python
# Création
POST /api/v3/userDataStream  → {"listenKey": "..."}

# Keepalive (toutes les 30 min, expire après 60 min sans keepalive)
PUT /api/v3/userDataStream?listenKey=...

# Suppression
DELETE /api/v3/userDataStream?listenKey=...

# Si le listenKey expire → recréer et reconnecter
```

### Events à traiter

#### `executionReport` (le plus important)

```json
{
  "e": "executionReport",
  "s": "BTCUSDC",
  "c": "my-intent-uuid",          ← clientOrderId = notre intent.id
  "S": "BUY",
  "o": "LIMIT",
  "q": "0.001",                   ← quantité commandée
  "p": "45000.00",                ← prix limite
  "X": "FILLED",                  ← statut
  "i": 123456789,                 ← orderId Binance
  "l": "0.001",                   ← quantité exécutée sur ce fill
  "z": "0.001",                   ← quantité totale exécutée
  "L": "45000.50",                ← prix du dernier fill
  "n": "0.00001000",              ← commission
  "N": "BNB",                     ← asset commission
  "T": 1700000000000,             ← trade time ms
}
```

**Traitement :**
```python
async def _handle_execution_report(event: dict) -> None:
    client_order_id = event["c"]    # = notre intent.id (UUID)
    binance_order_id = event["i"]
    status = event["X"]             # NEW | PARTIALLY_FILLED | FILLED | CANCELED | EXPIRED
    filled_qty = Decimal(event["z"])
    avg_price = Decimal(event["L"])

    intent = await order_intent_repo.get_by_id(client_order_id)
    if not intent:
        log.warning("user_stream_unknown_order", client_order_id=client_order_id)
        return

    # Même logique que reconcile_orders Phase 4
    await _sync_intent_with_binance_status(intent, status, filled_qty, avg_price, binance_order_id)
```

#### `outboundAccountPosition` (balance update)

```python
async def _handle_balance_update(event: dict) -> None:
    # Mettre à jour un cache mémoire des balances (pas en DB)
    # Utilisé pour vérifier le solde disponible avant de créer un intent BUY
    for balance in event["B"]:
        _balance_cache[balance["a"]] = Decimal(balance["f"])  # "f" = free
```

### UserStreamHandler — `src/tradebot/apps/user_stream_main.py`

```python
async def main() -> None:
    load_dotenv()
    settings = Settings()

    # Injection des dépendances
    session_factory = create_session_factory(settings)
    order_intent_repo = OrderIntentRepoSql(session_factory)
    position_repo = PositionRepoSql(session_factory)

    handler = UserStreamHandler(order_intent_repo, position_repo)

    ws_user = BinanceWsUser(
        settings=settings,
        on_execution_report=handler.handle_execution_report,
        on_balance_update=handler.handle_balance_update,
    )

    # Graceful shutdown sur SIGTERM/SIGINT
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(ws_user.stop()))

    await ws_user.start()
```

### Reconnexion et résilience

```python
RECONNECT_DELAYS = [1, 2, 4, 8, 16, 30]  # secondes, plafonné à 30s

async def _reconnect_loop(self) -> None:
    attempt = 0
    while not self._stopped:
        try:
            await self._connect_and_listen()
            attempt = 0  # reset sur connexion réussie
        except Exception as e:
            delay = RECONNECT_DELAYS[min(attempt, len(RECONNECT_DELAYS) - 1)]
            log.warning("user_stream_reconnect", attempt=attempt, delay=delay, error=str(e))
            self._metrics_reconnect_total.inc()
            await asyncio.sleep(delay)
            attempt += 1
```

### Métriques Prometheus

```python
# Dans observability/metrics.py, ajouter :
user_stream_events_total = Counter(
    "tradebot_user_stream_events_total",
    "Total user stream events received",
    ["event_type"],
)
user_stream_reconnect_total = Counter(
    "tradebot_user_stream_reconnect_total",
    "Total user stream reconnections",
)
user_stream_fill_latency_seconds = Histogram(
    "tradebot_user_stream_fill_latency_seconds",
    "Latency between order fill and DB update",
)
```

## Contraintes techniques

- **listenKey keepalive** : tâche `asyncio` indépendante qui tourne toutes les 30 min
- **listenKey expiré** : si WebSocket se coupe avec code 1006 (no listen key) → recréer le listenKey avant de reconnecter
- **Idempotence** : un fill peut arriver en double (reconnexion) → `_sync_intent_with_binance_status` idempotente
- **Ne jamais bloquer** la boucle WebSocket dans les callbacks : utiliser `asyncio.create_task()` pour les opérations DB longues
- **Pas de perte sur crash** : `reconcile_orders` reste le filet de sécurité, le user stream est une optimisation

## Hors périmètre

- WebSocket market stream (déjà dans ws_candle_daemon)
- Gestion du trailing stop (dans ExitEngine)
- Annulation d'ordres (dans cancel_order activity)

## Tests

- `tests/unit/test_binance_ws_user.py`
  - Mock WebSocket, tester routing executionReport → callback
  - Tester keepalive listenKey (appel PUT toutes les 30 min)
  - Tester reconnexion sur disconnect avec backoff

- `tests/unit/test_user_stream_handler.py`
  - Fill BUY → position ACTIVE
  - Fill SELL lot A → lot_a.is_filled = True, breakeven activé
  - Fill SELL tous lots → position CLOSED
  - Event inconnu (client_order_id non trouvé) → warning, pas crash

## Critères d'acceptation

1. listenKey keepalive toutes les 30 min (pas d'expiration)
2. Reconnexion automatique avec backoff exponentiel plafonné à 30s
3. Fill idempotent (doublon sur reconnexion → pas de double mise à jour)
4. DB callbacks dans `asyncio.create_task()` (pas de blocage WebSocket)
5. Métriques Prometheus : events_total, reconnect_total, fill_latency
6. Graceful shutdown : DELETE listenKey avant fermeture
