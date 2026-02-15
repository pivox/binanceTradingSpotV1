# Validation QA - Tickets dev (2026-02-15)

## Scope valide
- `T-0011` (CI secrets): conforme (check secrets + alerting + doc)
- `T-0013` (CD staging/production): conforme (ci gate + secrets check + rollback smoke + doc)
- `T-0015` (alerting workflow): conforme (run_id/job + format `field=value` sur CI/Deploy)
- `T-0036` (UI daemon RBAC): conforme (endpoint permissions + UX boutons + tests API + doc UI)
- `T-0037` (finalisation CI/CD): conforme (ci duration artifact + rollback executable + check secrets deploy + format alerting unifie)

## Revalidation dev (2026-02-15)
- `T-0035`: correctifs presents cote dev, en attente de validation QA
  - `B-0012` - reproduction KO (corrige): `UPSERT_CANDLE_SQL` contient une seule instruction `INSERT INTO candles`.
  - `B-0013` - corrige: documentation ajoutee dans:
    - `docs/observability-indicators-live.md`
    - `docs/runbook-indicators-live.md`

## Reproductions executees sur bugs QA en TODO
- `B-0008`: correctif deja present dans le code (demarrage daemon/etat process), a confirmer par QA E2E.
- `B-0009`: reproduction KO (corrige) - RSI(14) ne retourne pas de valeur avec seulement 14 bougies.
- `B-0010`: reproduction KO (corrige) - changement de payload modifie bien l'ETag.
- `B-0011`: reproduction KO (corrige) - `timeframe_to_ms(\"1M\")` leve `ValueError` (timeframe non supporte).
- `B-0012`: reproduction KO (corrige) - plus de double `INSERT` dans l'UPSERT SQL.
- `B-0013`: reproduction KO (corrige) - occurrences des variables/metriques/logs de hardening websocket presentes dans `docs/`.

## Verification qualite executee
```bash
poetry run ruff check .
poetry run ruff format . --check
poetry run pytest -q
```

Resultats:
- `ruff check`: OK
- `ruff format --check`: OK
- `pytest -q`: OK (58 passed)
