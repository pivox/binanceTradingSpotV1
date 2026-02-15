---
id: B-0011
title: "Backfill: timeframe `1M` traite comme 30 jours fixes"
status: VALIDATED
owner: qa
links: ["B-0011", "T-0023", "US-0006"]
---

# B-0011 - Mauvaise granularite de gap detection sur `1M`

## Contexte
Le backfill detecte des trous via un `step_ms` calcule a partir du timeframe.

## Reproduction
1. Executer:
```bash
poetry run python - <<'PY'
from tradebot.infra.db.repositories.backfill_repo_sql import timeframe_to_ms
print(timeframe_to_ms("1M"))
PY
```
2. Observer la valeur retournee: `2592000000` (30 jours fixes).

## Resultat observe
- Le code mappe `M` a `2_592_000_000` ms (30 jours).
- Les mois calendaires Binance ne font pas tous 30 jours (28/29/30/31).

## Resultat attendu
- Le calcul des gaps ne doit pas supposer une duree fixe pour `M`.
- Soit `M` est explicitement exclu, soit gere via logique calendaire.

## Impact
- Detection de trous incorrecte sur les timeframes mensuels.
- Fenetres de backfill mal bornees et jobs potentiellement faux.

## References
- `src/tradebot/infra/db/repositories/backfill_repo_sql.py:14`
- `src/tradebot/infra/db/repositories/backfill_repo_sql.py:22`
