---
id: T-0015
title: "Alertes en cas d'echec workflow"
status: NEEDS_QA
owner: dev
links: ["TL-15", "B-0007"]
---

## Contexte
Recevoir une alerte rapide en cas d'echec d'un workflow ou job critique.

## Perimetre
- Notification Slack via webhook.
- Message contenant run ID et job.
- Ajout d'une etape `if: failure()`.

## Plan
1. Ajouter `SLACK_WEBHOOK_URL` aux secrets GitHub.
2. Notifier sur echec dans les workflows CI et Deploy.
3. Documenter l'alerte et le secret.

## Definition of Done
- Notification envoyee sur echec.
- Message inclut run ID et job.
- Secret documente.

## Livrables
- Alerting CI enrichi avec resume d'erreur et couverture des jobs critiques dans `/.github/workflows/ci.yml`.
- Documentation des secrets d'alerting dans `/docs/ci.md` et `/docs/deploy.md`.
