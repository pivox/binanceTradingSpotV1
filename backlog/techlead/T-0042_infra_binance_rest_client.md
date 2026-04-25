---
id: T-0042
title: "Infra - BinanceRestClient : client HTTP Binance pour ordres, klines et compte"
status: TODO
owner: techlead
phase: 1
priority: P0
links: ["T-0044", "T-0045", "T-0051", "T-0052"]
---

## Contexte

`src/tradebot/infra/binance/rest.py` est une classe vide.
Toute la chaîne d'exécution (ordres, backfill, exchange info) dépend de ce client.
C'est le premier composant à implémenter — rien d'autre ne peut être intégré sans lui.

## Périmètre

Implémenter `BinanceRestClient` dans `src/tradebot/infra/binance/rest.py`.

### Endpoints à couvrir

| Méthode | Endpoint | Usage |
|---------|----------|-------|
| GET | `/api/v3/klines` | Backfill candles |
| GET | `/api/v3/exchangeInfo` | Filtres LOT_SIZE, TICK_SIZE, NOTIONAL |
| GET | `/api/v3/ticker/24hr` | Sélection paires USDC par volume |
| GET | `/api/v3/account` | Soldes disponibles par asset |
| POST | `/api/v3/order` | Placer ordre LIMIT ou STOP_MARKET |
| DELETE | `/api/v3/order` | Annuler un ordre ouvert |
| GET | `/api/v3/order` | Statut d'un ordre |
| GET | `/api/v3/openOrders` | Tous les ordres ouverts d'un symbole |

### Interface publique attendue

```python
class BinanceRestClient:
    def __init__(self, settings: Settings) -> None: ...

    # Marché
    async def get_klines(
        self, symbol: str, interval: str,
        start_ms: int | None = None,
        end_ms: int | None = None,
        limit: int = 1000,
    ) -> list[dict]: ...

    async def get_ticker_24h(self, symbol: str | None = None) -> list[dict]: ...

    async def get_exchange_info(self, symbols: list[str] | None = None) -> dict: ...

    # Compte
    async def get_account_balances(self) -> dict[str, Decimal]: ...

    # Ordres
    async def place_order(
        self,
        symbol: str,
        side: str,           # "BUY" | "SELL"
        order_type: str,     # "LIMIT" | "STOP_MARKET" | "MARKET"
        quantity: Decimal,
        price: Decimal | None = None,
        stop_price: Decimal | None = None,
        client_order_id: str | None = None,
        time_in_force: str = "GTC",
    ) -> dict: ...

    async def cancel_order(self, symbol: str, order_id: int) -> dict: ...

    async def get_order(self, symbol: str, order_id: int) -> dict: ...

    async def get_open_orders(self, symbol: str) -> list[dict]: ...
```

## Contraintes techniques

### Authentification
- Signature HMAC-SHA256 sur les requêtes privées (compte + ordres)
- Header `X-MBX-APIKEY` avec la clé API
- Paramètre `signature` = HMAC-SHA256(query_string, secret)
- Paramètre `timestamp` = epoch ms, `recvWindow` = 5000 ms

### HTTP
- Client : `aiohttp.ClientSession` (réutiliser la session, ne pas créer par requête)
- Timeout : `aiohttp.ClientTimeout(total=10)` sur les ordres, `total=30` sur le backfill
- Base URL issue de `settings.binance_rest_url` (permet de pointer sur le testnet)

### Rate limiting
- Exposer les headers de réponse : `X-MBX-USED-WEIGHT-1M`, `X-MBX-ORDER-COUNT-10S`
- Retourner ces valeurs dans un objet `RestResponse(data, weight_used, order_count)`
- Ne PAS gérer le rate limiting ici (c'est la responsabilité de l'appelant)

### Gestion d'erreurs
- HTTP 4xx Binance : parser le JSON `{"code": -XXXX, "msg": "..."}` et lever une exception typée :
  - `BinanceApiError(code, msg, http_status)`
  - Sous-classes : `BinanceRateLimitError` (429), `BinanceIpBanError` (418), `BinanceInvalidQtyError` (-1013)
- HTTP 5xx : lever `BinanceServerError`
- Timeout : lever `BinanceTimeoutError`
- Pas de retry ici — la logique de retry appartient aux activités Temporal

### Idempotence ordres
- Toujours passer `newClientOrderId` = `client_order_id` fourni par l'appelant
- Binance rejette un doublon de `clientOrderId` avec `-2010` → catcher et retourner l'ordre existant

## Hors périmètre

- WebSocket market/user stream (tickets séparés)
- Retry automatique (géré par Temporal)
- Rate limiting proactif (géré par l'activité appelante)

## Structure fichiers

```
src/tradebot/infra/binance/
├── rest.py          ← implémenter ici
├── exceptions.py    ← créer : BinanceApiError et sous-classes
└── _signing.py      ← créer : sign_query(params, secret) → str
```

## Tests

- `tests/unit/test_binance_rest.py`
  - Mock `aiohttp.ClientSession` avec `aresponses` ou `pytest-aiohttp`
  - Tester : signature correcte, parsing erreur, BinanceRateLimitError, timeout
- `tests/integration/test_binance_rest_live.py` (skip si pas de clé)
  - Tester `get_klines("BTCUSDC", "1m", limit=10)` sur testnet

## Critères d'acceptation

1. Tous les endpoints listés fonctionnels en mode testnet
2. Signature HMAC validée par Binance (pas d'erreur -1100/-1022)
3. `BinanceRateLimitError` et `BinanceIpBanError` levées correctement sur 429/418
4. `client_order_id` doublon → retourne l'ordre existant sans exception
5. Headers de poids retournés dans `RestResponse`
6. Session `aiohttp` réutilisée (pas de création par appel)
