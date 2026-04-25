---
id: T-0051
title: "Temporal - Activities pipeline candles : fetch, validate, compute_snapshot, mark_processed"
status: TODO
owner: techlead
phase: 3
priority: P0
links: ["T-0044", "T-0046", "T-0048"]
---

## Contexte

Quatre activités Temporal sont des stubs dans `src/tradebot/temporal_app/activities.py`.
Elles constituent le pipeline de traitement des candles fermées :
candle close event → validation → snapshot d'indicateurs → marquage processed.

Ce pipeline est déclenché toutes les 10s par `ProcessClosedCandlesWorkflow`.
Son output alimente `CascadeValidateAndEnterWorkflow`.

## Périmètre

### Activity 1 — `fetch_candle_close_events`

```python
@activity.defn
async def fetch_candle_close_events(input: FetchCandleEventsInput) -> FetchCandleEventsOutput:
```

**Input :**
```python
@dataclass
class FetchCandleEventsInput:
    shard_id: int
    batch_size: int = 100
    since_ms: int | None = None   # cursor : uniquement les events après ce ts
```

**Logique :**
```python
# Lire la table candle_close_event pour les events non traités du shard
# Filtrer : processed_at IS NULL ET shard_id = input.shard_id
# Limiter à batch_size, ordonner par close_time_ms ASC
# Retourner la liste des events + le count

SELECT id, symbol, timeframe, open_time_ms, close_time_ms, shard_id
FROM candle_close_event
WHERE processed_at IS NULL
  AND shard_id = :shard_id
  AND (:since_ms IS NULL OR close_time_ms > :since_ms)
ORDER BY close_time_ms ASC
LIMIT :batch_size
```

**Output :**
```python
@dataclass
class FetchCandleEventsOutput:
    events: list[CandleCloseEvent]
    total_pending: int   # COUNT(*) WHERE processed_at IS NULL AND shard_id = X
```

---

### Activity 2 — `validate_candle_event`

```python
@activity.defn
async def validate_candle_event(input: ValidateCandleInput) -> ValidateCandleOutput:
```

**Logique :**
```python
# Vérifications :
# 1. Le symbole est toujours dans la liste active (in exchange_info_cache)
# 2. La candle correspondante existe dans la table candles (pas juste l'event)
# 3. Le timeframe est dans la liste configurée
# 4. open_time_ms et close_time_ms sont cohérents (close > open, durée attendue ±5s)

# Retourner valid=True/False + raison si invalide
```

**Output :**
```python
@dataclass
class ValidateCandleOutput:
    event_id: str
    valid: bool
    reason: str | None
```

---

### Activity 3 — `compute_indicator_snapshot`

```python
@activity.defn
async def compute_indicator_snapshot(input: ComputeSnapshotInput) -> ComputeSnapshotOutput:
```

**Input :**
```python
@dataclass
class ComputeSnapshotInput:
    symbol: str
    timeframe: str
    close_time_ms: int
    candle_limit: int = 500   # nb de candles à charger pour le calcul
```

**Logique :**
1. Lire les dernières `candle_limit` candles via `CandleRepoSql.fetch_latest()`
2. Appeler `build_indicator_snapshot(symbol, timeframe, candles)` (déjà implémenté)
3. Persister le snapshot dans `indicator_snapshots` via `IndicatorRepository.upsert_snapshot()`
4. Retourner le snapshot sérialisé

**Gestion heartbeat Temporal :**
```python
# Si candle_limit > 200, envoyer un heartbeat Temporal pour éviter timeout
activity.heartbeat("loading_candles")
```

**Output :**
```python
@dataclass
class ComputeSnapshotOutput:
    symbol: str
    timeframe: str
    snapshot: dict     # résultat de build_indicator_snapshot
    from_cache: bool   # True si snapshot existant non recalculé (ETag match)
```

**Optimisation :** avant de recalculer, vérifier si un snapshot récent existe déjà
(`indicator_snapshots.close_time_ms == input.close_time_ms`). Si oui → retourner le cache.

---

### Activity 4 — `mark_candle_close_events_processed`

```python
@activity.defn
async def mark_candle_close_events_processed(input: MarkProcessedInput) -> None:
```

**Input :**
```python
@dataclass
class MarkProcessedInput:
    event_ids: list[str]
    processed_at_ms: int
```

**Logique :**
```python
UPDATE candle_close_event
SET processed_at = :processed_at_ms
WHERE id = ANY(:event_ids)
```

Opération en batch. Si un event_id n'existe pas → logger warning, ne pas crasher.

---

## Contraintes communes

### Timeouts Temporal
```python
@activity.defn(name="fetch_candle_close_events")
# schedule_to_close_timeout = 30s
# heartbeat_timeout = 10s
```

### Retry policy (à configurer dans le workflow appelant)
```python
RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=30),
    maximum_attempts=5,
)
```

### Sessions async
- Chaque activité crée et ferme sa propre session DB
- Ne pas partager de session entre activités

## Tests

- `tests/unit/test_candle_pipeline_activities.py`
  - Mock DB session et `build_indicator_snapshot`
  - `fetch_candle_close_events` : retourne seulement les events non traités du bon shard
  - `validate_candle_event` : invalid si symbole absent de exchange_info_cache
  - `compute_indicator_snapshot` : cache hit si close_time_ms identique
  - `mark_candle_close_events_processed` : idempotent sur event_ids inconnus

## Critères d'acceptation

1. `fetch_candle_close_events` retourne uniquement `processed_at IS NULL` pour le bon shard
2. `compute_indicator_snapshot` utilise le cache si disponible (pas de recalcul)
3. `mark_candle_close_events_processed` idempotent (event inconnu → warning, pas crash)
4. Heartbeat Temporal envoyé dans `compute_indicator_snapshot` si > 200 candles
5. Chaque activité ferme proprement sa session DB même en cas d'erreur
