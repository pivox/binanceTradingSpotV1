---
id: TL-13
title: "CD - Deploiement controle vers staging puis production"
status: DONE
owner: techlead
links: ["TL-13"]
---

# TL-13 CD - Deploiement controle vers staging puis production

## Objectif
Mettre en place un deploiement manuel vers `staging` puis `production` avec validations.

## Scope
- Workflow de deploiement (`.github/workflows/deploy.yml`).
- Environnements GitHub `staging` et `production` avec approbations.
- Build/push d'une image (Docker) ou package selon l'infra cible.
- Procedure de rollback documentee.

## Taches
- Choisir la cible de deploiement (host Docker, k8s, VPS, etc.).
- Definir la strategie d'artefact (image GHCR ou package).
- Creer un workflow `workflow_dispatch` pour deploiement.
- Configurer `environment` GitHub pour gating (approval requise en prod).
- Documenter et tester une procedure de rollback.

## Criteres d'acceptation
- Le deploiement `staging` est possible apres CI verte.
- Le deploiement `production` necessite une validation manuelle.
- Une procedure de rollback est documentee et testable.

## Dependances
- TL-09.
- TL-11.
- Definition de l'infra cible.
