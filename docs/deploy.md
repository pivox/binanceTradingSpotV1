# CD Deployment

## Workflow
Le workflow `Deploy` est defini dans `.github/workflows/deploy.yml` et se declenche manuellement via `workflow_dispatch`.

## Environnements
Configurer deux environnements GitHub :
- `staging`
- `production`

Parametrer l'environnement `production` avec une approbation manuelle obligatoire.

## Secrets par environnement
1. Aller dans `Settings` -> `Environments` -> `staging` puis `production`.
2. Ajouter `BINANCE_API_KEY` et `BINANCE_API_SECRET` dans chaque environnement.
3. (Optionnel) Ajouter `SLACK_WEBHOOK_URL` dans chaque environnement si vous voulez des alertes distinctes.

## Artefact
Le deploiement publie une image Docker sur GHCR :
- `ghcr.io/<org>/<repo>:<sha>`
- `ghcr.io/<org>/<repo>:staging` ou `ghcr.io/<org>/<repo>:production`

## Rollback
Pour revenir a une version precedente :
1. Recuperer le tag `sha` de la derniere version stable.
2. Relancer le workflow `Deploy` vers l'environnement cible.
3. Verifier que l'image taggee par le `sha` attendu est bien deployee.

## Gate CI
Le workflow `Deploy` verifie automatiquement que la CI est verte pour le commit cible avant d'autoriser le deploiement.

## Alerting
- Configurer le secret `SLACK_WEBHOOK_URL` pour recevoir une notification en cas d'echec du workflow `Deploy`.
- L'alerte couvre les echecs du gate `ci_gate` et du job `deploy`, avec `run_id`, job en echec et `error_summary`.
