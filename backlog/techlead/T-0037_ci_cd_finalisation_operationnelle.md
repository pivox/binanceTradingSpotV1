---
id: T-0037
title: "CI/CD - Finalisation operationnelle (SLO, rollback, checks deploy)"
status: NEEDS_QA
owner: dev
links: ["US-0015", "US-0016", "US-0017", "US-0018", "US-0019", "US-0021", "T-0034"]
---

## Contexte
Les workflows CI/CD existent et couvrent le socle attendu. Les US demandent toutefois une operabilite complete (evidence SLO, rollback testable, checks explicites par environnement).

## Perimetre
- Ajouter une mesure exploitable du temps CI (ex: extraction duree run + publication resume artefact/step).
- Formaliser un test de rollback "prouvable" (procedure executable/documentee avec verification).
- Ajouter un check explicite des secrets deploy requis par environnement avant build/push.
- Uniformiser la structure des messages d'alerting (champ stable `field=value` ou JSON) entre CI et Deploy.

## Hors perimetre
- Migration vers une autre plateforme CI.
- Refactor complet de la strategie release.

## Plan d'implementation
1. Ajouter step CI de synthese runtime (`ci_duration_sec`, status global) exportee en artifact.
2. Ajouter job/commande rollback smoke documente(e) dans le workflow de deploy ou workflow dedie.
3. Ajouter un `secrets_check` cote deploy pour les secrets critiques d'environnement.
4. Harmoniser le template des notifications Slack CI/Deploy.
5. Mettre a jour `docs/ci.md` et `docs/deploy.md` avec les evidences attendues.

## Tests
- Validation manuelle guidee:
  - run CI nominal avec evidence duree,
  - simulation echec deploy sans secret -> echec explicite,
  - test rollback smoke conforme au runbook.
- Tests scripts utilitaires associes (si ajout de scripts shell/python).

## Criteres d'acceptation
1. La duree CI est visible et exploitable pour suivre l'objectif NFR.
2. Le rollback est teste via une procedure executable, pas uniquement narrative.
3. Le deploy echoue explicitement si secrets requis manquants.
4. Les alertes CI/Deploy partagent un format de message stable.

## Definition of Done
- Workflows et docs merges.
- Verification executionnelle sur au moins un run CI et un run Deploy de test.
