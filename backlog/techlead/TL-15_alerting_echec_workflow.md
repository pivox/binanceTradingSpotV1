---
id: TL-15
title: "Alertes en cas d'echec workflow"
status: DONE
owner: techlead
links: ["TL-15"]
---

# TL-15 Alertes en cas d'echec workflow

## Objectif
Recevoir une alerte rapide en cas d'echec d'un workflow ou job critique.

## Scope
- Notification vers Slack ou Email.
- Message avec `run ID`, job et erreur principale.
- Envoi en moins d'une minute apres echec.

## Taches
- Choisir le canal (Slack webhook ou email).
- Ajouter les secrets necessaires (ex: `SLACK_WEBHOOK_URL`).
- Implementer une etape `if: failure()` dans les workflows critiques.
- Construire un message incluant run ID, job et resume de l'erreur.

## Criteres d'acceptation
- Une notification est envoyee vers Slack ou Email.
- Le message inclut `run ID`, job et erreur principale.
- L'alerte est envoyee en moins d'une minute apres l'echec.

## Dependances
- TL-09.
- Secrets de notification.
