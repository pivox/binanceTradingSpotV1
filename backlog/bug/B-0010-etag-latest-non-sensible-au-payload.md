---
id: B-0010
title: "ETag `/indicators/latest` inchange quand le payload change"
status: VALIDATED
owner: qa
links: ["B-0010", "T-0024", "US-0007"]
---

# B-0010 - ETag stale sur latest snapshot

## Contexte
Le ticket API impose cache conditionnel fiable via `ETag` / `If-None-Match`.

## Reproduction
1. Executer:
```bash
poetry run python - <<'PY'
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from tradebot.infra.db.models import Base
from tradebot.api.indicator_repository import IndicatorRepository
import tempfile, os

fd, path = tempfile.mkstemp(suffix='.db'); os.close(fd)
url = f"sqlite:///{path}"
engine = create_engine(url, future=True); Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)

with Session() as s:
    repo = IndicatorRepository(s)
    a = repo.upsert_snapshot(symbol="BTCUSDC", timeframe="1m", close_time_ms=1000, computed_at_ms=2000, schema_version="1.0.0", payload={"rsi":{"status":"available","value":40}})
    etag1 = a.etag
with Session() as s:
    repo = IndicatorRepository(s)
    b = repo.upsert_snapshot(symbol="BTCUSDC", timeframe="1m", close_time_ms=1000, computed_at_ms=2000, schema_version="1.0.0", payload={"rsi":{"status":"available","value":99}})
    etag2 = b.etag
print(etag1, etag2, etag1 == etag2)
engine.dispose(); os.remove(path)
PY
```
2. Observer: `True` (ETag identique) alors que le payload a change.

## Resultat observe
- L'ETag est derive uniquement de `(symbol, timeframe, close_time_ms, computed_at_ms, schema_version)`.
- Un changement de contenu sans changement de `computed_at_ms` produit le meme ETag.

## Resultat attendu
- L'ETag doit changer des que la representation de la ressource change (payload inclus).

## Impact
- Risque de reponse `304` alors que les donnees ont change.
- Cache client invalide et UI potentiellement stale.

## References
- `src/tradebot/api/indicator_repository.py:39`
- `src/tradebot/api/indicator_repository.py:143`
