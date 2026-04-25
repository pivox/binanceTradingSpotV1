---
id: T-0044
title: "Infra - CandleRepoSql : lecture des candles depuis PostgreSQL"
status: TODO
owner: techlead
phase: 1
priority: P0
links: ["T-0047", "T-0048", "T-0051"]
---

## Contexte

`src/tradebot/infra/db/repositories/candle_repo_sql.py` est une classe vide.
Les services de trading (cascade MTF, calcul d'indicateurs, signal engine)
ont besoin de lire des séries de candles depuis la DB.
C'est un composant de lecture pure — les écritures sont déjà faites par le daemon WebSocket.

## Périmètre

Implémenter `CandleRepoSql` dans `src/tradebot/infra/db/repositories/candle_repo_sql.py`.

### Interface publique

```python
class CandleRepoSql:
    def __init__(self, session_factory: async_sessionmaker) -> None: ...

    async def fetch_latest(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 500,
    ) -> list[Candle]:
        """
        Retourne les `limit` dernières candles closes ordonnées ASC (plus vieille en premier).
        Filtre : is_partial = False.
        Usage principal : calcul d'indicateurs.
        """

    async def fetch_range(
        self,
        symbol: str,
        timeframe: str,
        start_ms: int,
        end_ms: int,
    ) -> list[Candle]:
        """
        Retourne les candles dans [start_ms, end_ms] (bornes incluses sur open_time_ms).
        Ordonnées ASC. Inclure les partielles si elles tombent dans la plage.
        Usage : backfill validation, replay.
        """

    async def fetch_symbols_with_timeframe(
        self,
        timeframe: str,
    ) -> list[str]:
        """
        Retourne la liste distincte de symboles ayant au moins une candle
        pour ce timeframe. Usage : initialisation de la cascade MTF.
        """

    async def get_last_close_time(
        self,
        symbol: str,
        timeframe: str,
    ) -> int | None:
        """
        Retourne le close_time_ms de la dernière candle close (is_partial=False).
        Retourne None si aucune candle.
        Usage : détection de gap au démarrage.
        """
```

### Modèle ORM existant

La table `candles` existe déjà dans `src/tradebot/infra/db/models.py`.
Vérifier les champs disponibles avant de coder :
- `symbol`, `timeframe`, `open_time_ms`, `close_time_ms`
- `open`, `high`, `low`, `close`, `volume` (type Numeric)
- `is_partial` (bool)
- `inserted_at`

### Conversion ORM → domaine

```python
def _row_to_candle(row: CandleModel) -> Candle:
    return Candle(
        symbol=row.symbol,
        timeframe=Timeframe(row.timeframe),
        open_time_ms=row.open_time_ms,
        close_time_ms=row.close_time_ms,
        open=Decimal(str(row.open)),
        high=Decimal(str(row.high)),
        low=Decimal(str(row.low)),
        close=Decimal(str(row.close)),
        volume=Decimal(str(row.volume)),
        is_partial=row.is_partial,
    )
```

## Contraintes techniques

### Performance
- `fetch_latest` : utiliser `ORDER BY open_time_ms DESC LIMIT :limit` puis inverser en Python
  (plus performant que ASC + OFFSET sur grandes tables)
- Index attendu sur `(symbol, timeframe, open_time_ms)` — vérifier qu'il existe dans `init.sql`
- Pas de `SELECT *` : sélectionner uniquement les colonnes nécessaires

### Sessions async
- Utiliser `async with session_factory() as session:` dans chaque méthode
- Pas de session partagée entre méthodes (pas de state dans la classe)

### Typing
- Retourner `list[Candle]` du domaine, jamais les modèles ORM en dehors du repo

## Hors périmètre

- Écriture de candles (faite par le daemon via asyncpg)
- Calcul d'indicateurs
- Pagination curseur (le caller passe directement limit/range)

## Tests

- `tests/unit/test_candle_repo_sql.py`
  - Mock SQLAlchemy session avec des fixtures de données
  - Tester `fetch_latest` : tri ASC correct, filtre is_partial, limit respecté
  - Tester `fetch_range` : bornes incluses
  - Tester `get_last_close_time` : None si vide, valeur correcte sinon

- `tests/integration/test_candle_repo_sql_integration.py`
  - DB de test PostgreSQL (pytest-asyncio + vraie DB)
  - Insérer 100 candles, vérifier fetch_latest(limit=10) retourne les 10 plus récentes

## Critères d'acceptation

1. `fetch_latest(limit=500)` retourne les candles en ordre ASC (index 0 = la plus vieille)
2. Les candles partielles sont exclues de `fetch_latest`
3. `fetch_range` : bornes incluses sur `open_time_ms`
4. Tous les champs prix en `Decimal` (pas de float)
5. Zéro ORM model visible en dehors du repo
