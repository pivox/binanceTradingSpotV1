# CI GitHub Actions

## Workflow
Le workflow CI est defini dans `.github/workflows/ci.yml` et se declenche sur `push` et `pull_request` vers `main`.

## Branch protection
Pour bloquer le merge en cas d'echec CI, activer une regle de protection de branche sur `main` et rendre obligatoire le status check suivant :
- `CI / test`
- `CI / secrets_check`

## Notes
- Le job installe Python 3.11, Poetry et les dependances.
- Le lint est execute via `poetry run ruff check .` (gate obligatoire).
- Les tests sont executes via `poetry run pytest -q --junitxml=artifacts/pytest.xml`.
- Le gate `mypy` est deferre en attendant la resolution de `BUG-004`.
- Les secrets requis pour le job `secrets_check` sont `BINANCE_API_KEY` et `BINANCE_API_SECRET` (secrets GitHub). La verification ne s'execute que sur `push` vers `main`.
- Les artefacts publies incluent `dist/` (build) et `artifacts/` (logs/tests) avec une retention de 7 jours.
- Alerting: configurer le secret `SLACK_WEBHOOK_URL` pour recevoir une notification en cas d'echec du workflow CI.

## Configuration des secrets
Le workflow CI utilise des secrets de **repository** (le job ne reference pas d'environnement GitHub).
1. Aller dans `Settings` -> `Secrets and variables` -> `Actions` -> `Repository secrets`.
2. Ajouter `BINANCE_API_KEY` et `BINANCE_API_SECRET`.
3. (Optionnel) Ajouter `SLACK_WEBHOOK_URL` pour l'alerting CI.

## Secrets par environnement (pour le Deploy)
Le workflow `Deploy` (voir `docs/deploy.md`) cible des environnements GitHub (`staging`/`production`). Pour ces jobs, vous pouvez definir des secrets scopes par environnement :
- `BINANCE_API_KEY`
- `BINANCE_API_SECRET`
- (Optionnel) `SLACK_WEBHOOK_URL` si vous voulez des alertes distinctes par environnement.
