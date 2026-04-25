---
id: T-0043
title: "Infra - BinanceMapper + BinanceFilters : conversion raw JSON → domaine et arrondi Binance"
status: TODO
owner: techlead
phase: 1
priority: P0
links: ["T-0042", "T-0045", "T-0052"]
---

## Contexte

`mapper.py` et `filters.py` sont des classes vides.
Le mapper convertit les réponses JSON brutes de Binance en objets domaine.
Les filters appliquent les règles d'arrondi Binance sur quantités et prix
(LOT_SIZE, TICK_SIZE, MIN_NOTIONAL) avant de placer tout ordre.

Un ordre avec une quantité mal arrondie est rejeté par Binance avec `-1013`.
Ce composant est critique pour l'exactitude des ordres.

## Périmètre

### BinanceMapper — `src/tradebot/infra/binance/mapper.py`

Conversion des réponses API Binance vers les dataclasses du domaine.

```python
class BinanceMapper:

    @staticmethod
    def kline_to_candle(raw: list, symbol: str, timeframe: str) -> Candle:
        """
        raw = [open_time, open, high, low, close, volume,
               close_time, quote_volume, trades, ...]
        Tous les champs prix/volume sont des str Binance → Decimal.
        open_time et close_time sont en ms (int).
        """

    @staticmethod
    def order_response_to_order_intent(raw: dict) -> OrderIntent:
        """
        Champs clés : orderId, clientOrderId, symbol, side, type,
                      origQty, executedQty, price, stopPrice,
                      status, transactTime.
        status Binance → OrderIntentStatus du domaine.
        """

    @staticmethod
    def exchange_info_to_filters(raw: dict) -> dict[str, SymbolFilters]:
        """
        Extraire par symbole :
          LOT_SIZE  → min_qty, max_qty, step_size
          PRICE_FILTER → min_price, max_price, tick_size
          NOTIONAL / MIN_NOTIONAL → min_notional
        Retourner dict[symbol, SymbolFilters].
        """

    @staticmethod
    def account_to_balances(raw: dict) -> dict[str, Decimal]:
        """
        raw["balances"] = [{"asset": "BTC", "free": "0.5", "locked": "0.1"}, ...]
        Retourner dict[asset, free_balance].
        """
```

### Dataclass `SymbolFilters` (nouveau, à créer dans `domain/models/`)

```python
@dataclass(frozen=True)
class SymbolFilters:
    symbol: str
    step_size: Decimal        # LOT_SIZE step
    min_qty: Decimal
    max_qty: Decimal
    tick_size: Decimal        # PRICE_FILTER tick
    min_price: Decimal
    max_price: Decimal
    min_notional: Decimal     # valeur minimale de l'ordre en quote asset
```

### BinanceFilters — `src/tradebot/infra/binance/filters.py`

Arrondi conforme Binance. **Règle Binance** : arrondir vers le bas (floor) sur step_size.

```python
class BinanceFilters:

    @staticmethod
    def round_quantity(qty: Decimal, filters: SymbolFilters) -> Decimal:
        """
        Floor(qty / step_size) × step_size
        Nombre de décimales = nb de chiffres après la virgule de step_size.
        """

    @staticmethod
    def round_price(price: Decimal, filters: SymbolFilters) -> Decimal:
        """
        Round(price / tick_size) × tick_size
        (pour les prix on arrondit au plus proche, pas floor)
        """

    @staticmethod
    def validate_order(
        qty: Decimal,
        price: Decimal,
        filters: SymbolFilters,
    ) -> None:
        """
        Lever ValueError si :
          qty < min_qty
          qty > max_qty
          qty × price < min_notional
          price < min_price (si price fourni)
          price > max_price (si price fourni)
        """

    @staticmethod
    def apply(
        qty: Decimal,
        price: Decimal | None,
        filters: SymbolFilters,
    ) -> tuple[Decimal, Decimal | None]:
        """
        Raccourci : round_quantity + round_price + validate_order.
        Retourne (rounded_qty, rounded_price).
        """
```

## Contraintes techniques

### Précision Decimal
- Utiliser `decimal.Decimal` partout, jamais de float
- `Decimal(str(raw_value))` pour parser les strings Binance (éviter erreurs flottantes)
- Contexte : `decimal.getcontext().prec = 28`

### Floor sur les quantités
```python
# Exemple correct pour step_size = Decimal("0.001")
step = Decimal("0.001")
qty = Decimal("1.2349")
rounded = (qty // step) * step  # → Decimal("1.234")
```

### Gestion des symboles inconnus
- `exchange_info_to_filters` : ignorer silencieusement les symboles sans les 3 filtres attendus
- Logger un warning avec le symbole concerné

## Hors périmètre

- Appels HTTP (dans `rest.py`)
- Logique de retry
- Cache des filtres (géré par `ExchangeInfoCache` en DB)

## Structure fichiers

```
src/tradebot/
├── domain/models/
│   └── symbol_filters.py    ← nouveau dataclass SymbolFilters
└── infra/binance/
    ├── mapper.py             ← implémenter
    └── filters.py            ← implémenter
```

## Tests

- `tests/unit/test_binance_mapper.py`
  - Fixtures : payloads JSON réels de l'API Binance (copiés depuis la doc)
  - Tester : kline → Candle (tous les champs, types Decimal), order → OrderIntent, exchange_info parsing
- `tests/unit/test_binance_filters.py`
  - Tester floor sur qty (pas round), tick_size sur price
  - Tester validate_order : qty trop petite, notional insuffisant
  - Tester step_size = "0.00000100" (précision extrême, paires BTC)

## Critères d'acceptation

1. `round_quantity` floor strict (jamais au-dessus du qty initial)
2. `validate_order` lève `ValueError` avec message lisible sur chaque violation
3. Tous les prix/volumes en `Decimal`, zéro float dans le code
4. `exchange_info_to_filters` robuste aux symboles incomplets (warning, pas crash)
5. `kline_to_candle` : `open_time_ms` et `close_time_ms` corrects en ms
