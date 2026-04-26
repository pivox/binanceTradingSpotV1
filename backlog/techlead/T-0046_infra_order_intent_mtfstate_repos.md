---
id: T-0046
title: "Infra - OrderIntentRepoSql + MtfStateRepoSql : persistance des intents et de l'état MTF"
status: TODO
owner: techlead
phase: 1
priority: P0
links: ["T-0045", "T-0052", "T-0053"]
---

## Contexte

Deux repos sont des classes vides :
- `order_intent_repo_sql.py` : stocke les intentions d'ordre avant envoi à Binance
- `mtf_state_repo_sql.py` : stocke l'état de la cascade MTF par symbole (persist entre les runs Temporal)

## Périmètre — OrderIntentRepoSql

### Rôle

`OrderIntent` est la représentation d'un ordre avant et après son envoi à Binance.
Il sert de journal d'idempotence : si Temporal rejoue une activité, on ne place pas deux fois le même ordre.

### Interface publique

```python
class OrderIntentRepoSql:
    def __init__(self, session_factory: async_sessionmaker) -> None: ...

    async def create(self, intent: OrderIntent) -> None:
        """INSERT. Idempotent sur intent.id (clé de déduplication)."""

    async def get_by_id(self, intent_id: str) -> OrderIntent | None: ...

    async def get_by_intent_key(self, intent_key: str) -> OrderIntent | None:
        """
        intent_key = make_intent_key(symbol, side, open_time_ms, lot_id).
        Permet de détecter un doublon avant de placer l'ordre.
        """

    async def update_status(
        self,
        intent_id: str,
        status: OrderIntentStatus,
        binance_order_id: int | None = None,
        filled_qty: Decimal | None = None,
        avg_price: Decimal | None = None,
        error_msg: str | None = None,
    ) -> None:
        """
        Met à jour le statut après retour de Binance.
        Statuts : PENDING → SENT → FILLED | PARTIALLY_FILLED | CANCELLED | FAILED
        """

    async def list_pending_by_symbol(self, symbol: str) -> list[OrderIntent]:
        """Ordres PENDING ou SENT non encore résolus."""

    async def list_by_position(self, position_id: str) -> list[OrderIntent]:
        """Tous les intents d'une position (pour réconciliation)."""
```

### Modèle ORM à ajouter dans `models.py`

```python
class OrderIntentModel(Base):
    __tablename__ = "order_intents"

    id = Column(String(36), primary_key=True)           # UUID
    intent_key = Column(String(128), unique=True, nullable=False)  # clé idempotence
    position_id = Column(String(36), nullable=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(String(4), nullable=False)             # BUY | SELL
    order_type = Column(String(20), nullable=False)      # LIMIT | STOP_MARKET | MARKET
    quantity = Column(Numeric(20, 8), nullable=False)
    price = Column(Numeric(20, 8), nullable=True)        # None si MARKET
    stop_price = Column(Numeric(20, 8), nullable=True)
    lot_id = Column(String(1), nullable=True)            # A | B | C | None (pour BUY)
    status = Column(String(20), nullable=False, index=True)
    binance_order_id = Column(BigInteger, nullable=True)
    filled_qty = Column(Numeric(20, 8), nullable=True)
    avg_price = Column(Numeric(20, 8), nullable=True)
    error_msg = Column(Text, nullable=True)
    created_at_ms = Column(BigInteger, nullable=False)
    updated_at_ms = Column(BigInteger, nullable=False)
```

---

## Périmètre — MtfStateRepoSql

### Rôle

La cascade MTF maintient un état par symbole : régime de marché, scores par timeframe,
timestamp du dernier signal évalué. Cet état est persisté entre les exécutions
du workflow Temporal pour éviter de recalculer depuis zéro à chaque run.

### Interface publique

```python
class MtfStateRepoSql:
    def __init__(self, session_factory: async_sessionmaker) -> None: ...

    async def get(self, symbol: str) -> MtfState | None:
        """Retourne l'état courant ou None si jamais évalué."""

    async def upsert(self, state: MtfState) -> None:
        """INSERT ON CONFLICT (symbol) DO UPDATE."""

    async def list_all(self) -> list[MtfState]:
        """Tous les états — pour debug/monitoring."""

    async def delete(self, symbol: str) -> None:
        """Reset d'un état (si le symbole est retiré du marché)."""
```

### Dataclass `MtfState` — vérifier `domain/models/mtf_state.py`

```python
@dataclass
class MtfState:
    symbol: str
    regime: str                    # TRENDING_UP | RANGING | RECOVERY | TRENDING_DOWN | VOLATILE
    cascade_passed: bool
    score: float
    quality: str                   # HIGH | MEDIUM | LOW | REJECTED
    active_setup: str | None       # A | B | C | D
    scores_by_tf: dict[str, float] # {"4h": 0.8, "1h": 0.6, ...}
    rejection_reason: str | None
    evaluated_at_ms: int
    signal_open_time_ms: int | None  # open_time_ms du signal en cours (pour expiry)
```

### Modèle ORM

```python
class MtfStateModel(Base):
    __tablename__ = "mtf_states"

    symbol = Column(String(20), primary_key=True)
    regime = Column(String(20), nullable=False)
    cascade_passed = Column(Boolean, nullable=False)
    score = Column(Float, nullable=False)
    quality = Column(String(10), nullable=False)
    active_setup = Column(String(1), nullable=True)
    scores_by_tf_json = Column(Text, nullable=False)     # dict sérialisé
    rejection_reason = Column(Text, nullable=True)
    evaluated_at_ms = Column(BigInteger, nullable=False)
    signal_open_time_ms = Column(BigInteger, nullable=True)
```

## Contraintes techniques

### Idempotence OrderIntent
- `create()` : `INSERT ... ON CONFLICT (id) DO NOTHING`
- La clé d'idempotence réelle est `intent_key` (unique constraint)
- Si `intent_key` existe déjà → retourner l'existant silencieusement (log DEBUG)

### MtfState upsert
```sql
INSERT INTO mtf_states (...) VALUES (...)
ON CONFLICT (symbol) DO UPDATE SET
  regime = EXCLUDED.regime,
  cascade_passed = EXCLUDED.cascade_passed,
  ...
  evaluated_at_ms = EXCLUDED.evaluated_at_ms
```

## Tests

- `tests/unit/test_order_intent_repo_sql.py`
  - Idempotence create (doublon id → no-op)
  - Idempotence intent_key (doublon key → retourne existant)
  - `update_status` : transitions valides
- `tests/unit/test_mtf_state_repo_sql.py`
  - Round-trip upsert → get (scores_by_tf dict préservé)
  - Upsert 2 fois le même symbole → dernier état gagne

## Critères d'acceptation

1. `OrderIntent.create()` idempotent sur `id` ET sur `intent_key`
2. `update_status()` ne peut pas rétrograder (FILLED → PENDING interdit)
3. `MtfStateRepoSql.upsert()` : `ON CONFLICT DO UPDATE` (pas de doublon)
4. Round-trip complet sans perte pour `scores_by_tf`
