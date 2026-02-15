---
id: B-0012
title: "WS daemon: requete UPSERT candles invalide (double INSERT)"
status: VALIDATED
owner: qa
links: ["B-0012", "T-0035", "US-0012", "US-0014"]
---

# B-0012 - Echec runtime de persistance candles

## Contexte
Le ticket `T-0035` renforce la robustesse du daemon websocket. La persistance des candles reste toutefois executee via `UPSERT_CANDLE_SQL`.

## Reproduction
1. Executer:
```bash
poetry run python - <<'PY'
from tradebot.apps.ws_candle_daemon import UPSERT_CANDLE_SQL
print(UPSERT_CANDLE_SQL)
print("insert_count=", UPSERT_CANDLE_SQL.upper().count("INSERT INTO CANDLES"))
PY
```
2. Observer `insert_count=2` dans une seule requete SQL.

## Resultat observe
- La constante SQL contient deux lignes consecutives `INSERT INTO candles(...)`.
- Cette syntaxe est invalide et provoque une erreur SQL lors de `conn.execute(...)` au premier persist.

## Resultat attendu
- Une seule instruction `INSERT INTO candles(...)` dans la requete UPSERT.

## Impact
- Le daemon peut se connecter au websocket mais echoue lors de la premiere ecriture DB.
- La collecte live devient non operationnelle malgre les protections de reconnexion.

## References
- `src/tradebot/apps/ws_candle_daemon.py:253`
- `src/tradebot/apps/ws_candle_daemon.py:254`
- `src/tradebot/apps/ws_candle_daemon.py:311`
