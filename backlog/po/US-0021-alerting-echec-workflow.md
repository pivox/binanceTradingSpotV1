---
id: US-0021
title: "Alerting - Notifier rapidement en cas d'echec workflow ou job critique"
status: TODO
owner: po
links: ["EPIC-CICD-TRADING-SECURISE", "T-0037"]
---

## User Story
En tant que PO
Je veux recevoir une alerte en cas d'echec de workflow ou de job critique (CI/CD)
Afin de reagir rapidement et de limiter le temps de panne/instabilite.

## Contexte
- Les canaux v1: Slack ou Email.
- Une alerte doit etre actionnable (contexte et lien vers le run).

## Criteres d'acceptation
1. Une notification est envoyee vers Slack ou Email en cas d'echec d'un workflow ou job critique.
2. Le message inclut au minimum: `run_id`, workflow, job/step en echec, ref/branch, et une URL vers le run.
3. L'alerte est envoyee en moins d'une minute apres la detection de l'echec (objectif).
4. Si le secret de notification est absent, le workflow n'echoue pas pour cette raison mais loggue explicitement que l'alerte est skippee.
5. Le format de message est stable et facilement parsable (champ=value ou JSON).

## NFR
1. Les alertes n'exposent pas de secrets.

