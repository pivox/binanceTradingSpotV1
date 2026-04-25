---
id: T-0045
title: "Infra - PositionRepoSql : CRUD des positions ouvertes"
status: TODO
owner: techlead
phase: 1
priority: P0
links: ["T-0052", "T-0053", "T-0054"]
---

## Contexte

`src/tradebot/infra/db/repositories/position_repo_sql.py` est une classe vide.
La gestion des positions (ouverture, suivi des lots, clôture) est le cœur
de la logique de trading. Ce repo est la seule source de vérité sur l'état
des positions en cours.

## Périmètre

### Modèle `Position` du domaine (vérifier/compléter `domain/models/position.py`)

```python
@dataclass
class Position:
    id: str                        # UUID
    symbol: str
    side: str                      # "BUY" (spot only)
    status: PositionStatus         # OPEN | CLOSING | CLOSED
    entry_price: Decimal
    quantity_total: Decimal        # quantité totale achetée
    stop_loss: Decimal
    atr_at_entry: Decimal          # ATR au moment de l'entrée (pour trailing)
    signal_score: float
    setup_type: str                # "A" | "B" | "C" | "D"
    shard_id: int
    opened_at_ms: int
    closed_at_ms: int | None
    exit_plan: ExitPlan            # lots A/B/C avec leurs règles
    high_since_entry: Decimal      # pour le trailing stop Lot C
    last_checked_ms: int | None    # dernier tick de ManageOpenPositions
```

### Interface publique `PositionRepoSql`

```python
class PositionRepoSql:
    def __init__(self, session_factory: async_sessionmaker) -> None: ...

    async def create(self, position: Position) -> None:
        """INSERT. Lever une exception si position.id existe déjà."""

    async def get_by_id(self, position_id: str) -> Position | None: ...

    async def get_open_by_symbol(self, symbol: str) -> Position | None:
        """
        Retourne la position OPEN ou CLOSING pour ce symbole.
        Max 1 par symbole (contrainte métier).
        """

    async def list_open_by_shard(
        self,
        shard_id: int,
        due_before_ms: int,
    ) -> list[Position]:
        """
        Retourne les positions OPEN ou CLOSING du shard dont
        last_checked_ms IS NULL OR last_checked_ms < due_before_ms.
        Ordonnées par opened_at_ms ASC.
        Usage : ManageOpenPositionsWorkflow.
        """

    async def update(self, position: Position) -> None:
        """
        UPDATE full sur tous les champs mutables :
          status, stop_loss, high_since_entry, last_checked_ms,
          closed_at_ms, exit_plan (sérialiser en JSON).
        Lever PositionNotFoundError si l'id n'existe pas.
        """

    async def count_open(self) -> int:
        """Nombre total de positions OPEN + CLOSING. Pour la limite max_open_positions."""

    async def count_open_by_symbol_prefix(self, prefix: str) -> int:
        """
        Compte les positions ouvertes sur des paires corrélées.
        Exemple : prefix="BTC" → compte BTCUSDC.
        Usage : filtre de corrélation.
        """
```

### Modèle ORM à créer dans `src/tradebot/infra/db/models.py`

```python
class PositionModel(Base):
    __tablename__ = "positions"

    id = Column(String(36), primary_key=True)      # UUID
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(String(4), nullable=False)
    status = Column(String(10), nullable=False, index=True)
    entry_price = Column(Numeric(20, 8), nullable=False)
    quantity_total = Column(Numeric(20, 8), nullable=False)
    stop_loss = Column(Numeric(20, 8), nullable=False)
    atr_at_entry = Column(Numeric(20, 8), nullable=False)
    signal_score = Column(Float, nullable=False)
    setup_type = Column(String(1), nullable=False)
    shard_id = Column(SmallInteger, nullable=False, index=True)
    opened_at_ms = Column(BigInteger, nullable=False)
    closed_at_ms = Column(BigInteger, nullable=True)
    exit_plan_json = Column(Text, nullable=False)       # ExitPlan sérialisé
    high_since_entry = Column(Numeric(20, 8), nullable=False)
    last_checked_ms = Column(BigInteger, nullable=True)
```

Index composites à créer :
- `(shard_id, status, last_checked_ms)` → pour `list_open_by_shard`
- `(symbol, status)` → pour `get_open_by_symbol`

### Sérialisation ExitPlan

`ExitPlan` contient des `Decimal` et des `Enum`. Sérialiser en JSON :
```python
import json
from decimal import Decimal

def exit_plan_to_json(plan: ExitPlan) -> str:
    # Convertir Decimal → str, Enum → .value
    ...

def exit_plan_from_json(raw: str) -> ExitPlan:
    # Reconstruire depuis dict
    ...
```

Ces helpers vont dans `src/tradebot/infra/db/repositories/_serializers.py`.

## Contraintes techniques

- Contrainte DB : un seul enregistrement OPEN/CLOSING par symbole
  → ajouter une contrainte SQL `UNIQUE` partielle : `WHERE status IN ('OPEN', 'CLOSING')`
  (PostgreSQL supporté)
- Tous les prix en `Numeric(20, 8)`, jamais `Float` en DB
- `update()` doit être idempotent : si le status est déjà CLOSED, ne pas écraser

## Hors périmètre

- Logique de calcul du trailing stop (dans ExitEngine)
- Création des OrderIntent (dans OrderIntentRepoSql)
- Réconciliation avec Binance (dans reconcile_orders)

## Tests

- `tests/unit/test_position_repo_sql.py`
  - Sérialisation/désérialisation ExitPlan (round-trip sans perte)
  - Conversion ORM → domaine (tous champs Decimal corrects)
- `tests/integration/test_position_repo_sql_integration.py`
  - `create` + `get_by_id` round-trip
  - `list_open_by_shard` : filtre `last_checked_ms` correct
  - Contrainte unicité OPEN par symbole

## Critères d'acceptation

1. Round-trip `create` → `get_by_id` sans perte de données (y compris ExitPlan)
2. `list_open_by_shard` retourne uniquement les positions dues (last_checked_ms correct)
3. Contrainte unicité OPEN/CLOSING par symbole en DB
4. `update()` lève `PositionNotFoundError` si id inconnu
5. Zéro Float en DB — tout Numeric
