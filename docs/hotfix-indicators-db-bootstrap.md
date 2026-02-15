# Hotfix API indicateurs: bootstrap schema DB

Date: 2026-02-14

## Probleme

`GET /indicators/latest` pouvait renvoyer `db_error` (500) sur une base fraiche quand la table `indicator_snapshots` n'etait pas presente.

## Correctif applique

- `src/tradebot/infra/db/engine.py`
  - ajout de `Base.metadata.create_all(bind=engine)` dans `create_session_factory` pour creer les tables mappees au demarrage.
- `docker/init.sql`
  - ajout des tables `indicator_snapshots` et `backfill_jobs` pour aligner l'init DB Docker avec les modeles SQLAlchemy.
- `tests/unit/test_indicator_api.py`
  - ajout d'un test de non-regression: sur DB fraiche, `/indicators/latest` renvoie `snapshot_not_found` (404) et non `db_error`.

## Impact attendu

- Environnement neuf: schema cree automatiquement, endpoints indicateurs stables.
- Environnement existant: plus de risque de `db_error` lie a une table manquante sur ce chemin.
