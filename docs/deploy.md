# CD Deployment

## Workflow
Le workflow `Deploy` est defini dans `.github/workflows/deploy.yml` et se declenche manuellement via `workflow_dispatch`.
Inputs:
- `environment`: `staging` ou `production`
- `rollback_sha` (optionnel): tag SHA a verifier via rollback smoke

## Environnements
Configurer deux environnements GitHub :
- `staging`
- `production`

Parametrer l'environnement `production` avec une approbation manuelle obligatoire.

## Secrets par environnement
1. Aller dans `Settings` -> `Environments` -> `staging` puis `production`.
2. Ajouter `BINANCE_API_KEY` et `BINANCE_API_SECRET` dans chaque environnement.
3. (Optionnel) Ajouter `SLACK_WEBHOOK_URL` dans chaque environnement si vous voulez des alertes distinctes.
4. Le job `deploy_secrets_check` bloque le deploy si les secrets requis sont absents.

## Artefact
Le deploiement publie une image Docker sur GHCR :
- `ghcr.io/<org>/<repo>:<sha>`
- `ghcr.io/<org>/<repo>:staging` ou `ghcr.io/<org>/<repo>:production`

## Rollback
Pour revenir a une version precedente :
1. Recuperer le tag `sha` de la derniere version stable.
2. Relancer le workflow `Deploy` vers l'environnement cible avec `rollback_sha=<sha>`.
3. Le job `rollback_smoke` execute `scripts/rollback_smoke.sh` et verifie la presence de l'image `ghcr.io/<org>/<repo>:<sha>`.
4. Verifier que l'image taggee par le `sha` attendu est bien deployee.

## Gate CI
Le workflow `Deploy` verifie automatiquement que la CI est verte pour le commit cible avant d'autoriser le deploiement.

## Alerting
- Configurer le secret `SLACK_WEBHOOK_URL` pour recevoir une notification en cas d'echec du workflow `Deploy`.
- L'alerte couvre les echecs de `ci_gate`, `deploy_secrets_check`, `deploy` et `rollback_smoke`.
- Le format des alertes Deploy est standardise en `field=value` avec `run_id`, `job`, `ref`, `env`, `rollback_sha`, `error_summary`.
