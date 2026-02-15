# Epic: Workflows CI/CD et execution trading securisee

## Decomposition en User Stories
- US-0015 CI - Declencher automatiquement la CI sur push et pull_request (`US-0015-ci-declenchement-automatique.md`)
- US-0016 CI - Rendre obligatoires le lint et les tests unitaires (`US-0016-ci-lint-tests-obligatoires.md`)
- US-0017 CI - Gerer les secrets Binance de maniere securisee (`US-0017-ci-secrets-securises.md`)
- US-0018 CI - Publier des artefacts (build + logs) a chaque run reussi (`US-0018-ci-publication-artefacts.md`)
- US-0019 CD - Deployer manuellement vers staging puis production avec validations (`US-0019-cd-deploiement-staging-production.md`)
- US-0020 Execution trading - Mode securise avec simulation par defaut (`US-0020-execution-trading-mode-securise.md`)
- US-0021 Alerting - Notifier rapidement en cas d'echec workflow ou job critique (`US-0021-alerting-echec-workflow.md`)

## US-01 - Declenchement CI automatique
**En tant que** developpeur  
**Je veux** que la CI se lance sur `push` et `pull_request` sur `main`  
**Afin de** valider rapidement le code.

### Criteres d'acceptation
1. Le workflow se declenche sur `push` et `pull_request`.
2. Le statut du workflow est visible dans la PR.
3. Le merge est bloque si le workflow echoue.

## US-02 - Lint et tests obligatoires
**En tant que** equipe  
**Je veux** executer lint et tests unitaires dans la CI  
**Afin de** eviter les regressions.

### Criteres d'acceptation
1. Une etape `lint` est obligatoire.
2. Une etape `test` est obligatoire.
3. Si une etape echoue, le workflow echoue.

## US-03 - Gestion securisee des secrets
**En tant que** PO/SecOps  
**Je veux** que les cles API Binance soient gerees via les secrets CI  
**Afin de** securiser l'execution des workflows.

### Criteres d'acceptation
1. Aucune cle n'est stockee en dur dans le repository.
2. Les jobs utilisent uniquement les secrets du runner.
3. Le workflow echoue si un secret requis est absent.

## US-04 - Publication d'artefacts
**En tant que** developpeur  
**Je veux** publier les artefacts de build et les logs  
**Afin de** faciliter le diagnostic des executions.

### Criteres d'acceptation
1. Un artefact est publie a chaque run reussi.
2. L'artefact contient le build et les logs.
3. La retention est configuree (ex: 7 jours).

## US-05 - Deploiement controle staging puis production
**En tant que** PO  
**Je veux** un deploiement manuel vers `staging` puis `production`  
**Afin de** maitriser la mise en production.

### Criteres d'acceptation
1. Le deploiement `staging` est possible apres CI verte.
2. Le deploiement `production` necessite une validation manuelle.
3. Une procedure de rollback est documentee et testable.

## US-06 - Execution trading en mode securise
**En tant que** trader/PO  
**Je veux** que la strategie demarre en mode simulation par defaut  
**Afin de** valider la logique avant passage en mode reel.

### Criteres d'acceptation
1. Le mode `paper/simulation` est active par defaut.
2. Le mode reel n'est possible qu'avec un flag explicite et une approbation.
3. Les signaux et ordres sont journalises avec horodatage.

## US-07 - Alertes en cas d'echec workflow
**En tant que** PO  
**Je veux** recevoir une alerte en cas d'echec de workflow ou de job critique  
**Afin de** reagir rapidement.

### Criteres d'acceptation
1. Une notification est envoyee vers Slack ou Email.
2. Le message inclut `run ID`, job et erreur principale.
3. L'alerte est envoyee en moins d'une minute apres l'echec.
