---
id: B-0009
title: "RSI(14) calcule une valeur avec 14 bougies au lieu de 15 (off-by-one)"
status: VALIDATED
owner: qa
links: ["B-0009", "T-0022", "US-0005"]
---

# B-0009 - RSI warmup off-by-one

## Contexte
Le moteur indicateurs livre un RSI normatif (Wilder) pour `US-0005`.

## Reproduction
1. Executer:
```bash
poetry run python - <<'PY'
from tradebot.services.indicators.rsi import rsi_series
values_14 = [44.34,44.09,44.15,43.61,44.33,44.83,45.10,45.42,45.84,46.08,45.89,46.03,45.61,46.28]
print(rsi_series(values_14, period=14))
PY
```
2. Observer la sortie: une valeur RSI est deja presente sur la 14e bougie.

## Resultat observe
- Le premier RSI apparait a l'index `period-1` (14e bougie), alors que le calcul Wilder requiert `period` variations, donc 15 bougies pour RSI(14).
- La boucle d'initialisation utilise `range(1, period)` (13 deltas) puis divise par `period`.

## Resultat attendu
- Tant que moins de 15 bougies sont presentes pour RSI(14), le statut doit rester `unavailable/warmup`.
- Le premier RSI doit etre calcule avec 14 deltas (entre 15 closes).

## Impact
- Signal RSI publie trop tot (faux positif de disponibilite).
- Biais numerique sur la premiere valeur RSI et sur les valeurs derivees.

## References
- `src/tradebot/services/indicators/rsi.py:19`
- `src/tradebot/services/indicators/rsi.py:27`
- `src/tradebot/services/indicators/rsi.py:32`
- `src/tradebot/services/indicators/factory.py:244`
