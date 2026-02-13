# Temporal: workflows et batchs (local)

Ce document liste ce qui existe **dans le code** du repo et comment obtenir la liste **en UI/CLI**.

## Code (workflows)
Déclarés et enregistrés dans le worker: `src/tradebot/apps/temporal_worker_main.py`.

Workflows actifs (source: `src/tradebot/temporal_app/workflows.py`):
- `ConsumeCandleEventsWorkflow`
- `CascadeValidateAndEnterWorkflow`
- `ProcessClosedCandlesWorkflow`
- `ManageOpenPositionsWorkflow`
- `ReconcileKlinesWorkflow`
- `ReconcileOrdersWorkflow`
- `RefreshExchangeInfoWorkflow`
- `IntentDispatcherWorkflow`
- `PositionWorkflow`

Workflows présents mais non branchés au worker (dossier `src/tradebot/infra/temporal/workflows/`):
- `ConsumeCandleEventsWorkflow`
- `CascadeValidateWorkflow`
- `ReconcileKlinesWorkflow`
- `ReconcileOrdersWorkflow`
- `RefreshExchangeInfoWorkflow`
- `ManagePositionsWorkflow`

## Code (batchs / schedules)
- Des workflows « batch » existent (par ex. `ConsumeCandleEventsWorkflow`, `ManageOpenPositionsWorkflow`) mais ce sont **des workflows** classiques, pas des Batch Operations Temporal.
- Config de schedules: `src/tradebot/config/types.py` + `src/tradebot/config/loader.py`.
- Bootstrap schedules: `src/tradebot/infra/temporal/schedules.py` est vide (pas d’implémentation).

## UI (liste réelle en runtime)
Ouvre l’UI (`http://localhost:8080`) et consulte :
- `Workflows` pour les exécutions actives/terminées.
- `Schedules` pour les schedules actifs.
- `Batch Operations` pour les batchs (si activés et créés).

Si rien n’apparaît, c’est souvent que les workflows n’ont pas été lancés, ou que le namespace n’est pas celui attendu.

## CLI (liste réelle en runtime)
Si tu as le CLI `temporal` ou `tctl`, tu peux lister :

```bash
# Workflows (temporal CLI)
temporal --address localhost:7234 workflow list

# Workflows (tctl)
tctl --address localhost:7234 workflow list

# Batch operations (si supporté)
temporal --address localhost:7234 batch list
# ou
 tctl --address localhost:7234 batch list
```

Note: dans ce repo, le port gRPC exposé par Temporal est `7234` (mapping `7234:7233` dans `docker-compose.yml`).
