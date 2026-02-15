# Dev log — valeurs indicateurs sur `/chart` (2026-02-15)

## Objectif
Afficher sur la page `http://localhost:8000/chart` les valeurs des indicateurs techniques (snapshot le plus récent) en plus des OHLC.

## Implémentation
- Ajout d’un panneau **Indicateurs** dans `src/tradebot/api/static/chart.html`.
- Style du panneau + “pills” dans `src/tradebot/api/static/chart.css`.
- Récupération et rendu du snapshot via `GET /indicators/latest?symbol=...&timeframe=...` dans `src/tradebot/api/static/chart.js`.
  - Rafraîchissement au chargement / changement de pair / timeframe.
  - Rafraîchissement en live (throttlé) quand la dernière bougie avance.
  - Affichage des timestamps `close_time` / `computed_at` et du retard éventuel vs dernière bougie.

## Commandes (tests / qualité)
```bash
poetry run ruff check .
```
Output:
```
All checks passed!
```

```bash
poetry run ruff format .
```
Output:
```
109 files left unchanged
```

```bash
poetry run pytest -q
```
Output:
```
..................................................................       [100%]
66 passed in 4.82s
```

