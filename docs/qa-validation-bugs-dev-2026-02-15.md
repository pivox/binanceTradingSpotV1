# Validation QA - Bugs traites par le dev (2026-02-15)

## Scope
- `B-0008`
- `B-0009`
- `B-0010`
- `B-0011`
- `B-0012`
- `B-0013`

## Verifications executees
- Reproductions bug executees et verifiees:
  - `B-0009`: `rsi_series(values_14, period=14)` retourne uniquement des `None`.
  - `B-0010`: modification de payload => `etag1 != etag2`.
  - `B-0011`: `timeframe_to_ms("1M")` leve `ValueError unsupported timeframe: 1M`.
  - `B-0012`: `UPSERT_CANDLE_SQL` contient `insert_count=1`.
  - `B-0013`: occurrences presentes dans `docs/observability-indicators-live.md` et `docs/runbook-indicators-live.md`.
- Validation `B-0008` (daemon/chart):
  - `poetry run pytest -q tests/unit/test_daemon_control.py tests/unit/test_daemon_api.py tests/unit/test_chart_api.py` -> `18 passed`.
  - Couvre le demarrage en echec (`start_failed`), propagation d'env et statut process stale/non-running.

## Qualite Python
- `poetry run ruff check .` -> OK.
- `poetry run ruff format . --check` -> OK.
- `poetry run pytest -q` -> `58 passed`.

## Decision QA
- Tous les bugs du scope sont **VALIDATED**.
